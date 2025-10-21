## ディレクトリ構造
```
MyTool/
├─ icon/
│   └─ MyTool.png
├─ scripts/
│   ├─ main.py
│   └─ __init__.py
├─ shelves/
│   ├─ add_to_shelf.mel
└─ drag_and_drop_install.py
```
基本的に上記の構造を共通化し、ツール名（例：MyTool）を変えるだけで別ツールとして拡張できるようにします。

すべてのファイルは相対パスで連携し、ツール名が変更されても自動で対応します。

## **各ファイルの機能**
#### `drag_and_drop_install.py`

マヤのビューポートに**ドラッグ＆ドロップ**することでツールを自動インストールします。

**主な処理内容**
1. **現在のフォルダ名をツール名として取得**
	
    - 例：C:tools/maya/CV_Scaler/drag_and_drop_install.py → CV_Scaler
    
2. **Mayaユーザースクリプトフォルダへコピー**
	
	-  `~/Documents/maya/<ver>/scripts/<TOOL_NAME>/scripts` 
		
	-   `~/Documents/maya/<ver>/scripts/<TOOL_NAME>/icon`
    
3. **環境パス設定**
    
    - sys.path に scripts を追加
        
    - XBMLANGPATH に icon パスを追加
    
4. **シェルフボタンの自動登録**
    
    - 相対パスで shelves/add_to_shelf.mel を source
        
    - シェルフタブ（デフォルト "Python"）にツール名のボタンを生成
        
    - ボタン押下時に scripts/main.py の run() が呼ばれるように設定
    
5. **進行メッセージの表示**
    - cmds.inViewMessage により画面中央に完了通知を表示。

6. **.mod ファイルの自動生成**
    - `~/Documents/maya/modules/<TOOL_NAME>.mod` を作成し、インストール先ルート（例：`~/Documents/maya/<ver>/scripts/<TOOL_NAME>`）をモジュールの ROOT として参照できるようにします。
    - これにより、Maya のモジュール機構でも同ツールを認識可能になり、将来的な環境統一・一括管理に移行しやすくなります。

    **出力テンプレート**
  ```txt
    + <TOOL_NAME> <VERSION> <ROOT>
    requires maya any
    PYTHONPATH +:= scripts
    MAYA_SCRIPT_PATH +:= scripts
    XBMLANGPATH +:= icon
```
    - `<ROOT>` には実際のインストール先（例：`~/Documents/maya/<ver>/scripts/<TOOL_NAME>` の絶対パス）が入ります。
    - 例：`+ CV_Scaler 1.0 /Users/you/Documents/maya/2026/scripts/CV_Scaler`

---

### ⚙️ `shelves/add_to_shelf.mel`
Python側から呼ばれる、**シェルフボタン登録専用スクリプト**です。

**機能**
- 指定されたシェルフタブ（`Python`）を自動作成
- 同名ボタンが存在する場合は削除 → 上書き登録
- アイコン指定および `python` コマンドの紐付けを行う

**呼び出しシグネチャ**
```mel
global proc add_to_shelf(string $shelfName, string $label, string $pyCmd, string $icon);
```

| 引数 | 内容 |
|------|------|
| `$shelfName` | 作成先のシェルフ名（例: "Python"） |
| `$label` | ボタンラベル（通常ツール名） |
| `$pyCmd` | 実行するPythonコマンド（`main.run()` など） |
| `$icon` | アイコンファイル名（`XBMLANGPATH` で解決） |

---

### 📄 `scripts/main.py`
ツールのメインエントリポイント。シェルフボタンから呼ばれる関数 `run()` を**必ず**定義します。

**サンプル**
```python
# scripts/main.py

def run():
    """ツールのメイン処理"""
    from maya import cmds
    cmds.confirmDialog(title="MyTool", message="MyTool is running!", button=["OK"]) 
```

> 実装側では `importlib.reload(main)` を併用しているため、`main.py` を編集後も Maya 再起動なしで反映されます。

---

### 🖼️ `icon/`
シェルフボタンに使用するアイコンを配置します。フォルダ内で最初に見つかった `.png` が自動採用されます。指定がない場合は Maya 標準の `pythonFamily.png` が使用されます。

**推奨構成**
```
icon/
└─ MyTool.png  # ツール名と合わせると分かりやすい
```

---

### 🧩 `scripts/__init__.py`
`scripts` フォルダをパッケージとして認識させるための空ファイルです。必要に応じて共通関数やバージョン情報などを定義しても構いません。

**例**
```python
# scripts/__init__.py
version = "1.0.0"
```

---

## 💡 運用ルール
| 項目 | 内容 |
|------|------|
| **インストール** | `drag_and_drop_install.py` を Maya ビューポートにドラッグ＆ドロップ |
| **アンインストール** | `~/Documents/maya/<ver>/scripts/<TOOL_NAME>` ディレクトリを削除 |
| **更新** | D&D を再実行すると上書き（旧版フォルダを自動削除） |
| **命名規則** | フォルダ名＝ツール名（英数字＋アンダースコア推奨） |
| **共通スクリプト** | `shelves/add_to_shelf.mel` は全ツール同一シグネチャで統一 |

---

## 📦 `.mod` 自動生成（モジュール対応）
**目的**
- チーム配布や将来のランチャー管理に備え、Maya のモジュール機構でも本ツールを検出できるようにします。
- D&D 配布の軽さは維持しつつ、モジュール運用への移行コストを最小化します。

**生成場所**
- `~/Documents/maya/modules/<TOOL_NAME>.mod`
  - バージョン非依存の共通モジュールディレクトリです（標準の `MAYA_MODULE_PATH`）。

**.mod の内容（例）**
```txt
+ MyTool 1.0 /Users/you/Documents/maya/2026/scripts/MyTool
requires maya any
PYTHONPATH +:= scripts
MAYA_SCRIPT_PATH +:= scripts
XBMLANGPATH +:= icon
```
> 1行目の `<ROOT>` には、D&D で実際に展開されたツールルートの**絶対パス**を入れます。以降の相対パス（`scripts`, `icon` 等）は `<ROOT>` を基準に解決されます。

**メリット**
- モジュール機構による自動パス解決（`sys.path`/`XBMLANGPATH` をグローバルに追加可能）
- チーム環境の一貫性を保ちやすい
- バージョンや配置換えに強い

**注意点**
- パスにスペースが含まれる場合、OS 側での解決は問題ありませんが、パスの変更時は `.mod` の更新が必要です。
- `.mod` のみではインストールは完結しません。本仕様では **D&D による展開 + `.mod` 生成** を行います（両輪）。