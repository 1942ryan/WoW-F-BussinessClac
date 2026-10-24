"""路线计算引擎测试。"""

from __future__ import annotations

import math

import pytest

from app.config import get_settings
from app.models import Recipe
from app.schemas import CalcIn
from app.services.calc import (
    _chance,
    _expected_crafts,
    calc_route,
    effective_prices,
    fmt_copper,
    is_limited_vendor,
)
from tests.conftest import add_price, make_item, make_material_source, make_profession, make_recipe, make_server


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


class TestChanceModel:
    """涨点几率：公式模式复现 WoW 经典客户端 (灰档-当前)/(灰档-黄档)。"""

    def _view(self, orange=1, yellow=10, green=12, gray=15):
        from app.services.calc import RecipeView

        return RecipeView(
            id=1,
            product_item_id=None,
            product_name="X",
            product_qty=1,
            is_new=False,
            orange=orange,
            yellow=yellow,
            green=green,
            gray=gray,
            source_type="trainer",
            source_item_id=None,
        )

    def test_formula_orange_is_full(self):
        v = self._view()
        assert _chance(v, 5, "formula", {}) == 1.0
        assert _chance(v, 9.99, "formula", {}) == 1.0

    def test_formula_linear_decay(self):
        v = self._view()  # 黄10 绿12 灰15
        assert _chance(v, 10, "formula", {}) == 1.0      # 刚变黄仍必涨
        assert _chance(v, 12, "formula", {}) == 0.6      # (15-12)/(15-10)
        assert _chance(v, 14, "formula", {}) == 0.2
        assert _chance(v, 15, "formula", {}) == 0.0      # 灰档

    def test_formula_expected_crafts(self):
        v = self._view()
        # 橙档 9 点 → 9 次
        assert _expected_crafts(v, 1, 10, "formula", {}) == 9
        # 黄档 2 点：1/1.0 + 1/0.8 = 2.25
        assert _expected_crafts(v, 10, 12, "formula", {}) == pytest.approx(2.25)
        # 绿档 3 点：1/0.6 + 1/0.4 + 1/0.2
        assert _expected_crafts(v, 12, 15, "formula", {}) == pytest.approx(1 / 0.6 + 1 / 0.4 + 1 / 0.2)

    def test_fixed_mode_uses_band_probs(self):
        v = self._view()
        probs = {"orange": 1.0, "yellow": 0.5, "green": 0.25}
        assert _chance(v, 5, "fixed", probs) == 1.0
        assert _chance(v, 11, "fixed", probs) == 0.5
        assert _chance(v, 13, "fixed", probs) == 0.25


