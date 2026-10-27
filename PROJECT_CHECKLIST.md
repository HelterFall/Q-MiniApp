# Q Mini App — project checklist

This checklist tracks the original Telegram Mini App specification. Items marked complete exist in the current code; a complete checkbox does not mean every edge case has been manually verified in a live Colab runtime.

## Original specification

- [x] **Async bot and user profile:** aiogram 3 polling, /start user registration, SQLite user row, demo balance default, current profile endpoint.
- [x] **Mini App UI:** single-page HTML/CSS/Vanilla JS, Telegram theme variables, system fonts, responsive cards, rounded corners and status animation.
- [x] **Telegram authentication:** backend HMAC-SHA256 validation of Telegram.WebApp.initData, constant-time signature comparison, age check, protected HTTP endpoints and WebSocket handshake.
- [x] **Order creation and demo accounting:** server-side product catalogue/pricing, atomic debit, idempotency key and insufficient-balance rejection.
- [x] **Mock 1C:** asynchronous three-second wait, SQLite-backed stock, atomic one-unit reservation, out-of-stock cancellation and one-time refund. This is deliberately a mock, not a real 1C connection.
- [x] **Live status:** WebSocket updates for order statuses; frontend updates the status indicator without a page reload.
- [x] **Logging and admin alert:** Python logging, traceback capture and optional Telegram notification to ADMIN_ID.
- [x] **Automated test suite exists:** signature-validation and order/stock/refund/recovery tests are in tests/.
- [x] **Google Colab with ngrok:** colab_launcher.py asks for secrets without echoing them, establishes an HTTPS tunnel, sets WEBAPP_URL, then starts Uvicorn and the bot. README contains two launch cells.
- [ ] **Live Colab acceptance run:** launch the latest main, open the HTTPS URL through Telegram /start, and verify one successful order and one out-of-stock cancellation end to end.
- [ ] **Confirm CI for the latest changes:** the GitHub commit status endpoint returned no check statuses during the latest review; do not treat the newest launcher/checklist commits as test-verified yet.

## Deferred review queue — do not interrupt feature work unless blocking

- [ ] Reproduce and diagnose the unexpected extra 1,200 RUB seen during rapid testing; probable timing interaction with the test-balance reset, but exact historical cause is not established.
- [ ] Stress-test simultaneous order requests and retries, including stale/reused idempotency keys.
- [ ] Verify WebSocket reconnect/recovery when the final status event is missed or the browser reconnects after the order has finished.
- [ ] Verify restart/recovery after interruption at each order-processing status.
- [ ] Do a final responsive/mobile and dark/light Telegram theme pass.

## Scope notes

- The balance is demo accounting only; there is no real card payment provider.
- 1C is simulated with SQLite and an asynchronous delay; no real 1C endpoint is configured.
- Google Colab is suitable for development/demo sessions, not persistent enterprise hosting. Runtime shutdown stops the bot and tunnel, and the public URL can change.
- Before production, revisit durable job execution, cross-process WebSocket broadcasting, operational monitoring, database choice, and payment/1C integrations.
