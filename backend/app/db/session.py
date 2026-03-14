import os
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool


DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
engine_kwargs = {"echo": False}

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

    # Supabase pooler / PgBouncer compatibility:
    # disable statement caching and avoid SQLAlchemy-side pooling.
    is_pooler_port = parsed.port == 6543
    is_pgbouncer_hint = str(query_items.get("pgbouncer", "")).lower() in {"1", "true", "yes", "on"}
    if is_pooler_port or is_pgbouncer_hint:
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }
    else:
        engine_kwargs["connect_args"] = {"prepared_statement_cache_size": 0}

default_url = "sqlite+aiosqlite:///./strategos_dev.db"

engine = create_async_engine(DATABASE_URL or default_url, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
