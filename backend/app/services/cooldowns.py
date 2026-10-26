"""有冷却时间（CD）的配方识别。

数据在 `backend/data/recipe_cooldowns.json`（产物名 / 产物物品 ID 两个数组），
不写进数据库：CD 属于游戏机制、不随价格变，改清单重启即生效。

用途：界面「确认采用」的默认制作次数——
- 有 CD：默认 1（一个 CD 周期只能做一次，做多了没有意义）
- 无 CD：默认不限（由算法自己冲到收益最大的次数）
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def _table() -> tuple[frozenset[str], frozenset[int]]:
    f = DATA_DIR / "recipe_cooldowns.json"
    if not f.is_file():
        return frozenset(), frozenset()
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return frozenset(), frozenset()
    names = frozenset(str(x) for x in (raw.get("products") or []))
    ids = frozenset(int(x) for x in (raw.get("item_ids") or []))
    return names, ids


def has_cooldown(product_name: str | None, product_item_id: int | None = None) -> bool:
    """该配方是否有冷却时间。"""
    names, ids = _table()
    if product_item_id is not None and product_item_id in ids:
        return True
    return bool(product_name) and product_name.strip() in names
