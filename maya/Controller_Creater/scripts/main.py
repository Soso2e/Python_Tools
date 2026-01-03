# main.py
# -*- coding: utf-8 -*-
"""
Controller Creator (Rig-friendly, Single Shape: Circle)
- UI lists selected objects.
- Shape: Circle (created at origin, frozen cleanly).
- Circle Normal Axis: selectable X/Y/Z (controls cmds.circle nr).
- Placement: per-target offset group is ALWAYS snapped to the target (position + orientation) via bake-snap.
- Orientation:
    - Match Target: controller inherits offset group's orientation (matches joint).
    - World: controller's rotation is canceled to world (0,0,0), then rotation-only freeze is applied
             so the NURBS curve becomes world-aligned while keeping ctrl transforms clean.
- Hierarchy: optionally mirrors joint hierarchy by parenting each child controller GROUP under its parent controller.
- Constraints: controller drives target via parentConstraint (+ optional scaleConstraint).
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


def _create_shape_transform(shape_key: str, name: str, normal_axis: str) -> str:
    """Create controller shape at origin. Placement/orientation is handled by offset groups."""
    shape_def = SHAPE_DEFS.get(shape_key)
    if shape_def is None:
        raise RuntimeError(f"Unknown shape_key: {shape_key}")

    ctrl = ""
    if shape_def == "circle":
        # Circle normal axis selectable (X/Y/Z)
        axis = (normal_axis or "Y").upper()
        if axis == "X":
            nr = (1, 0, 0)
        elif axis == "Z":
            nr = (0, 0, 1)
        else:
            nr = (0, 1, 0)

        ctrl = cmds.circle(n=name, ch=False, o=True, nr=nr, r=1.0)[0]

    elif isinstance(shape_def, CurveShapeDef):
        ctrl = cmds.curve(n=name, d=shape_def.degree, p=list(shape_def.points), k=list(shape_def.knots))

    if not ctrl:
        raise RuntimeError(f"Failed to create shape for {shape_key}")

    # Keep clean TRS at origin
    cmds.xform(ctrl, ws=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0))
    return ctrl


def _get_world_matrix(target: str) -> List[float]:
    return [float(v) for v in cmds.xform(target, q=True, ws=True, m=True)]


def _get_world_position(target: str) -> Tuple[float, float, float]:
    """Get robust world position for the target."""
    t = cmds.xform(target, q=True, ws=True, t=True)
    return (float(t[0]), float(t[1]), float(t[2]))


def _matrix_remove_scale_shear(m: List[float]) -> List[float]:
    """Return a matrix with orthonormal rotation axes (scale/shear removed), preserving translation."""
    # Row-major axes
    x = [m[0], m[1], m[2]]
    y = [m[4], m[5], m[6]]
    z = [m[8], m[9], m[10]]

    def _norm(v: List[float]) -> List[float]:
        import math
        l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        if l < 1e-8:
            return [0.0, 0.0, 0.0]
        return [v[0] / l, v[1] / l, v[2] / l]

    xn = _norm(x)
    yn = _norm(y)
    zn = _norm(z)

    out = list(m)
    out[0], out[1], out[2] = xn
    out[4], out[5], out[6] = yn
    out[8], out[9], out[10] = zn

    # Preserve translation
    out[12], out[13], out[14] = m[12], m[13], m[14]
    out[3] = out[7] = out[11] = 0.0
    out[15] = 1.0
    return out


def _freeze_trs(node: str) -> None:
    cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=False)


def _freeze_rot(node: str) -> None:
    """Freeze rotation only (bake into shape), keeping translate/scale untouched."""
    cmds.makeIdentity(node, apply=True, t=False, r=True, s=False, n=False)


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
        except Exception:
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
            if not p:
                break
            if is_joint(p[0]):
                cur = p[0]
            else:
                break
        return _safe_name_from_target(cur)

    long_name = cmds.ls(target, l=True) or [target]
    dag = long_name[0]
    if "|" in dag:
        parts = [p for p in dag.split("|") if p]
        if parts:
            return _safe_name_from_target(parts[0])

    return _safe_name_from_target(target)


def _parent_preserve_world(child: str, new_parent: str) -> None:
    """Parent `child` under `new_parent` while preserving child's world transform."""
    child_m = cmds.xform(child, q=True, ws=True, m=True)
    cmds.parent(child, new_parent)
    cmds.xform(child, ws=True, m=child_m)


