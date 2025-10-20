# -*- coding: utf-8 -*-
from maya import cmds

def _ensure_menu():
    # 上部メニューバーに Tools> ControllerPicker を作る例
    if cmds.menu("controllerPickerMenu", exists=True):
        try: cmds.deleteUI("controllerPickerMenu")
        except Exception: pass

    main_win = cmds.mel.eval('$tmp=$gMainWindow')  # Mayaのメインウィンドウ
    m = cmds.menu("controllerPickerMenu", label="ControllerPicker", parent=main_win, tearOff=True)

    cmds.menuItem(label="Open UI", parent=m, command=lambda *_: _open_ui())
    cmds.menuItem(divider=True, parent=m)
    cmds.menuItem(label="About...", parent=m, command=lambda *_: cmds.confirmDialog(t="ControllerPicker",
                                                                                   m="ControllerPicker 1.0"))

def _ensure_shelf():
    # 既存の好きなシェルフ名にボタン追加（なければ 'Custom' を使用）
    shelf = cmds.mel.eval('global string $gShelfTopLevel; $gShelfTopLevel')
    shelves = cmds.shelfTabLayout(shelf, q=True, ca=True) or []
    target_shelf = "Custom" if "Custom" in shelves else (shelves[0] if shelves else None)
    if not target_shelf:
        return

    # 同名ボタンがあれば消す
    for c in cmds.shelfLayout(target_shelf, q=True, ca=True) or []:
        if cmds.control(c, q=True, l=True) == "ControllerPicker":
            try: cmds.deleteUI(c)
            except Exception: pass

    cmds.shelfButton(l="ControllerPicker",
                     i="controller_picker.png",  # XBMLANGPATHに載っていれば使える
                     c="python(\"from controller_picker.ui import show; show()\")",
                     parent=target_shelf)
    try:
        cmds.mel.eval('saveAllShelves')
    except Exception:
        pass

def _open_ui():
    from controller_picker.ui import show
    show()

# 起動時に走る
_ensure_menu()
_ensure_shelf()