import asyncio
import logging

from app.services import mock_1c

log = logging.getLogger(__name__)


async def process_order(
    order_id: int,
    broadcast,
    set_status,
    report_error,
    initial_status: str = "Заказ создан",
):
    """Process a demo order and resume from the last persisted status."""
    try:
        if initial_status == "Заказ создан":
            # Mock 1C performs the simulated network/warehouse wait and stock check.
            result = await mock_1c.submit_order(order_id)
            user_id = result["user_id"]
            if not result["accepted"]:
                await broadcast(user_id, {
                    "type": "order_status",
                    "order_id": order_id,
                    "status": result["status"],
                })
                return

            user_id = await set_status(order_id, "Сборка на складе")
            await broadcast(user_id, {
                "type": "order_status",
                "order_id": order_id,
                "status": "Сборка на складе",
            })
            initial_status = "Сборка на складе"

        if initial_status == "Сборка на складе":
            await asyncio.sleep(2)
            user_id = await set_status(order_id, "Передано курьеру")
            await broadcast(user_id, {
                "type": "order_status",
                "order_id": order_id,
                "status": "Передано курьеру",
            })
        elif initial_status != "Передано курьеру":
            log.warning(
                "Not resuming order %s from unrecognised status %r",
                order_id,
                initial_status,
            )
    except asyncio.CancelledError:
        # Keep the last persisted status so a later app startup can resume it.
        raise
    except Exception:
        log.exception("Order workflow failed: %s", order_id)
        await report_error("Обработка заказа #" + str(order_id))
