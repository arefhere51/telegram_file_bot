#!/usr/bin/env python3
"""
Telegram File Bot - Combined Bot + Web Panel
Runs both the Telegram bot (Pyrogram) and the FastAPI web panel together.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

import uvicorn
from pyrogram import idle

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import settings
from database import init_db
from bot import app as bot_app
from web_app import app as web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


async def run_web():
    config = uvicorn.Config(
        web_app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    await bot_app.start()
    me = await bot_app.get_me()
    logger.info(f"Bot started as @{me.username} (id={me.id})")
    await idle()
    await bot_app.stop()


async def main():
    init_db()
    logger.info(f"Data directory : {settings.data_path}")
    logger.info(f"Web panel      : http://{settings.WEB_HOST}:{settings.WEB_PORT}")
    logger.info(f"Public base URL: {settings.PUBLIC_BASE_URL}")
    logger.info(f"Max file size  : {settings.MAX_FILE_SIZE_GB} GB")
    logger.info(f"Admins         : {settings.admin_ids}")

    # Run both concurrently
    await asyncio.gather(
        run_bot(),
        run_web(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
