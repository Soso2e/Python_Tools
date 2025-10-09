# -*- coding: utf-8 -*-
"""
CV Scaler: Scale CVs of selected NURBS (curves/surfaces) with a simple UI.

- 選択された Transform から nurbsCurve / nurbsSurface の Shape を抽出
- CV コンポーネント（curve: .cv[*] / surface: .cv[*][*]）を相対スケール
- ピボットは各Transformの回転ピボット（World座標）を使用
"""

from __future__ import annotations
from typing import List, Tuple
from maya import cmds


WINDOW_TITLE = "CV_Scaler"
WINDOW_NAME = "CV_Scaler_Window"

# --- Preview state (temporary clusters) ---
_PREVIEW = {"handles": [], "factor": 1.0}


def _selected_nurbs_shapes() -> List[Tuple[str, str]]:
    """選択から NURBS の shape を抽出する。

    Returns:
        list[tuple[str, str]]: (transform, shape) のタプル配列
    """
    sel = cmds.ls(sl=True, long=True) or []
    results: List[Tuple[str, str]] = []
    for node in sel:
        # Transform配下のshapeを取得
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        for s in shapes:
            t = cmds.nodeType(s)
            if t in ("nurbsCurve", "nurbsSurface"):
                results.append((node, s))
    return results


def _shape_cvs(shape: str) -> List[str]:
    """NURBS shape の CV コンポーネントを返す。

    Args:
        shape: シェイプのフルパス

    Returns:
        list[str]: CV コンポーネント（curve: shape.cv[*] / surface: shape.cv[*][*]）
    """
    ntype = cmds.nodeType(shape)
    if ntype == "nurbsCurve":
        return [f"{shape}.cv[*]"]
    if ntype == "nurbsSurface":
        return [f"{shape}.cv[*][*]"]
    return []


def _ensure_list(obj):
    return obj if isinstance(obj, list) else [obj]


def _create_preview_clusters(pairs: List[Tuple[str, str]]) -> None:
    """選択中NURBSに一時クラスターを作成（非破壊プレビュー用）。

    - 各 shape のCVをクラスター化し、ハンドルのピボットを Transform の回転ピボットに合わせる
    - 作成したハンドル(transform)を _PREVIEW["handles"] に保持
    """
    _clear_preview()  # 既存プレビューを一旦クリア
    handles: List[str] = []

    for xform, shape in pairs:
        comps = _shape_cvs(shape)
        if not comps:
            continue
        # クラスター作成（すべてのCVを対象）
        cluster_nodes = cmds.cluster(comps, name="cvScalerTmpCluster#")  # [cluster, handle]
        cluster_nodes = _ensure_list(cluster_nodes)
        if len(cluster_nodes) < 2:
            # Mayaの戻り値が [u'cluster1', u'cluster1Handle'] 想定
            continue
        handle = cluster_nodes[1]
        # ハンドルのピボットを Transform の回転ピボットに合わせる
        pv = _pivot_world_pos(xform)
        try:
            cmds.xform(handle, ws=True, sp=pv, rp=pv)  # scale/rotate pivot
        except Exception:
            pass
        handles.append(handle)

    _PREVIEW["handles"] = handles
    _PREVIEW["factor"] = 1.0


def _update_preview_factor(factor: float) -> None:
    """プレビュー中のクラスター ハンドルのスケールを更新。"""
    if not _PREVIEW["handles"]:
        return
    for h in _PREVIEW["handles"]:
        if cmds.objExists(h):
            try:
                cmds.setAttr(h + ".scaleX", factor)
                cmds.setAttr(h + ".scaleY", factor)
                cmds.setAttr(h + ".scaleZ", factor)
            except Exception:
                pass
    _PREVIEW["factor"] = factor


def _clear_preview() -> None:
    """プレビュー用クラスターを削除（元形状へ復帰）。"""
    handles = _PREVIEW.get("handles", [])
    for h in handles:
        # ハンドルからクラスター本体を辿ってまとめて削除
        if cmds.objExists(h):
            try:
                # handle の親にクラスターシェイプがある想定なので handle だけ消せばOK
                cmds.delete(h)
            except Exception:
                pass
    _PREVIEW["handles"] = []
    _PREVIEW["factor"] = 1.0


