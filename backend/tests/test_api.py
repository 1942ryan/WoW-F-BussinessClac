"""API 端到端测试。"""

from __future__ import annotations

import pytest

CSV_UTF8 = "物品名称,单价\n铜锭,25\n铁锭,80\n不存在的东西,999\n".encode("utf-8")


def test_server_create_and_list(client):
    r = client.post("/api/v1/servers", json={"name": "安苏"})
    assert r.status_code == 201 and r.json()["name"] == "安苏"
    r2 = client.post("/api/v1/servers", json={"name": "安苏"})
    assert r2.status_code == 201 and r2.json()["existed"] is True
    lst = client.get("/api/v1/servers").json()
    assert len(lst) == 1 and lst[0]["name"] == "安苏"


def test_import_and_calc_and_share_flow(client, db_session):
    from tests.conftest import make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "瑞雪")
    prof = make_profession(db_session, "test", "测试专业")
    # 与导入 CSV 对应的物品
    make_item(db_session, 2840, "铜锭")
    make_item(db_session, 3575, "铁锭")
    m1 = make_item(db_session, 9001, "材料甲")
    p1 = make_item(db_session, 9101, "货品A", vendor_price=10)
    make_recipe(db_session, prof, p1, "货品A", [(m1, 2)], 1, 10, 12, 15)
    db_session.commit()

    # 导入价格（含一个无法匹配的名称）
    r = client.post(
        "/api/v1/prices/import",
        files={"file": ("auc.csv", CSV_UTF8, "text/csv")},
        data={"server_id": server.id, "imported_by": "测试员"},
    )
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["matched"] == 2 and summary["unmatched"] == 1
    assert "不存在的东西" in summary["unmatched_names"]

    # 有效价格
    prices = client.get(f"/api/v1/prices?server_id={server.id}").json()
    price_map = {p["name"]: p["price"] for p in prices}
    assert price_map["铜锭"] == 25 and price_map["铁锭"] == 80

    # 计算（材料甲无价 → 配方不参与）
    r = client.post(
        "/api/v1/routes/calc",
        json={
            "server_id": server.id,
            "profession_key": "test",
            "from_skill": 1,
            "to_skill": 15,
        },
    )
    assert r.status_code == 200, r.text
    calc = r.json()
    assert calc["steps"] == []
    assert any("材料无价格" in e["reason"] for e in calc["excluded"])

    # 手动补材料价后重算
    r = client.post(
        "/api/v1/prices/manual",
        json={"server_id": server.id, "item_id": 9001, "unit_price": 30},
    )
    assert r.status_code == 200
    r = client.post(
        "/api/v1/routes/calc",
        json={
            "server_id": server.id,
            "profession_key": "test",
            "from_skill": 1,
            "to_skill": 15,
            "product_disposition": "sell_npc",
        },
    )
    calc = r.json()
    assert len(calc["steps"]) == 1  # 同配方跨档位合并：1→15 连续做货品A
    assert calc["steps"][0]["recipe_name"] == "货品A"
    assert calc["steps"][0]["crafts"] == pytest.approx(20.4166666, abs=1e-3)  # 橙9+黄2.25+绿9.17
    # 公式模式总期望次数：9 + (1/1.0+1/0.8) + (1/0.6+1/0.4+1/0.2)
    assert calc["totals"]["crafts"] == pytest.approx(20.4166666, abs=1e-3)

    # 保存路线
    r = client.post(
        "/api/v1/routes",
        json={
            "server_id": server.id,
            "profession_key": "test",
            "from_skill": 1,
            "to_skill": 15,
            "title": "我的测试路线",
            "author": "测试员",
            "product_disposition": "sell_npc",
            "is_public": True,
        },
    )
    assert r.status_code == 201, r.text
    route = r.json()
    code = route["share_code"]
    assert route["server"]["name"] == "瑞雪"

    # 列表与详情
    lst = client.get("/api/v1/routes?public_only=true").json()
    assert any(x["share_code"] == code for x in lst)
    detail = client.get(f"/api/v1/routes/{code}").json()
    assert detail["title"] == "我的测试路线"

    # 他人采用：按当前价格重算
    recalc = client.post(f"/api/v1/routes/{code}/recalc").json()
    assert len(recalc["steps"]) == 1  # 同配方跨档位合并为一段
    assert recalc["params"]["product_disposition"] == "sell_npc"


