from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from backend.main import app
from backend.services import generate_ghs_code, list_generated_codes

# Run backend API with: uvicorn bot:app --reload
# Run Telegram bot polling with: python bot.py

TELEGRAM_API_BASE = "https://api.telegram.org"
GENERATE_CODES_CB = "generate_codes"
MANAGE_CODES_CB = "manage_codes"


def main_menu_markup() -> dict[str, list[list[dict[str, str]]]]:
    """Inline keyboard with two main actions."""
    return {
        "inline_keyboard": [
            [{"text": "Generate codes", "callback_data": GENERATE_CODES_CB}],
            [{"text": "Manage codes", "callback_data": MANAGE_CODES_CB}],
        ]
    }


async def telegram_request(
    client: httpx.AsyncClient, token: str, method: str, payload: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        f"{TELEGRAM_API_BASE}/bot{token}/{method}", json=payload, timeout=30.0
    )
    response.raise_for_status()
    return response.json()


async def send_main_menu(
    client: httpx.AsyncClient, token: str, chat_id: int, text: str | None = None
) -> None:
    await telegram_request(
        client,
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
            or "Choose an option from the main menu:",
            "reply_markup": main_menu_markup(),
        },
    )


async def answer_callback(
    client: httpx.AsyncClient, token: str, callback_id: str, message: str
) -> None:
    await telegram_request(
        client,
        token,
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
            "text": message,
            "show_alert": False,
        },
    )


async def handle_update(client: httpx.AsyncClient, token: str, update: dict[str, Any]) -> None:
    if message := update.get("message"):
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")

        if not chat_id:
            return

        if text in {"/start", "/menu"}:
            await send_main_menu(
                client,
                token,
                chat_id,
                "Welcome! Use the buttons below to continue.",
            )

    if callback := update.get("callback_query"):
        callback_id = callback.get("id")
        data = callback.get("data")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")

        if not callback_id or not chat_id:
            return

        if data == GENERATE_CODES_CB:
            generated = generate_ghs_code()
            await answer_callback(client, token, callback_id, "Code generated")
            await send_main_menu(
                client,
                token,
                chat_id,
                f"✅ New code created: {generated.code}",
            )
        elif data == MANAGE_CODES_CB:
            codes = list_generated_codes()
            latest = codes[0].code if codes else "None"
            await answer_callback(client, token, callback_id, "Opening code management...")
            await send_main_menu(
                client,
                token,
                chat_id,
                f"📦 Total generated codes: {len(codes)}\nLatest code: {latest}",
            )
        else:
            await answer_callback(client, token, callback_id, "Unknown action")


async def run_telegram_bot() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    offset = 0
    async with httpx.AsyncClient() as client:
        while True:
            updates = await telegram_request(
                client,
                token,
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 20,
                    "allowed_updates": ["message", "callback_query"],
                },
            )

            for update in updates.get("result", []):
                offset = max(offset, update["update_id"] + 1)
                await handle_update(client, token, update)


if __name__ == "__main__":
    asyncio.run(run_telegram_bot())
