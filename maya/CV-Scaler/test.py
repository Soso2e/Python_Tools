# -*- coding: utf-8 -*-
# Drag & Drop installer for Maya

from maya import cmds, mel
import os, shutil

def main(*_):
    cmds.confirmDialog(title="CV_Scaler Installer", message="ドラッグ＆ドロップ実行 OK。\nファイルをコピーします。", button=["続行"])
    cmds.inViewMessage(amg="<hl>CV_Scaler</hl> installer executed!", pos='topCenter', fade=True)

# D&D 実行時、Mayaは global scope でファイルを eval するので、
# 以下のブロックが main() を呼ばない場合は D&Dが認識されていない。
if __name__ == "__main__":
    main()