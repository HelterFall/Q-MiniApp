# Q Mini App

Telegram Mini App prototype using aiogram 3, FastAPI, SQLite/aiosqlite, and WebSockets.

## Included

- Telegram /start registration with a demo balance of 5,000 RUB.
- Server-side Telegram Mini App initData HMAC validation and auth_date expiry.
- Server-owned product catalogue; the frontend cannot choose a price.
- Atomic SQLite order creation with an idempotency key.
- WebSocket order-status events and a responsive light/dark interface.
- Error logging and optional Telegram admin notifications.

## Layout

- app/main.py — async Telegram bot, FastAPI routes, initData validation, WebSockets.
- app/database.py — async SQLite schema and transactional data operations.
- app/config.py — environment configuration.
- app/services/orders.py — demo order-status workflow.
- web/index.html — Mini App frontend.

## Run in Colab

Install dependencies:

    %pip install -r requirements.txt

Set environment variables before starting Uvicorn:

- BOT_TOKEN — token from BotFather.
- ADMIN_ID — optional numeric Telegram user ID for error notifications.
- WEBAPP_URL — public HTTPS URL of the Mini App tunnel.
- DATABASE_PATH — optional database path; default is data/app.db.

Then run:

    !uvicorn app.main:app --host 0.0.0.0 --port 8000

Expose port 8000 using ngrok or another HTTPS tunnel, set WEBAPP_URL to the public HTTPS address before starting the app, then open the Mini App through the bot's /start button. Do not print or commit secrets.

## Demo behaviour

The balance is a test-only internal ledger. The order workflow sleeps to simulate a stock check and changes the status to “Сборка на складе”, then “Передано курьеру”. There is no real card payment and no actual 1C connection.

## Production gaps

This is a development prototype, not an enterprise SLA system. The demo workflow runs in process memory and can be interrupted by a restart; use a durable task queue/worker and recovery logic before production. WebSocket connections are process-local; multi-instance deployments need a shared pub/sub broker. SQLite is intended for a small prototype, not multi-instance production writes. Real card payments require a provider and verified server-side callbacks. A real 1C adapter needs authentication, timeouts, retries, idempotency, and reconciliation.

Keep BOT_TOKEN, API keys, and tunnel credentials out of GitHub, including private repositories.
