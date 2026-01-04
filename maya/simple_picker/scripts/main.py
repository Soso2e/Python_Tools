# -*- coding: utf-8 -*-
"""
Controller Picker (Tabs + Instant Select + AlwaysOnTop)
- 選択階層から NURBS Curve の親トランスフォーム列挙（左ペイン）
- タブごと（パーツ箱）に登録・管理（右ペイン）
- 単/複数クリックで即 Maya セレクト
- ウィンドウが常に前面（Mayaの下へ潜らない）

Maya: 2020+ / PySide2 前提
"""

from typing import List, Set, Dict
import re
import os
import json
from pathlib import Path
from maya import cmds
from maya import OpenMayaUI as omui
from pathlib import Path

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
except Exception:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance

WINDOW_OBJECT_NAME = "ControllerPickerWindowV2"


def _mqt_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QMainWindow)


def list_curve_ctrls_under(roots: List[str]) -> List[str]:
    """roots配下から nurbsCurve を持つトランスフォームを、見つかった順（上→下）で列挙。

    発見順を安定させるため、親から子へBFSでトラバースする。
    ルートが未指定なら現在の選択順を採用する。
    """
    if not roots:
        roots = cmds.ls(sl=True, long=True) or []

    result: List[str] = []
    seen: Set[str] = set()

    for r in roots:
        if not cmds.objExists(r):
            continue
        queue = [r]
        while queue:
            node = queue.pop(0)
            # まず発見（親→子）順で自ノードを評価
            shapes = cmds.listRelatives(node, s=True, f=True) or []
            if shapes and any(cmds.nodeType(s) == "nurbsCurve" for s in shapes):
                if node not in seen:
                    seen.add(node)
                    result.append(node)
            # 子のトランスフォームを、Mayaが返す順序のままキューへ追加
            children = cmds.listRelatives(node, c=True, type="transform", f=True) or []
            if children:
                queue.extend(children)

    return result


class PartsTab(QtWidgets.QWidget):
    """パーツ（タブ）1枚分のリストUI"""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.list = QtWidgets.QListWidget(self)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.list)

    def set_items(self, names: List[str]):
        self.list.clear()
        for n in names:
            short = cmds.ls(n, sn=True)[0] if cmds.objExists(n) else n
            item = QtWidgets.QListWidgetItem(short)
            item.setToolTip(n)
            item.setData(QtCore.Qt.UserRole, n)
            self.list.addItem(item)

    def items(self) -> List[str]:
        out = []
        for i in range(self.list.count()):
            out.append(self.list.item(i).data(QtCore.Qt.UserRole))
        return out


