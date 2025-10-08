# -*- coding: utf-8 -*-
# Drag & Drop into Maya viewport to install CV_Scaler shelf & scripts.

from __future__ import annotations
import os, sys, shutil
from maya import cmds, mel

def _log(msg): cmds.inViewMessage(amg=msg, pos='midCenter', fade=True)

def _ensure_dir(p):
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

def _copytree(src, dst):
    # Python3.8-: dirs_exist_okが無い環境向けフォールバック
    if not os.path.exists(src):
        return
    _ensure_dir(dst)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out_dir = dst if rel == '.' else os.path.join(dst, rel)
        _ensure_dir(out_dir)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(out_dir, f)
            shutil.copy2(s, d)

def onMayaDroppedPythonFile(filePath):
    """Maya viewport Drag & Drop entry point.
    Maya calls this when a .py is dropped onto the viewport.
    """
    try:
        # Prefer the dropped file's directory as the package root
        pkg_root = os.path.dirname(filePath) if filePath else None
        main(pkg_root)
    except Exception as e:
        try:
            cmds.warning("[CV_Scaler] D&D install failed: {}".format(e))
        except Exception:
            pass

def main(pkg_root: str | None = None):
    # 1) パッケージルート推定（このファイルの場所 or ドロップ元）
    if not pkg_root:
        pkg_root = os.path.dirname(__file__)

    # 2) ソースとコピー先の設定
    shelves_src = os.path.join(pkg_root, "shelves")
    scripts_src = os.path.join(pkg_root, "scripts")
    icons_src   = os.path.join(pkg_root, "icon")

    user_root = cmds.internalVar(userAppDir=True)
    ver = cmds.about(v=True)
    prefs = os.path.join(user_root, ver, "prefs")
    shelves_dst = os.path.join(prefs, "shelves")
    icons_dst   = os.path.join(prefs, "icons")
    scripts_dst = os.path.join(user_root, ver, "scripts")

    for d in (shelves_dst, icons_dst, scripts_dst):
        _ensure_dir(d)

    # 3) ファイルのコピー
    mel_src = os.path.join(shelves_src, "add_to_shelf.mel")
    if os.path.exists(mel_src):
        shutil.copy2(mel_src, os.path.join(shelves_dst, "add_to_shelf.mel"))

    if os.path.isdir(scripts_src):
        _copytree(scripts_src, scripts_dst)

    if os.path.isdir(icons_src):
        _copytree(icons_src, icons_dst)

    # 4) 反映
    try:
        mel.eval('source "add_to_shelf.mel";')
    except Exception as e:
        cmds.warning(f"[CV_Scaler] add_to_shelf.mel の反映に失敗: {e}")

    _log(u"<hl>CV_Scaler</hl>: インストール完了！シェルフのボタンから起動できます。")
    cmds.confirmDialog(title="CV_Scaler", message="インストール完了！\nShelfにボタンが追加されました。", button=["OK"])

if __name__ == "__main__":
    main(None)