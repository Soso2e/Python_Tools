import hou
import re, sys, math
from pathlib import Path
import importlib, remote_ctrl


# 引数
root = hou.node("/")
all_nodes = root.allSubChildren()
pj_path = Path(hou.hipFile.path()).parent
scene_name = Path(hou.hipFile.basename()).stem

target_name = "Scene"

# fbx, output の入るノード検索
fbx_export_node = []
for node in all_nodes:
    ntype = node.type().name().lower()
    if "fbx" in ntype and "output" in ntype:
        fbx_export_node.append(node)

# Scene番号取得
def get_sequence_name(name: str, target_name: str) -> str:
    """命名規則の統一のための接頭辞の取得。シーンの番号を取得し "name000" で返す。

    Args:
        name ( str ) : 取得したシーンの名前 \n
            Scene000_aaa_bbb.hip
        target_name ( str ) : シーンの中から取り出したい接頭辞の名前 \n
            e.g.) Scene

    Rrturn:
        取得したシーン名＋ナンバリング : str

    Example:
        >>> get_sequence_name(scene120_fightanim_v001.hip, scene)
        scene120

    """

    padding = 3
    name_got = re.search(fr'({target_name})(\d+)', name, flags=re.IGNORECASE)

    if not name_got:
        print(f"{target_name}がありません。 {target_name}{'0'.zfill(padding)} に設定します。")
        return f"{target_name}{'0'.zfill(padding)}"

    base, num = name_got.group(1).lower(), name_got.group(2)
    print(f"UEシーケンス名 : LS_{base}{num.zfill(padding)}")

    return f"{base}{num.zfill(padding)}"

mainNom_name = get_sequence_name(scene_name, target_name)

# 出力先パス入れる　書き出す
start_frame, end_frame = hou.playbar.playbackRange()
start_frame = math.floor(start_frame)
end_frame = math.floor(end_frame)

parent_dir = pj_path.parents[3]  # go to "cg_data/"
fbx_export_path = (rf"{parent_dir}/animation/common/human/sotai/export_fbx/")

def set_arg(export_path: str, export_fbx_names: list) -> list:
    """Unrealに送信する引数をリスト化して保存する。

    Args:
        export_fbx_names ( list ) : 書き出したFBXのリスト \n
            e.g.) [scene001_bob, scene001_mike]
        export_path ( str ) : 書き出した先のパス \n
            e.g.) aaa/bbb/ccc/

    Return:
        引数を連ねた一つのリスト : list

    Example:
        >>> save_arg( [aaa, bbb], "000" )
        [ 000, aaa, bbb]

    """

    print(f"エクスポート先 : {export_path}")
    print(f"FBXのリスト : {export_fbx_names}")

    global args
    args = export_path + " " + " ".join(export_fbx_names)
    print(f"送信する引数 : {args}")
    return args

exported_list = []
if fbx_export_node:
    for rop in fbx_export_node:
        print(f"{rop}をエクスポートしています。現在の表示されているスタートフレーム  {start_frame}  、エンドフレーム  {end_frame}  を参照します。")
        rop.parm("outputfilepath").set(f"{fbx_export_path}{mainNom_name}_CHR_{rop.name()}.fbx")
        rop.parm("execute").pressButton()
        exported_list.append(f"{mainNom_name}_CHR_{rop.name()}.fbx")

    send_arg = set_arg(fbx_export_path, exported_list)
    importlib.reload(remote_ctrl)
    remote_ctrl.run_and_send_arguments(send_arg)

else:
    print(f"実行できませんでした。対応するノードがありません。")
