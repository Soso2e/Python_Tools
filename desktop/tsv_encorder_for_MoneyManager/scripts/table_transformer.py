# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List


def should_skip_row(transaction_content: str) -> bool:
    """H列（取引内容）に「獲得」が含まれる行をスキップする。"""
    return "獲得" in (transaction_content or "")


def build_tsv_header() -> List[str]:
    return ["日付", "資産", "分類", "小分類", "内容", "金額", "収入/支出"]