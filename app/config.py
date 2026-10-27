import os
from pathlib import Path

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

BOT_TOKEN = required("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")
INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("INIT_DATA_MAX_AGE_SECONDS", "3600"))
INITIAL_BALANCE = 5000
PRODUCTS = {"iphone17": {"name": "Новый iPhone 17", "price": 1200}}
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
