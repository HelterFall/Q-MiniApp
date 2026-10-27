import pytest

from app import database


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
