import unreal, re, importlib
from pathlib import Path

# py
import fbx_import, constants

importlib.reload(constants)
importlib.reload(fbx_import)

#
binding_name_list = []

# ----------------------[レベルシーケンスの名前を設定]------------------------

# 特定の名前(picname)を探して、数字を取得し接頭辞LS_をつける。
def pic_name_for_sequence(name: str, picname: str, pad: int = 3) -> str:
    """特定の名前(picname)を探して、数字を取得しシーケンス名にして返却

    Args:
        name ( str ) : 取得される側の名前 \n
            e.g.) hogehoge_Scene1_hoge.fbx

        picname ( str ) : 取得する名前。(picname)の後に続く数字を取得 \n
            e.g.) Scene

        pad ( int ) : 数字の桁数、デフォルトは3桁 \n
            e.g.) 5  ->  00001

    Return:
        シーケンス名になるテキスト : string

    Example:
        >>>pic_name_for_sequence(name: 12345_v12, picname: v, pad: int = 3)
        LS_v012

    """

    pick = re.search(fr'({picname})(\d+)', name, flags=re.IGNORECASE)
    if not pick:
        return f"LS_{picname}{'0'.zfill(pad)}"
    base_name, number = pick.group(1).lower(), pick.group(2)
    print(f"シーケンス名 : LS_{base_name}{number.zfill(pad)}")

    return f"LS_{base_name}{number.zfill(pad)}"

# ----------------------[レベルシーケンス作成]------------------------

# レベルシーケンスを作成
def make_sequence(sequence_path: str, sequence_stem: str) -> None:
    """概要

    対応する名前のシーケンスを作成します。

    Args:
        sequence_path ( str ) : シーケンスを作成するパス /Game~ \n
            e.g.) /Gmae/Sequences

        sequence_stem ( str ) : シーケンスを作成する名前 \n
            e.g.) LS_000

    return:
        名前をもとにシーケンスを作成 : None

    """

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.LevelSequenceFactoryNew()

    if unreal.EditorAssetLibrary.does_asset_exist(f"{sequence_path}{sequence_stem}"):
        # 存在している場合、バインディングを取得
        get_match_binding(sequence_path, sequence_stem)
        print(f"{sequence_path}{sequence_stem}は存在しているためシーケンスは作成されませんでした。")
    else:
        level_sequence = unreal.AssetTools.create_asset(
            asset_tools,
            asset_name=sequence_stem,
            package_path=sequence_path,
            asset_class=unreal.LevelSequence,
            factory=unreal.LevelSequenceFactoryNew()
        )
        print(f"{sequence_path}{sequence_stem}を作成しました。")

def get_match_binding(sequence_path: str, sequence_stem: str) -> list:
    global binding_name_list
    binding_name_list = []
    current_sequence = unreal.load_asset(f"{sequence_path}{sequence_stem}")
    binding_exist_list = unreal.MovieSceneSequence.get_bindings(current_sequence)
    for binding_list in binding_exist_list:
        add_binding_list = binding_list.get_display_name()
        binding_name_list.append(add_binding_list)
    return binding_name_list

# ----------------------[対応skeletal_meshの取得]------------------------

def get_skeletal_mesh_path(animFBX_stem: str) -> str:
    """名前にあったスケルタルメッシュを検索

    Args:
        animFBX_stem ( str ) : 取り入れてきたアニメーションのFBXの名前のみ。拡張子なし。 \n
            e.g.) sample

    return:
        名前一致のスケルタルメッシュのパス : str

    """

    # stemの末尾を検索
    chara_stem = animFBX_stem.split("_")[-1]
    print(f"スケルタルメッシュを取得しています。 : {chara_stem}")

    # skeletal_meshだけまとめて取得
    asset_registory = unreal.AssetRegistryHelpers.get_asset_registry()

    asset_filter = unreal.ARFilter(
            class_names=["SkeletalMesh"],
            package_paths=[],
            recursive_paths= True
        )
    get_all_sleketal_mesh = asset_registory.get_assets(asset_filter)

    # Chara_nameだけにしよう
    for skeletal_mesh in get_all_sleketal_mesh:
        name = Path(skeletal_mesh.get_full_name()).stem
        if chara_stem in name:
            match_name = str(skeletal_mesh.package_name)
            print(f"取得したskeletal_mesh : {match_name}")
    return match_name

# ----------------------[メッシュ、アニメーションをシーケンスへ追加]------------------------

