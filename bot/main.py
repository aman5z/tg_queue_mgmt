"""Bot entry point — runs the Telegram bot and FastAPI server concurrently."""

import asyncio
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_bot(app):
    """Initialise and run the Telegram bot (long-polling)."""
    await app.initialize()
    await app.start()
    logger.info("Bot started (long-polling)")
    await app.updater.start_polling(drop_pending_updates=True)
    # Keep running until shutdown
    await asyncio.Event().wait()


async def run_web(port: int):
    """Run the FastAPI/uvicorn server."""
    from web.app import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info(f"Web server starting on port {port}")
    await server.serve()


async def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set in the environment. Please create a .env file.")
        sys.exit(1)

    port = int(os.getenv("PORT", "8000"))

    # Import DB and handlers here (after load_dotenv so env vars are available)
    from db.database import init_db
    from bot.handlers.admin import register_admin_handlers
    from bot.handlers.customer import register_customer_handlers

    await init_db()
    logger.info("Database initialised")

    builder = ApplicationBuilder().token(bot_token)
    telegram_app = builder.build()

    register_customer_handlers(telegram_app)
    register_admin_handlers(telegram_app)

    await asyncio.gather(
        run_bot(telegram_app),
        run_web(port),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down.")
