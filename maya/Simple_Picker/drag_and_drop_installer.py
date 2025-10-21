# -*- coding: utf-8 -*-
"""
汎用 Maya Drag & Drop インストーラ
--------------------------------
任意ツールフォルダ内の drag_and_drop_install.py として配置し、
Maya のビューポートにドラッグ＆ドロップすることでツールを自動インストールします。

構造:
MyTool/
├─ icon/
│   └─ MyTool.png
├─ scripts/
│   ├─ main.py
│   └─ __init__.py
├─ shelves/
│   └─ add_to_shelf.mel
└─ drag_and_drop_install.py
"""

from __future__ import annotations
import os
import sys
import shutil
from maya import cmds, mel

# =========================================================
# Entry point
# =========================================================
def onMayaDroppedPythonFile(*_):
    try:
        install_tool()
        _inview("<hl>Install complete.</hl>")
    except Exception as e:
        cmds.warning(f"[Installer] Failed: {e}")
        _inview(f"<hl>Install failed:</hl> {e}")


# =========================================================
# Core Install Logic
# =========================================================
def install_tool() -> None:
    # このスクリプトの場所
    this_py = os.path.abspath(__file__)
    tool_root = os.path.dirname(this_py)
    tool_name = os.path.basename(tool_root)

    # パス構成
    src_scripts = os.path.join(tool_root, "scripts")
    src_icons = os.path.join(tool_root, "icon")
    src_mel = os.path.join(tool_root, "shelves", "add_to_shelf.mel")

    # チェック
    if not os.path.isfile(os.path.join(src_scripts, "main.py")):
        raise FileNotFoundError(f"main.py が存在しません: {src_scripts}")
    if not os.path.isfile(src_mel):
        raise FileNotFoundError(f"add_to_shelf.mel が存在しません: {src_mel}")

    # コピー先
    user_scripts_root = cmds.internalVar(userScriptDir=True)
    dst_root = os.path.join(user_scripts_root, tool_name)
    dst_scripts = os.path.join(dst_root, "scripts")
    dst_icon = os.path.join(dst_root, "icon")

    _copy_subdir(src_scripts, dst_scripts)
    _copy_subdir(src_icons, dst_icon)

    # 環境パス
    if dst_scripts not in sys.path:
        sys.path.append(dst_scripts)
    if os.path.isdir(dst_icon):
        os.environ["XBMLANGPATH"] = os.environ.get("XBMLANGPATH", "") + (os.pathsep + dst_icon)

    # .mod 自動生成
    _ensure_mod_file(tool_name, dst_root)

    # シェルフ登録
    mel_path = src_mel.replace("\\", "/")
    mel.eval(f'source "{mel_path}";')
    norm_scripts = dst_scripts.replace("\\", "/")
    py_cmd = (
        "import sys, importlib; "
        f"p=r'{norm_scripts}'; "
        "sys.path.append(p) if p not in sys.path else None; "
        "import main; importlib.reload(main); main.run()"
    )
    _call_add_to_shelf("Python", tool_name, py_cmd, _find_icon(dst_icon))

    cmds.confirmDialog(
        title=tool_name,
        message=f"{tool_name} をインストールしました。\n\n{dst_root}\n\nPython > {tool_name} から起動できます。",
        button=["OK"]
    )


# =========================================================
# Helper Functions
# =========================================================
def _copy_subdir(src: str, dst: str):
    if not os.path.isdir(src):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _find_icon(icon_dir: str) -> str:
    if not os.path.isdir(icon_dir):
        return "pythonFamily.png"
    for f in os.listdir(icon_dir):
        if f.lower().endswith(".png"):
            return os.path.join(icon_dir, f).replace("\\", "/")
    return "pythonFamily.png"


def _mel_escape(s: str) -> str:
    return s.replace("\\", "/").replace('"', '\\"')


def _call_add_to_shelf(shelf_name: str, label: str, py_cmd: str, icon: str):
    a = _mel_escape(shelf_name)
    b = _mel_escape(label)
    c = _mel_escape(py_cmd)
    d = _mel_escape(icon)
    mel.eval(f'add_to_shelf("{a}", "{b}", "{c}", "{d}");')


def _inview(msg: str):
    try:
        cmds.inViewMessage(amg=msg, pos="midCenter", fade=True)
    except Exception:
        pass


def _ensure_mod_file(tool_name: str, dst_root: str):
    """~/Documents/maya/modules/<TOOL_NAME>.mod を生成"""
    maya_app_dir = os.environ.get("MAYA_APP_DIR") or os.path.join(os.path.expanduser("~"), "Documents", "maya")
    modules_dir = os.path.join(maya_app_dir, "modules")
    os.makedirs(modules_dir, exist_ok=True)
    mod_path = os.path.join(modules_dir, f"{tool_name}.mod")

    # Try to get version from scripts/__init__.py if available
    version = "1.0"
    scripts_init = os.path.join(dst_root, 'scripts', '__init__.py')
    if os.path.isfile(scripts_init):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"{tool_name}_scripts_init", scripts_init)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            version = getattr(mod, "version", version)
        except Exception:
            version = "1.0"

    root = dst_root.replace("\\", "/")

    with open(mod_path, "w", encoding="utf-8") as f:
        f.write(
            f"+ {tool_name} {version} {root}\n"
            "requires maya any\n"
            "PYTHONPATH +:= scripts\n"
            "MAYA_SCRIPT_PATH +:= scripts\n"
            "XBMLANGPATH +:= icon\n"
        )
    print(f"[Installer] .mod file generated: {mod_path}")