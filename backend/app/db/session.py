import os
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

if DATABASE_URL and DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    parsed = urlparse(DATABASE_URL)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" in query_items and "ssl" not in query_items:
        sslmode = query_items.pop("sslmode")
        if sslmode in ("require", "verify-ca", "verify-full"):
            query_items["ssl"] = "require"
        else:
            query_items["ssl"] = sslmode
        DATABASE_URL = urlunparse(parsed._replace(query=urlencode(query_items)))

default_url = "sqlite+aiosqlite:///./strategos_dev.db"

engine = create_async_engine(DATABASE_URL or default_url, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
