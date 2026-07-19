import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = (
    f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:"
    f"{os.environ['POSTGRES_PASSWORD']}@db:5432/{os.environ['POSTGRES_DB']}"
)

_engine_kwargs: dict = {"echo": False}
if os.environ.get("DB_DISABLE_POOL") == "1":
    # Test-only: pytest-asyncio runs each async session on its own
    # (function-scoped) event loop. A pooled asyncpg connection created on one
    # loop and later reused on another raises "attached to a different loop" /
    # "Event loop is closed", which silently empties query results in seed-
    # heavy tests. NullPool opens a fresh connection per session, so no
    # connection is ever shared across loops. Never set in production —
    # connection pooling stays enabled there.
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
