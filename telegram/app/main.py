from __future__ import annotations

import asyncio
import contextlib

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from app.bots.builder import create_builder_router
from app.config import Settings
from app.database import Database
from app.security import TokenCipher, configure_logging
from app.services.builder import BuilderService
from app.services.registry import TenantRegistry
from app.services.zarinpal import ZarinpalClient
from app.web import create_web_app


async def reconcile_forever(registry: TenantRegistry) -> None:
    while True:
        await asyncio.sleep(60)
        await registry.reconcile()


async def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)
    await database.init_schema()
    cipher = TokenCipher(settings.token_encryption_key)
    zarinpal = ZarinpalClient()
    registry = TenantRegistry(
        sessions=database.session_factory,
        settings=settings,
        cipher=cipher,
        zarinpal=zarinpal,
    )
    await registry.start_all()

    builder_bot = Bot(
        token=settings.builder_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(
        create_builder_router(
            service=BuilderService(database.session_factory),
            settings=settings,
            cipher=cipher,
            registry=registry,
        )
    )

    web_app = create_web_app(
        registry=registry,
        sessions=database.session_factory,
        zarinpal=zarinpal,
    )
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.web_host, settings.web_port)
    await site.start()
    reconcile_task = asyncio.create_task(reconcile_forever(registry))

    try:
        await builder_bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(builder_bot)
    finally:
        reconcile_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reconcile_task
        await registry.stop_all()
        await runner.cleanup()
        await builder_bot.session.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
