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

## Run a demo in Google Colab

This setup is for a school/demo run, not guaranteed 24/7 hosting.

1. Download the ZIP from the private GitHub repository (**Code → Download ZIP**) and upload that ZIP in Colab with the first cell below.
2. In Colab's Secrets panel, add `BOT_TOKEN` (from BotFather) and `NGROK_AUTHTOKEN` (from your ngrok account). Enable notebook access for these secrets. Add `ADMIN_ID` only if you want Telegram error notifications.
3. Run the cells in order. The app will show a public HTTPS URL and then start Uvicorn. Open the bot in Telegram and send `/start`.

**Cell 1 — upload and unpack the repository ZIP:**

```python
from google.colab import files
from pathlib import Path
import os
import zipfile

uploaded = files.upload()  # Select the ZIP downloaded from GitHub
zip_name = next(iter(uploaded))
extract_to = Path("/content/q-miniapp")
extract_to.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_name) as archive:
    archive.extractall(extract_to)

repo_dir = next(extract_to.glob("Q-MiniApp-*"))
os.chdir(repo_dir)
print("Project folder:", repo_dir)
```

**Cell 2 — install dependencies:**

```python
%pip install -r requirements.txt
```

**Cell 3 — load secrets and create the HTTPS tunnel:**

```python
import os
from google.colab import userdata
from pyngrok import ngrok

os.environ["BOT_TOKEN"] = userdata.get("BOT_TOKEN")
try:
    os.environ["ADMIN_ID"] = userdata.get("ADMIN_ID")
except Exception:
    os.environ["ADMIN_ID"] = "0"

ngrok.set_auth_token(userdata.get("NGROK_AUTHTOKEN"))
tunnel = ngrok.connect(8000, "http")
os.environ["WEBAPP_URL"] = tunnel.public_url
print("Mini App HTTPS URL:", tunnel.public_url)
```

**Cell 4 — start the app:**

```python
!uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Keep that cell running while testing. If the Colab runtime stops or restarts, the bot and tunnel stop too; create a new tunnel and repeat the setup. Never paste real tokens into chat, source files, notebook output, or GitHub.

**Run tests in a terminal or notebook cell:**

```bash
pytest -q
```

## Demo behaviour

The balance is a test-only internal ledger. The order processor waits briefly to simulate a stock check, then changes the status to “Сборка на складе” and “Передано курьеру”. No real card payment or actual 1C integration is performed.

## Production limitations

This is a development prototype, not an enterprise SLA system. Order processing runs as an in-process background task and can be interrupted by a restart; use a durable queue/worker and recovery logic before production. WebSocket connections are process-local; multi-instance deployments need a shared pub/sub broker. SQLite is intended for a small prototype, not multi-instance production writes. Real card payments require a payment provider and verified server-side callbacks. A real 1C adapter needs authentication, timeouts, retries, idempotency, and reconciliation.

Keep BOT_TOKEN, API keys, and tunnel credentials out of GitHub, including private repositories.
