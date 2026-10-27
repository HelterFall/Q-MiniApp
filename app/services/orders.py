import asyncio
import logging
log = logging.getLogger(__name__)

async def process_order(order_id: int, broadcast, set_status, report_error):
    """Demo workflow. Replace the sleeps with an authenticated 1C adapter."""
    try:
        await asyncio.sleep(3)
        user_id = await set_status(order_id, "Сборка на складе")
        await broadcast(user_id, {"type": "order_status", "order_id": order_id, "status": "Сборка на складе"})
        await asyncio.sleep(2)
        user_id = await set_status(order_id, "Передано курьеру")
        await broadcast(user_id, {"type": "order_status", "order_id": order_id, "status": "Передано курьеру"})
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Order workflow failed: %s", order_id)
        await report_error("Обработка заказа #" + str(order_id))
