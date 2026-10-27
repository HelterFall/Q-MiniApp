import asyncio
import hashlib
import hmac
import json
import logging
import time
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import database
from app.config import ADMIN_ID, BOT_TOKEN, INIT_DATA_MAX_AGE_SECONDS, PRODUCTS, WEBAPP_URL
from app.services.orders import process_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("q-miniapp")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
connections: dict[int, set[WebSocket]] = {}
background_tasks: set[asyncio.Task] = set()
INDEX_HTML = Path(__file__).resolve().parent.parent / "web" / "index.html"


def validate_init_data(init_data: str) -> dict:
    if not init_data or len(init_data) > 16_384:
        raise HTTPException(403, "Missing or oversized Telegram initData")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError("Duplicate parameters")
        received_hash = data.pop("hash", None)
        if not received_hash:
            raise ValueError("Missing hash")
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            raise ValueError("Invalid signature")
        age = time.time() - int(data["auth_date"])
        if age < -30 or age > INIT_DATA_MAX_AGE_SECONDS:
            raise ValueError("Expired initData")
        user = json.loads(data["user"])
        if not isinstance(user, dict) or not isinstance(user.get("id"), int):
            raise ValueError("Invalid Telegram user")
        return user
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(403, "Invalid Telegram initData") from exc


async def report_error(where: str):
    details = traceback.format_exc()
    log.error("%s\n%s", where, details)
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, ("⚠️ Q Mini App: " + where + "\n\n" + details)[:3900])
        except Exception:
            log.exception("Could not notify admin")


async def broadcast(user_id: int, payload: dict):
    for ws in list(connections.get(user_id, set())):
        try:
            await ws.send_json(payload)
        except Exception:
            connections.get(user_id, set()).discard(ws)


def track_task(task: asyncio.Task):
    background_tasks.add(task)

    def done(completed):
        background_tasks.discard(completed)
        if not completed.cancelled():
            exc = completed.exception()
            if exc:
                log.error("Background task crashed: %r", exc)

    task.add_done_callback(done)


def start_order_processing(order_id: int, status: str):
    task = asyncio.create_task(
        process_order(
            order_id,
            broadcast,
            database.set_order_status,
            report_error,
            initial_status=status,
        ),
        name=f"order-processing-{order_id}",
    )
    track_task(task)


@dp.message(CommandStart())
async def start(message: Message):
    try:
        await database.register_user(message.from_user.id, message.from_user.username)
        if WEBAPP_URL.startswith("https://"):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Открыть личный кабинет", web_app=WebAppInfo(url=WEBAPP_URL))
            ]])
            await message.answer("Добро пожаловать в Q! Тестовый баланс — 5 000 ₽.", reply_markup=keyboard)
        else:
            await message.answer("Добро пожаловать в Q! Баланс для тестов — 5 000 ₽.\n"
                                 "Для Mini App настройте WEBAPP_URL с публичным HTTPS-адресом.")
    except Exception:
        await report_error("Обработка /start")
        await message.answer("Не удалось загрузить профиль. Попробуйте позже.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    pending_orders = await database.get_pending_orders()
    for order in pending_orders:
        start_order_processing(order["order_id"], order["status"])
    if pending_orders:
        log.info("Resuming %s pending order(s) from SQLite", len(pending_orders))

    polling = asyncio.create_task(dp.start_polling(bot, handle_signals=False), name="telegram-polling")
    log.info("Q Mini App started")
    try:
        yield
    finally:
        polling.cancel()
        for task in list(background_tasks):
            task.cancel()
        await asyncio.gather(polling, *background_tasks, return_exceptions=True)
        await bot.session.close()


app = FastAPI(title="Q Mini App", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse(
        INDEX_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


async def current_user(x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data")):
    return validate_init_data(x_telegram_init_data)


@app.get("/api/me")
async def get_me(user: dict = Depends(current_user)):
    try:
        await database.register_user(user["id"], user.get("username"))
        profile = await database.get_user(user["id"])
        if profile is None:
            raise HTTPException(404, "User not found")
        return profile
    except HTTPException:
        raise
    except Exception:
        await report_error("Получение профиля")
        raise HTTPException(500, "Не удалось загрузить профиль")


@app.post("/api/demo/reset-balance")
async def reset_demo_balance(user: dict = Depends(current_user)):
    """Restore fake balance for end-to-end demo testing; never moves real money."""
    try:
        await database.register_user(user["id"], user.get("username"))
        balance = await database.reset_demo_balance(user["id"])
        return {"balance": balance, "demo": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception:
        await report_error("Восстановление тестового баланса")
        raise HTTPException(500, "Не удалось восстановить тестовый баланс")


@app.get("/api/products")
async def products():
    return [{"id": key, "name": val["name"], "price": val["price"]} for key, val in PRODUCTS.items()]


@app.get("/api/stock")
async def stock():
    """Expose the demo warehouse quantity so the Mini App can show Mock 1C results."""
    try:
        return await database.get_mock_stock()
    except Exception:
        await report_error("Получение остатков тестового склада")
        raise HTTPException(500, "Не удалось загрузить остатки тестового склада")


class OrderRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=16, max_length=100)


@app.post("/api/create-order")
async def create_order(payload: OrderRequest, user: dict = Depends(current_user)):
    if payload.product_id not in PRODUCTS:
        raise HTTPException(400, "Неизвестный товар")
    try:
        order, created = await database.create_order(user["id"], payload.product_id, payload.idempotency_key)
        profile = await database.get_user(user["id"])
        if created:
            start_order_processing(order["order_id"], order["status"])
        return {**order, "balance": profile["balance"] if profile else None, "created": created}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception:
        await report_error("Создание заказа")
        raise HTTPException(500, "Не удалось создать заказ")


@app.get("/api/orders")
async def list_orders(user: dict = Depends(current_user)):
    try:
        return await database.get_recent_orders(user["id"])
    except Exception:
        await report_error("Список заказов")
        raise HTTPException(500, "Не удалось загрузить заказы")


@app.get("/api/orders/{order_id}")
async def order_status(order_id: int, user: dict = Depends(current_user)):
    order = await database.get_order(order_id, user["id"])
    if not order:
        raise HTTPException(404, "Заказ не найден")
    return order


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    try:
        # initData is sent as the first WS message rather than a query string.
        init_data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        user = validate_init_data(init_data)
        user_id = user["id"]
        connections.setdefault(user_id, set()).add(websocket)
        await websocket.send_json({"type": "connected"})
        while True:
            text = await websocket.receive_text()
            if text == "ping":
                await websocket.send_json({"type": "pong"})
    except HTTPException:
        await websocket.close(code=1008)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception:
        log.exception("WebSocket handler failed")
    finally:
        if user_id is not None:
            connections.get(user_id, set()).discard(websocket)
            if not connections.get(user_id):
                connections.pop(user_id, None)
