"""Google Colab launcher for Q Mini App.

Prompts for secrets without writing them to the repository, opens an HTTPS
ngrok tunnel, sets WEBAPP_URL before app imports, and starts Uvicorn + aiogram.
"""
import os
from getpass import getpass

from pyngrok import ngrok


def secret_from_env_or_prompt(name: str, prompt: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        value = getpass(prompt).strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    os.environ[name] = value
    return value


def main() -> None:
    secret_from_env_or_prompt("BOT_TOKEN", "Telegram bot token (input hidden): ")
    ngrok_token = secret_from_env_or_prompt(
        "NGROK_AUTHTOKEN", "ngrok authtoken (input hidden): "
    )

    admin_id = os.getenv("ADMIN_ID", "").strip()
    if not admin_id:
        admin_id = input("Telegram admin_id (optional; Enter to skip): ").strip()
    if admin_id:
        try:
            int(admin_id)
        except ValueError as exc:
            raise RuntimeError("ADMIN_ID must be a numeric Telegram user ID") from exc
        os.environ["ADMIN_ID"] = admin_id

    ngrok.set_auth_token(ngrok_token)
    tunnel = ngrok.connect(addr=8000, proto="http")
    public_url = tunnel.public_url.rstrip("/")
    if not public_url.startswith("https://"):
        https_url = next(
            (item.public_url.rstrip("/") for item in ngrok.get_tunnels()
             if item.public_url.startswith("https://")),
            None,
        )
        if not https_url:
            ngrok.kill()
            raise RuntimeError(
                "ngrok did not provide an HTTPS URL. Check your ngrok account/configuration."
            )
        public_url = https_url

    # config.py and the bot keyboard read WEBAPP_URL at import time.
    os.environ["WEBAPP_URL"] = public_url
    print("\nMini App HTTPS URL:", public_url)
    print("Open your bot in Telegram and send /start.")
    print("This Colab session must remain running for the app to stay online.\n")

    import uvicorn

    try:
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
    finally:
        try:
            ngrok.disconnect(public_url)
        finally:
            ngrok.kill()


if __name__ == "__main__":
    main()
