# -*- coding: utf-8 -*-
"""コントローラー作成ツール(リグフレンドリー、単一形状：円)。

UIで選択したオブジェクトをリスト表示し、各ターゲットに対してコントローラーを作成します。
形状は円のみで、原点で作成され、クリーンにフリーズされます。

主な機能:
    - 円の法線軸: X/Y/Z選択可能(cmds.circle nrパラメータを制御)
    - 配置: ターゲットごとのオフセットグループは常にターゲットにスナップ(位置+方向)
    - 方向:
        - Match Target: コントローラーはオフセットグループの方向を継承(ジョイントに一致)
        - World: コントローラーの回転をワールド(0,0,0)にキャンセルし、回転のみフリーズを適用
                 これによりNURBSカーブがワールド整列され、ctrlトランスフォームはクリーンに保たれます
    - 階層: オプションでジョイント階層をミラーリング(各子コントローラーGROUPを親コントローラー下に配置)
    - コンストレイント: コントローラーがparentConstraint(+オプションでscaleConstraint)でターゲットを駆動
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import maya.cmds as cmds

# =========================
# 形状定義
# =========================

Point = Tuple[float, float, float]


@dataclass(frozen=True)
class CurveShapeDef:
    """NURBSカーブの形状定義。

    Attributes:
        degree: カーブの次数。
        points: コントロールポイントのタプル。
        knots: ノットベクトルのタプル。
    """
    degree: int
    points: Tuple[Point, ...]
    knots: Tuple[float, ...]


ShapeDef = Union[str, CurveShapeDef]


def _shape_defs() -> Dict[str, ShapeDef]:
    """利用可能な形状定義の辞書を返す。

    Returns:
        形状名をキーとした形状定義の辞書。
    """
    defs: Dict[str, ShapeDef] = {}
    defs["Circle"] = "circle"
    return defs


# =========================
# コアロジック
# =========================

WINDOW_NAME = "soso_ctrl_maker"
UI_TITLE = "Controller Maker"
SHAPE_DEFS: Dict[str, ShapeDef] = _shape_defs()


def _safe_name_from_target(target: str) -> str:
    """ターゲット名から安全な名前を生成する。

    ロングネームから最後の要素を抽出し、コロンをアンダースコアに置換します。

    Args:
        target: Mayaオブジェクトの名前(ロングネーム可)。

    Returns:
        安全な名前文字列。
    """
    base = target.split("|")[-1]
    return base.replace(":", "_")


def _unique_name(base: str) -> str:
    """ユニークな名前を生成する。

    指定された名前が存在しない場合はそのまま返し、存在する場合は
    末尾に数字を付加してユニークな名前を生成します。

    Args:
        base: ベースとなる名前。

    Returns:
        ユニークな名前文字列。
    """
    if not cmds.objExists(base):
        return base
    i = 1
    while cmds.objExists(f"{base}{i}"):
        i += 1
    return f"{base}{i}"


def _create_shape_transform(shape_key: str, name: str, normal_axis: str) -> str:
    """コントローラー形状を原点に作成する。

    配置と方向はオフセットグループで制御します。
    円の法線軸(X/Y/Z)を選択可能です。

    Args:
        shape_key: 形状の種類("Circle"など)。
        name: 作成するトランスフォームの名前。
        normal_axis: 円の法線軸("X", "Y", "Z")。

    Returns:
        作成されたコントローラーのトランスフォーム名。

    Raises:
        RuntimeError: 未知の形状キーまたは作成に失敗した場合。
    """
    shape_def = SHAPE_DEFS.get(shape_key)
    if shape_def is None:
        raise RuntimeError(f"Unknown shape_key: {shape_key}")

    ctrl = ""
    if shape_def == "circle":
        # 円の法線軸を選択可能 (X/Y/Z)
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

    # 原点でクリーンなTRSを保持
    cmds.xform(ctrl, ws=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0))
    return ctrl


def _get_world_matrix(target: str) -> List[float]:
    """ターゲットのワールドマトリックスを取得する。

    Args:
        target: Mayaオブジェクトの名前。

    Returns:
        16要素のワールドマトリックスリスト。
    """
    return [float(v) for v in cmds.xform(target, q=True, ws=True, m=True)]


def _get_world_position(target: str) -> Tuple[float, float, float]:
    """ターゲットの堅牢なワールド位置を取得する。

    Args:
        target: Mayaオブジェクトの名前。

    Returns:
        (x, y, z)のワールド座標タプル。
    """
    t = cmds.xform(target, q=True, ws=True, t=True)
    return (float(t[0]), float(t[1]), float(t[2]))


def _matrix_remove_scale_shear(m: List[float]) -> List[float]:
    """マトリックスからスケールとシアーを除去する。

    正規直交化された回転軸を持つマトリックスを返します。
    移動成分は保持されます。

    Args:
        m: 16要素の4x4マトリックスリスト(行優先)。

    Returns:
        正規化された回転軸と元の移動成分を持つマトリックス。
    """
    # 行優先の軸
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

    # 移動成分を保持
    out[12], out[13], out[14] = m[12], m[13], m[14]
    out[3] = out[7] = out[11] = 0.0
    out[15] = 1.0
    return out


def _freeze_trs(node: str) -> None:
    """トランスフォーム属性をフリーズする。

    移動・回転・スケールをすべてフリーズします。

    Args:
        node: フリーズするノードの名前。
    """
    cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=False)


def _freeze_rot(node: str) -> None:
    """回転のみをフリーズする。

    回転を形状に焼き込み、移動とスケールは変更しません。

    Args:
        node: フリーズするノードの名前。
    """
    cmds.makeIdentity(node, apply=True, t=False, r=True, s=False, n=False)


def _rename_shape_as_transform_shape(ctrl: str) -> None:
    """形状ノードをトランスフォーム名に基づいてリネームする。

    単一の形状の場合は{ctrl}Shape、複数の場合は{ctrl}Shape1, Shape2...とします。

    Args:
        ctrl: トランスフォームノードの名前。
    """
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
    """ターゲットのジョイント階層のルート名を検索する。

    ターゲットから親をたどり、最上位のジョイントノード名を返します。
    ジョイントが見つからない場合はDAG階層の最上位ノード名を返します。

    Args:
        target: 検索開始するターゲットノードの名前。

    Returns:
        ジョイントルートまたは階層ルートの安全な名前。
    """
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
    """ワールドトランスフォームを保持しながら親子付けする。

    子ノードのワールド空間でのトランスフォームを記憶し、
    親子付け後に同じワールド位置を復元します。

    Args:
        child: 子ノードの名前。
        new_parent: 新しい親ノードの名前。
    """
    child_m = cmds.xform(child, q=True, ws=True, m=True)
    cmds.parent(child, new_parent)
    cmds.xform(child, ws=True, m=child_m)


def _make_offset_group(
        ctrl: str,
        target: str,
        match_orientation: bool,
        desired_root_grp_name: str,
        desired_offset_grp_name: str,
        orientation_mode: str,
) -> str:
    """コントローラーグループを作成する。

    - ルートコンテナ(再利用): {jointRoot}_{InputName}_GRP
    - ターゲットごとのオフセットグループ(ユニーク): {target}_{InputName}_CTL_GRP

    リグフレンドリーな主要ルール:
    - ターゲットごとのオフセットグループは最初にワールド空間でターゲットにスナップ(位置+方向)。
    - その後、ワールドを保持しながらルートコンテナ下に親子付け。
    - CTRLはクリーンに保持; Worldモードでは回転をキャンセルし回転のみフリーズ。

    Args:
        ctrl: コントローラートランスフォームの名前。
        target: スナップ先のターゲットノードの名前。
        match_orientation: 互換性のために保持(配置は常にスナップされます)。
        desired_root_grp_name: ルートグループの希望名。
        desired_offset_grp_name: オフセットグループの希望名。
        orientation_mode: "match"または"world"。

    Returns:
        作成されたオフセットグループの名前。
    """
    # ルートコンテナ(再利用)
    if cmds.objExists(desired_root_grp_name):
        root_grp = desired_root_grp_name
    else:
        root_grp = cmds.group(em=True, n=desired_root_grp_name)
        cmds.xform(root_grp, ws=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0))

    # ターゲットごとのオフセットグループ(ユニーク) — 最初は親なしで作成
    offset_grp = desired_offset_grp_name
    if cmds.objExists(offset_grp):
        offset_grp = _unique_name(offset_grp)
    offset_grp = cmds.group(em=True, n=offset_grp)

    # 1) オフセットグループをワールド空間でスナップ(親子付け前)
    # モード間で配置が崩れないように常にスナップします。
    tmp = cmds.parentConstraint(target, offset_grp, mo=False)[0]
    cmds.delete(tmp)

    # 2) ピボットを現在位置に強制
    pos_now = _get_world_position(offset_grp)
    cmds.xform(offset_grp, ws=True, rp=pos_now, sp=pos_now)

    # 3) CTRLをオフセットグループ下に親子付け(ワールド位置は保持しない)
    cmds.parent(ctrl, offset_grp, relative=True)

    # Worldモード: 継承された回転をキャンセルして円をワールド水平に保ち、
    # 回転のみフリーズして形状に焼き込みます。
    if (orientation_mode or "match").lower() == "world":
        # CTRLのワールド回転を0に設定 -> Mayaが親の回転をキャンセルするローカル値を計算
        cmds.xform(ctrl, ws=True, ro=(0.0, 0.0, 0.0))
        _freeze_rot(ctrl)
        # CTRLをクリーンに保持
        cmds.xform(ctrl, os=True, t=(0.0, 0.0, 0.0), ro=(0.0, 0.0, 0.0), s=(1.0, 1.0, 1.0))

    # 4) オフセットグループをルートコンテナ下に親子付け、ワールドを保持
    _parent_preserve_world(offset_grp, root_grp)

    return offset_grp


def _constrain_target_to_ctrl(
        target: str,
        ctrl: str,
        maintain_offset: bool,
        use_scale_constraint: bool,
) -> List[str]:
    """ターゲットにコンストレイントを作成する。

    parentConstraintを作成し、オプションでscaleConstraintも追加します。

    Args:
        target: コンストレイント先のターゲットノード。
        ctrl: コンストレイント元のコントローラー。
        maintain_offset: オフセットを維持するかどうか。
        use_scale_constraint: scaleConstraintを追加するかどうか。

    Returns:
        作成されたコンストレイントノードのリスト。
    """
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
    """ターゲットに対してコントローラーを作成する。

    以下の手順でコントローラーを作成します:
    1. 原点でコントローラー形状を作成(クリーン)
    2. 原点でフリーズ(安全)
    3. ルートコンテナ下にターゲットごとのオフセットグループを作成
    4. ターゲットをコントローラーにコンストレイント

    Args:
        target: コントローラーを作成するターゲットノード。
        shape_key: 形状の種類。
        input_name: 命名に使用する入力名。
        match_orientation: 方向をターゲットに一致させるか。
        maintain_offset: コンストレイントでオフセットを維持するか。
        use_scale_constraint: scaleConstraintを使用するか。
        normal_axis: 円の法線軸("X", "Y", "Z")。
        orientation_mode: "match"または"world"。

    Returns:
        (コントローラー名, グループ名, コンストレイントリスト)のタプル。

    Raises:
        RuntimeError: ターゲットが存在しない場合。
    """
    if not cmds.objExists(target):
        raise RuntimeError(f"Target does not exist: {target}")

    base = _safe_name_from_target(target)
    input_name = input_name.strip() or "CTL"

    # 命名
    desired_ctrl_name = _unique_name(f"{base}_{input_name}_CTL")
    root_name = _find_joint_root_name(target)
    desired_root_grp_name = f"{root_name}_{input_name}_GRP"
    desired_offset_grp_name = _unique_name(f"{base}_{input_name}_CTL_GRP")

    # 1) 原点でコントローラーを作成(クリーン)
    ctrl = _create_shape_transform(shape_key, desired_ctrl_name, normal_axis=normal_axis)

    # 2) 原点でフリーズ(安全)
    _freeze_trs(ctrl)

    # 3) ルートコンテナ下にターゲットごとのオフセットグループを作成
    grp = _make_offset_group(
        ctrl=ctrl,
        target=target,
        match_orientation=match_orientation,
        desired_root_grp_name=desired_root_grp_name,
        desired_offset_grp_name=desired_offset_grp_name,
        orientation_mode=orientation_mode,
    )

    _rename_shape_as_transform_shape(ctrl)

    # 4) ターゲットをコントローラーにコンストレイント
    constraints = _constrain_target_to_ctrl(
        target=target,
        ctrl=ctrl,
        maintain_offset=maintain_offset,
        use_scale_constraint=use_scale_constraint,
    )

    return ctrl, grp, constraints


# =========================
# 階層ミラーヘルパー
# =========================

def _mirror_joint_hierarchy_with_controllers(
        targets: Sequence[str],
        target_to_ctrl: Dict[str, str],
        target_to_grp: Dict[str, str],
) -> None:
    """コントローラーでジョイント階層をミラーリングする。

    各ターゲットのコントローラーGROUPを親ターゲットのコントローラー下に親子付けします。

    ルール:
    - 子コントローラーGROUP(*_CTL_GRP) -> 親CTRL transform下に親子付け
    - 親が作成済みセットに存在する場合のみ適用

    Args:
        targets: ターゲットノードのシーケンス。
        target_to_ctrl: ターゲットからコントローラーへのマッピング。
        target_to_grp: ターゲットからグループへのマッピング。
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

        # 子のワールドトランスフォームを保持しながら親子付け
        try:
            _parent_preserve_world(child_grp, parent_ctrl)
        except Exception:
            pass


