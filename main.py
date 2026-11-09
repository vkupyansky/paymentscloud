from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation

from bot import router, throttling
from db import initialize_database
from config import (
    BASE_WEBHOOK_URL,
    BOT,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    WEB_SERVER_HOST,
    WEB_SERVER_PORT,
)


async def on_startup(bot: Bot) -> None:
    await initialize_database()
    await throttling.storage.redis.ping()
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET)


async def on_shutdown() -> None:
    await throttling.storage.close()


def main() -> None:
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=BOT,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=BOT)
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    main()
