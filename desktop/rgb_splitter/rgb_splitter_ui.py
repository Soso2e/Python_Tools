from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Optional

from PIL import Image


class RGBSplitterApp(tk.Tk):
    """RGB分解ツールのメインウィンドウ."""

    def __init__(self) -> None:
        super().__init__()

        self.title("RGB分解ツール")
        self.geometry("480x220")

        # 選択されたパスを保持
        self.image_path: Optional[Path] = None
        self.output_dir: Optional[Path] = None

        self._create_widgets()

    # --------------------------------------------------------------------- #
    # UI初期化
    # --------------------------------------------------------------------- #
    def _create_widgets(self) -> None:
        """ウィジェットを作成して配置する."""

        # 画像選択
        frame_image = tk.Frame(self, padx=10, pady=10)
        frame_image.pack(fill=tk.X)

        btn_image = tk.Button(frame_image, text="画像を選択", command=self.on_select_image)
        btn_image.pack(side=tk.LEFT)

        self.label_image = tk.Label(frame_image, text="未選択", anchor="w")
        self.label_image.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # 出力フォルダ選択
        frame_output = tk.Frame(self, padx=10, pady=5)
        frame_output.pack(fill=tk.X)

        btn_output = tk.Button(frame_output, text="出力フォルダを選択", command=self.on_select_output_dir)
        btn_output.pack(side=tk.LEFT)

        self.label_output = tk.Label(frame_output, text="未選択", anchor="w")
        self.label_output.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # 実行ボタン
        frame_run = tk.Frame(self, padx=10, pady=15)
        frame_run.pack(fill=tk.X)

        btn_run = tk.Button(frame_run, text="RGBに分解して出力", command=self.on_run)
        btn_run.pack()

        # グレースケール出力のチェックボックス
        self.grayscale_var = tk.BooleanVar(value=True)
        chk_grayscale = tk.Checkbutton(
            frame_run,
            text="グレースケールで出力する",
            variable=self.grayscale_var,
        )
        chk_grayscale.pack(pady=(10, 0))

        # ステータス表示
        self.status_label = tk.Label(self, text="", anchor="w", fg="#555555")
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    # --------------------------------------------------------------------- #
    # イベントハンドラ
    # --------------------------------------------------------------------- #
    def on_select_image(self) -> None:
        """画像ファイルを選択する."""
        filetypes = [
            ("画像ファイル", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp"),
            ("すべてのファイル", "*.*"),
        ]
        path_str = filedialog.askopenfilename(title="画像を選択してください", filetypes=filetypes)

        if not path_str:
            return

        self.image_path = Path(path_str)
        self.label_image.config(text=str(self.image_path))
        self._set_status("画像ファイルを選択しました。")

    def on_select_output_dir(self) -> None:
        """出力フォルダを選択する."""
        dir_str = filedialog.askdirectory(title="出力先フォルダを選択してください")

        if not dir_str:
            return

        self.output_dir = Path(dir_str)
        self.label_output.config(text=str(self.output_dir))
        self._set_status("出力フォルダを選択しました。")

    def on_run(self) -> None:
        """RGB分解処理を実行する."""
        if self.image_path is None or not self.image_path.is_file():
            messagebox.showwarning("警告", "画像ファイルを選択してください。")
            return

        if self.output_dir is None or not self.output_dir.is_dir():
            messagebox.showwarning("警告", "出力フォルダを選択してください。")
            return

        try:
            output_paths = split_image_to_rgb(
                self.image_path,
                self.output_dir,
                grayscale=self.grayscale_var.get(),
            )
        except Exception as e:
            messagebox.showerror("エラー", f"変換中にエラーが発生しました。\n{e}")
            self._set_status("エラーが発生しました。詳細はメッセージを確認してください。")
            return

        msg = "書き出し完了:\n" + "\n".join(str(p.name) for p in output_paths)
        messagebox.showinfo("完了", msg)
        self._set_status("RGB分解が完了しました。")

    # --------------------------------------------------------------------- #
    # ユーティリティ
    # --------------------------------------------------------------------- #
    def _set_status(self, text: str) -> None:
        """ステータスメッセージを更新する."""
        self.status_label.config(text=text)


# ------------------------------------------------------------------------- #
# 画像処理ロジック
# ------------------------------------------------------------------------- #
def split_image_to_rgb(image_path: Path, output_dir: Path, grayscale: bool = False) -> list[Path]:
    """画像をR/G/Bそれぞれの画像に分解して保存する.

    R/G/Bのどれか1チャンネルだけを残し、他のチャンネルは0にした画像を保存する。

    Args:
        image_path: 入力画像のパス。
        output_dir: 出力先ディレクトリ。
        grayscale: True の場合は各チャンネルをグレースケール画像(L)として保存し、
            False の場合は現在のように単一チャンネルだけ色が残ったRGB画像として保存する。

    Returns:
        保存した画像ファイルのパス一覧 [R, G, B] の順。
    """
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path)
    img = img.convert("RGB")

    r, g, b = img.split()

    # 元ファイル名と拡張子を取得
    stem = image_path.stem  # 拡張子を除いたファイル名
    suffix = image_path.suffix or ".png"  # 拡張子がない場合は png として扱う

    outputs: list[Path] = []

    if grayscale:
        # 各チャンネルをそのままグレースケール(L)画像として保存
        out_r = output_dir / f"{stem}_R{suffix}"
        r.save(out_r)
        outputs.append(out_r)

        out_g = output_dir / f"{stem}_G{suffix}"
        g.save(out_g)
        outputs.append(out_g)

        out_b = output_dir / f"{stem}_B{suffix}"
        b.save(out_b)
        outputs.append(out_b)
    else:
        # 各チャンネルだけ色が残ったRGB画像として保存
        red_img = Image.merge("RGB", (r, Image.new("L", img.size, 0), Image.new("L", img.size, 0)))
        out_r = output_dir / f"{stem}_R{suffix}"
        red_img.save(out_r)
        outputs.append(out_r)

        green_img = Image.merge("RGB", (Image.new("L", img.size, 0), g, Image.new("L", img.size, 0)))
        out_g = output_dir / f"{stem}_G{suffix}"
        green_img.save(out_g)
        outputs.append(out_g)

        blue_img = Image.merge("RGB", (Image.new("L", img.size, 0), Image.new("L", img.size, 0), b))
        out_b = output_dir / f"{stem}_B{suffix}"
        blue_img.save(out_b)
        outputs.append(out_b)

    return outputs


def main() -> None:
    """アプリケーションのエントリポイント."""
    app = RGBSplitterApp()
    app.mainloop()


if __name__ == "__main__":
    main()