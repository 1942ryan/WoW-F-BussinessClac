"""API 端到端测试。"""

from __future__ import annotations

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
    assert len(calc["steps"]) == 3  # 1→10 橙、10→12 黄、12→15 绿
    assert calc["steps"][0]["recipe_name"] == "货品A"
    assert calc["steps"][0]["crafts"] == 9  # 橙档 100%，需 9 点
    assert calc["totals"]["crafts"] == 25

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
    assert len(recalc["steps"]) == 3
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
