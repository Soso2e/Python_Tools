# -*- coding: utf-8 -*-
"""
Substanceテクスチャから aiStandardSurface を自動作成・接続するツール
- UIでマテリアル名とテクスチャを指定、またはフォルダ自動検出
- BaseColor / Metalness / Roughness / Normal を接続
- Normal は bump2d（Tangent Space Normals）経由で normalCamera に接続

使い方:
import importlib, my_sp2ai; importlib.reload(my_sp2ai); my_sp2ai.run()

対応:Maya 2020+ / Arnold(MtoA)
"""

from typing import Dict, Optional, Tuple
import os
import re
import maya.cmds as cmds


# 検出用キーワード
DEFAULT_PATTERNS = {
    # 例: *_BaseColor.png, *_Albedo.tif, *_col.png などを想定
    "basecolor": r"(?:base(?:color)?|albedo|diffuse|col)(?!.*(?:normal|rough|metal))",
    # 例: *_Metalness.png, *_Metallic.exr
    "metalness": r"(?:metal(?:lic|ness)?)(?!.*(?:rough|base|normal))",
    # 例: *_Roughness.png
    "roughness": r"(?:rough(?:ness)?)(?!.*(?:metal|base|normal))",
    # 例: *_Normal.png, *_Norm.tif, *_nrm.exr
    "normal": r"(?:normal|norm|nrm)(?!.*(?:rough|metal|base))",
}

# カラースペースの規定
COLORSPACE_RULES = {
    "basecolor": "sRGB",
    "metalness": "Raw",
    "roughness": "Raw",
    "normal": "Raw",
}



