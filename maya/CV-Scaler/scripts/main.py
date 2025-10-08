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

    cmds.separator(h=6, style="none")

    def _apply(*_):
        factor = cmds.floatSliderGrp(slider, q=True, value=True)
        _do_scale(factor)

    def _reset(*_):
        cmds.floatSliderGrp(slider, e=True, value=1.0)

    cmds.button(label="Apply", c=_apply, h=30)
    cmds.button(label="Reset Slider to 1.0", c=_reset, h=24)

    cmds.separator(h=4, style="none")
    cmds.text(l=u"選択中の Transform 配下の NURBS（curve/surface）のCVを、回転ピボット基準で相対スケールします。", al="left")

    cmds.showWindow(win)


def main() -> None:
    """エントリーポイント：UI起動。"""
    _build_ui()