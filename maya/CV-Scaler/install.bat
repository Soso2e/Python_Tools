@echo off
setlocal EnableDelayedExpansion

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
set "SRC_ICONS=%SRC%icon"

for %%V in (%VERSIONS%) do (
  set "DEST_PREFS=%MAYA_ROOT%\%%V\prefs"
  if exist "%DEST_PREFS%" (
    echo.
    echo === Installing for Maya %%V ===

    mkdir "%DEST_PREFS%\shelves"  >nul 2>&1
    mkdir "%MAYA_ROOT%\%%V\scripts" >nul 2>&1
    mkdir "%DEST_PREFS%\icons"    >nul 2>&1

    REM --- shelf (上書き) ---
    if exist "%SRC_SHELVES%\add_to_shelf.mel" (
      copy /Y "%SRC_SHELVES%\add_to_shelf.mel" "%DEST_PREFS%\shelves\add_to_shelf.mel" >nul
      echo Copied add_to_shelf.mel
    ) else (
      echo [WARN] shelves\add_to_shelf.mel not found in package.
    )

    REM --- scripts（上書き） ---
    if exist "%SRC_SCRIPTS%" (
      xcopy /E /I /Y "%SRC_SCRIPTS%\*" "%MAYA_ROOT%\%%V\scripts\" >nul
      echo Copied scripts
    ) else (
      echo [WARN] scripts folder not found in package.
    )

    REM --- icons（上書き） ---
    if exist "%SRC_ICONS%" (
      xcopy /E /I /Y "%SRC_ICONS%\*.png" "%DEST_PREFS%\icons\" >nul
      echo Copied icons (*.png)
    ) else (
      echo [INFO] icon folder not found. Skipping icons.
    )
  )
)

echo.
echo --- Detecting newest Maya and launching ---

REM ====== 3) 最も新しいMayaバージョンを検出して起動 ======
set "NEWEST_VER="
set "MAYA_EXE="

REM 3-a) ユーザprefs配下(20xx)から最大値を決定
for /f "delims=" %%D in ('dir /ad /b "%MAYA_ROOT%" ^| findstr /r "^20[0-9][0-9]$"') do (
  call :_cmp_set_newest "%%D"
)

REM 3-b) Program Files のインストール先からも検出（prefs未生成ケースの補完）
for /f "delims=" %%D in ('dir /ad /b "%ProgramFiles%\Autodesk" ^| findstr /r "^Maya20[0-9][0-9]$"') do (
  set "VERNAME=%%D"
  set "VERNUM=!VERNAME:Maya=!"
  call :_cmp_set_newest "!VERNUM!"
)

if defined NEWEST_VER (
  set "MAYA_EXE=%ProgramFiles%\Autodesk\Maya%NEWEST_VER%\bin\maya.exe"
)

REM 3-c) もし上の推定で見つからない場合は Program Files を総当たりで探索
if not exist "%MAYA_EXE%" (
  for /f "delims=" %%F in ('dir /b /s "%ProgramFiles%\Autodesk\Maya20??\bin\maya.exe" 2^>nul') do (
    set "MAYA_EXE=%%F"
  )
)

REM 3-d) PATHに登録されていれば where で拾う
if not exist "%MAYA_EXE%" (
  for /f "delims=" %%F in ('where maya.exe 2^>nul') do (
    set "MAYA_EXE=%%F"
    goto :_found_exe
  )
)

:_found_exe
if defined MAYA_EXE (
  echo Launching: "%MAYA_EXE%"
  start "" "%MAYA_EXE%"
) else (
  echo [WARN] maya.exe を検出できませんでした。手動で起動してください。
)

goto :after_detect

:_cmp_set_newest
set "CAND=%~1"
REM 数値チェック（簡易）：4桁数値前提なのでそのまま比較でOK
if not defined NEWEST_VER (
  set "NEWEST_VER=%CAND%"
) else (
  if %CAND% GTR %NEWEST_VER% set "NEWEST_VER=%CAND%"
)
exit /b 0

:after_detect

echo.
echo ✅ インストール完了。次回の通常起動で「Python」棚に「CV_Scaler」ボタンが出ます。
pause
endlocal