"""路线计算引擎测试。"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.models import Recipe
from app.schemas import CalcIn
from app.services.calc import calc_route, effective_prices, fmt_copper
from tests.conftest import add_price, make_item, make_profession, make_recipe, make_server


def _settings():
    return get_settings()


def _build_scenario(db):
    """1→60 小专业：A(1-15) B(10-40) C(30-60)；材料 m1@50、m2@500；A 拍卖价 100。"""
    prof = make_profession(db, "test", "测试专业")
    m1 = make_item(db, 9001, "材料甲", vendor_price=0)
    m2 = make_item(db, 9002, "材料乙", vendor_price=0)
    a = make_item(db, 9101, "货品A", vendor_price=0)
    b = make_item(db, 9102, "货品B", vendor_price=0)
    c = make_item(db, 9103, "货品C", vendor_price=0)
    # A：2×m1（100铜），拍卖 100 → 净 0
    make_recipe(db, prof, a, "货品A", [(m1, 2)], 1, 10, 12, 15)
    # B：3×m1（150铜），无收入
    make_recipe(db, prof, b, "货品B", [(m1, 3)], 10, 30, 35, 40)
    # C：1×m2（500铜），无收入
    make_recipe(db, prof, c, "货品C", [(m2, 1)], 30, 45, 50, 60)
    server = make_server(db)
    add_price(db, server, m1, 50)
    add_price(db, server, m2, 500)
    add_price(db, server, a, 100)
    db.commit()
    return prof, server, {"m1": m1, "m2": m2, "a": a, "b": b, "c": c}


class TestEffectivePrices:
    def test_latest_takes_newest(self, db_session):
        _prof, server, items = _build_scenario(db_session)
        add_price(db_session, server, items["m1"], 60)
        db_session.commit()
        assert effective_prices(db_session, server.id, "latest")[9001] == 60

    def test_median(self, db_session):
        _prof, server, items = _build_scenario(db_session)
        add_price(db_session, server, items["m1"], 70)
        db_session.commit()
        # 50 与 70 两个数，中位数取均值 60
        assert effective_prices(db_session, server.id, "median")[9001] == 60


class TestCalcRoute:
    def test_single_recipe_bands(self, db_session):
        """1→15 只有 A 可用：橙 9 次 + 黄 4 次 + 绿 12 次 = 25 次，净成本 0。"""
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test", from_skill=1, to_skill=15),
            _settings(),
        )
        assert [s["recipe_name"] for s in result["steps"]] == ["货品A"] * 3
        assert [s["band"] for s in result["steps"]] == ["orange", "yellow", "green"]
        assert [s["crafts"] for s in result["steps"]] == [9, 4, 12]
        assert result["totals"]["crafts"] == 25
        assert result["totals"]["net"] == 0  # 收入正好抵材料

    def test_switch_by_cost(self, db_session):
        """1→40：A 用到 15 灰，之后 B 比 C 便宜（B 黄档 300/点 < C 橙档 500/点）。"""
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test", from_skill=1, to_skill=40),
            _settings(),
        )
        names = [s["recipe_name"] for s in result["steps"]]
        assert names[:3] == ["货品A"] * 3
        assert "货品B" in names and "货品C" in names
        assert names[-1] == "货品C"  # 35 起 B 绿档 600/点 > C 橙档 500/点
        assert result["totals"]["net"] > 0

    def test_block_recipe_switches(self, db_session):
        _prof, server, _ = _build_scenario(db_session)
        a_id = db_session.query(Recipe).filter_by(product_name="货品A").one().id
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=10,
                to_skill=40,
                blocked_recipe_ids=[a_id],
            ),
            _settings(),
        )
        names = [s["recipe_name"] for s in result["steps"]]
        assert "货品A" not in names
        assert names[0] == "货品B"

    def test_block_item_makes_unusable(self, db_session):
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=30,
                to_skill=60,
                blocked_item_ids=[9002],
            ),
            _settings(),
        )
        assert any("无可用配方" in w for w in result["warnings"])
        assert any(e["reason"].startswith("材料无价格") for e in result["excluded"])

    def test_confirmed_priority(self, db_session):
        _prof, server, _ = _build_scenario(db_session)
        b_id = db_session.query(Recipe).filter_by(product_name="货品B").one().id
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=10,
                to_skill=40,
                confirmed_recipe_ids=[b_id],
            ),
            _settings(),
        )
        assert result["steps"][0]["recipe_name"] == "货品B"
        assert result["steps"][0]["confirmed"] is True

    def test_missing_price_excluded(self, db_session):
        _prof, server, _ = _build_scenario(db_session)
        empty = make_server(db_session, "空服")
        result = calc_route(
            db_session,
            CalcIn(server_id=empty.id, profession_key="test", from_skill=1, to_skill=15),
            _settings(),
        )
        assert result["steps"] == []
        assert all(e["reason"].startswith("材料无价格") for e in result["excluded"])

    def test_exclude_designs(self, db_session):
        prof = make_profession(db_session, "test2", "设计图专业")
        mat = make_item(db_session, 9201, "图纸材料")
        design = make_item(db_session, 9202, "设计图：X")
        prod = make_item(db_session, 9203, "图纸贷")
        make_recipe(
            db_session, prof, prod, "图纸贷", [(mat, 1)], 1, 10, 12, 15, source_type="design"
        )
        server = make_server(db_session, "图纸服")
        add_price(db_session, server, mat, 10)
        db_session.commit()
        r_off = calc_route(
            db_session,
            CalcIn(
                server_id=server.id, profession_key="test2", from_skill=1, to_skill=15,
                include_designs=False,
            ),
            _settings(),
        )
        assert r_off["steps"] == []
        assert any("设计图配方未启用" in e["reason"] for e in r_off["excluded"])

    def test_design_cost_ah_counts_once(self, db_session):
        """设计图配方：AH 计价时图纸成本一次性计入，不随制作次数增加。"""
        prof = make_profession(db_session, "test3", "图纸成本专业")
        mat = make_item(db_session, 9301, "图纸材料")
        design = make_item(db_session, 9302, "设计图：一次性")
        prod = make_item(db_session, 9303, "图纸成品")
        make_recipe(
            db_session, prof, prod, "图纸成品", [(mat, 1)], 1, 10, 12, 15,
            source_type="design", source_item=design,
        )
        server = make_server(db_session, "图纸成本服")
        add_price(db_session, server, mat, 10)
        add_price(db_session, server, design, 500)
        db_session.commit()
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id, profession_key="test3", from_skill=1, to_skill=15,
                design_cost="ah",
            ),
            _settings(),
        )
        # 3 段（橙/黄/绿），图纸只在第一段计一次
        design_steps = [s for s in result["steps"] if s["design_cost"]]
        assert len(design_steps) == 1
        assert design_steps[0]["design_cost"] == 500
        assert design_steps[0]["design_name"] == "设计图：一次性"
        # 材料 = 25 次 × 10 + 图纸 500
        assert result["totals"]["mat_cost"] == 25 * 10 + 500
        # 材料清单里图纸单独一行、数量 1
        dline = [m for m in result["materials"] if m["kind"] == "design"]
        assert len(dline) == 1 and dline[0]["qty"] == 1 and dline[0]["cost"] == 500

    def test_design_cost_drop_ignored(self, db_session):
        """掉落图纸：不计成本，也无警告。"""
        prof = make_profession(db_session, "test4", "掉落图纸专业")
        mat = make_item(db_session, 9401, "掉落材料")
        design = make_item(db_session, 9402, "设计图：掉落")
        prod = make_item(db_session, 9403, "掉落成品")
        make_recipe(
            db_session, prof, prod, "掉落成品", [(mat, 1)], 1, 10, 12, 15,
            source_type="design", source_item=design,
        )
        server = make_server(db_session, "掉落服")
        add_price(db_session, server, mat, 10)
        add_price(db_session, server, design, 500)
        db_session.commit()
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id, profession_key="test4", from_skill=1, to_skill=15,
                design_cost="drop",
            ),
            _settings(),
        )
        assert all(s["design_cost"] == 0 for s in result["steps"])
        assert result["totals"]["mat_cost"] == 25 * 10
        assert not any("设计图" in w for w in result["warnings"])

    def test_design_missing_price_warns(self, db_session):
        """AH 计价但图纸无价格：按 0 计并警告。"""
        prof = make_profession(db_session, "test5", "缺价图纸专业")
        mat = make_item(db_session, 9501, "缺价材料")
        design = make_item(db_session, 9502, "设计图：缺价")
        prod = make_item(db_session, 9503, "缺价成品")
        make_recipe(
            db_session, prof, prod, "缺价成品", [(mat, 1)], 1, 10, 12, 15,
            source_type="design", source_item=design,
        )
        server = make_server(db_session, "缺价服")
        add_price(db_session, server, mat, 10)
        db_session.commit()
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test5", from_skill=1, to_skill=15),
            _settings(),
        )
        assert any("暂无价格" in w for w in result["warnings"])

    def test_block_design_item(self, db_session):
        """屏蔽设计图物品 → 该设计图配方不参与计算。"""
        prof = make_profession(db_session, "test6", "屏蔽图纸专业")
        mat = make_item(db_session, 9601, "屏蔽材料")
        design = make_item(db_session, 9602, "设计图：屏蔽")
        prod = make_item(db_session, 9603, "屏蔽成品")
        make_recipe(
            db_session, prof, prod, "屏蔽成品", [(mat, 1)], 1, 10, 12, 15,
            source_type="design", source_item=design,
        )
        server = make_server(db_session, "屏蔽服")
        add_price(db_session, server, mat, 10)
        db_session.commit()
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id, profession_key="test6", from_skill=1, to_skill=15,
                blocked_item_ids=[9602],
            ),
            _settings(),
        )
        assert result["steps"] == []
        assert any("设计图物品被屏蔽" in e["reason"] for e in result["excluded"])

    def test_invalid_range(self, db_session):
        _prof, server, _ = _build_scenario(db_session)
        with pytest.raises(ValueError):
            calc_route(
                db_session,
                CalcIn(server_id=server.id, profession_key="test", from_skill=40, to_skill=40),
                _settings(),
            )


class TestFmtCopper:
    def test_format(self):
        assert fmt_copper(0) == "0铜"
        assert fmt_copper(12304) == "1金23银4铜"
        assert fmt_copper(250) == "2银50铜"
        assert fmt_copper(-150) == "-1银50铜"
