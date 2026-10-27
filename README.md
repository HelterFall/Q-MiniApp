# Q Mini App

Telegram Mini App prototype built with Python, aiogram 3, FastAPI, SQLite/aiosqlite, and WebSockets.

## Features

- Registers users through Telegram /start with a demo balance of 5,000 RUB.
- Validates Telegram Mini App initData HMAC and auth_date on protected API and WebSocket connections.
- Server-owned product catalogue; client-submitted prices are never trusted.
- Creates orders atomically in SQLite and uses an idempotency key to prevent duplicate debits for the same request key.
- Pushes demo order-status updates through WebSockets.
- Logs errors and can notify an administrator in Telegram.
- Includes basic signature-validation tests.

## Layout

- app/main.py — Telegram bot, FastAPI endpoints, initData validation, WebSockets.
- app/database.py — asynchronous SQLite repository and transactions.
- app/config.py — environment configuration.
- app/services/orders.py — demo order workflow.
- web/index.html — responsive Mini App interface.
- tests/test_init_data.py — initData validation tests.

## Run in Google Colab

Install dependencies:

    %pip install -r requirements.txt

Set environment variables before starting Uvicorn:

- BOT_TOKEN — token from BotFather.
- ADMIN_ID — optional numeric Telegram user ID for error notifications.
- WEBAPP_URL — public HTTPS URL of the Mini App tunnel.
- DATABASE_PATH — optional SQLite path; defaults to data/app.db.

Then start:

    !uvicorn app.main:app --host 0.0.0.0 --port 8000

Expose port 8000 using ngrok or another HTTPS tunnel. Set WEBAPP_URL to that HTTPS URL before starting the app, then open the Mini App through the bot's /start button. Never print or commit secrets.

Run tests:

    pytest -q

## Demo behaviour

The balance is a test-only internal ledger. The order processor waits briefly to simulate a stock check, then changes the status to “Сборка на складе” and “Передано курьеру”. No real card payment or actual 1C integration is performed.

## Production limitations

This is a development prototype, not an enterprise SLA system. Order processing runs as an in-process background task and can be interrupted by a restart; use a durable queue/worker and recovery logic before production. WebSocket connections are process-local; multi-instance deployments need a shared pub/sub broker. SQLite is intended for a small prototype, not multi-instance production writes. Real card payments require a payment provider and verified server-side callbacks. A real 1C adapter needs authentication, timeouts, retries, idempotency, and reconciliation.

Keep BOT_TOKEN, API keys, and tunnel credentials out of GitHub, including private repositories.