def test_import_bad_file(client, db_session):
    from tests.conftest import make_server

    server = make_server(db_session, "空服2")
    db_session.commit()
    r = client.post(
        "/api/v1/prices/import",
        files={"file": ("bad.csv", "没有表头也没有数据".encode("utf-8"), "text/csv")},
        data={"server_id": server.id},
    )
    # 无表头时按两列解析 → 无有效行 → 400
    assert r.status_code == 400


def test_import_auc_export_with_level_disambiguation(client, db_session):
    """AUC 导出格式：同名不同物品按物品等级分别导入。"""
    from tests.conftest import make_item, make_server

    server = make_server(db_session, "等级服")
    make_item(db_session, 4358, "劣质炸药", item_level=10)
    make_item(db_session, 4365, "劣质炸药", item_level=20)
    make_item(db_session, 4357, "劣质火药", item_level=5)
    db_session.commit()

    auc = (
        '"价格","名称","物品等级","拥有？","可售数量"\n'
        '115,"劣质火药",5,"",1169\n'
        '200,"劣质炸药",20,"",61\n'
        '90,"劣质炸药",10,"",399\n'
    ).encode("utf-8")
    r = client.post(
        "/api/v1/prices/import",
        files={"file": ("auc_export.csv", auc, "text/csv")},
        data={"server_id": server.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["matched"] == 3 and r.json()["inserted"] == 3

    prices = {
        p["item_id"]: p["price"]
        for p in client.get(f"/api/v1/prices?server_id={server.id}").json()
    }
    assert prices[4357] == 115
    assert prices[4365] == 200  # 物品等级 20
    assert prices[4358] == 90   # 物品等级 10


def test_watchlist_export(client, db_session):
    from tests.conftest import make_item, make_profession, make_recipe, make_server

    make_server(db_session, "模板服")
    prof = make_profession(db_session, "bs", "锻造")
    mat = make_item(db_session, 2840, "铜锭")
    prod = make_item(db_session, 2851, "铜棒")
    design = make_item(db_session, 2020, "设计图：铜棒")
    make_recipe(
        db_session, prof, prod, "铜棒", [(mat, 1)], 1, 10, 12, 15,
        source_type="design", source_item=design,
    )
    db_session.commit()

    r = client.get("/api/v1/professions/bs/watchlist")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["list_name"] == "锻造"
    assert data["count"] == 3
    names = {i["name"] for i in data["items"]}
    assert names == {"铜锭", "铜棒", "设计图：铜棒"}
    kinds = {i["name"]: i["kind"] for i in data["items"]}
    assert kinds["设计图：铜棒"] == "design" and kinds["铜锭"] == "material"
    assert data["text"].startswith("锻造^")
    for n in names:
        assert n in data["text"]


def test_icons_in_recipes_and_calc(client, db_session):
    """物品图标应随配方列表与计算结果输出。"""
    from tests.conftest import add_price, make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "图标服")
    prof = make_profession(db_session, "bs", "锻造")
    m1 = make_item(
        db_session, 2840, "铜锭",
        icon="https://wowforever.wclbox.com/tubiao/inv_ingot_02.jpg",
    )
    p1 = make_item(
        db_session, 2851, "铜棒",
        icon="https://wowforever.wclbox.com/tubiao/inv_misc_flute_01.jpg",
    )
    make_recipe(db_session, prof, p1, "铜棒", [(m1, 1)], 1, 10, 12, 15)
    db_session.commit()

    # 配方列表带成品与材料图标
    recipes = client.get("/api/v1/professions/bs/recipes").json()
    r0 = recipes[0]
    assert r0["product_icon"].endswith("inv_misc_flute_01.jpg")
    assert r0["materials"][0]["icon"].endswith("inv_ingot_02.jpg")

    # 计算结果带图标（材料清单 + 步骤）
    add_price(db_session, server, m1, 25)
    db_session.commit()
    calc = client.post(
        "/api/v1/routes/calc",
        json={
            "server_id": server.id,
            "profession_key": "bs",
            "from_skill": 1,
            "to_skill": 10,
            "price_mode": "latest",
            "product_disposition": "sell_npc",
        },
    ).json()
    assert calc["steps"][0]["product_icon"].endswith("inv_misc_flute_01.jpg")
    mat = next(m for m in calc["materials"] if m["item_id"] == 2840)
    assert mat["icon"].endswith("inv_ingot_02.jpg")


def test_revenue_fallback_flag(client, db_session):
    """成品拍卖行无价 → revenue_fallback=True（冷门信号），有 AH 价则 False。

    该标记只做展示提示，不改变计算口径：无价时收入仍按 NPC 卖店价估算，
    是否屏蔽交由用户判断（前端配方行显示「AH无价」标签 + ⊘ 屏蔽按钮）。
    """
    from tests.conftest import add_price, make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "缺价服")
    prof = make_profession(db_session, "rk", "标记专业")
    mat = make_item(db_session, 9701, "标记材料")
    hot = make_item(db_session, 9702, "热门成品", vendor_price=100)
    cold = make_item(db_session, 9703, "冷门成品", vendor_price=500)
    make_recipe(db_session, prof, hot, "热门成品", [(mat, 1)], 1, 5, 8, 12)
    make_recipe(db_session, prof, cold, "冷门成品", [(mat, 1)], 1, 5, 8, 12)
    # 只给「热门成品」导拍卖行价，「冷门成品」不导 → 后者应被标记
    add_price(db_session, server, mat, 10)
    add_price(db_session, server, hot, 1000)
    db_session.commit()

    recipes = client.get(f"/api/v1/professions/rk/recipes?server_id={server.id}").json()
    flags = {r["product_name"]: r["revenue_fallback"] for r in recipes}
    assert flags["热门成品"] is False
    assert flags["冷门成品"] is True

    # 路线步骤同样带标记，方便在计算结果里发现混进来的冷门配方
    calc = client.post(
        "/api/v1/routes/calc",
        json={
            "server_id": server.id,
            "profession_key": "rk",
            "from_skill": 1,
            "to_skill": 12,
            "price_mode": "latest",
        },
    ).json()
    assert calc["steps"], "应至少产生一个步骤"
    for s in calc["steps"]:
        assert s["revenue_fallback"] == (s["recipe_name"] == "冷门成品")