class TestCalcRoute:
    def test_single_recipe_bands_formula(self, db_session):
        """1→15 只有 A 可用；公式模式：橙 9 + 黄 2.25 + 绿 9.17 ≈ 20.42 次。

        同一配方跨档位连续制作合并为一段，档位几率以区间展示（100% → 20%）。
        """
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test", from_skill=1, to_skill=15),
            _settings(),
        )
        assert [s["recipe_name"] for s in result["steps"]] == ["货品A"]
        assert result["steps"][0]["band"] == "orange"
        assert result["steps"][0]["prob"] == 1.0
        assert result["steps"][0]["prob_end"] == pytest.approx(0.2)
        assert result["steps"][0]["crafts"] == pytest.approx(20.4166666, abs=1e-3)
        assert result["totals"]["crafts"] == pytest.approx(20.4166666, abs=1e-3)
        assert result["totals"]["net"] == 0  # 收入正好抵材料

    def test_single_recipe_bands_fixed(self, db_session):
        """fixed 模式（旧口径）：橙 9 + 黄 4 + 绿 12 = 25 次，合并为一段。"""
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=1,
                to_skill=15,
                prob_mode="fixed",
                prob_orange=1.0,
                prob_yellow=0.5,
                prob_green=0.25,
            ),
            _settings(),
        )
        assert len(result["steps"]) == 1
        assert result["steps"][0]["crafts"] == 25
        assert result["totals"]["crafts"] == 25

    def test_switch_by_cost(self, db_session):
        """1→40：公式模式下 B 绿档早期仍有性价比，(500-35)/(40-35)=300/点 < C 500/点。"""
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test", from_skill=1, to_skill=40),
            _settings(),
        )
        names = [s["recipe_name"] for s in result["steps"]]
        assert names[0] == "货品A"
        assert "货品B" in names and "货品C" not in names  # 公式模式下全程 B 更优
        assert names[-1] == "货品B"
        assert result["totals"]["net"] > 0

    def test_switch_by_cost_fixed_prefers_c_late(self, db_session):
        """fixed 模式（黄50/绿25）：35 起 B 绿档 600/点 > C 橙档 500/点 → 切 C。"""
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=1,
                to_skill=40,
                prob_mode="fixed",
                prob_yellow=0.5,
                prob_green=0.25,
            ),
            _settings(),
        )
        names = [s["recipe_name"] for s in result["steps"]]
        assert names[-1] == "货品C"

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

    def test_confirmed_count_limits_usage(self, db_session):
        """确认配方默认 1 次：B 只做 1 次即退出（长 CD 语义），后续回到 A。"""
        _prof, server, _ = _build_scenario(db_session)
        b_id = db_session.query(Recipe).filter_by(product_name="货品B").one().id
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=10,
                to_skill=15,
                confirmed_recipe_ids=[b_id],
            ),
            _settings(),
        )
        b_steps = [s for s in result["steps"] if s["recipe_id"] == b_id]
        assert len(b_steps) == 1
        assert b_steps[0]["crafts"] == 1
        assert any(e["reason"] == "确认次数已用完" for e in result["excluded"])
        # 1 次 B 涨 1 点（10→11），其余交给 A（A 的 11→15 合并为一段）
        assert [s["recipe_name"] for s in result["steps"]] == ["货品B", "货品A"]

    def test_confirmed_count_multi(self, db_session):
        """确认 5 次：B 连续 5 次（10→15 橙档各 1 点）。"""
        _prof, server, _ = _build_scenario(db_session)
        b_id = db_session.query(Recipe).filter_by(product_name="货品B").one().id
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=10,
                to_skill=15,
                confirmed_recipe_ids=[b_id],
                confirmed_counts={b_id: 5},
            ),
            _settings(),
        )
        b_steps = [s for s in result["steps"] if s["recipe_id"] == b_id]
        assert sum(s["crafts"] for s in b_steps) == 5

    def test_recipe_disposition_override(self, db_session):
        """单配方处置覆盖：B 改卖店（vendor 0）后收入为 0，A 仍走全局拍卖。"""
        _prof, server, _ = _build_scenario(db_session)
        b_id = db_session.query(Recipe).filter_by(product_name="货品B").one().id
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=10,
                to_skill=40,
                recipe_dispositions={b_id: "sell_npc"},
            ),
            _settings(),
        )
        b_steps = [s for s in result["steps"] if s["recipe_id"] == b_id]
        assert b_steps and all(s["disposition"] == "sell_npc" for s in b_steps)
        # B 无拍卖价也无卖店价 → 收入 0，净成本 = 材料费
        assert all(s["revenue"] == 0 for s in b_steps)

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
        # 期望制作 20.4167 次 × 10 + 图纸 500
        assert result["totals"]["mat_cost"] == pytest.approx(500 + 10 * 20.4166666, abs=1e-3)
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
        assert result["totals"]["mat_cost"] == pytest.approx(10 * 20.4166666, abs=1e-3)
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


