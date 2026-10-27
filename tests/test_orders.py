import os

os.environ.setdefault("BOT_TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
os.environ.setdefault("DATABASE_PATH", "/tmp/q-miniapp-test.db")

import pytest

from app import database
from app.services import orders as order_service


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
