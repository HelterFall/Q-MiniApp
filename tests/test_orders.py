import os

os.environ.setdefault("BOT_TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
os.environ.setdefault("DATABASE_PATH", "/tmp/q-miniapp-test.db")

import pytest

from app import database
from app.services import mock_1c, orders as order_service


@pytest.mark.asyncio
async def test_order_debits_balance_once_for_idempotent_request(tmp_path, monkeypatch):
    db_path = tmp_path / "orders-test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))

    await database.init_db()
    await database.register_user(987654321, "test_user")

    first, created_first = await database.create_order(
        987654321, "iphone17", "test-idempotency-key-0001"
    )
    second, created_second = await database.create_order(
        987654321, "iphone17", "test-idempotency-key-0001"
    )

    profile = await database.get_user(987654321)
    orders = await database.get_recent_orders(987654321)

    assert created_first is True
    assert created_second is False
    assert first["order_id"] == second["order_id"]
    assert profile["balance"] == 5000 - first["price"]
    assert len(orders) == 1


@pytest.mark.asyncio
async def test_insufficient_balance_does_not_create_an_order(tmp_path, monkeypatch):
    db_path = tmp_path / "insufficient-balance.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))

    await database.init_db()
    await database.register_user(987654322, "test_user")

    for index in range(4):
        await database.create_order(
            987654322, "iphone17", f"purchase-test-key-{index:04d}"
        )

    with pytest.raises(ValueError, match="Недостаточно средств"):
        await database.create_order(
            987654322, "iphone17", "purchase-test-key-final"
        )

    profile = await database.get_user(987654322)
    orders = await database.get_recent_orders(987654322)
    assert profile["balance"] == 200
    assert len(orders) == 4


@pytest.mark.asyncio
async def test_pending_orders_lists_only_resumable_orders(tmp_path, monkeypatch):
    db_path = tmp_path / "pending-orders.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))

    await database.init_db()
    await database.register_user(987654323, "test_user")

    first, _ = await database.create_order(
        987654323, "iphone17", "pending-test-key-0001"
    )
    second, _ = await database.create_order(
        987654323, "iphone17", "pending-test-key-0002"
    )
    third, _ = await database.create_order(
        987654323, "iphone17", "pending-test-key-0003"
    )
    await database.set_order_status(first["order_id"], "Сборка на складе")
    await database.set_order_status(second["order_id"], "Передано курьеру")

    pending = await database.get_pending_orders()
    assert [(item["order_id"], item["status"]) for item in pending] == [
        (first["order_id"], "Сборка на складе"),
        (third["order_id"], "Заказ создан"),
    ]


@pytest.mark.asyncio
async def test_mock_1c_reserves_stock_only_once(tmp_path, monkeypatch):
    db_path = tmp_path / "mock-1c-reserve.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))

    await database.init_db()
    await database.register_user(987654325, "test_user")
    order, _ = await database.create_order(
        987654325, "iphone17", "mock-1c-reserve-key-001"
    )

    first = await database.reserve_mock_stock(order["order_id"])
    second = await database.reserve_mock_stock(order["order_id"])
    stock = await database.get_mock_stock()

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert next(item["quantity"] for item in stock if item["product_id"] == "iphone17") == 9
    profile = await database.get_user(987654325)
    assert profile["balance"] == 3800


@pytest.mark.asyncio
async def test_mock_1c_rejects_out_of_stock_and_refunds_only_once(tmp_path, monkeypatch):
    db_path = tmp_path / "mock-1c-no-stock.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))

    await database.init_db()
    await database.register_user(987654326, "test_user")
    await database.set_mock_stock("iphone17", 0)
    order, _ = await database.create_order(
        987654326, "iphone17", "mock-1c-out-of-stock-key"
    )

    first = await database.reserve_mock_stock(order["order_id"])
    second = await database.reserve_mock_stock(order["order_id"])
    profile = await database.get_user(987654326)
    saved_order = await database.get_order(order["order_id"], 987654326)
    stock = await database.get_mock_stock()

    assert first["accepted"] is False
    assert first["status"] == "Отменён: нет в наличии"
    assert second["accepted"] is False
    assert profile["balance"] == 5000
    assert saved_order["status"] == "Отменён: нет в наличии"
    assert next(item["quantity"] for item in stock if item["product_id"] == "iphone17") == 0


@pytest.mark.asyncio
async def test_workflow_broadcasts_out_of_stock_result(monkeypatch):
    broadcasts = []

    async def fake_submit_order(order_id):
        assert order_id == 42
        return {
            "user_id": 987654327,
            "accepted": False,
            "status": "Отменён: нет в наличии",
        }

    async def broadcast(user_id, payload):
        broadcasts.append((user_id, payload))

    async def set_status(order_id, status):
        raise AssertionError("Rejected order must not enter warehouse assembly")

    async def report_error(where):
        raise AssertionError(f"Unexpected processing error: {where}")

    monkeypatch.setattr(mock_1c, "submit_order", fake_submit_order)

    await order_service.process_order(42, broadcast, set_status, report_error)

    assert broadcasts == [(987654327, {
        "type": "order_status",
        "order_id": 42,
        "status": "Отменён: нет в наличии",
    })]


@pytest.mark.asyncio
async def test_processing_resumes_from_warehouse_status(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(order_service.asyncio, "sleep", no_sleep)
    status_updates = []
    broadcasts = []

    async def set_status(order_id, status):
        status_updates.append((order_id, status))
        return 987654324

    async def broadcast(user_id, payload):
        broadcasts.append((user_id, payload))

    async def report_error(where):
        raise AssertionError(f"Unexpected processing error: {where}")

    await order_service.process_order(
        42,
        broadcast,
        set_status,
        report_error,
        initial_status="Сборка на складе",
    )

    assert status_updates == [(42, "Передано курьеру")]
    assert len(broadcasts) == 1
    assert broadcasts[0][1]["status"] == "Передано курьеру"



@pytest.mark.asyncio
async def test_websocket_reconnect_replays_latest_order_status(monkeypatch):
    from app import main

    messages = []

    class FakeWebSocket:
        async def send_json(self, payload):
            messages.append(payload)

    async def fake_recent_orders(user_id, limit=10):
        assert user_id == 987654328
        assert limit == 1
        return [{
            "order_id": 73,
            "status": "Сборка на складе",
        }]

    monkeypatch.setattr(database, "get_recent_orders", fake_recent_orders)

    await main.send_latest_order_status(FakeWebSocket(), 987654328)

    assert messages == [{
        "type": "order_status",
        "order_id": 73,
        "status": "Сборка на складе",
    }]


@pytest.mark.asyncio
async def test_websocket_reconnect_does_not_send_fake_status_when_no_orders(monkeypatch):
    from app import main

    messages = []

    class FakeWebSocket:
        async def send_json(self, payload):
            messages.append(payload)

    async def fake_recent_orders(user_id, limit=10):
        assert user_id == 987654329
        assert limit == 1
        return []

    monkeypatch.setattr(database, "get_recent_orders", fake_recent_orders)

    await main.send_latest_order_status(FakeWebSocket(), 987654329)

    assert messages == []
