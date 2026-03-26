from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aristocrtic-telegram-bot")


@dataclass
class BotConfig:
    telegram_token: str
    backend_url: str


def load_config() -> BotConfig:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    return BotConfig(telegram_token=token, backend_url=backend_url.rstrip("/"))


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧾 Register", callback_data="register")],
            [InlineKeyboardButton("🔐 Get Login Code", callback_data="get_code")],
            [InlineKeyboardButton("💳 Wallet", callback_data="wallet")],
            [InlineKeyboardButton("▶️ Run GHS", callback_data="run")],
            [InlineKeyboardButton("🎁 Referral", callback_data="referral")],
        ]
    )


def call_backend(method: str, url: str, token: str | None = None, json: dict | None = None) -> dict:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(method, url, json=json, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Welcome to Aristocrtic GHS Bot.\n"
        "Use the buttons below to register, get login code, check wallet, and run GHS."
    )
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    config: BotConfig = context.bot_data["config"]
    user_state = context.user_data

    try:
        if query.data == "register":
            tg_name = query.from_user.full_name or "telegram-user"
            payload = call_backend(
                "POST",
                f"{config.backend_url}/users/register",
                json={"name": tg_name},
            )
            user_state["user_id"] = payload["user_id"]
            user_state["referral_code"] = payload["referral_code"]
            await query.edit_message_text(
                f"Registered ✅\nUser ID: {payload['user_id']}\nReferral: {payload['referral_code']}",
                reply_markup=menu_keyboard(),
            )

        elif query.data == "get_code":
            user_id = user_state.get("user_id")
            if not user_id:
                await query.edit_message_text("Register first.", reply_markup=menu_keyboard())
                return
            code_payload = call_backend("POST", f"{config.backend_url}/auth/code/create/{user_id}")
            verify = call_backend(
                "POST",
                f"{config.backend_url}/auth/code/verify",
                json={"code": code_payload["code"]},
            )
            user_state["access_token"] = verify["access_token"]
            await query.edit_message_text(
                f"Your login code: {code_payload['code']}\nSession ready ✅",
                reply_markup=menu_keyboard(),
            )

        elif query.data == "wallet":
            token = user_state.get("access_token")
            if not token:
                await query.edit_message_text("Get login code first.", reply_markup=menu_keyboard())
                return
            wallet = call_backend("GET", f"{config.backend_url}/wallet/me", token=token)
            await query.edit_message_text(
                f"Wallet\nAvailable: {wallet['available_credits']}\n"
                f"Locked: {wallet['locked_credits']}\nRun Cost: {wallet['run_cost']}",
                reply_markup=menu_keyboard(),
            )

        elif query.data == "run":
            token = user_state.get("access_token")
            if not token:
                await query.edit_message_text("Get login code first.", reply_markup=menu_keyboard())
                return

            run = call_backend("POST", f"{config.backend_url}/runs", token=token, json={})
            hold = call_backend(
                "POST",
                f"{config.backend_url}/wallet/hold",
                token=token,
                json={"run_id": run["run_id"]},
            )
            result = call_backend(
                "POST",
                f"{config.backend_url}/runs/execute",
                token=token,
                json={
                    "run_id": run["run_id"],
                    "hold_id": hold["hold_id"],
                    "country": "us",
                    "state": "ca",
                    "city": "san francisco",
                    "simulate_failure": False,
                },
            )
            await query.edit_message_text(
                f"Run Complete ✅\nRun ID: {result['run_id']}\nStatus: {result['status']}\n"
                f"College: {result.get('college')}",
                reply_markup=menu_keyboard(),
            )

        elif query.data == "referral":
            code = user_state.get("referral_code")
            if not code:
                await query.edit_message_text("Register first.", reply_markup=menu_keyboard())
                return
            await query.edit_message_text(
                f"Your referral code: {code}\nShare this code with friends 🎉",
                reply_markup=menu_keyboard(),
            )

    except requests.HTTPError as err:
        logger.exception("Backend request failed")
        await query.edit_message_text(
            f"Request failed: {err}",
            reply_markup=menu_keyboard(),
        )


async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Use /start and inline buttons to control the bot.",
        reply_markup=menu_keyboard(),
    )


def build_app(config: BotConfig) -> Application:
    app = Application.builder().token(config.telegram_token).build()
    app.bot_data["config"] = config
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))
    return app


def main() -> None:
    config = load_config()
    app = build_app(config)
    logger.info("Starting Telegram bot against backend: %s", config.backend_url)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
