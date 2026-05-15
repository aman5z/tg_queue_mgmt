"""Customer-facing bot handlers."""

import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from db.database import get_counters, create_token, tokens_ahead, get_current_token_for_counter


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with link to take a token."""
    take_url = f"{BASE_URL}/take"
    text = (
        "👋 *Welcome to Queue Management!*\n\n"
        "To take a token, visit:\n"
        f"{take_url}\n\n"
        "Or use /status to see current queue status."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def register_customer_handlers(app) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