def _make_offset_group(
        ctrl: str,
        target: str,
        match_orientation: bool,  # kept for compatibility; placement is always snapped now
        desired_root_grp_name: str,
        desired_offset_grp_name: str,
        orientation_mode: str,
) -> str:
    """Create controller groups:
    - Root container (reused): {jointRoot}_{InputName}_GRP
    - Per-target offset group (unique): {target}_{InputName}_CTL_GRP

    Key rules (rig-friendly):
    - Per-target offset group is snapped to target in WORLD (pos+orient) first.
    - Then parent under the root container while preserving WORLD.
    - CTRL stays clean; for World mode we cancel ctrl rotation and freeze rotation only.
    """
    # Root container (reused)
    if cmds.objExists(desired_root_grp_name):
        root_grp = desired_root_grp_name
    else:
        root_grp = cmds.group(em=True, n=desired_root_grp_name)
        cmds.xform(root_grp, ws=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0))

    # Per-target offset group (unique) — create UNPARENTED first
    offset_grp = desired_offset_grp_name
    if cmds.objExists(offset_grp):
        offset_grp = _unique_name(offset_grp)
    offset_grp = cmds.group(em=True, n=offset_grp)

    # 1) Snap offset group in WORLD (before parenting)
    # Always snap so placement never breaks between modes.
    tmp = cmds.parentConstraint(target, offset_grp, mo=False)[0]
    cmds.delete(tmp)

    # 2) Force pivots to current position
    pos_now = _get_world_position(offset_grp)
    cmds.xform(offset_grp, ws=True, rp=pos_now, sp=pos_now)

    # 3) Parent CTRL under offset group (do NOT keep world position)
    cmds.parent(ctrl, offset_grp, relative=True)

    # World mode: keep the circle horizontal in WORLD by canceling inherited rotation,
    # then bake it into the shape by freezing rotation only.
    if (orientation_mode or "match").lower() == "world":
        # Set CTRL world rotation to 0 -> Maya computes local values that cancel parent's rotation
        cmds.xform(ctrl, ws=True, ro=(0.0, 0.0, 0.0))
        _freeze_rot(ctrl)
        # Keep CTRL clean
        cmds.xform(ctrl, os=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0), s=(1.0, 1.0, 1.0))

    # 4) Parent offset group under root container, preserving world
    _parent_preserve_world(offset_grp, root_grp)

    return offset_grp


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
        normal_axis: str,
        orientation_mode: str,
) -> Tuple[str, str, List[str]]:
    if not cmds.objExists(target):
        raise RuntimeError(f"Target does not exist: {target}")

    base = _safe_name_from_target(target)
    input_name = input_name.strip() or "CTL"

    # Naming
    desired_ctrl_name = _unique_name(f"{base}_{input_name}_CTL")
    root_name = _find_joint_root_name(target)
    desired_root_grp_name = f"{root_name}_{input_name}_GRP"
    desired_offset_grp_name = _unique_name(f"{base}_{input_name}_CTL_GRP")

    # 1) Create ctrl at origin (clean)
    ctrl = _create_shape_transform(shape_key, desired_ctrl_name, normal_axis=normal_axis)

    # 2) Freeze at origin (safe)
    _freeze_trs(ctrl)

    # 3) Create per-target offset group under root container
    grp = _make_offset_group(
        ctrl=ctrl,
        target=target,
        match_orientation=match_orientation,
        desired_root_grp_name=desired_root_grp_name,
        desired_offset_grp_name=desired_offset_grp_name,
        orientation_mode=orientation_mode,
    )

    _rename_shape_as_transform_shape(ctrl)

    # 4) Constrain target to ctrl
    constraints = _constrain_target_to_ctrl(
        target=target,
        ctrl=ctrl,
        maintain_offset=maintain_offset,
        use_scale_constraint=use_scale_constraint,
    )

    return ctrl, grp, constraints


# =========================
# Hierarchy mirror helper
# =========================

def _mirror_joint_hierarchy_with_controllers(
        targets: Sequence[str],
        target_to_ctrl: Dict[str, str],
        target_to_grp: Dict[str, str],
) -> None:
    """Parent each target's controller GROUP under its parent target's controller.

    Rule:
    - child controller GROUP (*_CTL_GRP) -> parent under parent CTRL transform
    - only applies when the parent exists in the created set
    """
    for t in targets:
        parents = cmds.listRelatives(t, p=True, f=True) or []
        if not parents:
            continue
        p = parents[0]
        if p not in target_to_ctrl:
            continue

        child_grp = target_to_grp.get(t)
        parent_ctrl = target_to_ctrl.get(p)
        if not child_grp or not parent_ctrl:
            continue

        # Parent while preserving child's world transform
        try:
            _parent_preserve_world(child_grp, parent_ctrl)
        except Exception:
            pass


# =========================
# UI
# =========================

