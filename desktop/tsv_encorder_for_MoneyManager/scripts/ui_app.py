# ui_app.py
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import filedialog, messagebox

from encoder_core import run_encode


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("MMEnc - MoneyManager Encoder")
        self.geometry("520x260")

        self.csv_path: str | None = None
        self.yaml_path: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        # CSV選択
        tk.Button(self, text="CSVを選択", command=self.select_csv).pack(pady=5)
        self.csv_label = tk.Label(self, text="未選択")
        self.csv_label.pack()

        # YAML選択
        tk.Button(self, text="YAMLを選択", command=self.select_yaml).pack(pady=5)
        self.yaml_label = tk.Label(self, text="未選択")
        self.yaml_label.pack()

        # 変換実行
        tk.Button(self, text="TSV変換", command=self.run).pack(pady=15)

    def select_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="PayPay CSVを選択",
            filetypes=[("CSV", "*.csv")]
        )
        if path:
            self.csv_path = path
            self.csv_label.config(text=path)

    def select_yaml(self) -> None:
        path = filedialog.askopenfilename(
            title="Preset YAMLを選択",
            filetypes=[("YAML", "*.yaml *.yml")]
        )
        if path:
            self.yaml_path = path
            self.yaml_label.config(text=path)

    def run(self) -> None:
        if not self.csv_path or not self.yaml_path:
            messagebox.showerror("エラー", "CSVとYAMLの両方を選択してください")
            return

        ok, messages = run_encode(self.csv_path, self.yaml_path)
        if ok:
            messagebox.showinfo("完了", "\n".join(messages))
        else:
            messagebox.showerror("エラー", "\n".join(messages))


def run_app() -> None:
    app = App()
    app.mainloop()