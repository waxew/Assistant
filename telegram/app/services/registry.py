from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bots.store.factory import create_store_dispatcher
from app.config import Settings
from app.models import BotStatus, TenantBot, utc_now
from app.security import TokenCipher
from app.services.builder import BuilderService
from app.services.store import StoreService, tenant_runtime_active
from app.services.zarinpal import ZarinpalClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TenantHandle:
    bot: Bot
    dispatcher: Dispatcher
    task: asyncio.Task[None]


class TenantRegistry:
    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings,
        cipher: TokenCipher,
        zarinpal: ZarinpalClient,
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.cipher = cipher
        self.zarinpal = zarinpal
        self.handles: dict[int, TenantHandle] = {}
        self._lock = asyncio.Lock()

    async def start_all(self) -> None:
        tenants = await BuilderService(self.sessions).active_tenants()
        for tenant in tenants:
            if tenant_runtime_active(tenant):
                try:
                    await self.start_tenant(tenant.id)
                except Exception:
                    logger.exception("Could not start tenant %s", tenant.id)

    async def start_tenant(self, tenant_id: int) -> None:
        async with self._lock:
            existing = self.handles.get(tenant_id)
            if existing and not existing.task.done():
                return
            async with self.sessions() as session:
                tenant = await session.get(TenantBot, tenant_id)
                if not tenant or not tenant_runtime_active(tenant):
                    raise ValueError("اشتراک این ربات فعال نیست.")
                token = self.cipher.decrypt(tenant.encrypted_token)
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            service = StoreService(tenant_id, self.sessions)
            dispatcher = create_store_dispatcher(service, self.settings, self.zarinpal)
            task = asyncio.create_task(
                self._poll(tenant_id, bot, dispatcher), name=f"tenant-bot-{tenant_id}"
            )
            self.handles[tenant_id] = TenantHandle(bot, dispatcher, task)

    async def _poll(self, tenant_id: int, bot: Bot, dispatcher: Dispatcher) -> None:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            async with self.sessions() as session:
                tenant = await session.get(TenantBot, tenant_id)
                if tenant:
                    tenant.last_started_at = utc_now()
                    tenant.last_error = None
                    await session.commit()
            await dispatcher.start_polling(
                bot,
                handle_signals=False,
                allowed_updates=dispatcher.resolve_used_update_types(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Tenant %s polling stopped", tenant_id)
            async with self.sessions() as session:
                tenant = await session.get(TenantBot, tenant_id)
                if tenant:
                    tenant.last_error = f"{type(exc).__name__}: {exc}"[:4000]
                    await session.commit()
        finally:
            await bot.session.close()

    async def reconcile(self) -> None:
        async with self.sessions() as session:
            tenants = list((await session.scalars(select(TenantBot))).all())
            for tenant in tenants:
                running = tenant.id in self.handles and not self.handles[tenant.id].task.done()
                active = tenant_runtime_active(tenant)
                if not active and tenant.status in {BotStatus.TRIAL, BotStatus.ACTIVE}:
                    tenant.status = BotStatus.EXPIRED
                if active and not running:
                    asyncio.create_task(self.start_tenant(tenant.id))
                if not active and running:
                    self.handles[tenant.id].task.cancel()
            await session.commit()
        finished = [key for key, handle in self.handles.items() if handle.task.done()]
        for key in finished:
            self.handles.pop(key, None)

    def get_bot(self, tenant_id: int) -> Bot | None:
        handle = self.handles.get(tenant_id)
        return handle.bot if handle and not handle.task.done() else None

    async def stop_all(self) -> None:
        handles = list(self.handles.values())
        for handle in handles:
            handle.task.cancel()
        if handles:
            await asyncio.gather(*(item.task for item in handles), return_exceptions=True)
        self.handles.clear()