def test_vendor_favor_flag(client, db_session, monkeypatch):
    """贸易营地图纸：带 vendor_favor + vendor_camp，source_detail 说明怎么获得青睐。

    营地配方用「商人青睐」购买（不是声望），两阵营价格相同，
    所以营地信息按服务器阵营给出对应一侧。
    """
    from tests.conftest import make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "营地服", faction="alliance")
    prof = make_profession(db_session, "vc", "营地专业")
    mat = make_item(db_session, 9801, "营地图纸")
    prod = make_item(db_session, 9802, "营地成品", vendor_price=200)
    r = make_recipe(
        db_session, prof, prod, "营地成品", [(mat, 1)], 1, 5, 8, 12,
        source_type="design", source_item=mat,
    )
    r.vendor_favor = 30
    r.source_note = "贸易营地 · 艾泽拉斯贸易局（联盟 斯通德里·暗锤）"
    db_session.commit()

    # 伪造抓取结果（真实数据由 backend/data/vendor_recipes.json 提供）
    from app.routers import professions as prof_mod

    monkeypatch.setattr(
        prof_mod,
        "_vendor_data",
        lambda: {
            "vc": {
                "by_item": {"9801": {"favor": 30}},
                "alliance": {
                    "camp": "艾泽拉斯贸易局", "npc": "斯通德里·暗锤",
                    "zone": "赤脊山 · 三角路口", "coord": "10.2,72.5",
                    "crate_npc": "玛茜·贝克",
                },
                "horde": {
                    "camp": "杜隆塔尔补给后勤部", "npc": "戈尔马克",
                    "zone": "贫瘠之地 · 十字路口", "coord": "49.7,29.5",
                    "crate_npc": "多基米",
                },
            }
        },
    )

    recipes = client.get(f"/api/v1/professions/vc/recipes?server_id={server.id}").json()
    camp = [x for x in recipes if x["vendor_favor"]]
    assert len(camp) == 1
    item = camp[0]
    assert item["vendor_favor"] == 30
    # 联盟服务器 → 给联盟营地
    assert item["vendor_camp"]["camp"] == "艾泽拉斯贸易局"
    assert item["vendor_camp"]["npc"] == "斯通德里·暗锤"
    detail = item["source_detail"]
    assert "商人青睐" in detail and "30" in detail
    assert "板条箱" in detail