class _UI:
    def __init__(self) -> None:
        self.win: Optional[str] = None
        self.shape_menu: Optional[str] = None
        self.target_list: Optional[str] = None
        self.normal_menu: Optional[str] = None
        self.orient_menu: Optional[str] = None
        self.chk_build_hierarchy: Optional[str] = None
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

        cmds.text(l="Circle Normal Axis:")
        self.normal_menu = cmds.optionMenu(w=260)
        cmds.menuItem(label="X")
        cmds.menuItem(label="Y")
        cmds.menuItem(label="Z")
        cmds.optionMenu(self.normal_menu, e=True, v="Y")

        cmds.text(l="Controller Orientation:")
        self.orient_menu = cmds.optionMenu(w=260)
        cmds.menuItem(label="World")
        cmds.menuItem(label="Match Target")
        cmds.optionMenu(self.orient_menu, e=True, v="Match Target")

        self.chk_build_hierarchy = cmds.checkBox(label="Mirror Joint Hierarchy (recommended)", v=True)
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
        cmds.text(
            l=(
                "Naming:\n"
                "- Ctrl : {target}_{InputName}_CTL\n"
                "- Root : {jointRoot}_{InputName}_GRP\n"
                "- Per  : {target}_{InputName}_CTL_GRP\n"
            ),
            align="left",
        )

        cmds.showWindow(self.win)

    def _get_shape_key(self) -> str:
        return "Circle"

    def _opt_orientation_mode(self) -> str:
        v = cmds.optionMenu(self.orient_menu, q=True, v=True)
        return "world" if v == "World" else "match"

    def _opt_normal_axis(self) -> str:
        v = cmds.optionMenu(self.normal_menu, q=True, v=True)
        return (v or "Y").strip().upper()

    def _opt_maintain_offset(self) -> bool:
        return bool(cmds.checkBox(self.chk_maintain_offset, q=True, v=True))

    def _opt_scale_constraint(self) -> bool:
        return bool(cmds.checkBox(self.chk_scale_constraint, q=True, v=True))

    def _opt_build_hierarchy(self) -> bool:
        return bool(cmds.checkBox(self.chk_build_hierarchy, q=True, v=True))

    def _opt_input_name(self) -> str:
        name = cmds.textFieldGrp(self.txt_input_name, q=True, text=True) or "CTL"
        return name.strip() or "CTL"

    def refresh_targets(self) -> None:
        sel = cmds.ls(sl=True, long=True) or []
        cmds.textScrollList(self.target_list, e=True, removeAll=True)
        if sel:
            cmds.textScrollList(self.target_list, e=True, append=sel)

    def _get_all_targets_in_list(self) -> List[str]:
        return list(cmds.textScrollList(self.target_list, q=True, allItems=True) or [])

    def _get_selected_targets_in_list(self) -> List[str]:
        return list(cmds.textScrollList(self.target_list, q=True, selectItem=True) or [])

    def create_for_all(self) -> None:
        targets = self._get_all_targets_in_list()
        if not targets:
            cmds.warning("List is empty.")
            return
        self._create_batch(targets)

    def create_for_selected(self) -> None:
        targets = self._get_selected_targets_in_list()
        if not targets:
            cmds.warning("No selection in list.")
            return
        self._create_batch(targets)

    def _create_batch(self, targets: Sequence[str]) -> None:
        shape_key = self._get_shape_key()
        input_name = self._opt_input_name()
        orientation_mode = self._opt_orientation_mode()
        match_orient = (orientation_mode == "match")
        normal_axis = self._opt_normal_axis()

        maintain_offset = self._opt_maintain_offset()
        use_scale_constraint = self._opt_scale_constraint()
        build_hierarchy = self._opt_build_hierarchy()

        created: List[str] = []
        target_to_ctrl: Dict[str, str] = {}
        target_to_grp: Dict[str, str] = {}

        cmds.undoInfo(openChunk=True)
        try:
            # 1) Create controllers (independent)
            for t in targets:
                try:
                    ctrl, grp, cons = create_controller_for_target(
                        target=t,
                        shape_key=shape_key,
                        input_name=input_name,
                        match_orientation=match_orient,
                        maintain_offset=maintain_offset,
                        use_scale_constraint=use_scale_constraint,
                        normal_axis=normal_axis,
                        orientation_mode=orientation_mode,
                    )
                    created.append(ctrl)
                    target_to_ctrl[t] = ctrl
                    target_to_grp[t] = grp
                except Exception as e:
                    cmds.warning(f"Failed {t}: {e}")

            # 2) Mirror hierarchy (group under parent ctrl)
            if build_hierarchy and target_to_ctrl:
                _mirror_joint_hierarchy_with_controllers(targets, target_to_ctrl, target_to_grp)

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