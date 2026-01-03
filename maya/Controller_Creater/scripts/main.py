# main.py
# -*- coding: utf-8 -*-
"""
Controller Creator (Rig-friendly, Single Shape: Circle)
- UI lists selected objects.
- Shape: Circle (Created at target position, then frozen).
- Grouping: Reuses existing root groups to avoid clutter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import maya.cmds as cmds

# =========================
# Shape definitions
# =========================

Point = Tuple[float, float, float]


@dataclass(frozen=True)
class CurveShapeDef:
    degree: int
    points: Tuple[Point, ...]
    knots: Tuple[float, ...]


ShapeDef = Union[str, CurveShapeDef]  # "circle" or CurveShapeDef


def _shape_defs() -> Dict[str, ShapeDef]:
    defs: Dict[str, ShapeDef] = {}
    defs["Circle"] = "circle"
    return defs


# =========================
# Core logic
# =========================

WINDOW_NAME = "soso_ctrl_creator_win"
UI_TITLE = "Controller Creator (Circle Only)"
SHAPE_DEFS: Dict[str, ShapeDef] = _shape_defs()


def _safe_name_from_target(target: str) -> str:
    base = target.split("|")[-1]
    return base.replace(":", "_")


def _unique_name(base: str) -> str:
    if not cmds.objExists(base):
        return base
    i = 1
    while cmds.objExists(f"{base}{i}"):
        i += 1
    return f"{base}{i}"


def _create_shape_transform(shape_key: str, name: str, target: str) -> str:
    """
    ターゲットの位置にコントローラを作成します。
    """
    shape_def = SHAPE_DEFS.get(shape_key)
    if shape_def is None:
        raise RuntimeError(f"Unknown shape_key: {shape_key}")

    # ターゲットの位置と回転を取得
    target_pos = cmds.xform(target, q=True, ws=True, t=True)
    target_rot = cmds.xform(target, q=True, ws=True, ro=True)

    ctrl = ""
    if shape_def == "circle":
        # Circle oriented to Y-up plane (XZ plane)
        ctrl = cmds.circle(n=name, ch=False, o=True, nr=(0, 1, 0), r=1.0)[0]
    elif isinstance(shape_def, CurveShapeDef):
        ctrl = cmds.curve(n=name, d=shape_def.degree, p=list(shape_def.points), k=list(shape_def.knots))

    if not ctrl:
        raise RuntimeError(f"Failed to create shape for {shape_key}")

    # ターゲットの位置へ移動
    cmds.xform(ctrl, ws=True, t=target_pos, ro=target_rot)
    return ctrl


def _get_world_matrix(target: str) -> List[float]:
    return [float(v) for v in cmds.xform(target, q=True, ws=True, m=True)]


def _get_world_position(target: str) -> Tuple[float, float, float]:
    m = _get_world_matrix(target)
    return (m[12], m[13], m[14])


def _freeze_trs(node: str) -> None:
    cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=False)


def _rename_shape_as_transform_shape(ctrl: str) -> None:
    shapes = cmds.listRelatives(ctrl, s=True, ni=True, f=False) or []
    if not shapes:
        return

    if len(shapes) == 1:
        new_shape = f"{ctrl}Shape"
        if cmds.objExists(new_shape):
            new_shape = _unique_name(new_shape)
        cmds.rename(shapes[0], new_shape)
        return

    for i, shp in enumerate(shapes, start=1):
        new_shape = f"{ctrl}Shape{i}"
        if cmds.objExists(new_shape):
            new_shape = _unique_name(new_shape)
        cmds.rename(shp, new_shape)


def _find_joint_root_name(target: str) -> str:
    if not cmds.objExists(target):
        return _safe_name_from_target(target)

    def is_joint(n: str) -> bool:
        try:
            return cmds.nodeType(n) == "joint"
        except:
            return False

    start_joint: Optional[str] = None
    if is_joint(target):
        start_joint = target
    else:
        parents = cmds.listRelatives(target, p=True, f=True) or []
        cur = parents[0] if parents else None
        while cur:
            if is_joint(cur):
                start_joint = cur
                break
            p = cmds.listRelatives(cur, p=True, f=True) or []
            cur = p[0] if p else None

    if start_joint:
        cur = start_joint
        while True:
            p = cmds.listRelatives(cur, p=True, f=True) or []
            if not p: break
            if is_joint(p[0]):
                cur = p[0]
            else:
                break
        return _safe_name_from_target(cur)

    long_name = cmds.ls(target, l=True) or [target]
    dag = long_name[0]
    if "|" in dag:
        parts = [p for p in dag.split("|") if p]
        if parts: return _safe_name_from_target(parts[0])

    return _safe_name_from_target(target)


def _make_offset_group(
        ctrl: str,
        target: str,
        match_orientation: bool,
        desired_grp_name: str,
) -> str:
    """
    指定された名前のグループが既にあればそれを使い、なければ作成します。
    """
    if cmds.objExists(desired_grp_name):
        grp = desired_grp_name
    else:
        grp = cmds.group(em=True, n=desired_grp_name)
        if match_orientation:
            m = _get_world_matrix(target)
            cmds.xform(grp, ws=True, m=m)
        else:
            pos = _get_world_position(target)
            cmds.xform(grp, ws=True, t=pos)

    # コントローラをグループに入れる
    cmds.parent(ctrl, grp)
    return grp


def _constrain_target_to_ctrl(
        target: str,
        ctrl: str,
        maintain_offset: bool,
        use_scale_constraint: bool,
) -> List[str]:
    created: List[str] = []
    created.append(cmds.parentConstraint(ctrl, target, mo=maintain_offset)[0])
    if use_scale_constraint:
        created.append(cmds.scaleConstraint(ctrl, target, mo=maintain_offset)[0])
    return created


def create_controller_for_target(
        target: str,
        shape_key: str,
        input_name: str,
        match_orientation: bool,
        maintain_offset: bool,
        use_scale_constraint: bool,
) -> Tuple[str, str, List[str]]:
    if not cmds.objExists(target):
        raise RuntimeError(f"Target does not exist: {target}")

    base = _safe_name_from_target(target)
    input_name = input_name.strip() or "CTL"

    # 命名規則
    desired_ctrl_name = _unique_name(f"{base}_{input_name}")
    root_name = _find_joint_root_name(target)
    desired_grp_name = f"{root_name}_{input_name}_GRP"

    # 1. コントローラをターゲットの位置に作成
    ctrl = _create_shape_transform(shape_key, desired_ctrl_name, target)

    # 2. フリーズ (位置は維持したまま数値を0にする)
    _freeze_trs(ctrl)

    # 3. オフセットグループ (既存のグループがあれば集約)
    grp = _make_offset_group(
        ctrl=ctrl,
        target=target,
        match_orientation=match_orientation,
        desired_grp_name=desired_grp_name,
    )

    _rename_shape_as_transform_shape(ctrl)

    # 4. コンストレイント
    constraints = _constrain_target_to_ctrl(
        target=target,
        ctrl=ctrl,
        maintain_offset=maintain_offset,
        use_scale_constraint=use_scale_constraint,
    )

    return ctrl, grp, constraints


# =========================
# UI
# =========================

class _UI:
    def __init__(self) -> None:
        self.win: Optional[str] = None
        self.shape_menu: Optional[str] = None
        self.target_list: Optional[str] = None
        self.chk_match_orient: Optional[str] = None
        self.chk_maintain_offset: Optional[str] = None
        self.chk_scale_constraint: Optional[str] = None
        self.txt_input_name: Optional[str] = None

    def build(self) -> None:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        self.win = cmds.window(WINDOW_NAME, title=UI_TITLE, sizeable=False)
        cmds.columnLayout(adj=True, rowSpacing=8)

        cmds.text(l="Shape:")
        self.shape_menu = cmds.optionMenu(w=360)
        cmds.menuItem(label="Circle")

        cmds.separator(h=8, style="in")

        cmds.frameLayout(label="Create Options", collapsable=True, collapse=False, mw=8, mh=6)
        cmds.columnLayout(adj=True, rowSpacing=6)

        self.chk_match_orient = cmds.checkBox(label="Match Target Orientation (recommended)", v=True)
        self.chk_maintain_offset = cmds.checkBox(label="Maintain Offset (mo)", v=False)
        self.chk_scale_constraint = cmds.checkBox(label="Scale Constraint (use with care)", v=False)

        self.txt_input_name = cmds.textFieldGrp(label="Input Name", text="CTL", cw2=(120, 220))

        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=8, style="in")

        cmds.rowLayout(nc=2, cw2=(240, 120), adjustableColumn=1)
        cmds.text(l="Targets (Refresh from selection):")
        cmds.button(l="Refresh", c=lambda *_: self.refresh_targets())
        cmds.setParent("..")

        self.target_list = cmds.textScrollList(numberOfRows=12, allowMultiSelection=True, height=220)

        cmds.rowLayout(nc=2, cw2=(240, 240))
        cmds.button(l="Create + Constrain (ALL)", h=34, c=lambda *_: self.create_for_all())
        cmds.button(l="Create + Constrain (SELECTED)", h=34, c=lambda *_: self.create_for_selected())
        cmds.setParent("..")

        cmds.separator(h=8, style="in")
        cmds.text(l="Naming:\n- Ctrl : {target}_{InputName}\n- Grp  : {jointRoot}_{InputName}_GRP", align="left")

        cmds.showWindow(self.win)

    def _get_shape_key(self) -> str:
        return "Circle"

    def _opt_match_orient(self) -> bool:
        return bool(cmds.checkBox(self.chk_match_orient, q=True, v=True))

    def _opt_maintain_offset(self) -> bool:
        return bool(cmds.checkBox(self.chk_maintain_offset, q=True, v=True))

    def _opt_scale_constraint(self) -> bool:
        return bool(cmds.checkBox(self.chk_scale_constraint, q=True, v=True))

    def _opt_input_name(self) -> str:
        name = cmds.textFieldGrp(self.txt_input_name, q=True, text=True) or "CTL"
        return name.strip() or "CTL"

    def refresh_targets(self) -> None:
        sel = cmds.ls(sl=True, long=True) or []
        cmds.textScrollList(self.target_list, e=True, removeAll=True)
        if sel: cmds.textScrollList(self.target_list, e=True, append=sel)

    def _get_all_targets_in_list(self) -> List[str]:
        return list(cmds.textScrollList(self.target_list, q=True, allItems=True) or [])

    def _get_selected_targets_in_list(self) -> List[str]:
        return list(cmds.textScrollList(self.target_list, q=True, selectItem=True) or [])

    def create_for_all(self) -> None:
        targets = self._get_all_targets_in_list()
        if not targets: cmds.warning("List is empty."); return
        self._create_batch(targets)

    def create_for_selected(self) -> None:
        targets = self._get_selected_targets_in_list()
        if not targets: cmds.warning("No selection in list."); return
        self._create_batch(targets)

    def _create_batch(self, targets: Sequence[str]) -> None:
        shape_key = self._get_shape_key()
        input_name = self._opt_input_name()
        match_orient = self._opt_match_orient()
        maintain_offset = self._opt_maintain_offset()
        use_scale_constraint = self._opt_scale_constraint()

        created: List[str] = []
        cmds.undoInfo(openChunk=True)
        try:
            for t in targets:
                try:
                    ctrl, grp, cons = create_controller_for_target(
                        target=t, shape_key=shape_key, input_name=input_name,
                        match_orientation=match_orient, maintain_offset=maintain_offset,
                        use_scale_constraint=use_scale_constraint
                    )
                    created.append(ctrl)
                except Exception as e:
                    cmds.warning(f"Failed {t}: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

        if created:
            cmds.select(created, r=True)
            cmds.inViewMessage(amg=f"<hl>Created:</hl> {len(created)} controllers.", pos="topCenter", fade=True)


_UI_INSTANCE: Optional[_UI] = None


def run() -> None:
    global _UI_INSTANCE
    _UI_INSTANCE = _UI()
    _UI_INSTANCE.build()


if __name__ == "__main__":
    run()