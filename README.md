# Q Mini App

Telegram Mini App prototype built with Python, aiogram 3, FastAPI, SQLite/aiosqlite, and WebSockets.

## Features

- Registers users through Telegram /start with a demo balance of 5,000 RUB.
- Validates Telegram Mini App initData HMAC and auth_date on protected API and WebSocket connections.
- Server-owned product catalogue; client-submitted prices are never trusted.
- Creates orders atomically in SQLite and uses an idempotency key to prevent duplicate debits for the same request key.
- Includes a SQLite-backed Mock 1C warehouse adapter with demo stock, one-item reservations, and out-of-stock rejection/refund.
- Makes stock reservation and rejection idempotent, so a retry cannot consume stock or refund the same order twice.
- Persists order status in SQLite and resumes demo orders left in an active status when the app starts again.
- Pushes demo order-status updates through WebSockets.
- Logs errors and can notify an administrator in Telegram.
- Includes tests for signature validation, order/balance behaviour, Mock 1C stock reservations, out-of-stock refunds, and pending-order recovery.

## Layout

- app/main.py — Telegram bot, FastAPI endpoints, initData validation, WebSockets.
- app/database.py — asynchronous SQLite repository, transactions, and demo warehouse tables.
- app/config.py — environment configuration.
- app/services/mock_1c.py — simulated 1C stock-check and reservation adapter (no real 1C connection).
- app/services/orders.py — demo order workflow.
- web/index.html — responsive Mini App interface.
- tests/test_init_data.py — initData validation tests.
- tests/test_orders.py — order, balance, warehouse, and recovery tests.

## Running and testing

The code and automated checks live in GitHub. GitHub Actions runs the test suite on pushes to `main` and on pull requests. A running Telegram Mini App still needs a reachable HTTPS backend; GitHub itself is not a persistent Python host.

Install dependencies with `python -m pip install -r requirements.txt`, set `BOT_TOKEN` in the environment, optionally set `WEBAPP_URL` to a public HTTPS address and `ADMIN_ID` for admin notifications, then run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run tests with:

```bash
python -m pytest -q
```

Keep `BOT_TOKEN`, API keys, and tunnel credentials out of source code, notebook output, and GitHub.

## Demo behaviour

The balance is a test-only internal ledger, not real card payment. On purchase, the app debits the test balance and creates an order. The Mock 1C adapter waits three seconds, checks the SQLite-backed demo warehouse, and atomically reserves one item when stock is available. A successful order advances to “Сборка на складе” and then “Передано курьеру”. If stock is unavailable, the order is cancelled as “Отменён: нет в наличии” and the test balance is refunded. A repeated processing attempt cannot reserve or refund the same order twice.

The demo warehouse starts with 10 units for each configured product. The initial quantity is only seeded when a product has no stock row, so it is not reset on application restarts. This is a simulation only; no real 1C integration or card payment is performed.

## Production limitations

This is a development prototype, not an enterprise SLA system. Recovery is checked on app startup, while order processing still runs in an in-process background task; a durable queue/worker, retry policy, and operational monitoring are needed before production. WebSocket connections are process-local; multi-instance deployments need a shared pub/sub broker. SQLite is intended for a small prototype, not multi-instance production writes. Real card payments require a payment provider and verified server-side callbacks. A real 1C adapter needs authentication, timeouts, retries, idempotency, and reconciliation.