# コア機能
def find_maps_in_dir(
    directory: str,
    patterns: Dict[str, str] = DEFAULT_PATTERNS,
) -> Dict[str, Optional[str]]:
    """ディレクトリ内から代表的なテクスチャを自動検出する.

    Args:
        directory: 検索するフォルダパス
        patterns: 各チャンネルの正規表現

    Returns:
        各チャンネル名 -> ファイルパス（見つからなければ None）
    """
    result = {k: None for k in patterns.keys()}
    if not directory or not os.path.isdir(directory):
        return result

    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    # 優先拡張子（上から優先）
    exts = (".tx", ".exr", ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp")

    # Substance標準の「*_BaseColor.png」などを想定しつつ、柔軟にマッチ
    for chan, pat in patterns.items():
        regex = re.compile(pat, re.IGNORECASE)
        candidates = [f for f in files if regex.search(f)]
        # 拡張子優先順位で選ぶ
        def score(name: str) -> int:
            for i, e in enumerate(exts):
                if name.lower().endswith(e):
                    return i
            return len(exts) + 1

        if candidates:
            best = sorted(candidates, key=score)[0]
            result[chan] = os.path.join(directory, best)

    return result


def make_place2d_and_connect(file_node: str) -> str:
    """place2dTexture を作成し、file ノードに一般的な属性接続を行う"""
    p2d = cmds.shadingNode("place2dTexture", asUtility=True)
    # よくある接続セット
    attrs = [
        "coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV",
        "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV",
        "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree",
        "vertexCameraOne", "outUV", "outUvFilterSize"
    ]
    for a in attrs:
        src = f"{p2d}.{a}"
        dst = f"{file_node}.{a}"
        if cmds.objExists(src) and cmds.objExists(dst):
            try:
                cmds.connectAttr(src, dst, f=True)
            except RuntimeError:
                pass
    return p2d


def create_ai_standard_surface(mat_name: str) -> Tuple[str, str]:
    """aiStandardSurface と ShadingGroup を作成して接続"""
    mat = cmds.shadingNode("aiStandardSurface", asShader=True, name=mat_name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{mat_name}SG")
    cmds.connectAttr(f"{mat}.outColor", f"{sg}.surfaceShader", f=True)
    return mat, sg


def make_file_node(texture_path: str, colorspace: str) -> str:
    """file ノードを作成し、テクスチャパスとカラースペースを設定"""
    node = cmds.shadingNode("file", asTexture=True, isColorManaged=True)
    cmds.setAttr(f"{node}.fileTextureName", texture_path, type="string")
    # カラースペース（OCIO使用時でも Maya の file.colorSpace に設定可能）
    if cmds.attributeQuery("colorSpace", n=node, exists=True):
        try:
            cmds.setAttr(f"{node}.colorSpace", colorspace, type="string")
        except RuntimeError:
            pass
    make_place2d_and_connect(node)
    return node


def connect_maps_to_ai(
    mat: str,
    maps: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """指定マップを aiStandardSurface に接続する.

    接続仕様:
      - BaseColor: file.outColor → ai.baseColor
      - Metalness: file.outColorR → ai.metalness
      - Roughness: file.outColorR → ai.specularRoughness
      - Normal: file → bump2d(Tangent Space Normals) → ai.normalCamera
                (file.outAlpha が存在しない場合は outColorR を使用)

    Args:
        mat: aiStandardSurface ノード名
        maps: 各チャンネルのテクスチャパス

    Returns:
        実際に接続した file ノード辞書（チャンネル名→ノード名）
    """
    created_files: Dict[str, Optional[str]] = {k: None for k in maps.keys()}

    # BaseColor
    if maps.get("basecolor"):
        f = make_file_node(maps["basecolor"], COLORSPACE_RULES["basecolor"])
        cmds.connectAttr(f"{f}.outColor", f"{mat}.baseColor", f=True)
        created_files["basecolor"] = f

    # Metalness
    if maps.get("metalness"):
        f = make_file_node(maps["metalness"], COLORSPACE_RULES["metalness"])
        # グレースケール前提なのでRチャンネルを使う
        cmds.connectAttr(f"{f}.outColorR", f"{mat}.metalness", f=True)
        created_files["metalness"] = f

    # Roughness
    if maps.get("roughness"):
        f = make_file_node(maps["roughness"], COLORSPACE_RULES["roughness"])
        cmds.connectAttr(f"{f}.outColorR", f"{mat}.specularRoughness", f=True)
        created_files["roughness"] = f

    # Normal → bump2d( TSN ) → ai.normalCamera
    if maps.get("normal"):
        f = make_file_node(maps["normal"], COLORSPACE_RULES["normal"])
        bump = cmds.shadingNode("bump2d", asUtility=True)
        # 0:Bump、1:Tangent Space Normals
        if cmds.attributeQuery("bumpInterp", n=bump, exists=True):
            cmds.setAttr(f"{bump}.bumpInterp", 1)

        # まず outAlpha を優先、それがダメなら outColorR
        try:
            cmds.connectAttr(f"{f}.outAlpha", f"{bump}.bumpValue", f=True)
        except RuntimeError:
            cmds.connectAttr(f"{f}.outColorR", f"{bump}.bumpValue", f=True)

        cmds.connectAttr(f"{bump}.outNormal", f"{mat}.normalCamera", f=True)
        created_files["normal"] = f

    return created_files


def build_material_with_maps(
    material_name: str,
    maps: Dict[str, Optional[str]],
) -> Tuple[str, str, Dict[str, Optional[str]]]:
    """aiStandardSurface＋SGを作成し、マップを接続する高水準関数.

    Args:
        material_name: マテリアル名
        maps: 各チャンネル名→パス（None可）: basecolor / metalness / roughness / normal

    Returns:
        (mat, sg, created_file_nodes)
    """
    mat, sg = create_ai_standard_surface(material_name)
    file_nodes = connect_maps_to_ai(mat, maps)
    return mat, sg, file_nodes


# ============================================================
# UI
# ============================================================
class SP2AIWindow:
    WINDOW = "SP2AI_Window"

    def __init__(self) -> None:
        self.fields: Dict[str, str] = {}         # textFieldButtonGrp のコントロール名
        self.status_labels: Dict[str, str] = {}  # 右側の ✓/— 表示用 text
        self.example_labels: Dict[str, str] = {} # 下行の「例: ...」表示用 text
        self.material_name_field: str = ""
        self.dir_field: str = ""

    def show(self) -> None:
        if cmds.window(self.WINDOW, exists=True):
            cmds.deleteUI(self.WINDOW)

        win = cmds.window(self.WINDOW, title="SP → aiStandardSurface Builder", sizeable=True)
        form = cmds.formLayout()
        main = cmds.columnLayout(adj=True, rowSpacing=8)

        cmds.text(label="Substance → aiStandardSurface（ここに各マップを選択してください）", align="center", h=24)
        cmds.separator(h=6, style="in")

        # マテリアル名
        cmds.frameLayout(label="マテリアル名", collapsable=False, borderVisible=True, marginHeight=4)
        self.material_name_field = cmds.textField(text="M_SP_Mat", h=24)
        cmds.setParent("..")

        # フォルダ自動検出
        cmds.frameLayout(label="テクスチャフォルダ（自動検出・任意）", collapsable=False, borderVisible=True, marginHeight=4)
        row = cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=(1, "both", 4), columnWidth2=(300, 80))
        self.dir_field = cmds.textField(text="", h=24, ann="このフォルダ内から BaseColor/Metalness/Roughness/Normal を自動検出します")
        cmds.button(label="参照", h=24, c=lambda *_: self._pick_dir())
        cmds.setParent("..")
        cmds.setParent("..")

        # 個別ファイル指定
        cmds.frameLayout(label="個別指定（自動検出より優先）", collapsable=False, borderVisible=True, marginHeight=4)
        for key, title in [
            ("basecolor", "BaseColor（カラー画像・sRGB）"),
            ("metalness", "Metalness（グレースケール・Raw）"),
            ("roughness", "Roughness（グレースケール・Raw）"),
            ("normal", "Normal（Tangent Space・Raw）"),
        ]:
            # 1行目: 入力欄 + 参照 + ステータス
            row = cmds.rowLayout(numberOfColumns=3, adjustableColumn=1,
                                 columnAttach=[(1, "both", 4), (2, "both", 4), (3, "both", 4)],
                                 columnWidth3=(300, 80, 30))
            grp = cmds.textFieldButtonGrp(
                label=title, buttonLabel="参照", text="",
                ann=EXPLANATIONS[key],
                bc=lambda *_ , k=key: self._pick_file(k)
            )
            status = cmds.text(label="—", align="center", w=30, ann="選択/検出の状態（✓=OK, —=未指定）")
            cmds.setParent("..")
            # 2行目: 例表示（薄いガイド）
            ex = cmds.text(label="例: " + EXPLANATIONS[key].split("（例: ")[-1].rstrip("）"), align="left", enable=False)
            cmds.separator(h=6, style="none")

            self.fields[key] = grp
            self.status_labels[key] = status
            self.example_labels[key] = ex
        cmds.setParent("..")

        # 実行
        cmds.separator(h=8, style="none")
        cmds.button(
            label="▶ マテリアル作成", h=36, bgc=(0.25, 0.5, 0.25),
            ann="指定されたテクスチャから aiStandardSurface を自動構築します",
            c=lambda *_: self._build()
        )

        cmds.formLayout(form, e=True,
                        attachForm=[(main, "top", 10), (main, "left", 10), (main, "right", 10), (main, "bottom", 10)])
        cmds.showWindow(win)

    # ---------- UI helpers ----------
    def _pick_dir(self) -> None:
        d = cmds.fileDialog2(dialogStyle=2, fileMode=3)
        if d:
            cmds.textField(self.dir_field, e=True, text=d[0])
            # 検出してUIに反映
            auto = find_maps_in_dir(d[0])
            for k, p in auto.items():
                if p:
                    cmds.textFieldButtonGrp(self.fields[k], e=True, text=p)
            self._update_status()

    def _pick_file(self, key: str) -> None:
        f = cmds.fileDialog2(dialogStyle=2, fileMode=1,
                             fileFilter="Images (*.tx *.exr *.png *.tif *.tiff *.jpg *.jpeg *.bmp)")
        if f:
            cmds.textFieldButtonGrp(self.fields[key], e=True, text=f[0])
            self._update_status()

    def _gather_inputs(self) -> Tuple[str, Dict[str, Optional[str]]]:
        mat_name = cmds.textField(self.material_name_field, q=True, text=True).strip()
        dir_path = cmds.textField(self.dir_field, q=True, text=True).strip()
        auto = find_maps_in_dir(dir_path) if dir_path else {k: None for k in DEFAULT_PATTERNS.keys()}

        maps: Dict[str, Optional[str]] = {}
        for k in DEFAULT_PATTERNS.keys():
            v = cmds.textFieldButtonGrp(self.fields[k], q=True, text=True).strip()
            maps[k] = v or auto.get(k)
        return mat_name, maps

    def _update_status(self) -> None:
        """各フィールドの ✓/— を更新"""
        for k, grp in self.fields.items():
            path = cmds.textFieldButtonGrp(grp, q=True, text=True).strip()
            ok = bool(path and os.path.isfile(path))
            label = "✓" if ok else "—"
            cmds.text(self.status_labels[k], e=True, label=label)

    def _build(self) -> None:
        """作成ボタン押下時の処理."""
        mat_name, maps = self._gather_inputs()

        if not mat_name:
            cmds.warning("マテリアル名を入力してください。")
            return
        if not any(maps.values()):
            cmds.warning("テクスチャが見つかりません。フォルダ指定または個別指定を行ってください。")
            return

        # 実行
        mat, sg, file_nodes = build_material_with_maps(mat_name, maps)

        # 結果表示（ユーザーにどれが接続されたか明示）
        used = [f"{k}: {os.path.basename(p) if p else '-'}" for k, p in maps.items()]
        cmds.inViewMessage(amg=f"<hl>作成完了:</hl> {mat} / {sg}<br>{'<br>'.join(used)}",
                           pos="midCenter", fade=True, alpha=.9)


# ============================================================
# エントリポイント
# ============================================================
def run() -> None:
    """ツールのエントリポイント."""
    SP2AIWindow().show()