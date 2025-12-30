# -*- coding: utf-8 -*-
from __future__ import annotations


def main() -> int:
    """MMEnc GUIエントリポイント（起動後にCSV/YAMLを選択）."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as e:
        print(f"GUIを起動できません: {e}")
        return 2

    from encoder_core import run_encode

    root = tk.Tk()
    root.withdraw()  # ダイアログのみ利用

    csv_path = filedialog.askopenfilename(
        title="PayPay CSVを選択",
        filetypes=[("CSV", "*.csv"), ("All Files", "*")],
    )
    if not csv_path:
        messagebox.showinfo("MMEnc", "CSVが選択されなかったため終了します")
        return 2

    yaml_path = filedialog.askopenfilename(
        title="Preset YAMLを選択",
        filetypes=[("YAML", "*.yaml *.yml"), ("All Files", "*")],
    )
    if not yaml_path:
        messagebox.showinfo("MMEnc", "YAMLが選択されなかったため終了します")
        return 2

    ok, msgs = run_encode(csv_path, yaml_path)
    if ok:
        messagebox.showinfo("MMEnc 完了", "\n".join(msgs))
        return 0

    messagebox.showerror("MMEnc エラー", "\n".join(msgs))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())