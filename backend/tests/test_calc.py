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
    ah_cut_of,
    ah_net_of,
    calc_route,
    effective_prices,
    fmt_copper,
    is_limited_vendor,
    pick_revenue,
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
        # 拍卖行收入按到手价（扣 5% 手续费）计：收入不再正好抵材料，
        # 净成本 = 成交额 × 5%，这正是「上架其实要贴手续费」的真实口径
        assert result["totals"]["revenue"] == pytest.approx(
            result["totals"]["mat_cost"] * (1 - 0.05), rel=1e-6
        )
        assert result["totals"]["net"] == pytest.approx(result["totals"]["mat_cost"] * 0.05, rel=1e-6)
        assert result["totals"]["ah_cut"] == pytest.approx(result["totals"]["mat_cost"] * 0.05, rel=1e-6)
        assert result["steps"][0]["ah_cut"] > 0

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

    def test_confirmed_count_is_cap_not_target(self, db_session):
        """确认次数是上限不是目标：A 本来就会被选中，次数填 999 也不改变路线。"""
        _prof, server, _ = _build_scenario(db_session)
        a_id = db_session.query(Recipe).filter_by(product_name="货品A").one().id
        base = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test", from_skill=1, to_skill=15),
            _settings(),
        )
        conf = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=1,
                to_skill=15,
                confirmed_recipe_ids=[a_id],
                confirmed_counts={a_id: 999},
            ),
            _settings(),
        )
        assert [s["recipe_name"] for s in conf["steps"]] == [s["recipe_name"] for s in base["steps"]]
        assert conf["totals"]["crafts"] == pytest.approx(base["totals"]["crafts"])
        assert conf["totals"]["net"] == base["totals"]["net"]

    def test_confirmed_no_effect_when_unavailable(self, db_session):
        """确认当前技能段用不到的配方（未解锁）→ 路线完全不变。"""
        _prof, server, _ = _build_scenario(db_session)
        c_id = db_session.query(Recipe).filter_by(product_name="货品C").one().id
        base = calc_route(
            db_session,
            CalcIn(server_id=server.id, profession_key="test", from_skill=1, to_skill=15),
            _settings(),
        )
        conf = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=1,
                to_skill=15,
                confirmed_recipe_ids=[c_id],
                confirmed_counts={c_id: 5},
            ),
            _settings(),
        )
        assert [s["recipe_name"] for s in conf["steps"]] == [s["recipe_name"] for s in base["steps"]]
        assert conf["totals"]["crafts"] == pytest.approx(base["totals"]["crafts"])

    def test_confirmed_priority_over_cheaper(self, db_session):
        """确认采用=优先权：B 确认且次数够大时，从 10 一路做到 40，绕过更便宜的 A。"""
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
                confirmed_counts={b_id: 999},
            ),
            _settings(),
        )
        assert [s["recipe_name"] for s in result["steps"]] == ["货品B"]
        assert result["steps"][0]["confirmed"] is True

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

    def test_design_missing_price_silent(self, db_session):
        """AH 计价但图纸无价格：按 0 静默计入，不再输出警告文案。"""
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
        assert all(s["design_cost"] == 0 for s in result["steps"])
        assert not any("暂无价格" in w for w in result["warnings"])

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


class TestAuctionCut:
    """拍卖行手续费：卖家拿到的是「到手价」，不是挂牌价。"""

    def test_cut_and_net(self):
        assert ah_cut_of(10000, 0.05) == 500
        assert ah_net_of(10000, 0.05) == 9500
        assert ah_cut_of(19, 0.05) == 0  # 按铜向下取整，不足 1 铜不收
        assert ah_net_of(19, 0.05) == 19
        assert ah_net_of(1000, 0.0) == 1000  # 费率置 0 = 旧口径
        assert ah_cut_of(0, 0.05) == 0
        assert ah_cut_of(-100, 0.05) == 0  # 负成交额不应产生负手续费

    def test_sell_npc_has_no_cut(self, db_session):
        """卖店/自用不经拍卖行，不应出现任何手续费。"""
        _prof, server, _ = _build_scenario(db_session)
        result = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="test",
                from_skill=1,
                to_skill=15,
                product_disposition="self_use",
            ),
            _settings(),
        )
        assert result["totals"]["ah_cut"] == 0
        assert all(s["ah_cut"] == 0 for s in result["steps"])


class TestRevenueVsNpc:
    """收益口径：拍卖行到手价与卖店价取高（用户 2026-10 口径）。"""

    def test_pick_revenue_rules(self):
        # 拍卖行无价 → 用卖店价（不是 0）
        assert pick_revenue(None, 500, 1, 0.05) == (500, 0, "npc", False)
        # 到手价高于卖店 → 用拍卖行，并记录抽成
        rev, cut, src, npc_better = pick_revenue(1000, 500, 1, 0.05)
        assert (rev, cut, src, npc_better) == (950, 50, "ah", False)
        # 到手价 950 < 卖店 960 → 自动按卖店
        rev, cut, src, npc_better = pick_revenue(1000, 960, 1, 0.05)
        assert (rev, cut, src, npc_better) == (960, 0, "npc", True)
        # 多份产出一起比（ah_gross 是这一批的总成交额，npc 是单份卖店价）
        rev, cut, src, _ = pick_revenue(3000, 400, 3, 0.05)
        assert rev == 2850 and cut == 150 and src == "ah"  # 3000-150=2850 > 3×400
        # 两种都没有 → 0
        assert pick_revenue(None, 0, 1, 0.05) == (0, 0, "npc", False)

    def test_ah_below_vendor_switches_to_npc(self, db_session):
        server = make_server(db_session, "取高服")
        prof = make_profession(db_session, "bs2", "锻造")
        m1 = make_item(db_session, 2840, "铜锭")
        p1 = make_item(db_session, 2851, "铜棒", vendor_price=960)
        make_recipe(db_session, prof, p1, "铜棒", [(m1, 1)], 1, 10, 12, 15)
        add_price(db_session, server, m1, 100)
        add_price(db_session, server, p1, 1000)  # 到手 950 < 卖店 960
        db_session.commit()

        res = calc_route(
            db_session,
            CalcIn(
                server_id=server.id,
                profession_key="bs2",
                from_skill=1,
                to_skill=10,
                price_mode="latest",
                product_disposition="sell_ah",
            ),
            get_settings(),
        )
        step = res["steps"][0]
        assert step["revenue_source"] == "npc"
        assert step["revenue_npc_better"] is True
        assert step["ah_cut"] == 0
        # 每次收入 960（卖店），材料 100 → 每份净 100-960 = -860
        assert step["net"] == pytest.approx((100 - 960) * step["crafts"])
