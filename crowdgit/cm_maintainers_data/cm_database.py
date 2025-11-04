import asyncpg
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from crowdgit.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

_read_conn = None
_write_conn = None


async def close_db_connections():
    global _read_conn, _write_conn

    logger.info("Closing database connections")

    if _read_conn:
        await _read_conn.close()
    if _write_conn:
        await _write_conn.close()


async def get_db_connection(is_read_operation: bool = True):
    global _read_conn, _write_conn

    if is_read_operation and _read_conn:
        return _read_conn
    elif not is_read_operation and _write_conn:
        return _write_conn

    db_params = {
        "database": os.getenv("DB_DATABASE"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT_READ") if is_read_operation else os.getenv("DB_PORT_WRITE"),
    }
    required_env_vars = [
        "DB_DATABASE",
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT_READ",
        "DB_PORT_WRITE",
    ]
    missing_env_vars = [var for var in required_env_vars if os.getenv(var) is None]
    if missing_env_vars:
        raise ValueError(
            f"The following environment variables are not set: {', '.join(missing_env_vars)}"
        )

    if is_read_operation:
        _read_conn = await asyncpg.connect(**db_params)
        return _read_conn
    else:
        _write_conn = await asyncpg.connect(**db_params)
        return _write_conn


async def query(sql: str, params: tuple = None) -> List[Dict[str, Any]]:
    try:
        conn = await get_db_connection(is_read_operation=True)
        results = await conn.fetch(sql, *params) if params else await conn.fetch(sql)
        return [dict(row) for row in results]
    except Exception as error:
        logger.error(f"Error executing query: {error}")
        raise


async def execute(sql: str, params: tuple = None) -> None:
    try:
        conn = await get_db_connection(is_read_operation=False)
        await conn.execute(sql, *params) if params else await conn.execute(sql)
    except Exception as error:
        logger.error(f"Error executing query: {error}")
        raise


async def batch_insert(sql: str, records: List[Any], batch_size=100) -> None:
    try:
        conn = await get_db_connection(is_read_operation=False)
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            await conn.executemany(sql, batch)
    except Exception as error:
        logger.error(f"Error executing batch insert: {error}")
        raise
