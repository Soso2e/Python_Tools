# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Tuple

from preset_manager import Preset, match_store_key


CARD_KEYWORDS = ("カード", "クレジット")


def decide_asset(method_text: str) -> str:
    """J列（取引方法）から資産（PayPay/カード）を判定する。"""
    t = (method_text or "").strip()
    if any(k in t for k in CARD_KEYWORDS):
        return "カード"
    return "PayPay"


def parse_int_amount(value: str) -> int:
    """金額文字列を整数にパースする（カンマ除去）。"""
    s = (value or "").strip().replace(",", "")
    if s == "":
        raise ValueError("amount is empty")
    # PayPay側がマイナスを出す可能性があるなら許容（不要ならここで弾ける）
    return int(float(s)) if "." in s else int(s)


def decide_amount_and_io(withdraw_jpy: str, deposit_jpy: str, overseas_withdraw: str) -> Tuple[int, str]:
    """B/C/D のどれか1つのみ記入、という前提で金額と収入/支出を決定する。

    B または D → 支出
    C → 収入
    """
    b = (withdraw_jpy or "").strip()
    c = (deposit_jpy or "").strip()
    d = (overseas_withdraw or "").strip()

    filled = [x for x in (b, c, d) if x != ""]
    if len(filled) != 1:
        raise ValueError(f"amount columns must have exactly 1 value. B='{b}', C='{c}', D='{d}'")

    if b != "":
        return parse_int_amount(b), "支出"
    if d != "":
        return parse_int_amount(d), "支出"
    return parse_int_amount(c), "収入"


def fill_category(store_name: str, preset: Preset) -> Tuple[str, str]:
    """I列（取引先）からカテゴリ/小カテゴリを埋める（代表語部分一致）。"""
    key = match_store_key(store_name, preset)
    if key is None:
        # ここに来るのは「検証」をすり抜けたケースなので基本は例外にする
        raise KeyError(f"unknown store: {store_name}")

    rec = preset.store_mapping[key]
    return rec.get("category", ""), rec.get("sub_category", "")