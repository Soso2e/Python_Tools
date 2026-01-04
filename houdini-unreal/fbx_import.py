import unreal,  os, importlib

# py
import constants
importlib.reload(constants)


def importFBX(fbx_path: str, fbx_dest_path: str, skeleton_path: str) -> None:
    """fbx_pathのFBXをfbx_dest_pathにインポートします。


    Args:
        fbx_path ( str ) : インポートするFBXの絶対パス + 拡張子。
            e.g.) D:/hoge/hoge/


        fbx_dest_path ( str ) : Unreal上の、目的地Path。
            e.g.) /Game~


        skeleton_path ( str ) : インポート時に紐づけるスケルトンのゲーム内パス。
            e.g.) /Game~


    return:
        FBXがアセットライブラリにインポートされる。 : None


    """




    print(f"FBXをインポートしています : {fbx_path}")
    fbx_name = os.path.splitext(os.path.basename(fbx_path))[0]
    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = fbx_dest_path
    task.options = unreal.FbxImportUI()
    task.options.import_animations = True
    task.options.import_as_skeletal = True
    task.automated = True
    task.save = True
    task.options.skeleton = unreal.load_asset(skeleton_path)


    task.options.mesh_type_to_import = unreal.FBXImportType.FBXIT_ANIMATION


    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    print(f"インポートしました : {fbx_name}")
    print(f"スケルトン : {skeleton_path}")


# test run
# importFBX(r"D:\internship\unorganized_data\houdini_sample\npc_hnd_emo_mid_talk5_b.fbx", "/Game/Characters/Sotai/Meshes/SK_Sotai.SK_Sotai", r"/Game/py_fbxs/")