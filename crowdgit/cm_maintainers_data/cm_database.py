import asyncio
import asyncpg
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from crowdgit.logger import get_logger
from dotenv import load_dotenv

logger = get_logger(__name__)

load_dotenv()


async def ensure_db_connection():
    try:
        async with get_db_connection(is_read_operation=True) as conn:
            await conn.execute("SELECT 1")
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        logger.warn("Database connection closed. Restarting db-ssh and db-port...")
        logger.warn("Waiting for connection to be re-established...")
        await asyncio.sleep(10)  # Wait for 10 seconds before retrying


async def get_db_connection(is_read_operation: bool = True):
    db_params = {
        "database": "cmProduction",
        "user": "cmProdUser",
        "password": os.getenv("DB_PASSWORD"),
        "host": "localhost",
        "port": "5445" if is_read_operation else "5444",
    }
    return await asyncpg.connect(**db_params)


async def query(sql: str, params: tuple = None) -> List[Dict[str, Any]]:
    await ensure_db_connection()
    try:
        async with get_db_connection(is_read_operation=True) as conn:
            results = await conn.fetch(sql, *params) if params else await conn.fetch(sql)
            return [dict(row) for row in results]
    except Exception as error:
        logger.error(f"Error executing query: {error}")
        raise error


async def execute(sql: str, params: tuple = None) -> None:
    await ensure_db_connection()
    try:
        async with get_db_connection(is_read_operation=False) as conn:
            await conn.execute(sql, *params) if params else await conn.execute(sql)
    except Exception as error:
        logger.error(f"Error executing query: {error}")
        raise error
