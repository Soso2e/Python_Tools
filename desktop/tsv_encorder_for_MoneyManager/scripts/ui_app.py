# ui_app.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path

from encoder_core import run_encode
from preset_manager import upsert_store_mapping, collect_category_options

CATEGORY_CHOICES = [
    "スタバ",
    "趣味",
    "食材",
    "外食",
    "ごほうび",
    "交通費",
    "コンビニ",
    "生活用品",
    "通信費？",
    "ファッション",
    "その他",
    "みつぎもの",
    "移動",
]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("MMEnc - MoneyManager Encoder")
        self.minsize(700, 450)

        self.csv_path: str | None = None
        self.yaml_path: str | None = None
        self.check_ok: bool = False
        self.preset_auto: bool = False
        self.unknown_stores: list[str] = []
        self.category_options: list[str] = []
        self.sub_category_options: list[str] = []

        self.csv_var = tk.StringVar(value="未選択")
        self.yaml_var = tk.StringVar(value="未選択")

        self._build_ui()

    def _build_ui(self) -> None:
        # ===== ファイル選択エリア =====
        top = tk.Frame(self, padx=12, pady=12)
        top.pack(fill="x")

        # CSV
        csv_row = tk.Frame(top)
        csv_row.pack(fill="x", pady=(0, 6))
        tk.Label(csv_row, text="PayPay CSV", width=12, anchor="w").pack(side="left")
        tk.Entry(csv_row, textvariable=self.csv_var).pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(csv_row, text="参照…", command=self.select_csv).pack(side="left")

        # Preset YAML（自動検出 / フォールバック選択）
        yaml_row = tk.Frame(top)
        yaml_row.pack(fill="x")

        tk.Label(yaml_row, text="Preset YAML", width=12, anchor="w").pack(side="left")

        self.yaml_entry = tk.Entry(yaml_row, textvariable=self.yaml_var, state="readonly")
        self.yaml_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.yaml_btn = tk.Button(yaml_row, text="参照…", command=self.select_yaml)
        self.yaml_btn.pack(side="left")

        # ===== 実行ボタン =====
        mid = tk.Frame(self, padx=12, pady=6)
        mid.pack(fill="x")

        self.check_btn = tk.Button(mid, text="店名チェック", height=2, command=self.check)
        self.check_btn.pack(side="left")

        self.run_btn = tk.Button(mid, text="TSV変換", height=2, command=self.run, state="disabled")
        self.run_btn.pack(side="left", padx=(8, 0))

        self.register_btn = tk.Button(mid, text="店舗を登録", height=2, command=self.open_register_dialog, state="disabled")
        self.register_btn.pack(side="left", padx=(8, 0))

        tk.Button(mid, text="ログクリア", command=self.clear_log).pack(side="left", padx=(8, 0))

        # ===== ログ表示（スクロール対応） =====
        bottom = tk.Frame(self, padx=12, pady=12)
        bottom.pack(fill="both", expand=True)

        tk.Label(bottom, text="結果 / エラー（スクロール可能）", anchor="w").pack(fill="x")

        text_frame = tk.Frame(bottom)
        text_frame.pack(fill="both", expand=True, pady=(6, 0))

        self.log_text = tk.Text(text_frame, wrap="word")
        scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.detect_preset()
        self.append_log("CSVとYAMLを選択して『TSV変換』を押してください。\n")

    def detect_preset(self) -> None:
        """ui_app.py の1つ上の階層 /presets/common_preset.yaml を自動検出
        見つからなければ手動選択にフォールバックする
        """
        base = Path(__file__).resolve().parent.parent
        preset = base / "presets" / "common_preset.yaml"

        if preset.exists():
            self.yaml_path = str(preset)
            self.yaml_var.set(str(preset))
            self.yaml_entry.config(state="readonly")
            self.yaml_btn.config(state="disabled")
            self.append_log(f"Preset検出: {preset}\n")
            self.preset_auto = True
            self.refresh_category_options()
        else:
            self.yaml_path = None
            self.yaml_var.set("Presetが見つかりません（手動で選択してください）")
            self.yaml_entry.config(state="normal")
            self.yaml_btn.config(state="normal")
            self.append_log("Preset YAML が見つかりません。手動選択してください。\n")
            self.preset_auto = False
            self.register_btn.config(state="disabled")

    def select_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="PayPay CSVを選択",
            filetypes=[("CSV", "*.csv"), ("All Files", "*")],
        )
        if path:
            self.csv_path = path
            self.csv_var.set(path)
            self.append_log(f"CSV選択: {path}\n")

    def select_yaml(self) -> None:
        path = filedialog.askopenfilename(
            title="Preset YAMLを選択",
            filetypes=[("YAML", "*.yaml *.yml"), ("All Files", "*")],
        )
        if path:
            self.yaml_path = path
            self.yaml_var.set(path)
            self.append_log(f"Preset手動選択: {path}\n")
            self.refresh_category_options()
            self.register_btn.config(state="disabled")
            self.run_btn.config(state="disabled")
            self.check_ok = False
            self.unknown_stores = []

    def clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    def append_log(self, msg: str) -> None:
        self.log_text.insert("end", msg)
        self.log_text.see("end")

    def refresh_category_options(self) -> None:
        """Preset内の既存マッピングから category / sub_category の候補を収集する。"""
        self.category_options = CATEGORY_CHOICES[:]
        self.sub_category_options = []

        if not self.yaml_path:
            return

        try:
            cats, subs = collect_category_options(self.yaml_path)
            # category は固定候補（10種類）を使う
            self.category_options = CATEGORY_CHOICES[:]
            # sub_category は既存presetから候補を集める（必要に応じて手入力も可）
            self.sub_category_options = subs
        except Exception as e:
            # category は固定候補だけでも出せるようにしておく
            self.category_options = CATEGORY_CHOICES[:]
            self.sub_category_options = []
            self.append_log(f"カテゴリ候補の取得に失敗: {e}\n")

    def extract_unknown_stores_from_messages(self, messages: list[str]) -> list[str]:
        """run_encode のメッセージから未登録店舗名を抽出する。

        想定:
            - "未登録店舗があります..." の後に
            - "- 店名" 形式の行が続く
        """
        unknown: list[str] = []
        for m in messages:
            line = str(m).strip()
            # 例: "- Google" のような箇条書き
            if line.startswith("-"):
                name = line.lstrip("-").strip()
                if name and name not in unknown:
                    unknown.append(name)
        return unknown

    def check(self) -> None:
        """店名チェックのみ実行。問題なければ変換を有効化"""
        self.run_btn.config(state="disabled")
        self.register_btn.config(state="disabled")
        self.check_ok = False
        self.unknown_stores = []

        if not self.csv_path:
            messagebox.showerror("エラー", "CSVを選択してください")
            return
        if not self.yaml_path:
            messagebox.showerror("エラー", "Preset YAML が未設定です（自動検出または手動選択してください）")
            return

        self.append_log("\n--- 店名チェック開始 ---\n")
        ok, messages = run_encode(self.csv_path, self.yaml_path)

        for m in messages:
            self.append_log(m + "\n")

        unknown = self.extract_unknown_stores_from_messages(messages)
        if unknown:
            self.unknown_stores = unknown
            self.append_log("--- チェックNG：未登録あり ---\n")
            self.append_log(f"未登録件数: {len(unknown)} 件\n")
            self.register_btn.config(state="normal")
            messagebox.showerror("チェックNG", f"未登録店舗が {len(unknown)} 件あります。『店舗を登録』から追加してください。")
            return

        if ok:
            self.append_log("--- チェックOK：変換可能 ---\n")
            self.check_ok = True
            self.run_btn.config(state="normal")
            messagebox.showinfo("チェックOK", "問題ありません。変換を実行できます。")
        else:
            # 未登録以外の理由でNG（フォーマット/ヘッダーなど）
            self.append_log("--- チェックNG ---\n")
            messagebox.showerror("チェックNG", "エラーがあります。ログを確認してください。")

    def open_register_dialog(self) -> None:
        """未登録店舗を preset に追記するポップアップを開く。"""
        if not self.yaml_path:
            messagebox.showerror("エラー", "Preset YAML が未設定です")
            return
        if not self.unknown_stores:
            messagebox.showinfo("情報", "未登録店舗はありません")
            return

        # 候補リスト更新
        self.refresh_category_options()

        dlg = tk.Toplevel(self)
        dlg.title("店舗を登録")
        dlg.transient(self)
        dlg.grab_set()
        dlg.minsize(540, 300)

        current_store = self.unknown_stores[0]
        info_var = tk.StringVar(value=f"残り {len(self.unknown_stores)} 件 / 今: {current_store}")
        tk.Label(dlg, textvariable=info_var, anchor="w").pack(fill="x", padx=12, pady=(12, 6))

        form = tk.Frame(dlg)
        form.pack(fill="both", expand=True, padx=12, pady=6)

        # 登録キー
        tk.Label(form, text="登録する名前（キー）", anchor="w").grid(row=0, column=0, sticky="w", pady=4)
        key_var = tk.StringVar(value=current_store)
        key_entry = tk.Entry(form, textvariable=key_var)
        key_entry.grid(row=0, column=1, sticky="ew", pady=4)

        # category
        tk.Label(form, text="category", anchor="w").grid(row=1, column=0, sticky="w", pady=4)
        cat_var = tk.StringVar(value=self.category_options[0] if self.category_options else "")
        cat_box = ttk.Combobox(form, textvariable=cat_var, values=self.category_options, state="readonly")
        cat_box.grid(row=1, column=1, sticky="ew", pady=4)

        # sub_category
        tk.Label(form, text="sub_category", anchor="w").grid(row=2, column=0, sticky="w", pady=4)
        sub_var = tk.StringVar(value=self.sub_category_options[0] if self.sub_category_options else "")
        sub_box = ttk.Combobox(form, textvariable=sub_var, values=self.sub_category_options, state="normal")
        sub_box.grid(row=2, column=1, sticky="ew", pady=4)

        form.columnconfigure(1, weight=1)

        btns = tk.Frame(dlg)
        btns.pack(fill="x", padx=12, pady=(6, 12))

        def go_next() -> None:
            if not self.unknown_stores:
                return
            nxt = self.unknown_stores[0]
            info_var.set(f"残り {len(self.unknown_stores)} 件 / 今: {nxt}")
            key_var.set(nxt)
            key_entry.focus_set()

        def commit_and_next() -> None:
            store_key = key_var.get().strip()
            cat = cat_var.get().strip()
            sub = sub_var.get().strip()

            if not store_key:
                messagebox.showerror("エラー", "登録する名前（キー）を入力してください", parent=dlg)
                return
            if not cat or not sub:
                messagebox.showerror("エラー", "category / sub_category を入力してください", parent=dlg)
                return

            try:
                upsert_store_mapping(self.yaml_path, store_key, cat, sub)
            except Exception as e:
                messagebox.showerror("エラー", f"YAMLへの追記に失敗: {e}", parent=dlg)
                return

            original = self.unknown_stores.pop(0)
            self.append_log(f"登録: '{store_key}' -> {cat} / {sub}  （元: {original}）\n")

            # 候補更新（新規入力が増えた可能性があるため）
            self.refresh_category_options()
            cat_box.configure(values=self.category_options)
            sub_box.configure(values=self.sub_category_options)

            if not self.unknown_stores:
                messagebox.showinfo("完了", "すべて登録しました。『店名チェック』を再実行してください。", parent=dlg)
                dlg.destroy()
                self.register_btn.config(state="disabled")
                self.check_ok = False
                self.run_btn.config(state="disabled")
                return

            go_next()

        def skip_and_next() -> None:
            if not self.unknown_stores:
                return
            skipped = self.unknown_stores.pop(0)
            self.append_log(f"スキップ: {skipped}\n")

            if not self.unknown_stores:
                messagebox.showinfo("情報", "残りがありません。『店名チェック』を再実行してください。", parent=dlg)
                dlg.destroy()
                # 未登録を残した可能性があるので、変換は無効のまま
                self.check_ok = False
                self.run_btn.config(state="disabled")
                self.register_btn.config(state="disabled")
                return

            go_next()

        tk.Button(btns, text="登録して次へ", command=commit_and_next).pack(side="left")
        tk.Button(btns, text="スキップ", command=skip_and_next).pack(side="left", padx=(8, 0))
        tk.Button(btns, text="閉じる", command=dlg.destroy).pack(side="right")

        key_entry.focus_set()

    def run(self) -> None:
        if not self.check_ok:
            messagebox.showerror("エラー", "先に店名チェックを実行してください")
            return

        if self.unknown_stores:
            messagebox.showerror("エラー", "未登録店舗があります。先に『店舗を登録』またはpresetの修正をしてください")
            return

        if not self.csv_path or not self.yaml_path:
            messagebox.showerror("エラー", "CSVとYAMLの両方を選択してください")
            return

        self.append_log("\n--- 実行開始 ---\n")
        ok, messages = run_encode(self.csv_path, self.yaml_path)

        for m in messages:
            self.append_log(m + "\n")

        self.append_log("--- 実行終了 ---\n")

        if ok:
            messagebox.showinfo("完了", "変換が完了しました。詳細はログを確認してください。")
        else:
            messagebox.showerror("エラー", "未登録店舗などのエラーがあります。ログを確認してください。")


def run_app() -> None:
    app = App()
    app.mainloop()