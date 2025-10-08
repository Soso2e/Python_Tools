# -*- coding: utf-8 -*-
# Drag & Drop into Maya viewport to install CV_Scaler shelf & scripts.

from __future__ import annotations
import os, sys, shutil, traceback
from maya import cmds, mel

def _log(msg): cmds.inViewMessage(amg=msg, pos='midCenter', fade=True)

def _ensure_dir(p):
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

def _copytree(src, dst):
    # Python3.8-: dirs_exist_okが無い環境向けフォールバック
    if not os.path.exists(src):
        return
    _ensure_dir(dst)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out_dir = dst if rel == '.' else os.path.join(dst, rel)
        _ensure_dir(out_dir)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(out_dir, f)
            shutil.copy2(s, d)

def _detect_pkg_root(dropped_path: str | None = None) -> str:
    """ドラッグ時は filePath が来るのでその親を、通常実行では __file__ を使う。"""
    if dropped_path and os.path.exists(dropped_path):
        return os.path.dirname(dropped_path)
    try:
        return os.path.dirname(__file__)  # D&D以外（モジュールとして実行など）
    except NameError:
        # ScriptEditorに貼って実行されたケースは__file__がないので手動選択
        sel = cmds.fileDialog2(dialogStyle=2, fileMode=3, caption="Select CV_Scaler package root")
        if sel:
            return sel[0]
        raise RuntimeError("パッケージルートが特定できませんでした。")

def _install_from_pkg_root(pkg_root: str) -> None:
    shelves_src = os.path.join(pkg_root, "shelves")
    scripts_src = os.path.join(pkg_root, "scripts")
    icons_src   = os.path.join(pkg_root, "icon")  # singular

    # Mayaユーザフォルダ/バージョン
    user_root = cmds.internalVar(userAppDir=True)  # .../Documents/maya/
    ver = cmds.about(v=True)                       # "2025" など
    prefs = os.path.join(user_root, ver, "prefs")
    shelves_dst = os.path.join(prefs, "shelves")
    icons_dst   = os.path.join(prefs, "icons")
    scripts_dst = os.path.join(user_root, ver, "scripts")

    for d in (shelves_dst, icons_dst, scripts_dst):
        _ensure_dir(d)

    # 配置（上書き）
    mel_src = os.path.join(shelves_src, "add_to_shelf.mel")
    if os.path.exists(mel_src):
        shutil.copy2(mel_src, os.path.join(shelves_dst, "add_to_shelf.mel"))
    else:
        cmds.warning("[CV_Scaler] shelves/add_to_shelf.mel が見つかりません。")

    if os.path.isdir(scripts_src):
        _copytree(scripts_src, scripts_dst)
    else:
        cmds.warning("[CV_Scaler] scripts フォルダが見つかりません。")

    if os.path.isdir(icons_src):
        _copytree(icons_src, icons_dst)  # *.png をまとめて
    # icons は任意。無ければスキップ

    # その場で棚を反映（次回起動を待たずにボタンを出す）
    try:
        mel.eval('source "add_to_shelf.mel";')
    except Exception as e:
        cmds.warning(f"[CV_Scaler] add_to_shelf.mel の反映に失敗: {e}")

def main(dropped_path: str | None = None) -> None:
    """通常実行／D&D両対応のメイン"""
    try:
        pkg_root = _detect_pkg_root(dropped_path)
        _install_from_pkg_root(pkg_root)
        _log(u"<hl>CV_Scaler</hl>: インストール完了！シェルフのボタンから起動できます。")
        cmds.confirmDialog(title="CV_Scaler", message="インストール完了！\nShelfにボタンが追加されました。", button=["OK"])
    except Exception:
        err = traceback.format_exc()
        cmds.warning(err)
        cmds.confirmDialog(title="CV_Scaler - Error", message=err, button=["OK"], icon="critical")

def onMayaDroppedPythonFile(filePath: str) -> None:
    """★D&Dエントリーポイント：必須★
    ビューポートに .py をドロップすると Maya はこの関数を探して呼びます。
    引数 filePath には“ドロップした .py のフルパス”が入ります。
    """
    # ドロップした .py の場所をパッケージルートの基準にして実行
    main(filePath)

if __name__ == "__main__":
    # ビューポートD&Dではここは使われません（保険で残す）
    main()