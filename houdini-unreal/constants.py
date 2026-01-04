from pathlib import Path


import_fbx_file_path = r"D:\internship\unorganized_data\houdini_sample\npc_hnd_emo_mid_talk5_b.fbx"
fbx_dest_path = r"/Game/py_fbxs/"


target_sequence_name = "Scene"
level_sequence_dest_path = "/Game/py_sequences/"


SCRIPTS_PATH = Path(__file__).parent
json_name = SCRIPTS_PATH/"args.json"


skeleton_path= "/Game/Characters/Sotai/Meshes/SK_Sotai.SK_Sotai"