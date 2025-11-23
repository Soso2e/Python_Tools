import importlib, sys

import fbx_import, constants, make_sequence, remote_ctrl
importlib.reload(fbx_import)
importlib.reload(constants)
importlib.reload(make_sequence)
importlib.reload(remote_ctrl)

imoprted_path = sys.argv[1]  # HoudiniからエクスポートしたPath
imported_fbxs = sys.argv[2:]  # HoudiniからエクスポートしたFBXのリスト


print(imoprted_path, imported_fbxs)
# FBXのインポート
for name in imported_fbxs:
    fbx_import.importFBX(
            f"{imoprted_path}{name}",
            constants.fbx_dest_path,
            constants.skeleton_path
        )


for name in imported_fbxs:
    print(f"--------------------------adding : {name}----------------------------")
    # 名前取得
    sequence_stem = make_sequence.pic_name_for_sequence(name, constants.target_sequence_name,)


    # シーケンスの作成
    make_sequence.make_sequence(constants.level_sequence_dest_path, sequence_stem)


    # SKM(constants.skeletal_mesh_path) ＆ Anim(constants.import_fbx_file_path)をシーケンスに入れる。
    make_sequence.assign_to_sequence(constants.level_sequence_dest_path, sequence_stem, name)
    print(f"--------------------------done : {name}----------------------------")