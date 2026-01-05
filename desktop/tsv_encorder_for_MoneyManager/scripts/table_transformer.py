# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List


def should_skip_row(transaction_content: str) -> bool:
    """H列（取引内容）に「獲得」が含まれる行をスキップする。"""
    return "獲得" in (transaction_content or "")




# 不要列(E,F,G,K,L,M)の中身を空欄にする
def clear_unused_columns(row: List[str]) -> None:
    """不要列(E,F,G,K,L,M)の中身を空欄にする（列自体は削除しない）。"""
    # インデックスは 0-based
    for idx in (4, 5, 6, 10, 11, 12):  # E,F,G,K,L,M
        if idx < len(row):
            row[idx] = ""


def decide_income_or_expense(row: List[str]) -> str:
    """金額列をもとに収入/支出を判定する。

    - B列 or D列に数値がある → 支出
    - C列に数値がある → 収入
    """
    def has_value(v: str) -> bool:
        try:
            return bool(v) and float(v) != 0.0
        except Exception:
            return False

    # B(1) or D(3) → 支出
    if (len(row) > 1 and has_value(row[1])) or (len(row) > 3 and has_value(row[3])):
        return "支出"
    # C(2) → 収入
    if len(row) > 2 and has_value(row[2]):
        return "収入"
    return ""


def move_amount_to_f(row: List[str]) -> str:
    """B列の金額をF列用として返す（row自体は破壊しない）。"""
    if len(row) > 1:
        return str(row[1]).strip()
    return ""