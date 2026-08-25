from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return "sqlite+aiosqlite:///" + url.removeprefix("sqlite:///")
    return url


class Database:
    def __init__(self, url: str) -> None:
        self.url = normalize_database_url(url)
        if self.url.startswith("sqlite+aiosqlite:///"):
            raw_path = self.url.removeprefix("sqlite+aiosqlite:///")
            if raw_path != ":memory:":
                Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

        connect_args: dict[str, object] = {}
        if self.url.startswith("sqlite"):
            connect_args["timeout"] = 30

        self.engine: AsyncEngine = create_async_engine(
            self.url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        if self.url.startswith("sqlite"):
            self._enable_sqlite_foreign_keys()
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    def _enable_sqlite_foreign_keys(self) -> None:
        @event.listens_for(self.engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    async def init_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()
