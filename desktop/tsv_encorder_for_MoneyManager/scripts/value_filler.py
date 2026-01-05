# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Tuple

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



# NOTE:
# 金額(F列)・収入/支出(G列)の判定は table_transformer / encoder_core 側で行う
def fill_category(store_name: str, preset: Preset) -> Tuple[str, str]:
    """I列（取引先）から分類/内容を埋める（代表語部分一致）。

    - category → C列（分類）
    - sub_category → E列（内容）
    ※ D列（小分類）は本ツールでは使用しない。
    """
    key = match_store_key(store_name, preset)
    if key is None:
        # ここに来るのは「検証」をすり抜けたケースなので基本は例外にする
        raise KeyError(f"unknown store: {store_name}")

    rec = preset.store_mapping[key]
    return rec.get("category", ""), rec.get("sub_category", "")