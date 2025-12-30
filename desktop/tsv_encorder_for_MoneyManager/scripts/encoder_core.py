# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Tuple

from preset_manager import Preset, validate_unknown_stores
from table_transformer import build_tsv_header, should_skip_row
from value_filler import decide_amount_and_io, decide_asset, fill_category


REQUIRED_HEADERS = [
    "取引日",
    "出金金額（円）",
    "入金金額（円）",
    "海外出金金額",
    "取引内容",
    "取引先",
    "取引方法",
]


def read_paypay_csv(csv_path: str | Path) -> Tuple[List[Dict[str, str]], List[str]]:
    """PayPay CSVをDict行として読み込む。"""
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = [row for row in reader]
    return rows, headers


def validate_headers(headers: List[str]) -> List[str]:
    """必須ヘッダーが揃っているか確認し、不足ヘッダーを返す。"""
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    return missing


def extract_store_names(rows: List[Dict[str, str]]) -> List[str]:
    """検証用に I列（取引先）相当を集める。"""
    return [(r.get("取引先") or "").strip() for r in rows if (r.get("取引先") or "").strip()]


def transform_to_tsv_rows(rows: List[Dict[str, str]], preset: Preset) -> List[List[str]]:
    """CSV行をTSV行（List[str]）に変換する。"""
    out: List[List[str]] = []
    for r in rows:
        date = (r.get("取引日") or "").strip()
        b = r.get("出金金額（円）") or ""
        c = r.get("入金金額（円）") or ""
        d = r.get("海外出金金額") or ""
        h = r.get("取引内容") or ""
        i = r.get("取引先") or ""
        j = r.get("取引方法") or ""

        if should_skip_row(h):
            continue

        amount, io = decide_amount_and_io(b, c, d)
        asset = decide_asset(j)
        category, sub_category = fill_category(i, preset)

        # 内容(E列)はH列（取引内容）を入れる（仕様）
        content = h.strip()

        out.append([
            date,
            asset,
            category,
            sub_category,
            content,
            str(amount),
            io,
        ])
    return out


def write_tsv(tsv_path: str | Path, rows: List[List[str]]) -> None:
    """TSVをUTF-8で出力する。"""
    path = Path(tsv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(build_tsv_header())
        w.writerows(rows)


def run_encode(csv_path: str | Path, preset_path: str | Path) -> Tuple[bool, List[str]]:
    """検証→変換を実行する（未登録があれば中断）。

    Returns:
        (success, messages)
    """
    from preset_manager import load_preset

    preset = load_preset(preset_path)
    rows, headers = read_paypay_csv(csv_path)

    missing = validate_headers(headers)
    if missing:
        return False, [f"必須ヘッダー不足: {', '.join(missing)}"]

    unknown = validate_unknown_stores(extract_store_names(rows), preset)
    if unknown:
        msgs = ["未登録店舗があります。登録してから再実行してください。"]
        msgs += [f"- {u}" for u in unknown]
        return False, msgs

    tsv_rows = transform_to_tsv_rows(rows, preset)

    out_path = Path(csv_path).with_suffix("")  # foo.csv -> foo
    tsv_path = str(out_path) + "_encoded.tsv"
    write_tsv(tsv_path, tsv_rows)

    return True, [f"OK: {tsv_path}"]