import os
import psycopg
from psycopg_pool import AsyncConnectionPool
from utils.logger import log_info, log_success, log_error

_pool: AsyncConnectionPool | None = None


def _build_conninfo() -> str:
    return (
        f"host={os.environ.get('DB_HOST', 'localhost')} "
        f"port={os.environ.get('DB_PORT', '5432')} "
        f"dbname={os.environ.get('DB_NAME', 'qa_agent')} "
        f"user={os.environ.get('DB_USER', 'qa_user')} "
        f"password={os.environ.get('DB_PASSWORD', '')} "
    )


async def get_pool() -> AsyncConnectionPool:
    global _pool

    if _pool is None:
        log_info("Initializing database connection pool...")
        _pool = AsyncConnectionPool(
            conninfo=_build_conninfo(),
            min_size=1,
            max_size=5,
            open=False,
        )
        await _pool.open()
        log_success("Database connection pool ready.")

    return _pool


async def close_pool():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None
        log_info("Database connection pool closed.")