def assign_to_sequence(sequence_path: str, sequence_stem: str, current_fbx_name: str) -> None:
    """指定したシーケンスに、メッシュとアニメーションを導入する

    Args:
        sequence_path ( str ) : シーケンスが入っているパス \n
            e.g.) Game/Sequences/

        sequence_stem ( str ) : シーケンスの名前 \n
            e.g.) LS_000

        current_fbx_name ( str ) : 扱うFBXアニメーションのファイル名 \n
            e.g.) sample.fbx

    Return:
        シーケンスにFBXが入った状態になる。: None

    Examples:
        >>> assign_to_sequence(
                    Game/Sequences/,
                    LS_001,
                    001_animation.fbx
                ):

    """

    animFBX_stem = Path(current_fbx_name).stem
    mesh_file = get_skeletal_mesh_path(animFBX_stem)
    current_sequence = unreal.load_asset(f"{sequence_path}{sequence_stem}")
    skeletal_mesh = unreal.load_asset(mesh_file)
    animation_asset = unreal.load_asset(f"{constants.fbx_dest_path}{animFBX_stem}")

    # 先ほど作成したシーケンスを開く。
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(current_sequence)

    # すでに同じものが存在した場合、アニメーションを差し替え
    if animFBX_stem in binding_name_list:
        print(f"{animFBX_stem}は既にシーケンス内に存在します。")

        binding_exist_list = unreal.MovieSceneSequence.get_bindings(current_sequence)

        for binding in binding_exist_list:
            binding_display_name = binding.get_display_name()

            # FBX名と同じもの
            if binding_display_name == animFBX_stem:
                current_binding = binding

        delete_animation_in_binding(current_binding)
        add_animation_track(current_binding, animation_asset, False)

        world = unreal.EditorLevelLibrary.get_editor_world()
        add_camera_track(current_sequence)
        # unreal.SequencerTools.import_level_sequence_fbx(world, current_sequence, [add_camera_track(current_sequence)], import_camera_FBX_options(), r"D:\internship\cg_data\cut\cinema\001\scene\cam1_scene0001.fbx")

    # 存在しない場合、新規作成
    else:
        binding = unreal.MovieSceneSequenceExtensions.add_spawnable_from_class(current_sequence, unreal.SkeletalMeshActor)

        binding.set_display_name(animFBX_stem)
        template_actor = binding.get_object_template()
        template_comp = template_actor.get_editor_property("skeletal_mesh_component")
        template_comp.set_editor_property("skeletal_mesh", skeletal_mesh)
        print(f"{mesh_file} を {sequence_path}{sequence_stem} にインポートしました。")

        # Transトラック追加
        trans_track = binding.add_track(unreal.MovieScene3DTransformTrack)
        trans_sec = trans_track.add_section()
        trans_sec.set_range_seconds(0.0, animation_asset.get_editor_property('sequence_length'))

        # Animトラック追加
        add_animation_track(binding, animation_asset, True)

        print(f"{constants.fbx_dest_path}{current_fbx_name} を {Path(mesh_file).stem} にアサインしました。")

# ------------------------------------------------------------------------------------------

def delete_animation_in_binding(binding) -> None:
    """指定されたバインディングから、アニメーショントラックを削除します。
    Args:
        binding ( binding ) : 削除対象のバインディング (unreal.SequencerBindingProxy)
    Return:
        バインディングからすべてのアニメーショントラックが削除される : None
    """

    if not binding:
        unreal.log_warning("無効なバインディングが指定されました。")
        return

    # すべてのアニメーショントラックを取得
    tracks_to_remove = []
    for track in binding.get_tracks():
        if isinstance(track, unreal.MovieSceneSkeletalAnimationTrack):
            tracks_to_remove.append(track)

    if not tracks_to_remove:
        unreal.log_warning(f"バインディング '{binding.get_display_name()}' にアニメーショントラックはありません。")
        return

    for track in tracks_to_remove:
        binding.remove_track(track)

    print(f"バインディング '{binding.get_display_name()}' のアニメーショントラックの削除が完了しました。")
# ------------------------------------------------------------------------------------------

def add_animation_track(binding: object, animation_asset: any, new: bool = True) -> None:
    """バインディングにアニメーショントラックを追加。
    Args:
        binding ( binding ) : 追加先バインディング

        animation_asset ( load_asset ) : 追加するアニメーションファイル

        new ( bool ) : 新しく作成する場合

    Return:
        バインディングにアニメーションが追加される。 : None
    """

    anim_track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    anim_sec = anim_track.add_section()

    params = anim_sec.get_editor_property("params")
    anim_sec.set_range_seconds(0.0, animation_asset.get_editor_property('sequence_length'))
    params.animation = animation_asset
    anim_sec.set_editor_property('Params', params)
    if not new:
        print(f"アニメーションを差し替えました。")