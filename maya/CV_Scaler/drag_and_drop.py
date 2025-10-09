# -*- coding: utf-8 -*-
# Drag & Drop installer:
# - Create:   <Documents>/maya/<ver>/scripts/CV_Scaler/
# - Copy:     <dropped>/scripts  -> .../CV_Scaler/scripts (丸ごと)
# - Copy opt: <dropped>/icon     -> .../CV_Scaler/icon   (あれば)
# - Path:     sys.path に scripts を追加（必要なら）
# - IconPath: XBMLANGPATH に .../CV_Scaler/icon を追加（あれば）
# - Shelves:  変更しない（存在すれば rehash + source のみ）

from __future__ import annotations
import os, sys, shutil
from maya import cmds, mel

def _log(msg):
    try:
        cmds.inViewMessage(amg=msg, pos='midCenter', fade=True)
    except Exception:
        pass

def _ensure_dir(p: str):
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

def _copytree(src: str, dst: str):
    if not os.path.exists(src):
        return
    _ensure_dir(dst)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out_dir = dst if rel in ('.', '') else os.path.join(dst, rel)
        _ensure_dir(out_dir)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(out_dir, f))

def _touch(path: str, content: str = ""):
    _ensure_dir(os.path.dirname(path))
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fw:
            fw.write(content)

def _append_env_path(var_name: str, new_path: str):
    # Maya は ; 区切り（Windows）/ : 区切り（mac/Linux）どちらも可
    sep = ";" if os.name == "nt" else ":"
    cur = os.environ.get(var_name, "")
    paths = [p for p in cur.split(sep) if p]
    if new_path not in paths:
        os.environ[var_name] = (cur + (sep if cur else "") + new_path)

def onMayaDroppedPythonFile(filePath):
    try:
        pkg_root = os.path.dirname(filePath) if filePath else os.path.dirname(__file__)
        main(pkg_root)
    except Exception as e:
        try:
            cmds.warning("[CV_Scaler] D&D install failed: {}".format(e))
        except Exception:
            pass

def main(dropped_root: str):
    # --- Maya user dirs
    user_root = cmds.internalVar(userAppDir=True)   # .../Documents/maya/
    ver = cmds.about(v=True)
    prefs_dir   = os.path.join(user_root, ver, "prefs")
    shelves_dir = os.path.join(prefs_dir, "shelves")
    scripts_dir = os.path.join(user_root, ver, "scripts")

    for d in (shelves_dir, scripts_dir):
        _ensure_dir(d)

    # --- Destination package layout
    dst_pkg_root    = os.path.join(scripts_dir, "CV_Scaler")
    dst_pkg_scripts = os.path.join(dst_pkg_root, "scripts")
    dst_pkg_icon    = os.path.join(dst_pkg_root, "icon")

    _ensure_dir(dst_pkg_scripts)
    _touch(os.path.join(dst_pkg_root, "__init__.py"))
    _touch(os.path.join(dst_pkg_scripts, "__init__.py"))

    # --- Copy scripts (丸ごと)
    src_scripts = os.path.join(dropped_root, "scripts")
    if os.path.isdir(src_scripts):
        _copytree(src_scripts, dst_pkg_scripts)
    else:
        # フォルダが無い場合、ルート直下の cv_scaler_main.py だけでも拾う
        root_cv = os.path.join(dropped_root, "cv_scaler_main.py")
        if os.path.isfile(root_cv):
            shutil.copy2(root_cv, os.path.join(dst_pkg_scripts, "cv_scaler_main.py"))

    # --- Copy icon (あれば)
    src_icon = os.path.join(dropped_root, "icon")
    if os.path.isdir(src_icon):
        _copytree(src_icon, dst_pkg_icon)
        # アイコン探索パスに追加（現在セッション有効）
        _append_env_path("XBMLANGPATH", dst_pkg_icon)

    # --- Python パス（保険で追加）
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)

    # --- Shelves は変更しない（存在すれば rehash + source のみ）
    #     例: add_to_shelf.mel に既に正しいコマンドが入っている前提
    mel_path = os.path.join(shelves_dir, "add_to_shelf.mel")
    try:
        mel.eval("rehash;")
        if os.path.exists(mel_path):
            mel.eval('source "{}";'.format(mel_path.replace("\\", "/")))
    except Exception as e:
        cmds.warning(f"[CV_Scaler] shelf refresh failed: {e}")

    _log(u"<hl>CV_Scaler</hl>: インストール完了！\n"
         u"・scripts/CV_Scaler にコピー\n"
         u"・icon があればパス追加（XBMLANGPATH）\n"
         u"・Shelves は未変更（再読込のみ）")

    try:
        cmds.confirmDialog(
            title="CV_Scaler",
            message=(
                "インストール完了！\n\n"
                "• コピー先:\n"
                f"{dst_pkg_root}\n"
                "• アイコン: ある場合は XBMLANGPATH に追加済み\n"
                "• Shelves: 変更なし（再読込のみ）"
            ),
            button=["OK"]
        )
    except Exception:
        pass

if __name__ == "__main__":
    main(os.path.dirname(__file__))
