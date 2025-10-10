import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout,
    QFileDialog, QComboBox
)
from PIL import Image

class AspectResizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像一括アスペクト比調整（ズーム）")
        self.layout = QVBoxLayout()

        # 入力フォルダ選択
        self.folder_label = QLabel("📂 画像フォルダを選択してください")
        self.layout.addWidget(self.folder_label)

        self.btn_folder = QPushButton("フォルダを選ぶ")
        self.btn_folder.clicked.connect(self.select_folder)
        self.layout.addWidget(self.btn_folder)

        # 出力フォルダ選択
        self.output_label = QLabel("💾 出力先フォルダを選択してください")
        self.layout.addWidget(self.output_label)

        self.btn_output = QPushButton("出力フォルダを選ぶ")
        self.btn_output.clicked.connect(self.select_output_folder)
        self.layout.addWidget(self.btn_output)

        # アスペクト比選択
        self.layout.addWidget(QLabel("🎯 アスペクト比を選択:"))
        self.aspect_box = QComboBox()
        self.aspect_box.addItems(["16:9", "4:3", "1:1", "3:2"])
        self.layout.addWidget(self.aspect_box)

        # 実行ボタン
        self.btn_convert = QPushButton("🚀 処理開始（ズーム）")
        self.btn_convert.clicked.connect(self.process_images)
        self.layout.addWidget(self.btn_convert)

        self.setLayout(self.layout)

        self.folder_path = ""
        self.output_folder = ""

    def select_folder(self):
        self.folder_path = QFileDialog.getExistingDirectory(self, "入力フォルダを選択")
        self.folder_label.setText(f"選択フォルダ: {self.folder_path}")

    def select_output_folder(self):
        self.output_folder = QFileDialog.getExistingDirectory(self, "出力フォルダを選択")
        self.output_label.setText(f"出力先: {self.output_folder}")

    def process_images(self):
        if not self.folder_path:
            self.folder_label.setText("⚠️ 入力フォルダが選択されていません")
            return

        if not self.output_folder:
            self.output_label.setText("⚠️ 出力フォルダが選択されていません")
            return

    target_ratio = self.aspect_box.currentText()
    w_ratio, h_ratio = map(int, target_ratio.split(":"))
    ratio = w_ratio / h_ratio

    for fname in os.listdir(self.folder_path):
        if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(self.folder_path, fname)
            img = Image.open(path)
            img = self.resize_and_crop(img, ratio)

            # 出力ファイルパスの生成（重複チェック付き）
            output_path = os.path.join(self.output_folder, fname)
            base, ext = os.path.splitext(output_path)
            counter = 1
            while os.path.exists(output_path):
                output_path = f"{base}_{counter}{ext}"
                counter += 1

            img.save(output_path)

    self.folder_label.setText("✅ 処理完了！")


    def resize_and_crop(self, img, target_ratio):
        w, h = img.size
        current_ratio = w / h

        # アスペクト比に合わせて中央をクロップ
        if current_ratio > target_ratio:
            # 横長すぎ → 高さを基準にクロップ
            new_height = h
            new_width = int(h * target_ratio)
        else:
            # 縦長すぎ → 幅を基準にクロップ
            new_width = w
            new_height = int(w / target_ratio)

        left = (w - new_width) // 2
        top = (h - new_height) // 2
        right = left + new_width
        bottom = top + new_height

        img_cropped = img.crop((left, top, right, bottom))
        return img_cropped

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AspectResizer()
    win.show()
    sys.exit(app.exec_())
