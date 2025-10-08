@echo off
setlocal

REM ====== 1) Mayaユーザフォルダ推定 ======
set "DOCS=%USERPROFILE%\Documents"
set "MAYA_ROOT=%DOCS%\maya"
if not exist "%MAYA_ROOT%" (
  echo Maya user dir not found: %MAYA_ROOT%
  echo 手動でパスを確認してください。
  pause
  exit /b 1
)

REM ====== 2) 対象バージョン列挙（必要に応じて編集）======
set VERSIONS=2022 2023 2024 2025 2026

REM ZIP内の相対パス
set "SRC=%~dp0"
set "SRC_SHELVES=%SRC%shelves"
set "SRC_SCRIPTS=%SRC%scripts"
set "SRC_ICONS=%SRC%icons"

for %%V in (%VERSIONS%) do (
  set "DEST_PREFS=%MAYA_ROOT%\%%V\prefs"
  if exist "%DEST_PREFS%" (
    echo.
    echo === Installing for Maya %%V ===

    mkdir "%DEST_PREFS%\shelves"  >nul 2>&1
    mkdir "%MAYA_ROOT%\%%V\scripts" >nul 2>&1
    mkdir "%DEST_PREFS%\icons"    >nul 2>&1

    REM --- shelf (上書き) ---
    copy /Y "%SRC_SHELVES%\shelf_Python.mel" "%DEST_PREFS%\shelves\shelf_Python.mel" >nul
    echo Copied shelf_Python.mel

    REM --- scripts（パッケージごと上書き） ---
    xcopy /E /I /Y "%SRC_SCRIPTS%\my_shelf" "%MAYA_ROOT%\%%V\scripts\my_shelf" >nul
    echo Copied my_shelf package

    REM --- icons（上書き） ---
    copy /Y "%SRC_ICONS%\cv_scaler.png" "%DEST_PREFS%\icons\cv_scaler.png" >nul
    echo Copied cv_scaler.png
  )
)

echo.
echo ✅ インストール完了。次回の通常起動で「Python」棚に「CV_Scaler」ボタンが出ます。
pause
endlocal