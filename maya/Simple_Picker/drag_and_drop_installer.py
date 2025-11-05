"""drag_and_drop_installer

このモジュールは、Maya のビューポートに Python ファイルをドラッグ&ドロップして実行される
インストーラ用スクリプトです。以下の処理を行います。

- ツールの `scripts/` と `icon/` をユーザスクリプトディレクトリ配下へコピー
- `.mod` ファイルを生成し、パス管理は .mod で管理
- 指定したシェルフタブ（Python)上に起動ボタンを追加。二つ上のディレクトリ名を参照。

設計方針:
- ランタイムの `sys.path` や `XBMLANGPATH` への直接追加は行わず、再起動後に .mod が効く前提。
- シェルフボタンは `main.run()` を呼び出します。インポート失敗時は再起動を促す警告を表示します。

使い方:
1) 本ファイルを Maya ビューポートへ D&D します。
2) ダイアログの案内に従い、インストール完了後に必要であれば Maya を再起動してください。
"""

from __future__ import annotations
import os
import sys
import shutil
from maya import cmds, mel

# 定数
DEFAULT_SHELF_TAB_NAME = "Python"  # 既定のシェルフタブ名（存在しない場合は自動生成されます）

# エントリーポイント
def onMayaDroppedPythonFile(*_):
    """Maya のビューポートへ D&D されたときに呼ばれるエントリポイント。

    例外はキャッチして画面表示（inViewMessage と warning）に出し、
    失敗しても Maya 自体が落ちないようにしています。

    Args:
        *_: D&D 呼び出し時の不要な引数（未使用）
    """
    try:
        install_tool()
        _inview("<hl>Installation completed successfully.</hl>")
    except Exception as e:
        cmds.warning(f"[Installer] Installation failed: {e}")
        _inview(f"<hl>Installation failed:</hl> {e}")


# コアロジック
def install_tool() -> None:
    """インストールのメイン処理を行う。

    - 実行ファイルの場所からツールルートを判定
    - `scripts/`, `icon/`, `shelves/add_to_shelf.mel` の存在検証
    - ユーザスクリプトディレクトリ配下へ必要フォルダをコピー
    - `.mod` ファイルの生成
    - シェルフボタンの作成

    Raises:
        FileNotFoundError: 必須ファイルが見つからない場合
    """
    this_py = os.path.abspath(__file__)
    tool_root = os.path.dirname(this_py)
    tool_name = os.path.basename(tool_root)
    shelf_tab_name = DEFAULT_SHELF_TAB_NAME

    src_scripts = os.path.join(tool_root, "scripts")
    src_icons = os.path.join(tool_root, "icon")
    src_mel = os.path.join(tool_root, "shelves", "add_to_shelf.mel")

    if not os.path.isfile(os.path.join(src_scripts, "main.py")):
        raise FileNotFoundError(f"main.py not found in: {src_scripts}")
    if not os.path.isfile(src_mel):
        raise FileNotFoundError(f"add_to_shelf.mel not found in: {src_mel}")

    user_scripts_root = cmds.internalVar(userScriptDir=True)
    dst_root = os.path.join(user_scripts_root, tool_name)
    dst_scripts = os.path.join(dst_root, "scripts")
    dst_icon = os.path.join(dst_root, "icon")

    _copy_subdir(src_scripts, dst_scripts)
    _copy_subdir(src_icons, dst_icon)

    # ランタイムでのパス注入は行わず、.mod のみで管理。
    _ensure_mod_file(tool_name, dst_root)

    shelf_name = _sanitize_shelf_name(shelf_tab_name)
    mel_path = src_mel.replace("\\", "/")
    mel.eval(f'source "{mel_path}";')

    # 再起動前でもユーザーが押して様子を見られるよう、試行して失敗時は警告。
    py_cmd = (
        "import importlib; "
        "try: "
        " import main; importlib.reload(main); main.run() "
        "except ImportError: "
        " import maya.cmds as cmds; cmds.warning('Module not found. Please restart Maya to complete installation.') "
    )

    _remove_existing_shelf_button(shelf_name, tool_name)
    _call_add_to_shelf(shelf_name, tool_name, py_cmd, _find_icon(dst_icon))

    cmds.confirmDialog(
        title=tool_name,
        message=(
            f"{tool_name} has been installed successfully.\n\n"
            f"Installation path:\n{dst_root}\n\n"
            f"Launch from Shelf: {shelf_name} > {tool_name}"
        ),
        button=["OK"]
    )


