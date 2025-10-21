# -*- coding: utf-8 -*-
import os
from maya import mel

SHELF_NAME = "Python"
BUTTON_LABEL = "SimplePicker"
ICON_NAME = "Simple_Picker.png"

def _ensure_shelf_on_startup():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, os.pardir))
    mel_path = os.path.join(root, "shelves", "add_to_shelf.mel").replace("\\", "/")
    mel.eval(f'source "{mel_path}";')

    scripts_path = os.path.join(root, "Scripts").replace("\\", "/")
    icon_abs = os.path.join(root, "icon", ICON_NAME).replace("\\", "/")
    inner_py = (
        "import sys; "
        f"p=r'{scripts_path}'; "
        "sys.path.append(p) if p not in sys.path else None; "
        "from main import show; show()"
    )
    py_cmd = 'python("' + inner_py.replace('"', '\\"') + '")'
    mel.eval(f'sp_addOrReplaceButton("{SHELF_NAME}", "{BUTTON_LABEL}", "{icon_abs}", "{py_cmd}")')

_ensure_shelf_on_startup()