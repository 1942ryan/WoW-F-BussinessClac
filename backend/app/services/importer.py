"""AUC 插件导出价格解析与导入。

支持三种输入（UTF-8 / GBK 编码自动识别）：
1. 文档格式 CSV（表头 + 名称/价格列）：
       物品名称,单价
       铜锭,25
       秘银锭,1银20铜
2. AUC 拍卖行导出（价格在前，带物品等级，用于同名不同物品消歧）：
       "价格","名称","物品等级","拥有？","可售数量"
       115,"劣质火药",5,"",1169
       200,"劣质炸药",20,"",61
       90,"劣质炸药",10,"",399
3. 物品链接格式（Auctioneer / TSM 等插件常见导出）：
       |cff1eff00|Hitem:2840:0:0:0:0:0:0:0|h[铜锭]|h|r,25
   链接格式直接按物品 ID 匹配，最可靠。

价格列支持：纯数字（铜）、1g23s4c / 1金23银4铜、1.5g（小数金）、25银 等写法。
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

NAME_HEADERS = {"物品", "物品名称", "名称", "名字", "道具", "item", "itemname", "name"}
PRICE_HEADERS = {"单价", "价格", "售价", "拍卖价", "price", "unitprice", "cost"}
QTY_HEADERS = {"数量", "组数量", "stack", "quantity", "count", "num"}
LEVEL_HEADERS = {"物品等级", "等级", "物品级别", "装等", "itemlevel", "level", "ilvl"}

_UNIT = {"g": 10000, "金": 10000, "s": 100, "银": 100, "c": 1, "铜": 1}


@dataclass
class ParsedRow:
    raw_name: str
    price: int  # 铜
    item_id: int | None = None  # 链接格式可直接拿到 ID
    item_level: int | None = None  # AUC 导出带物品等级，用于同名不同物品消歧


class ImportParseError(ValueError):
    pass


def decode_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ImportParseError("无法识别文件编码（支持 UTF-8 / GBK）")


def parse_price(text: str) -> int:
    """解析价格单元格 → 铜。"""
    s = text.strip().lower().replace(",", "")
    if not s:
        raise ImportParseError("价格为空")
    # 纯数字 → 铜
    if re.fullmatch(r"\d+", s):
        return int(s)
    # 1.5g / 2.5银 等小数
    m = re.fullmatch(r"([\d.]+)\s*([gsc金银铜])", s)
    if m:
        return int(round(float(m.group(1)) * _UNIT[m.group(2)]))
    # 1g23s4c / 1金23银4铜 组合
    parts = re.findall(r"([\d.]+)\s*([gsc金银铜])", s)
    if parts:
        return int(round(sum(float(n) * _UNIT[u] for n, u in parts)))
    # 带小数点的纯数字当铜处理
    m = re.fullmatch(r"([\d.]+)", s)
    if m:
        return int(round(float(m.group(1))))
    raise ImportParseError(f"无法解析价格: {text!r}")


_ITEM_LINK = re.compile(r"Hitem:(\d+)")


def normalize_name(name: str) -> str:
    """名称归一化：去首尾及内部空白、全角转半角、小写。"""
    s = unicodedata.normalize("NFKC", name).strip().lower()
    return re.sub(r"\s+", "", s)


def parse_csv(data: bytes) -> list[ParsedRow]:
    """解析导出文件 → ParsedRow 列表。"""
    text = decode_bytes(data)
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ImportParseError("文件为空")

    header = [normalize_name(c) for c in rows[0]]
    name_idx = next((i for i, h in enumerate(header) if h in NAME_HEADERS), None)
    price_idx = next((i for i, h in enumerate(header) if h in PRICE_HEADERS), None)
    level_idx = next((i for i, h in enumerate(header) if h in LEVEL_HEADERS), None)

    parsed: list[ParsedRow] = []
    if name_idx is not None and price_idx is not None:
        body = rows[1:]
    else:
        # 无表头：按「名称,价格」两列处理
        name_idx, price_idx, level_idx, body = 0, 1, None, rows

    for r in body:
        if len(r) <= max(name_idx, price_idx):
            continue
        raw = r[name_idx].strip()
        price_text = r[price_idx].strip()
        if not raw or not price_text:
            continue
        item_id = None
        m = _ITEM_LINK.search(raw)
        if m:
            item_id = int(m.group(1))
            bracket = re.search(r"\|h\[([^\]]+)\]", raw)
            raw = bracket.group(1) if bracket else raw
        level = None
        if level_idx is not None and len(r) > level_idx:
            lm = re.search(r"\d+", r[level_idx].strip())
            if lm:
                level = int(lm.group())
        try:
            price = parse_price(price_text)
        except ImportParseError:
            continue  # 跳过无法解析的价格行（如汇总行）
        parsed.append(
            ParsedRow(raw_name=raw, price=price, item_id=item_id, item_level=level)
        )

    if not parsed:
        raise ImportParseError("未解析到有效数据行，请检查表头是否包含名称与价格列")
    return parsed
