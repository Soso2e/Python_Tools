# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


@dataclass(frozen=True)
class Preset:
    """変換プリセット（YAML由来）."""
    name: str
    # 例: {"セブン": {"category": "食費", "sub_category": "コンビニ"}, ...}
    store_mapping: Dict[str, Dict[str, str]]


def load_preset(preset_path: str | Path) -> Preset:
    """YAMLプリセットを読み込む。

    Args:
        preset_path: YAMLファイルパス。

    Returns:
        Preset: 読み込んだプリセット。

    Raises:
        FileNotFoundError: ファイルが見つからない。
        ValueError: YAMLの形式が不正。
    """
    path = Path(preset_path)
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name = str(data.get("name", path.stem))
    store_mapping = data.get("store_mapping", {})

    if not isinstance(store_mapping, dict):
        raise ValueError("store_mapping must be a dict")

    # normalize structure
    normalized: Dict[str, Dict[str, str]] = {}
    for key, val in store_mapping.items():
        if not isinstance(val, dict):
            raise ValueError(f"store_mapping['{key}'] must be a dict")
        cat = str(val.get("category", "")).strip()
        sub = str(val.get("sub_category", "")).strip()
        normalized[str(key).strip()] = {"category": cat, "sub_category": sub}

    return Preset(name=name, store_mapping=normalized)


def match_store_key(store_name: str, preset: Preset) -> str | None:
    """取引先名(I列)に対し、代表語キーの部分一致でヒットしたキーを返す。

    例: store_name="セブンイレブン 新宿西口店" → "セブン"

    Args:
        store_name: 取引先名（I列）。
        preset: プリセット。

    Returns:
        str | None: ヒットした代表語キー。ヒットなしならNone。
    """
    s = (store_name or "").strip()
    if not s:
        return None

    # 代表語キーが短いものほど誤爆しやすいので、長いキー優先で評価
    keys = sorted(preset.store_mapping.keys(), key=len, reverse=True)
    for k in keys:
        if k and k in s:
            return k
    return None


def validate_unknown_stores(store_names: List[str], preset: Preset) -> List[str]:
    """未登録店舗を抽出する。

    Args:
        store_names: 取引先名(I列)のリスト（重複ありでOK）。
        preset: プリセット。

    Returns:
        List[str]: 未登録店舗名（ユニーク、入力順優先）。
    """
    unknown: List[str] = []
    seen: set[str] = set()

    for raw in store_names:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)

        if match_store_key(name, preset) is None:
            unknown.append(name)

    return unknown