def _pivot_world_pos(transform: str) -> Tuple[float, float, float]:
    """Transform の回転ピボットをワールド座標で取得。"""
    pv = cmds.xform(transform, q=True, rp=True, ws=True)
    # xform rp は [x,y,z] を返す
    return float(pv[0]), float(pv[1]), float(pv[2])


def _scale_cvs_uniform(components: List[str], factor: float, pivot: Tuple[float, float, float]) -> None:
    """CVコンポーネントを一括スケール（相対・等倍）"""
    if not components:
        return
    cmds.scale(factor, factor, factor, components, r=True, p=pivot)  # r=True: relative


def _do_scale(factor: float) -> None:
    """実行本体：選択から抽出 → 形状ごとにCVをスケール。"""
    # コミット前にプレビューを消去（二重適用を避ける）
    _clear_preview()
    pairs = _selected_nurbs_shapes()
    if not pairs:
        cmds.warning(u"[CV_Scaler] NURBSが選択されていません（Transformを選んでください）。")
        return

    # アンドゥをまとめる
    cmds.undoInfo(openChunk=True)
    try:
        count = 0
        for xform, shape in pairs:
            comps = _shape_cvs(shape)
            if not comps:
                continue
            pivot = _pivot_world_pos(xform)
            _scale_cvs_uniform(comps, factor, pivot)
            count += 1
        if count == 0:
            cmds.warning(u"[CV_Scaler] スケール対象が見つかりませんでした。")
        else:
            cmds.inViewMessage(amg=u"<hl>CV_Scaler</hl>: Applied ×%g to %d shape(s)" % (factor, count), pos="midCenter", fade=True)
    finally:
        cmds.undoInfo(closeChunk=True)


def _build_ui() -> None:
    """シンプルUIを構築。"""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME, window=True)

    win = cmds.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=False)
    cmds.columnLayout(adj=True, rs=8, co=("both", 10))

    # スライダー（0.1～3.0, default=1.0）
    slider = cmds.floatSliderGrp(
        "cvScaler_factor",
        label="Scale",
        field=True,
        min=0.1, max=3.0, value=1.0,
        precision=3,
    )

    # スライダー操作時にプレビューを更新（ドラッグ＆値確定の両方）
    def _on_slider_change(val=None, *_):
        try:
            f = cmds.floatSliderGrp(slider, q=True, value=True)
        except Exception:
            f = 1.0
        _update_preview_factor(f)

    cmds.floatSliderGrp(slider, e=True, dc=_on_slider_change, cc=_on_slider_change)

    cmds.separator(h=6, style="none")

    def _start_preview(*_):
        pairs = _selected_nurbs_shapes()
        if not pairs:
            cmds.warning(u"[CV_Scaler] プレビュー対象のNURBSが選択されていません。")
            return
        _create_preview_clusters(pairs)
        # 現在のスライダー値で即時反映
        _on_slider_change()

    def _apply(*_):
        # 現在のスライダー値を最終適用（プレビューは消去してから実適用）
        factor = cmds.floatSliderGrp(slider, q=True, value=True)
        _do_scale(factor)

    def _cancel(*_):
        _clear_preview()

    cmds.rowLayout(nc=3, cw3=(140, 100, 120), adj=1)
    cmds.button(label="Preview From Selection", c=_start_preview, h=28)
    cmds.button(label="Apply", c=_apply, h=28)
    cmds.button(label="Cancel Preview", c=_cancel, h=28)
    cmds.setParent("..")

    cmds.separator(h=4, style="none")
    cmds.text(l=u"選択中の Transform 配下の NURBS（curve/surface）のCVを、回転ピボット基準で相対スケールします。\nプレビューは一時クラスターで非破壊、Applyで確定、Cancelで元に戻せます。", al="left")

    cmds.showWindow(win)

    # ウィンドウが閉じられたらプレビューを自動解除
    try:
        cmds.scriptJob(uiDeleted=[win, _clear_preview])
    except Exception:
        pass


def main() -> None:
    """エントリーポイント：UI起動。"""
    _build_ui()