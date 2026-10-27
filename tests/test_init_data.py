import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

os.environ.setdefault("BOT_TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
os.environ.setdefault("DATABASE_PATH", "/tmp/q-miniapp-test.db")

from fastapi import HTTPException
from app.main import validate_init_data


def make_init_data(auth_date=None):
    values = {
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "user": json.dumps({"id": 123456, "first_name": "Test"}, separators=(",", ":")),
        "query_id": "AAExample",
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(os.environ["BOT_TOKEN"].encode(), b"WebAppData", hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_init_data_returns_user():
    user = validate_init_data(make_init_data())
    assert user["id"] == 123456


def test_tampered_init_data_is_rejected():
    data = make_init_data().replace("first_name", "last_name")
    try:
        validate_init_data(data)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Invalid signature should be rejected")


def test_expired_init_data_is_rejected():
    data = make_init_data(time.time() - 7200)
    try:
        validate_init_data(data)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expired initData should be rejected")