# Helper Functions
def _copy_subdir(src: str, dst: str) -> None:
    """サブディレクトリを丸ごとコピーする。

    既に `dst` が存在する場合は一度削除してからコピーします。

    Args:
        src: コピー元ディレクトリの絶対パス
        dst: コピー先ディレクトリの絶対パス
    """
    if not os.path.isdir(src):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _find_icon(icon_dir: str) -> str:
    """アイコンディレクトリから最初に見つかった PNG を返す。

    見つからない場合は Maya 付属の `pythonFamily.png` を返します。

    Args:
        icon_dir: アイコンディレクトリの絶対パス

    Returns:
        使用するアイコンファイルのパス（スラッシュ区切り）
    """
    if not os.path.isdir(icon_dir):
        return "pythonFamily.png"
    for f in os.listdir(icon_dir):
        if f.lower().endswith(".png"):
            return os.path.join(icon_dir, f).replace("\\", "/")
    return "pythonFamily.png"


def _mel_escape(s: str) -> str:
    """MEL 文字列リテラル用に最低限のエスケープを行う。

    Args:
        s: 対象文字列

    Returns:
        エスケープ後の文字列
    """
    return s.replace("\\", "/").replace('"', '\\"')


def _call_add_to_shelf(shelf_name: str, label: str, py_cmd: str, icon: str) -> None:
    """`add_to_shelf.mel` を呼び出してシェルフボタンを追加する。

    Args:
        shelf_name: シェルフタブ名（存在しなければ MEL 側で作成される想定）
        label: ボタンに表示するラベル
        py_cmd: ボタン押下時に実行する Python コマンド
        icon: ボタンアイコンのパス（またはファイル名）
    """
    a = _mel_escape(shelf_name)
    b = _mel_escape(label)
    c = _mel_escape(py_cmd)
    d = _mel_escape(icon)
    mel.eval(f'add_to_shelf("{a}", "{b}", "{c}", "{d}");')


def _inview(msg: str) -> None:
    """inViewMessage により、画面中央付近に一時的なメッセージを表示する。

    Args:
        msg: AMPL メッセージ文字列（`<hl>...</hl>` 等の簡易装飾可）
    """
    try:
        cmds.inViewMessage(amg=msg, pos="midCenter", fade=True)
    except Exception:
        # inViewMessage が使用不可な環境でも失敗で止まらないよう握りつぶす
        pass


def _ensure_mod_file(tool_name: str, dst_root: str) -> None:
    """`.mod` ファイルを `Documents/maya/modules` に生成する。

    `scripts/__init__.py` に `version` 変数があればそれを読み取り、
    `.mod` のバージョン表記に反映します。

    書き出すキー:
      - `PYTHONPATH +:= scripts`
      - `MAYA_SCRIPT_PATH +:= scripts`
      - `XBMLANGPATH +:= icon`

    Args:
        tool_name: ツール名（フォルダ名を想定）
        dst_root: ユーザスクリプト配下のツールルート
    """
    maya_app_dir = os.environ.get("MAYA_APP_DIR") or os.path.join(os.path.expanduser("~"), "Documents", "maya")
    modules_dir = os.path.join(maya_app_dir, "modules")
    os.makedirs(modules_dir, exist_ok=True)
    mod_path = os.path.join(modules_dir, f"{tool_name}.mod")

    version = None
    scripts_init = os.path.join(dst_root, 'scripts', '__init__.py')
    if os.path.isfile(scripts_init):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"{tool_name}_scripts_init", scripts_init)
            mod = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(mod)  # type: ignore[assignment]
            version = getattr(mod, "version", None)
        except Exception:
            # バージョン読取に失敗した場合は None のまま
            pass

    if version is None:
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
    print(f"[Installer] .mod file generated at: {mod_path}")


def _sanitize_shelf_name(name: str) -> str:
    """Maya シェルフレイアウト名として不適切な文字を `_` に置換する。

    Args:
        name: 入力シェルフ名

    Returns:
        置換後のシェルフ名
    """
    invalid_chars = r'\\/:*?"<>| '
    sanitized = ''.join(c if c not in invalid_chars else '_' for c in name)
    return sanitized


def _remove_existing_shelf_button(shelf_name: str, label: str) -> None:
    """同名ラベルのシェルフボタンがある場合に削除して重複追加を防ぐ。

    Args:
        shelf_name: 対象のシェルフタブ名
        label: 削除対象となるボタンラベル
    """
    if not cmds.shelfLayout(shelf_name, exists=True):
        return
    children = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
    for child in children:
        if cmds.control(child, query=True, label=True) == label:
            try:
                cmds.deleteUI(child)
                print(f"[Installer] Removed existing shelf button '{label}' from shelf '{shelf_name}'.")
            except Exception:
                # 失敗しても致命的ではないため握りつぶす
                pass