# =========================
# UI
# =========================

class _UI:
    """コントローラー作成ツールのUIクラス。

    Mayaウィンドウを作成し、コントローラー作成のためのインターフェースを提供します。
    """

    def __init__(self) -> None:
        """UIインスタンスを初期化する。"""
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
        """UIウィンドウを構築して表示する。"""
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        self.win = cmds.window(WINDOW_NAME, title=UI_TITLE, sizeable=False)
        cmds.columnLayout(adj=True, rowSpacing=8)

        cmds.text(l="Shape:")
        self.shape_menu = cmds.optionMenu(w=360)
        cmds.menuItem(label="Select Shape")

        cmds.separator(h=8, style="in")

        cmds.frameLayout(label="Create Options", collapsable=True, collapse=False, mw=8, mh=6)
        cmds.columnLayout(adj=True, rowSpacing=6)

        cmds.text(l="Shape Normal Axis:")
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
        """現在選択されている形状キーを取得する。

        Returns:
            形状キー文字列。
        """
        return "Circle"

    def _opt_orientation_mode(self) -> str:
        """UIから方向モードを取得する。

        Returns:
            "world"または"match"。
        """
        v = cmds.optionMenu(self.orient_menu, q=True, v=True)
        return "world" if v == "World" else "match"

    def _opt_normal_axis(self) -> str:
        """UIから法線軸を取得する。

        Returns:
            "X", "Y", または"Z"。
        """
        v = cmds.optionMenu(self.normal_menu, q=True, v=True)
        return (v or "Y").strip().upper()

    def _opt_maintain_offset(self) -> bool:
        """オフセット維持オプションを取得する。

        Returns:
            チェックされている場合True。
        """
        return bool(cmds.checkBox(self.chk_maintain_offset, q=True, v=True))

    def _opt_scale_constraint(self) -> bool:
        """スケールコンストレイントオプションを取得する。

        Returns:
            チェックされている場合True。
        """
        return bool(cmds.checkBox(self.chk_scale_constraint, q=True, v=True))

    def _opt_build_hierarchy(self) -> bool:
        """階層構築オプションを取得する。

        Returns:
            チェックされている場合True。
        """
        return bool(cmds.checkBox(self.chk_build_hierarchy, q=True, v=True))

    def _opt_input_name(self) -> str:
        """入力名を取得する。

        Returns:
            入力名文字列(空の場合は"CTL")。
        """
        name = cmds.textFieldGrp(self.txt_input_name, q=True, text=True) or "CTL"
        return name.strip() or "CTL"

    def refresh_targets(self) -> None:
        """現在の選択からターゲットリストを更新する。"""
        sel = cmds.ls(sl=True, long=True) or []
        cmds.textScrollList(self.target_list, e=True, removeAll=True)
        if sel:
            cmds.textScrollList(self.target_list, e=True, append=sel)

    def _get_all_targets_in_list(self) -> List[str]:
        """リスト内のすべてのターゲットを取得する。

        Returns:
            ターゲット名のリスト。
        """
        return list(cmds.textScrollList(self.target_list, q=True, allItems=True) or [])

    def _get_selected_targets_in_list(self) -> List[str]:
        """リスト内で選択されているターゲットを取得する。

        Returns:
            選択されているターゲット名のリスト。
        """
        return list(cmds.textScrollList(self.target_list, q=True, selectItem=True) or [])

    def create_for_all(self) -> None:
        """リスト内のすべてのターゲットに対してコントローラーを作成する。"""
        targets = self._get_all_targets_in_list()
        if not targets:
            cmds.warning("List is empty.")
            return
        self._create_batch(targets)

    def create_for_selected(self) -> None:
        """リスト内で選択されているターゲットに対してコントローラーを作成する。"""
        targets = self._get_selected_targets_in_list()
        if not targets:
            cmds.warning("No selection in list.")
            return
        self._create_batch(targets)

    def _create_batch(self, targets: Sequence[str]) -> None:
        """複数のターゲットに対してバッチでコントローラーを作成する。

        Args:
            targets: コントローラーを作成するターゲットのシーケンス。
        """
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
            # 1) コントローラーを作成(独立)
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

            # 2) 階層をミラーリング(グループを親コントローラー下に配置)
            if build_hierarchy and target_to_ctrl:
                _mirror_joint_hierarchy_with_controllers(targets, target_to_ctrl, target_to_grp)

        finally:
            cmds.undoInfo(closeChunk=True)

        if created:
            cmds.select(created, r=True)
            cmds.inViewMessage(amg=f"<hl>Created:</hl> {len(created)} controllers.", pos="topCenter", fade=True)


_UI_INSTANCE: Optional[_UI] = None


def run() -> None:
    """UIを実行する。

    新しいUIインスタンスを作成して表示します。
    """
    global _UI_INSTANCE
    _UI_INSTANCE = _UI()
    _UI_INSTANCE.build()


if __name__ == "__main__":
    run()