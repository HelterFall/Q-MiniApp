from datetime import datetime, timezone
from pathlib import Path
import aiosqlite
from app.config import DATABASE_PATH, INITIAL_BALANCE, PRODUCTS

PENDING_ORDER_STATUSES = ("Заказ создан", "Сборка на складе")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=10000")
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY, username TEXT,
          balance INTEGER NOT NULL DEFAULT 5000 CHECK(balance >= 0),
          order_status TEXT NOT NULL DEFAULT 'Нет активных заказов',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
          order_id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(user_id),
          product_id TEXT NOT NULL, product_name TEXT NOT NULL,
          price INTEGER NOT NULL CHECK(price > 0), status TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(user_id, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, order_id DESC);
        """)
        await db.commit()


async def register_user(user_id: int, username: str | None):
    stamp = now()
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("""
        INSERT INTO users(user_id, username, balance, order_status, created_at, updated_at)
        VALUES (?, ?, ?, 'Нет активных заказов', ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, updated_at=excluded.updated_at
        """, (user_id, username, INITIAL_BALANCE, stamp, stamp))
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT user_id, username, balance, order_status FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_order(user_id: int, product_id: str, idempotency_key: str):
    product = PRODUCTS.get(product_id)
    if not product:
        raise ValueError("Неизвестный товар")
    stamp = now()
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")
        try:
            cur = await db.execute("""
              SELECT order_id, product_id, product_name, price, status, created_at
              FROM orders WHERE user_id=? AND idempotency_key=?
            """, (user_id, idempotency_key))
            old = await cur.fetchone()
            if old:
                await db.commit()
                return {"order_id": old[0], "product_id": old[1], "product_name": old[2],
                        "price": old[3], "status": old[4], "created_at": old[5]}, False
            cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row:
                raise ValueError("Пользователь не зарегистрирован")
            if row[0] < product["price"]:
                raise ValueError("Недостаточно средств")
            await db.execute("UPDATE users SET balance=balance-?, order_status='Заказ создан', updated_at=? WHERE user_id=?",
                             (product["price"], stamp, user_id))
            cur = await db.execute("""
              INSERT INTO orders(user_id,product_id,product_name,price,status,idempotency_key,created_at,updated_at)
              VALUES(?,?,?,?, 'Заказ создан',?,?,?)
            """, (user_id, product_id, product["name"], product["price"], idempotency_key, stamp, stamp))
            order_id = cur.lastrowid
            await db.commit()
            return {"order_id": order_id, "product_id": product_id, "product_name": product["name"],
                    "price": product["price"], "status": "Заказ создан", "created_at": stamp}, True
        except Exception:
            await db.rollback()
            raise


async def get_pending_orders():
    """Return orders whose demo processing can safely resume after a restart."""
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT order_id, user_id, status
            FROM orders
            WHERE status IN (?, ?)
            ORDER BY order_id ASC
        """, PENDING_ORDER_STATUSES)
        return [dict(row) for row in await cur.fetchall()]


async def set_order_status(order_id: int, status: str) -> int:
    stamp = now()
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        await db.execute("PRAGMA busy_timeout=10000")
        await db.execute("BEGIN IMMEDIATE")
        try:
            cur = await db.execute("SELECT user_id FROM orders WHERE order_id=?", (order_id,))
            row = await cur.fetchone()
            if not row:
                raise ValueError("Заказ не найден")
            user_id = row[0]
            await db.execute("UPDATE orders SET status=?, updated_at=? WHERE order_id=?", (status, stamp, order_id))
            await db.execute("""
              UPDATE users SET order_status=?, updated_at=?
              WHERE user_id=? AND NOT EXISTS (
                SELECT 1 FROM orders newer WHERE newer.user_id=users.user_id AND newer.order_id>?
              )
            """, (status, stamp, user_id, order_id))
            await db.commit()
            return user_id
        except Exception:
            await db.rollback()
            raise


async def get_order(order_id: int, user_id: int):
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
          SELECT order_id, product_id, product_name, price, status, created_at, updated_at
          FROM orders WHERE order_id=? AND user_id=?
        """, (order_id, user_id))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_recent_orders(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DATABASE_PATH, timeout=10) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
          SELECT order_id, product_id, product_name, price, status, created_at, updated_at
          FROM orders WHERE user_id=? ORDER BY order_id DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in await cur.fetchall()]