class ControllerPicker(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or _mqt_main_window())
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("Controller Picker (Tabs)")
        self.setMinimumSize(640, 420)
        # 重要：前面維持（Maya下に行かない）
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        # ----- 左：スキャン＆フィルタ -----
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setPlaceholderText("Filter (regex OK) 例: ^CTRL_|hair")
        self.scan_list = QtWidgets.QListWidget(self)
        self.scan_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.refresh_btn = QtWidgets.QPushButton("Refresh from Selection", self)
        self.add_to_tab_btn = QtWidgets.QPushButton("➕ Add to Current Tab", self)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.search_edit)
        left_layout.addWidget(self.scan_list)
        left_btn_row = QtWidgets.QHBoxLayout()
        left_btn_row.addWidget(self.refresh_btn)
        left_btn_row.addWidget(self.add_to_tab_btn)
        left_layout.addLayout(left_btn_row)

        # ----- 右：タブ -----
        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self._ensure_default_tab()

        self.new_tab_btn = QtWidgets.QPushButton("新規タブ", self)
        self.rename_tab_btn = QtWidgets.QPushButton("タブ名変更", self)
        right_btns = QtWidgets.QHBoxLayout()
        right_btns.addWidget(self.new_tab_btn)
        right_btns.addWidget(self.rename_tab_btn)
        self.save_tabs_btn = QtWidgets.QPushButton("保存…", self)
        self.load_tabs_btn = QtWidgets.QPushButton("読込…", self)
        right_btns.addWidget(self.save_tabs_btn)
        right_btns.addWidget(self.load_tabs_btn)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.tabs)
        right_layout.addLayout(right_btns)

        # ----- 全体配置 -----
        splitter = QtWidgets.QSplitter(self)
        left_widget = QtWidgets.QWidget(self)
        left_widget.setLayout(left_layout)
        right_widget = QtWidgets.QWidget(self)
        right_widget.setLayout(right_layout)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main = QtWidgets.QVBoxLayout(self)
        main.addWidget(splitter)

        # 状態
        self._all_scanned: List[str] = []
        self._updating_selection = False  # ループ防止
        self._scriptjob_id = None

        # つなぎ込み
        self.refresh_btn.clicked.connect(self.refresh_from_scene)
        self.search_edit.textChanged.connect(self._apply_filter)
        self.add_to_tab_btn.clicked.connect(self._add_selected_scan_to_current_tab)

        # 即時セレクト（左ペイン）
        self.scan_list.itemSelectionChanged.connect(self._instant_select_from_scan)
        # 即時セレクト（右ペイン 各タブ）
        self.tabs.currentChanged.connect(self._hook_current_tab_signals)

        self.new_tab_btn.clicked.connect(self._create_new_tab)
        self.rename_tab_btn.clicked.connect(self._rename_current_tab)
        self.save_tabs_btn.clicked.connect(self._save_tabs_dialog)
        self.load_tabs_btn.clicked.connect(self._load_tabs_dialog)

        # 初期
        self.refresh_from_scene()
        self._install_selection_scriptjob()
        self._hook_current_tab_signals()  # 現在のタブのシグナルを接続

    # ---------------- Core ----------------
    def refresh_from_scene(self):
        roots = cmds.ls(sl=True, long=True) or []
        self._all_scanned = list_curve_ctrls_under(roots)
        self._rebuild_scan_list(self._all_scanned)

    # ---------------- 左ペイン（スキャン結果） ----------------
    def _rebuild_scan_list(self, names: List[str]):
        self.scan_list.clear()
        for n in names:
            short = cmds.ls(n, sn=True)[0] if cmds.objExists(n) else n
            item = QtWidgets.QListWidgetItem(short)
            item.setToolTip(n)
            item.setData(QtCore.Qt.UserRole, n)
            self.scan_list.addItem(item)

    def _apply_filter(self):
        pat = self.search_edit.text().strip()
        if not pat:
            self._rebuild_scan_list(self._all_scanned)
            return
        try:
            rx = re.compile(pat)
            filtered = [n for n in self._all_scanned if rx.search(n)]
        except re.error:
            filtered = [n for n in self._all_scanned if pat in n]
        self._rebuild_scan_list(filtered)

    def _instant_select_from_scan(self):
        if self._updating_selection:
            return
        names = [i.data(QtCore.Qt.UserRole) for i in self.scan_list.selectedItems()]
        self._select_in_maya(names)

    def _add_selected_scan_to_current_tab(self):
        tab: PartsTab = self.tabs.currentWidget()
        if not isinstance(tab, PartsTab):
            return
        picked = [i.data(QtCore.Qt.UserRole) for i in self.scan_list.selectedItems()]
        if not picked:
            return
        current = tab.items()
        # 重複回避
        merged = current + [n for n in picked if n not in current]
        tab.set_items(merged)

    # ---------------- 右ペイン（タブ） ----------------
    def _ensure_default_tab(self):
        if self.tabs.count() == 0:
            self._add_tab_with_title("Default")

    def _create_new_tab(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "新規タブ", "タブ名：", text=f"Part{self.tabs.count()+1}")
        if ok and text:
            self._add_tab_with_title(text)

    def _rename_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        cur = self.tabs.tabText(idx)
        text, ok = QtWidgets.QInputDialog.getText(self, "タブ名変更", "タブ名：", text=cur)
        if ok and text and text != cur:
            self.tabs.setTabText(idx, text)

    def _add_tab_with_title(self, title: str):
        tab = PartsTab(title, self)
        self.tabs.addTab(tab, title)
        self.tabs.setCurrentWidget(tab)
        # 右タブの即時セレクトをフック
        tab.list.itemSelectionChanged.connect(self._instant_select_from_tab)

    def _close_tab(self, index: int):
        if self.tabs.count() <= 1:
            QtWidgets.QMessageBox.information(self, "Info", "最後のタブは削除できません。")
            return
        w = self.tabs.widget(index)
        self.tabs.removeTab(index)
        w.deleteLater()

    def _hook_current_tab_signals(self, *_):
        tab = self.tabs.currentWidget()
        if isinstance(tab, PartsTab):
            # 念のため重複接続を避ける対策（Qtは同一関数複数回connectされうる）
            try:
                tab.list.itemSelectionChanged.disconnect(self._instant_select_from_tab)
            except Exception:
                pass
            tab.list.itemSelectionChanged.connect(self._instant_select_from_tab)

    def _instant_select_from_tab(self):
        if self._updating_selection:
            return
        tab: PartsTab = self.tabs.currentWidget()
        if not isinstance(tab, PartsTab):
            return
        names = [i.data(QtCore.Qt.UserRole) for i in tab.list.selectedItems()]
        self._select_in_maya(names)

    # ---------------- Serialize / Deserialize Tabs ----------------
    def _serialize_tabs(self):
        """UI上のタブ構成を辞書のリストに変換"""
        result = []
        for i in range(self.tabs.count()):
            tab: PartsTab = self.tabs.widget(i)
            result.append({
                "title": self.tabs.tabText(i),
                "items": tab.items(),
            })
        return result

    def _deserialize_tabs(self, tabs_data):
        """辞書からUIを再構築（既存タブは破棄）"""
        # 既存削除
        while self.tabs.count() > 0:
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()
        # 復元
        for info in tabs_data:
            title = info.get("title", "Untitled")
            items = info.get("items", [])
            tab = PartsTab(title, self)
            tab.set_items(items)
            self.tabs.addTab(tab, title)
            tab.list.itemSelectionChanged.connect(self._instant_select_from_tab)
        self._ensure_default_tab()
        self.tabs.setCurrentIndex(0)

    def _scripts_dir(self) -> Path:
        """main.py（このファイル）と同じディレクトリを返す"""
        return Path(os.path.dirname(os.path.abspath(__file__)))

    def _default_preset_dir(self) -> Path:
        """プリセット保存用の既定ディレクトリ（ツールルート直下の presets/）"""
        return (self._scripts_dir().parent / "presets")

    def _save_tabs_dialog(self):
        """名前を付けて保存（JSON）"""
        # ★ 追加：presets ディレクトリを必ず作成
        preset_dir = self._default_preset_dir()
        preset_dir.mkdir(parents=True, exist_ok=True)
        base = str(preset_dir)

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "タブセットを保存",
            os.path.join(base, "picker_tabs.json"),
            "Tab Preset (*.json)"
        )
        if not fname:
            return

        # ★ 追加：選択されたパスの親ディレクトリを作成（保険）
        Path(fname).parent.mkdir(parents=True, exist_ok=True)

        # 拡張子補完
        if not fname.lower().endswith(".json"):
            fname += ".json"

        data = {"tabs": self._serialize_tabs()}
        try:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            cmds.inViewMessage(amg=f"<hl>Saved:</hl> {fname}", pos="midCenter", fade=True)
        except Exception as e:
            cmds.warning(f"[ControllerPicker] Save failed: {e}")

    def _load_tabs_dialog(self):
        """ファイルを選んで読み込み（JSON）"""
        # ★ 追加：presets ディレクトリを必ず作成
        preset_dir = self._default_preset_dir()
        preset_dir.mkdir(parents=True, exist_ok=True)
        base = str(preset_dir)

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "タブセットを読込",
            base,
            "Tab Preset (*.json)"
        )
        if not fname:
            return
        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._deserialize_tabs(data.get("tabs", []))
            cmds.inViewMessage(amg=f"<hl>Loaded:</hl> {fname}", pos="midCenter", fade=True)
        except Exception as e:
            cmds.warning(f"[ControllerPicker] Load failed: {e}")

    # ---------------- Scene Sync ----------------
    def _install_selection_scriptjob(self):
        def on_sel_changed():
            # シーン選択 → UI反映（控えめに、現在タブだけ追随）
            self._sync_ui_selection_with_scene()
        self._remove_scriptjob()
        self._scriptjob_id = cmds.scriptJob(e=["SelectionChanged", on_sel_changed], protected=True)

    def _remove_scriptjob(self):
        if self._scriptjob_id and cmds.scriptJob(exists=self._scriptjob_id):
            try:
                cmds.scriptJob(kill=self._scriptjob_id, force=True)
            except Exception:
                pass
        self._scriptjob_id = None

    def _sync_ui_selection_with_scene(self):
        sel = set(cmds.ls(sl=True, long=True) or [])
        self._updating_selection = True
        try:
            # 左リスト
            for i in range(self.scan_list.count()):
                it = self.scan_list.item(i)
                it.setSelected(it.data(QtCore.Qt.UserRole) in sel)
            # 右カレントタブ
            tab: PartsTab = self.tabs.currentWidget()
            if isinstance(tab, PartsTab):
                for i in range(tab.list.count()):
                    it = tab.list.item(i)
                    it.setSelected(it.data(QtCore.Qt.UserRole) in sel)
        finally:
            self._updating_selection = False

    def _select_in_maya(self, names: List[str]):
        self._updating_selection = True
        try:
            # 存在しないノードを除去
            valid = [n for n in names if cmds.objExists(n)]
            cmds.select(valid, r=True) if valid else cmds.select(clear=True)
        except Exception as e:
            cmds.warning(f"[ControllerPicker] Select failed: {e}")
        finally:
            # 少し遅延してUI同期（クリック直後のちらつき防止）
            QtCore.QTimer.singleShot(0, self._sync_ui_selection_with_scene)
            self._updating_selection = False

    def closeEvent(self, ev):
        self._remove_scriptjob()
        super().closeEvent(ev)


# ---- Entrypoint ----
def run():
    # 既存ウィンドウ破棄
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == WINDOW_OBJECT_NAME:
            w.close()
            w.deleteLater()
    dlg = ControllerPicker()
    dlg.show()
    return dlg


def onMayaDroppedPythonFile(*_a, **_k):
    run()