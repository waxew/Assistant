from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bots.store.admin import create_admin_router
from app.bots.store.customer import create_customer_router
from app.config import Settings
from app.services.store import StoreService
from app.services.zarinpal import ZarinpalClient


def create_store_dispatcher(
    service: StoreService, settings: Settings, zarinpal: ZarinpalClient
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    # Admin state handlers are registered first so their wizard states win over customer fallbacks.
    dispatcher.include_router(create_admin_router(service))
    dispatcher.include_router(create_customer_router(service, settings, zarinpal))
    return dispatcher
