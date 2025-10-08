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

def main():
    # 1) パッケージルート推定（このファイルの場所）
    try:
        pkg_root = os.path.dirname(__file__)
    except NameError:
        # ScriptEditorに貼って実行されたケースは__file__がないので手動選択
        pkg_root = cmds.fileDialog2(dialogStyle=2, fileMode=3, caption="Select CV_Scaler package root")[0]
    shelves_src = os.path.join(pkg_root, "shelves")
    scripts_src = os.path.join(pkg_root, "scripts")
    icons_src   = os.path.join(pkg_root, "icon")  # singular

    # 2) Mayaユーザフォルダ/バージョン
    user_root = cmds.internalVar(userAppDir=True)  # .../Documents/maya/
    ver = cmds.about(v=True)                       # "2025" など
    prefs = os.path.join(user_root, ver, "prefs")
    shelves_dst = os.path.join(prefs, "shelves")
    icons_dst   = os.path.join(prefs, "icons")
    scripts_dst = os.path.join(user_root, ver, "scripts")

    for d in (shelves_dst, icons_dst, scripts_dst):
        _ensure_dir(d)

    # 3) 配置（上書き）
    mel_src = os.path.join(shelves_src, "add_to_shelf.mel")
    if os.path.exists(mel_src):
        shutil.copy2(mel_src, os.path.join(shelves_dst, "add_to_shelf.mel"))
    else:
        cmds.warning("[CV_Scaler] shelves/add_to_shelf.mel が見つかりません。")

    if os.path.isdir(scripts_src):
        _copytree(scripts_src, scripts_dst)
    else:
        cmds.warning("[CV_Scaler] scripts フォルダが見つかりません。")

    if os.path.isdir(icons_src):
        _copytree(icons_src, icons_dst)  # *.png をまとめて
    # icons は任意。無ければスキップ

    # 4) その場で棚を反映（次回起動を待たずにボタンを出す）
    try:
        mel.eval('source "add_to_shelf.mel";')
    except Exception as e:
        cmds.warning(f"[CV_Scaler] add_to_shelf.mel の反映に失敗: {e}")

    _log(u"<hl>CV_Scaler</hl>: インストール完了！シェルフのボタンから起動できます。")
    cmds.confirmDialog(title="CV_Scaler", message="インストール完了！\nShelfにボタンが追加されました。", button=["OK"])

if __name__ == "__main__":
    main()