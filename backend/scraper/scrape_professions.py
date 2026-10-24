"""抓取 wowforever.wclbox.com 专业配方页，解析为结构化 JSON。

输入：_research/prof_*.html（已下载的原始页面，见 README）
输出：backend/data/professions.json

用法：
    python scrape_professions.py [--html-dir DIR] [--out FILE]

页面结构（2026-10 实测）：
- 配方区 id="peifang"，含两个 <table>：首个 120 行，其余在 <details class="zk-recipe-rest"> 里
- 每行：成品 | 材料 | 技能 | 来源
  - 成品：<a class="zk-item" data-item="ID"> + <span class="zk-name zk-qN">名称</span>；
    附魔法术类成品为 <span class="zk-name zk-ench">附魔护腕 - 劣质耐力<small>耐力 +2</small></span>（无 data-item）
  - 产出倍率：<small class="zk-x">×3</small>（在成品链接内）
  - 无限新增标记：<em class="zk-new">新</em>
  - 材料：<a class="zk-mat" data-item="ID" aria-label="铜锭 ×1">
  - 技能：<b class="zk-t-o">1</b>（学会/橙）+ <i class="zk-t-y">10</i>（黄）+ <i class="zk-t-g">12</i>（绿）+ <i class="zk-t-x">15</i>（灰）
  - 来源：<span class="zk-src-t">训练师</span> 或 <span class="zk-src"><a data-item="ID">设计图：X</a></span>
- 购物清单 id="caigou"：材料按「商人出售 / 采集或拍卖行 / 途中自制」分组，含 data-item 与数量
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROFESSION_ORDER = [
    ("blacksmithing", "锻造"),
    ("leatherworking", "制皮"),
    ("tailoring", "裁缝"),
    ("alchemy", "炼金术"),
    ("enchanting", "附魔"),
    ("engineering", "工程学"),
    ("cooking", "烹饪"),
    ("first-aid", "急救"),
    ("mining", "采矿"),
]


def _int(text: str) -> int | None:
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def parse_recipe_row(row: str) -> dict | None:
    """解析单行 <tr>，返回配方 dict；无法解析返回 None。"""
    # ---- 成品 ----
    made = re.search(r'<td><span class="zk-made">(.*?)</td>', row, re.S)
    if not made:
        return None
    made_html = made.group(1)

    product: dict = {"item_id": None, "kind": "item"}
    ench = re.search(r'zk-name zk-ench">(.*?)</span>', made_html, re.S)
    if ench:
        # 附魔法术类成品：附魔护腕 - 劣质耐力<small>耐力 +2</small>
        name_html = ench.group(1)
        small = re.search(r"<small>(.*?)</small>", name_html, re.S)
        suffix = f"（{small.group(1).strip()}）" if small else ""
        name = re.sub(r"<small>.*?</small>", "", name_html, flags=re.S)
        name = re.sub(r"<[^>]+>", "", name).strip()
        product = {"item_id": None, "kind": "enchant", "name": name + suffix}
    else:
        item = re.search(
            r'<a class="zk-item" data-item="(\d+)"[^>]*>.*?zk-name zk-q(\d+)">([^<]+)</span>',
            made_html,
            re.S,
        )
        if not item:
            return None
        product = {
            "item_id": int(item.group(1)),
            "kind": "item",
            "name": item.group(3).strip(),
            "quality": int(item.group(2)),
        }
        yld = re.search(r'<small class="zk-x">×\s*<!-- -->\s*(\d+)', made_html)
        if not yld:
            yld = re.search(r'<small class="zk-x">×\s*(\d+)', made_html)
        product["yield_qty"] = int(yld.group(1)) if yld else 1
    product["is_new"] = 'class="zk-new"' in made_html

    # ---- 材料 ----
    materials = []
    mats_html = re.search(r'<td><span class="zk-mats">(.*?)</td>', row, re.S)
    if mats_html:
        for m in re.finditer(
            r'<a class="zk-mat" data-item="(\d+)"[^>]*aria-label="([^"]+)"', mats_html.group(1)
        ):
            label = m.group(2)  # 形如 "铜锭 ×1"
            parts = re.split(r"[×x]", label)
            mat_name = parts[0].strip()
            qty = _int(parts[1]) if len(parts) > 1 else 1
            materials.append(
                {"item_id": int(m.group(1)), "name": mat_name, "qty": qty or 1}
            )

    # ---- 技能四档 ----
    skill = re.search(
        r'<b class="zk-t-o">(\d+)</b>.*?<i class="zk-t-y">(\d+)</i>.*?<i class="zk-t-g">(\d+)</i>.*?<i class="zk-t-x">(\d+)</i>',
        row,
        re.S,
    )
    if not skill:
        return None
    orange, yellow, green, gray = (int(g) for g in skill.groups())

    # ---- 来源 ----
    source: dict = {"type": "trainer", "item_id": None, "name": None}
    src_t = re.search(r'<span class="zk-src-t">([^<]+)</span>', row)
    if src_t:
        source = {"type": src_t.group(1).strip(), "item_id": None, "name": None}
    else:
        src_i = re.search(
            r'<span class="zk-src"><a class="zk-item" data-item="(\d+)"[^>]*>.*?zk-name[^>]*>([^<]+)</span>',
            row,
            re.S,
        )
        if src_i:
            source = {
                "type": "design",
                "item_id": int(src_i.group(1)),
                "name": src_i.group(2).strip(),
            }

    return {
        "product": product,
        "materials": materials,
        "skill": {"orange": orange, "yellow": yellow, "green": green, "gray": gray},
        "source": source,
    }


def parse_shopping_list(html: str) -> dict[int, str]:
    """解析购物清单，返回 {item_id: kind}，kind ∈ vendor / gather_ah / crafted。"""
    i = html.find('id="caigou"')
    if i < 0:
        return {}
    seg = html[i : html.find("id=", i + 10) if html.find("id=", i + 10) > 0 else i + 60000]
    seg = html[i : i + 80000]
    result: dict[int, str] = {}
    # 按分组标题切分
    group_pattern = re.compile(r"(商人出售|采集或拍卖行|途中自制)")
    marks = list(group_pattern.finditer(seg))
    kind_map = {"商人出售": "vendor", "采集或拍卖行": "gather_ah", "途中自制": "crafted"}
    for idx, mk in enumerate(marks):
        start = mk.end()
        end = marks[idx + 1].start() if idx + 1 < len(marks) else len(seg)
        chunk = seg[start:end]
        for m in re.finditer(r'data-item="(\d+)"', chunk):
            item_id = int(m.group(1))
            kind = kind_map[mk.group(1)]
            # vendor 优先级最高，crafted 次之（同一材料可能出现在多组）
            priority = {"vendor": 3, "crafted": 2, "gather_ah": 1}
            if item_id not in result or priority[kind] > priority[result[item_id]]:
                result[item_id] = kind
    return result


def parse_profession_page(path: Path, key: str, name: str) -> dict:
    html = path.read_text(encoding="utf-8")
    i = html.find('id="peifang"')
    if i < 0:
        raise ValueError(f"{path.name}: 未找到配方区")
    tables = re.findall(r"<table.*?</table>", html[i:], re.S)
    recipes = []
    for tbl in tables:
        rows = re.findall(r"<tr>.*?</tr>", tbl, re.S)
        for row in rows:
            if 'scope="col"' in row:
                continue
            rec = parse_recipe_row(row)
            if rec:
                recipes.append(rec)
    # 去重（同一成品可能因分类重复出现）
    seen: set = set()
    unique = []
    for r in recipes:
        k = (r["product"]["item_id"], r["product"]["name"])
        if k in seen:
            continue
        seen.add(k)
        unique.append(r)
    material_sources = parse_shopping_list(html)
    return {
        "key": key,
        "name": name,
        "recipes": unique,
        "material_sources": {str(k): v for k, v in material_sources.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[2]  # 项目根目录
    ap.add_argument("--html-dir", default=str(root / "_research"))
    ap.add_argument("--out", default=str(root / "backend" / "data" / "professions.json"))
    args = ap.parse_args()

    html_dir = Path(args.html_dir)
    professions = []
    for key, name in PROFESSION_ORDER:
        path = html_dir / f"prof_{key}.html"
        if not path.exists():
            print(f"[warn] 缺少 {path.name}，跳过")
            continue
        prof = parse_profession_page(path, key, name)
        professions.append(prof)
        max_skill = max(r["skill"]["gray"] for r in prof["recipes"])
        print(
            f"{name}: {len(prof['recipes'])} 个配方, 材料来源标注 {len(prof['material_sources'])} 项, "
            f"最高灰档技能 {max_skill}"
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"professions": professions}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(p["recipes"]) for p in professions)
    print(f"\n共 {total} 个配方 -> {out}")


if __name__ == "__main__":
    main()