def test_item_tooltip_and_ah_cut(client, db_session):
    """物品详情返回游戏内 tooltip 原文；拍卖行收入按扣 5% 手续费的到手价。"""
    import json as _json

    from tests.conftest import add_price, make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "口径服")
    prof = make_profession(db_session, "bs", "锻造")
    m1 = make_item(db_session, 2840, "铜锭")
    p1 = make_item(db_session, 2851, "铜棒", item_level=12, quality=2)
    p1.tooltip = _json.dumps(
        ["装备后绑定", "胸部\t皮甲", "护甲值 62", "+2 耐力", "需要等级 7", "售价：1银92铜"],
        ensure_ascii=False,
    )
    make_recipe(db_session, prof, p1, "铜棒", [(m1, 1)], 1, 10, 12, 15)
    add_price(db_session, server, m1, 100)
    add_price(db_session, server, p1, 200)
    db_session.commit()

    tip = client.get(f"/api/v1/items/{p1.id}?server_id={server.id}").json()
    assert tip["tooltip"][1] == "胸部\t皮甲"
    assert tip["tooltip"][-1] == "售价：1银92铜"

    calc = client.post(
        "/api/v1/routes/calc",
        json={
            "server_id": server.id,
            "profession_key": "bs",
            "from_skill": 1,
            "to_skill": 10,
            "price_mode": "latest",
            "product_disposition": "sell_ah",
        },
    ).json()
    # 材料 100、成品挂 200 → 到手 190，每次净成本 -90
    assert calc["totals"]["ah_cut_rate"] == 0.05
    step = calc["steps"][0]
    assert step["revenue"] == step["crafts"] * 190
    assert step["ah_cut"] == step["crafts"] * 10


def test_confirmed_count_zero_means_unlimited(client, db_session):
    """非 CD 配方的确认次数 0 = 不限次：算法不会只做一次就退出。"""
    from tests.conftest import add_price, make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "不限次服")
    prof = make_profession(db_session, "bs9", "锻造")
    m1 = make_item(db_session, 2840, "铜锭")
    p1 = make_item(db_session, 2851, "铜棒")
    r1 = make_recipe(db_session, prof, p1, "铜棒", [(m1, 1)], 1, 10, 12, 15)
    add_price(db_session, server, m1, 100)
    db_session.commit()

    res = client.post(
        "/api/v1/routes/calc",
        json={
            "server_id": server.id,
            "profession_key": "bs9",
            "from_skill": 1,
            "to_skill": 10,
            "price_mode": "latest",
            "product_disposition": "sell_ah",
            "confirmed_recipe_ids": [r1.id],
            "confirmed_counts": {str(r1.id): 0},
        },
    ).json()
    assert res["steps"][0]["confirmed"] is True
    assert res["steps"][0]["crafts"] > 5  # 没有被截成 1 次


def test_cooldown_recipes_flagged(client, db_session):
    """有 CD 的配方（月布）在配方列表里带 has_cooldown，用于默认次数 1。"""
    from tests.conftest import make_item, make_profession, make_recipe, make_server

    server = make_server(db_session, "CD服")
    prof = make_profession(db_session, "tailor9", "裁缝")
    m1 = make_item(db_session, 2999, "符文布")
    cd_item = make_item(db_session, 14342, "月布")
    normal = make_item(db_session, 2998, "符文布卷")
    make_recipe(db_session, prof, cd_item, "月布", [(m1, 2)], 250, 260, 270, 280)
    make_recipe(db_session, prof, normal, "符文布卷", [(m1, 1)], 1, 10, 20, 30)
    db_session.commit()

    rows = client.get(f"/api/v1/professions/tailor9/recipes?server_id={server.id}").json()
    flags = {r["product_name"]: r["has_cooldown"] for r in rows}
    assert flags["月布"] is True
    assert flags["符文布卷"] is False


