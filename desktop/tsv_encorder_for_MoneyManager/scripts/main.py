# -*- coding: utf-8 -*-
from __future__ import annotations


def main() -> int:
    """MMEnc GUIエントリポイント（単一ウィンドウUI）."""
    try:
        from ui_app import run_app
    except Exception as e:
        print(f"GUIを起動できません: {e}")
        return 2

    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())