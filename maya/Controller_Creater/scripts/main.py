# main.py
# -*- coding: utf-8 -*-
"""
Controller Creator (Pivot -> Controller)
- UI lists selected objects; can create controllers for all or selected list items.
- Controller is created with chosen curve shape.
- Controller is frozen (0/0/0, 1/1/1) via offset group (grp holds placement).
- Constraint target to controller (parentConstraint + optional scaleConstraint).

Key options:
- Match Target Orientation:
    Place offset group to target world matrix (position+rotation). Best for rig controllers.
- Maintain Offset (mo):
    Use mo=True on constraints (prevents snapping).
- Scale Constraint:
    Optional (can cause issues with joints/SSC, so off by default).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import maya.cmds as cmds


# =========================
# Shape definitions (ported from MoxRigController.mel - partial)
# =========================

Point = Tuple[float, float, float]


@dataclass(frozen=True)
class CurveShapeDef:
    degree: int
    points: Tuple[Point, ...]
    knots: Tuple[float, ...]


ShapeDef = Union[str, CurveShapeDef]  # "circle" or CurveShapeDef


def _shape_defs_from_moxrig_mel_port() -> Dict[str, ShapeDef]:
    """
    Returns shape definitions ported from the MEL cases.
    NOTE: This is a practical subset. Add more cases here if needed.
    """
    defs: Dict[str, ShapeDef] = {}

    defs["mox001Circle"] = "circle"

    defs["mox001Circle2"] = CurveShapeDef(
        degree=3,
        points=(
            (7.06316e-09, 0.0, -1.0),
            (0.104714, 0.0, -0.990425),
            (0.314142, 0.0, -0.971274),
            (0.597534, 0.0, -0.821244),
            (0.822435, 0.0, -0.597853),
            (0.96683, 0.0, -0.314057),
            (1.016585, 0.0, -2.28604e-05),
            (0.96683, 0.0, 0.314148),
            (0.822435, 0.0, 0.597532),
            (0.597534, 0.0, 0.822435),
            (0.314142, 0.0, 0.96683),
            (0.104714, 0.0, 0.990425),
            (7.06316e-09, 0.0, 1.0),
            (-0.104714, 0.0, 0.990425),
            (-0.314142, 0.0, 0.96683),
            (-0.597534, 0.0, 0.822435),
            (-0.822435, 0.0, 0.597532),
            (-0.96683, 0.0, 0.314148),
            (-1.016585, 0.0, -2.28604e-05),
            (-0.96683, 0.0, -0.314057),
            (-0.822435, 0.0, -0.597853),
            (-0.597534, 0.0, -0.821244),
            (-0.314142, 0.0, -0.971274),
            (-0.104714, 0.0, -0.990425),
            (7.06316e-09, 0.0, -1.0),
        ),
        knots=(
            0.0, 0.0, 0.0,
            1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0,
            11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0,
            20.0, 20.0
        ),
    )

    defs["mox001Triangle"] = CurveShapeDef(
        degree=1,
        points=((0.0, 0.0, 1.0), (0.866025, 0.0, -0.5), (-0.866025, 0.0, -0.5), (0.0, 0.0, 1.0)),
        knots=(0.0, 1.0, 2.0, 3.0),
    )

    defs["mox001Square"] = CurveShapeDef(
        degree=1,
        points=((1.0, 0.0, 1.0), (1.0, 0.0, -1.0), (-1.0, 0.0, -1.0), (-1.0, 0.0, 1.0), (1.0, 0.0, 1.0)),
        knots=(0.0, 1.0, 2.0, 3.0, 4.0),
    )

    defs["mox001Cross"] = CurveShapeDef(
        degree=1,
        points=(
            (0.3, 0.0, 1.0), (0.3, 0.0, 0.3), (1.0, 0.0, 0.3),
            (1.0, 0.0, -0.3), (0.3, 0.0, -0.3), (0.3, 0.0, -1.0),
            (-0.3, 0.0, -1.0), (-0.3, 0.0, -0.3), (-1.0, 0.0, -0.3),
            (-1.0, 0.0, 0.3), (-0.3, 0.0, 0.3), (-0.3, 0.0, 1.0),
            (0.3, 0.0, 1.0),
        ),
        knots=tuple(float(i) for i in range(13)),
    )

    defs["mox001Cube"] = CurveShapeDef(
        degree=1,
        points=(
            (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, -1.0, 1.0), (-1.0, -1.0, 1.0), (-1.0, -1.0, -1.0),
            (-1.0, 1.0, -1.0), (1.0, 1.0, -1.0), (1.0, -1.0, -1.0),
            (1.0, 1.0, -1.0), (1.0, 1.0, 1.0), (1.0, -1.0, 1.0),
            (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0), (-1.0, -1.0, 1.0),
            (-1.0, 1.0, 1.0), (-1.0, 1.0, -1.0),
        ),
        knots=tuple(float(i) for i in range(16)),
    )

    defs["mox001Dia"] = CurveShapeDef(
        degree=1,
        points=((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        knots=(0.0, 1.0, 2.0, 3.0, 4.0),
    )

    defs["mox001Aim"] = CurveShapeDef(
        degree=1,
        points=(
            (0.0, 0.0, 1.0), (0.0, 0.0, -1.0),
            (0.0, 2.0, 0.0), (0.0, -2.0, 0.0),
            (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (2.0, 0.0, 0.0), (-2.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
        ),
        knots=tuple(float(i) for i in range(10)),
    )

    return defs


# =========================
# Core logic
# =========================

WINDOW_NAME = "soso_ctrl_creator_win"
UI_TITLE = "Controller Creator (Rig-friendly)"
SHAPE_DEFS: Dict[str, ShapeDef] = _shape_defs_from_moxrig_mel_port()


def _safe_name_from_target(target: str) -> str:
    base = target.split("|")[-1]
    base = base.replace(":", "_")
    return base


def _unique_name(base: str) -> str:
    if not cmds.objExists(base):
        return base
    i = 1
    while cmds.objExists(f"{base}{i}"):
        i += 1
    return f"{base}{i}"


def _create_shape_transform(shape_key: str, name: str) -> str:
    shape_def = SHAPE_DEFS.get(shape_key)
    if shape_def is None:
        raise RuntimeError(f"Unknown shape_key: {shape_key}")

    if shape_def == "circle":
        ctrl = cmds.circle(n=name, ch=False, o=True, nr=(0, 1, 0), r=1.0)[0]
        return ctrl

    if isinstance(shape_def, CurveShapeDef):
        ctrl = cmds.curve(n=name, d=shape_def.degree, p=list(shape_def.points), k=list(shape_def.knots))
        return ctrl

    raise RuntimeError(f"Invalid shape_def for {shape_key}: {shape_def}")


def _get_world_pivot(target: str) -> Tuple[float, float, float]:
    rp = cmds.xform(target, q=True, ws=True, rp=True)
    return (float(rp[0]), float(rp[1]), float(rp[2]))


def _get_world_matrix(target: str) -> List[float]:
    """
    16 floats world matrix. This includes translation+rotation(+scale).
    Maya returns row-major 16 floats for xform -q -ws -m.
    """
    return [float(v) for v in cmds.xform(target, q=True, ws=True, m=True)]


def _freeze_trs(node: str) -> None:
    cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=False)


def _rename_shape_as_transform_shape(ctrl: str) -> None:
    shapes = cmds.listRelatives(ctrl, s=True, ni=True, f=False) or []
    if not shapes:
        return
    # If multiple shapes exist, rename all with index suffix.
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


def _make_offset_group(ctrl: str, target: str, match_orientation: bool) -> str:
    """
    Create offset group and place it:
      - match_orientation=False: group is world axis, translation to target pivot
      - match_orientation=True : group matches target world matrix (pos+rot+scale)
    """
    grp_name = _unique_name(f"{ctrl}_GRP")
    grp = cmds.group(em=True, n=grp_name)

    if match_orientation:
        m = _get_world_matrix(target)
        cmds.xform(grp, ws=True, m=m)
        # IMPORTANT:
        # If you don't want group inherit scale, you can optionally strip scale from matrix.
        # Leaving as-is is consistent with "match target".
    else:
        pivot_ws = _get_world_pivot(target)
        cmds.xform(grp, ws=True, t=pivot_ws)

    cmds.parent(ctrl, grp)
    return grp


def _constrain_target_to_ctrl(
    target: str,
    ctrl: str,
    maintain_offset: bool,
    use_scale_constraint: bool,
) -> List[str]:
    """
    Constrain target to controller.
    - parentConstraint covers translate+rotate
    - scaleConstraint optional
    """
    created: List[str] = []
    pc = cmds.parentConstraint(ctrl, target, mo=maintain_offset)[0]
    created.append(pc)

    if use_scale_constraint:
        sc = cmds.scaleConstraint(ctrl, target, mo=maintain_offset)[0]
        created.append(sc)

    return created


def create_controller_for_target(
    target: str,
    shape_key: str,
    match_orientation: bool,
    maintain_offset: bool,
    use_scale_constraint: bool,
) -> Tuple[str, str, List[str]]:
    """
    Create controller at target pivot and constrain target.
    Returns: (ctrl, grp, constraints)
    """
    if not cmds.objExists(target):
        raise RuntimeError(f"Target does not exist: {target}")

    base = _safe_name_from_target(target)
    ctrl_name = _unique_name(f"{base}_CTL")
    ctrl = _create_shape_transform(shape_key, ctrl_name)

    # Rig-friendly: ctrl itself should be zeroed and frozen.
    # Place ctrl at origin, freeze, then use offset group for placement.
    cmds.xform(ctrl, ws=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0))
    _freeze_trs(ctrl)

    grp = _make_offset_group(ctrl, target, match_orientation=match_orientation)

    # Rename shape nodes
    _rename_shape_as_transform_shape(ctrl)

    constraints = _constrain_target_to_ctrl(
        target=target,
        ctrl=ctrl,
        maintain_offset=maintain_offset,
        use_scale_constraint=use_scale_constraint,
    )

    cmds.select(ctrl, r=True)
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

        self.txt_suffix: Optional[str] = None

    def build(self) -> None:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        self.win = cmds.window(WINDOW_NAME, title=UI_TITLE, sizeable=False)
        cmds.columnLayout(adj=True, rowSpacing=8)

        cmds.text(l="Shape (MEL case name):")
        self.shape_menu = cmds.optionMenu(w=360)
        for k in sorted(SHAPE_DEFS.keys()):
            cmds.menuItem(label=k)

        cmds.separator(h=8, style="in")

        cmds.frameLayout(label="Create Options", collapsable=True, collapse=False, mw=8, mh=6)
        cmds.columnLayout(adj=True, rowSpacing=6)

        # Defaults:
        # - match_orientation ON (rig-friendly)
        # - maintain_offset OFF (not needed if matching orientation)
        # - scaleConstraint OFF (safer)
        self.chk_match_orient = cmds.checkBox(
            label="Match Target Orientation (recommended)",
            v=True,
        )
        self.chk_maintain_offset = cmds.checkBox(
            label="Maintain Offset (mo)",
            v=False,
        )
        self.chk_scale_constraint = cmds.checkBox(
            label="Scale Constraint (use with care)",
            v=False,
        )

        self.txt_suffix = cmds.textFieldGrp(
            label="Controller Suffix",
            text="_CTL",
            cw2=(120, 220),
        )

        cmds.setParent("..")  # columnLayout
        cmds.setParent("..")  # frameLayout

        cmds.separator(h=8, style="in")

        cmds.rowLayout(nc=2, cw2=(240, 120), adjustableColumn=1)
        cmds.text(l="Targets (Refresh from selection):")
        cmds.button(l="Refresh", c=lambda *_: self.refresh_targets())
        cmds.setParent("..")

        self.target_list = cmds.textScrollList(
            numberOfRows=12,
            allowMultiSelection=True,
            height=220,
        )

        cmds.rowLayout(nc=2, cw2=(240, 240))
        cmds.button(
            l="Create + Constrain (ALL in list)",
            h=34,
            c=lambda *_: self.create_for_all(),
        )
        cmds.button(
            l="Create + Constrain (SELECTED)",
            h=34,
            c=lambda *_: self.create_for_selected(),
        )
        cmds.setParent("..")

        cmds.separator(h=8, style="in")
        cmds.text(
            l=(
                "Tips:\n"
                "- If targets snap/rotate when creating: turn ON either\n"
                "  'Match Target Orientation' OR 'Maintain Offset (mo)'.\n"
                "- For joints, scaleConstraint can cause issues depending on rig.\n"
            ),
            align="left",
        )

        cmds.showWindow(self.win)

    def _get_shape_key(self) -> str:
        assert self.shape_menu
        return cmds.optionMenu(self.shape_menu, q=True, v=True)

    def _opt_match_orient(self) -> bool:
        assert self.chk_match_orient
        return bool(cmds.checkBox(self.chk_match_orient, q=True, v=True))

    def _opt_maintain_offset(self) -> bool:
        assert self.chk_maintain_offset
        return bool(cmds.checkBox(self.chk_maintain_offset, q=True, v=True))

    def _opt_scale_constraint(self) -> bool:
        assert self.chk_scale_constraint
        return bool(cmds.checkBox(self.chk_scale_constraint, q=True, v=True))

    def _opt_suffix(self) -> str:
        assert self.txt_suffix
        suffix = cmds.textFieldGrp(self.txt_suffix, q=True, text=True) or "_CTL"
        return suffix

    def refresh_targets(self) -> None:
        assert self.target_list
        sel = cmds.ls(sl=True, long=True) or []
        cmds.textScrollList(self.target_list, e=True, removeAll=True)
        if sel:
            cmds.textScrollList(self.target_list, e=True, append=sel)

    def _get_all_targets_in_list(self) -> List[str]:
        assert self.target_list
        return list(cmds.textScrollList(self.target_list, q=True, allItems=True) or [])

    def _get_selected_targets_in_list(self) -> List[str]:
        assert self.target_list
        return list(cmds.textScrollList(self.target_list, q=True, selectItem=True) or [])

    def create_for_all(self) -> None:
        targets = self._get_all_targets_in_list()
        if not targets:
            cmds.warning("Target list is empty. Press Refresh after selecting objects.")
            return
        self._create_batch(targets)

    def create_for_selected(self) -> None:
        targets = self._get_selected_targets_in_list()
        if not targets:
            cmds.warning("No items selected in list.")
            return
        self._create_batch(targets)

    def _create_batch(self, targets: Sequence[str]) -> None:
        shape_key = self._get_shape_key()
        match_orient = self._opt_match_orient()
        maintain_offset = self._opt_maintain_offset()
        use_scale_constraint = self._opt_scale_constraint()
        suffix = self._opt_suffix()

        created: List[str] = []
        failed: List[Tuple[str, str]] = []

        cmds.undoInfo(openChunk=True)
        try:
            for t in targets:
                try:
                    # build name with suffix (override create_controller default)
                    base = _safe_name_from_target(t)
                    # temporarily adjust suffix by renaming after creation
                    ctrl, grp, cons = create_controller_for_target(
                        target=t,
                        shape_key=shape_key,
                        match_orientation=match_orient,
                        maintain_offset=maintain_offset,
                        use_scale_constraint=use_scale_constraint,
                    )

                    # Rename ctrl to match suffix
                    desired = _unique_name(f"{base}{suffix}")
                    if ctrl != desired:
                        ctrl = cmds.rename(ctrl, desired)
                        # group name and shapes also need consistency
                        # rename group based on ctrl
                        if cmds.objExists(grp):
                            grp = cmds.rename(grp, _unique_name(f"{ctrl}_GRP"))
                        _rename_shape_as_transform_shape(ctrl)

                    created.append(ctrl)

                except Exception as e:
                    failed.append((t, str(e)))
        finally:
            cmds.undoInfo(closeChunk=True)

        if created:
            cmds.select(created, r=True)
            cmds.inViewMessage(
                amg=f"<hl>Created:</hl> {len(created)} controller(s).",
                pos="topCenter",
                fade=True,
            )

        if failed:
            msg = "\n".join([f"- {t}: {err}" for t, err in failed])
            cmds.warning("Some targets failed:\n" + msg)


_UI_INSTANCE: Optional[_UI] = None


def run() -> None:
    """
    Entry point.
    """
    global _UI_INSTANCE
    _UI_INSTANCE = _UI()
    _UI_INSTANCE.build()