def test_camp_source_detail_only_selected_faction(client, db_session):
    """营地图纸的来源浮层只留当前阵营那一段，不再列两个阵营。"""
    from tests.conftest import make_item, make_profession, make_recipe, make_server

    prof = make_profession(db_session, "blacksmithing", "锻造")
    alliance = make_server(db_session, "联盟服", faction="alliance")
    horde = make_server(db_session, "部落服", faction="horde")
    m1 = make_item(db_session, 2840, "铜锭")
    prod = make_item(db_session, 4001, "老兵的链甲腰带")
    plan = make_item(db_session, 251365, "设计图：老兵的链甲腰带")
    make_recipe(
        db_session, prof, prod, "老兵的链甲腰带", [(m1, 5)], 45, 50, 55, 60,
        source_type="design", source_item=plan,
    )
    # 图纸 id 命中 data/vendor_recipes.json → 标记为营地配方
    db_session.execute(
        __import__("sqlalchemy").text("UPDATE recipes SET vendor_favor = 30")
    )
    db_session.commit()

    a = client.get(f"/api/v1/professions/blacksmithing/recipes?server_id={alliance.id}").json()
    detail_a = a[0]["source_detail"]
    # 只保留联盟这句，部落那句不再出现
    assert "艾泽拉斯贸易局" in detail_a
    assert "杜隆塔尔" not in detail_a
    assert "提示：" not in detail_a
    assert detail_a.count("\n") <= 3

    h = client.get(f"/api/v1/professions/blacksmithing/recipes?server_id={horde.id}").json()
    detail_h = h[0]["source_detail"]
    assert "杜隆塔尔补给后勤部" in detail_h
    assert "艾泽拉斯贸易局" not in detail_h


def test_price_freshness_and_tooltip_age(client, db_session):
    """云价格有效期：物品卡带「这条价多久前导的」，/prices/freshness 汇总覆盖与过期条数。"""
    from datetime import datetime, timedelta

    from app.models import PriceBatch, PriceRecord
    from tests.conftest import add_price, make_item, make_server

    server = make_server(db_session, "有效期服")
    a = make_item(db_session, 2840, "铜锭")
    b = make_item(db_session, 3575, "铁锭")
    add_price(db_session, server, a, 100)
    add_price(db_session, server, b, 200)
    db_session.commit()

    fresh = client.get(f"/api/v1/prices/freshness?server_id={server.id}").json()
    assert fresh["item_count"] == 2 and fresh["batch_count"] == 2
    assert fresh["stale_items"] == 0 and fresh["stale"] is False
    assert fresh["valid_hours"] == 24
    assert fresh["age_hours"] is not None and fresh["age_hours"] < 0.5

    tip = client.get(f"/api/v1/items/{a.id}?server_id={server.id}").json()
    assert tip["effective_ah"] == 100
    assert tip["price_age_hours"] is not None and tip["price_stale"] is False

    # 把批次和流水一起改成 72 小时前 → 整服数据过期、每个物品都过期
    old = datetime.utcnow() - timedelta(hours=72)
    for batch in db_session.query(PriceBatch).all():
        batch.created_at = old
    for rec in db_session.query(PriceRecord).all():
        rec.created_at = old
    db_session.commit()

    stale = client.get(f"/api/v1/prices/freshness?server_id={server.id}").json()
    assert stale["stale"] is True
    assert stale["stale_items"] == 2
    assert 71 < stale["age_hours"] < 73

    tip2 = client.get(f"/api/v1/items/{a.id}?server_id={server.id}").json()
    assert tip2["price_stale"] is True
    assert 71 < tip2["price_age_hours"] < 73