class TestLimitedVendor:
    """NPC 限量材料（草药等）：不采用 NPC 卖价，只认拍卖行。"""

    def test_is_limited_vendor_by_type(self, db_session):
        herb = make_item(db_session, 9650, "银叶草", type="Herb")
        ore = make_item(db_session, 9651, "铜锭", type="Metal & Stone")
        none_type = make_item(db_session, 9652, "无类型")
        assert is_limited_vendor(herb) is True
        assert is_limited_vendor(ore) is False
        assert is_limited_vendor(none_type) is False
        assert is_limited_vendor(None) is False

    def test_herb_ignores_npc_price(self, db_session):
        prof = make_profession(db_session, "herbprof", "草药专业")
        herb = make_item(db_session, 9701, "地根草", vendor_price=20, type="Herb")
        other = make_item(db_session, 9702, "普通材料", vendor_price=15)
        prod = make_item(db_session, 9703, "草药剂")
        # 购物清单把两者都标为商人出售
        make_material_source(db_session, prof, herb, "vendor")
        make_material_source(db_session, prof, other, "vendor")
        make_recipe(db_session, prof, prod, "草药剂", [(herb, 2), (other, 1)], 1, 10, 12, 15)
        server = make_server(db_session, "草药服")
        add_price(db_session, server, herb, 100)   # 拍卖 100
        add_price(db_session, server, other, 200)  # 拍卖 200（NPC 15 更便宜 → 取 15）
        db_session.commit()

        from app.services.calc import _load_recipes
        from app.services.calc import effective_prices

        prices = effective_prices(db_session, server.id, "latest", 0)
        views, _ = _load_recipes(
            db_session, prof, prices,
            CalcIn(server_id=server.id, profession_key="herbprof", from_skill=1, to_skill=15),
        )
        assert len(views) == 1
        v = views[0]
        # 地根草：NPC 20 被忽略，按拍卖 100 ×2；普通材料：min(200, NPC 15)=15
        assert v.mat_cost == 100 * 2 + 15
        herb_line = next(m for m in v.mats if m.item_id == 9701)
        assert herb_line.npc_limited is True
        assert herb_line.npc_price is None  # 限量材料不展示 NPC 价

    def test_herb_without_ah_price_excluded(self, db_session):
        """草药只有 NPC 价、没导入拍卖价 → 配方不参与，原因标注限量。"""
        prof = make_profession(db_session, "herbprof2", "草药专业2")
        herb = make_item(db_session, 9801, "皇血草", vendor_price=30, type="Herb")
        prod = make_item(db_session, 9802, "皇血药剂")
        make_material_source(db_session, prof, herb, "vendor")
        make_recipe(db_session, prof, prod, "皇血药剂", [(herb, 1)], 1, 10, 12, 15)
        server = make_server(db_session, "草药服2")
        db_session.commit()
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="herbprof2", from_skill=1, to_skill=15),
            _settings(),
        )
        assert result["steps"] == []
        assert any("NPC限量" in e["reason"] for e in result["excluded"])

    def test_materials_list_uses_ah_for_limited(self, db_session):
        """限量材料（草药）只按拍卖行计价：即使 NPC 有售也不取 25 铜的卖店价。"""
        prof = make_profession(db_session, "herbprof3", "草药专业3")
        herb = make_item(db_session, 9901, "跌打草", vendor_price=25, type="Herb")
        prod = make_item(db_session, 9902, "跌打药剂")
        make_material_source(db_session, prof, herb, "vendor")
        make_recipe(db_session, prof, prod, "跌打药剂", [(herb, 1)], 1, 10, 12, 15)
        server = make_server(db_session, "草药服3")
        add_price(db_session, server, herb, 80)
        db_session.commit()
        result = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="herbprof3", from_skill=1, to_skill=15),
            _settings(),
        )
        line = next(m for m in result["materials"] if m["item_id"] == 9901)
        assert line["price_source"] == "ah"  # 只走拍卖行
        assert line["unit_price"] == 80  # 不取 NPC 卖店价 25


class TestFmtCopper:
    def test_format(self):
        assert fmt_copper(0) == "0铜"
        assert fmt_copper(12304) == "1金23银4铜"
        assert fmt_copper(250) == "2银50铜"
        assert fmt_copper(-150) == "-1银50铜"
