"""Local mock adapter for the stock/order part normally handled by 1C.

This module intentionally uses a deterministic SQLite-backed demo warehouse.
It is not a connection to real 1C software.
"""
import asyncio
import logging

from app import database

log = logging.getLogger(__name__)
STOCK_CHECK_DELAY_SECONDS = 3


async def submit_order(order_id: int) -> dict:
    """Simulate sending an order to 1C, checking stock, and reserving one item."""
    await asyncio.sleep(STOCK_CHECK_DELAY_SECONDS)
    result = await database.reserve_mock_stock(order_id)
    if result["accepted"]:
        log.info("Mock 1C reserved stock for order #%s", order_id)
    else:
        log.info("Mock 1C rejected order #%s: no stock; test balance refunded", order_id)
    return result
