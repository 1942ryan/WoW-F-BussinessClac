"""AUC 导入解析测试。"""

from __future__ import annotations

import pytest

from app.services.importer import ImportParseError, normalize_name, parse_csv, parse_price


class TestParsePrice:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("25", 25),
            ("2500", 2500),
            ("1银", 100),
            ("25银", 2500),
            ("1金", 10000),
            ("1金23银4铜", 12304),
            ("1g23s4c", 12304),
            ("1.5g", 15000),
            ("0.5银", 50),
            ("1G", 10000),
            ("  100  ", 100),
        ],
    )
    def test_formats(self, text, expected):
        assert parse_price(text) == expected

    def test_invalid(self):
        with pytest.raises(ImportParseError):
            parse_price("")
        with pytest.raises(ImportParseError):
            parse_price("abc")


class TestNormalizeName:
    def test_fullwidth_and_space(self):
        assert normalize_name(" 铜　锭 ") == "铜锭"

    def test_case(self):
        assert normalize_name("Copper Bar") == "copperbar"


class TestParseCsv:
    def test_documented_format(self):
        data = "物品名称,单价\n铜锭,25\n秘银锭,1银20铜\n".encode("utf-8")
        rows = parse_csv(data)
        assert len(rows) == 2
        assert rows[0].raw_name == "铜锭" and rows[0].price == 25
        assert rows[1].raw_name == "秘银锭" and rows[1].price == 120

    def test_english_header(self):
        data = "item,price\nCopper Bar,30\n".encode("utf-8")
        rows = parse_csv(data)
        assert rows[0].raw_name == "Copper Bar" and rows[0].price == 30

    def test_gbk_encoding(self):
        data = "物品名称,单价\n铜锭,25\n".encode("gb18030")
        rows = parse_csv(data)
        assert rows[0].raw_name == "铜锭"

    def test_item_link_format(self):
        data = (
            "|cff1eff00|Hitem:2840:0:0:0:0:0:0:0|h[铜锭]|h|r,25\n"
            "|cffffffff|Hitem:3575:0:0:0|h[铁锭]|h|r,80\n"
        ).encode("utf-8")
        rows = parse_csv(data)
        assert rows[0].item_id == 2840 and rows[0].raw_name == "铜锭"
        assert rows[1].item_id == 3575 and rows[1].price == 80

    def test_no_header_two_columns(self):
        data = "铜锭,25\n铁锭,80\n".encode("utf-8")
        rows = parse_csv(data)
        assert len(rows) == 2 and rows[1].price == 80

    def test_skip_bad_price_rows(self):
        data = "物品名称,单价\n铜锭,25\n汇总行,-\n".encode("utf-8")
        rows = parse_csv(data)
        assert len(rows) == 1

    def test_empty_raises(self):
        with pytest.raises(ImportParseError):
            parse_csv("".encode("utf-8"))
        with pytest.raises(ImportParseError):
            parse_csv("物品名称,单价\n".encode("utf-8"))

    def test_auc_export_format(self):
        """AUC 拍卖行导出：价格在前、带物品等级（同名不同物品消歧用）。"""
        data = (
            '"价格","名称","物品等级","拥有？","可售数量"\n'
            '115,"劣质火药",5,"",1169\n'
            '200,"劣质炸药",20,"",61\n'
            '90,"劣质炸药",10,"",399\n'
        ).encode("utf-8")
        rows = parse_csv(data)
        assert len(rows) == 3
        assert rows[0].raw_name == "劣质火药" and rows[0].price == 115
        assert rows[0].item_level == 5
        assert rows[1].raw_name == "劣质炸药" and rows[1].price == 200
        assert rows[1].item_level == 20
        assert rows[2].raw_name == "劣质炸药" and rows[2].price == 90
        assert rows[2].item_level == 10

    def test_auc_export_gbk(self):
        data = (
            '"价格","名称","物品等级","拥有？","可售数量"\n'
            '115,"劣质火药",5,"",1169\n'
        ).encode("gb18030")
        rows = parse_csv(data)
        assert rows[0].raw_name == "劣质火药" and rows[0].price == 115
