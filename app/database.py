"""
Database layer — PostgreSQL connection management, schema, and query helpers.
Uses asyncpg for async connection pooling.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

class DatabaseSettings(BaseSettings):
    """Database configuration from environment variables."""
    model_config = SettingsConfigDict(env_prefix="")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "store_intel"
    db_password: str = "store_intel_pass"
    db_name: str = "store_intelligence"
    db_min_connections: int = 5
    db_max_connections: int = 20



# ─────────────────────────────────────────────
# Schema Definition
# ─────────────────────────────────────────────

SCHEMA_SQL = """
-- Events table — stores all ingested detection events
CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    store_id        TEXT NOT NULL,
    camera_id       TEXT NOT NULL,
    visitor_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    zone_id         TEXT,
    dwell_ms        INTEGER DEFAULT 0,
    is_staff        BOOLEAN DEFAULT FALSE,
    confidence      REAL NOT NULL,
    metadata        JSONB DEFAULT '{}',
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast query patterns
CREATE INDEX IF NOT EXISTS idx_events_store_id ON events (store_id);
CREATE INDEX IF NOT EXISTS idx_events_visitor_id ON events (visitor_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp);
CREATE INDEX IF NOT EXISTS idx_events_store_type ON events (store_id, event_type);
CREATE INDEX IF NOT EXISTS idx_events_store_visitor ON events (store_id, visitor_id);
CREATE INDEX IF NOT EXISTS idx_events_store_zone ON events (store_id, zone_id);
CREATE INDEX IF NOT EXISTS idx_events_staff ON events (is_staff);

-- POS transactions table
CREATE TABLE IF NOT EXISTS pos_transactions (
    id              SERIAL PRIMARY KEY,
    order_id        TEXT,
    invoice_number  TEXT,
    store_id        TEXT NOT NULL,
    order_date      DATE,
    order_time      TIME,
    timestamp       TIMESTAMPTZ,
    customer_name   TEXT,
    sku             TEXT,
    product_name    TEXT,
    brand_name      TEXT,
    department      TEXT,
    sub_category    TEXT,
    qty             INTEGER DEFAULT 1,
    gmv             REAL DEFAULT 0,
    nmv             REAL DEFAULT 0,
    total_amount    REAL DEFAULT 0,
    salesperson_id  TEXT,
    salesperson_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_pos_store_id ON pos_transactions (store_id);
CREATE INDEX IF NOT EXISTS idx_pos_timestamp ON pos_transactions (timestamp);
CREATE INDEX IF NOT EXISTS idx_pos_store_timestamp ON pos_transactions (store_id, timestamp);
"""


# ─────────────────────────────────────────────
# Connection Pool Management
# ─────────────────────────────────────────────

class Database:
    """Manages the PostgreSQL connection pool."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.settings = DatabaseSettings()
        self._start_time: Optional[float] = None

    async def connect(self) -> None:
        """Create the connection pool and initialize schema."""
        import time
        self._start_time = time.time()

        dsn = (
            f"postgresql://{self.settings.db_user}:{self.settings.db_password}"
            f"@{self.settings.db_host}:{self.settings.db_port}"
            f"/{self.settings.db_name}"
        )

        retries = 5
        for attempt in range(retries):
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=dsn,
                    min_size=self.settings.db_min_connections,
                    max_size=self.settings.db_max_connections,
                )
                logger.info("Database connection pool created successfully")
                break
            except (asyncpg.CannotConnectNowError, OSError, ConnectionRefusedError) as e:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        f"Database connection attempt {attempt + 1}/{retries} failed, "
                        f"retrying in {wait}s: {e}"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Failed to connect to database after {retries} attempts")
                    raise

        # Initialize schema
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
            logger.info("Database schema initialized")

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    @property
    def uptime_seconds(self) -> float:
        """Return service uptime in seconds."""
        import time
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection from the pool with error handling."""
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            yield conn

    async def is_healthy(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            if not self.pool:
                return False
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception:
            return False


# Singleton database instance
db = Database()
