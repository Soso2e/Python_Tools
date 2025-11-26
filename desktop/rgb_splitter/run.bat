@echo off
setlocal

REM このbatが置いてあるフォルダに移動
cd /d "%~dp0"

REM Pythonでスクリプトを実行
python rgb_splitter_ui.py

endlocal