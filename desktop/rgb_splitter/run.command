#!/bin/bash

# このスクリプトが置かれているディレクトリへ移動
cd "$(dirname "$0")"

# Python の位置確認（デバッグ用）
echo "==== Python path ===="
which python3
python3 --version
echo "====================="

# メインスクリプト実行
python3 rgb_splitter_ui.py

echo
echo "==== 終了。閉じるには Enter を押してください ===="
read