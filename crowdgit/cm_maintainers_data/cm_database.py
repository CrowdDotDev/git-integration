import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any
import os
import time
from dotenv import load_dotenv

load_dotenv()


def ensure_db_connection():
    try:
        with get_db_connection(is_read_operation=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except psycopg2.OperationalError:
        print("Database connection closed. Restarting db-ssh and db-port...")
        os.system("./restart_db_connection.sh")
        print("Waiting for connection to be re-established...")
        time.sleep(10)  # Wait for 10 seconds before retrying


def get_db_connection(is_read_operation: bool = True):
    db_params = {
        "dbname": "cmProduction",
        "user": "cmProdUser",
        "password": os.getenv("DB_PASSWORD"),
        "host": "localhost",
        "port": "5445" if is_read_operation else "5444",
    }
    return psycopg2.connect(**db_params)


def query(sql: str, params: tuple = None) -> List[Dict[str, Any]]:
    ensure_db_connection()
    try:
        with get_db_connection(is_read_operation=True) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
    except (Exception, psycopg2.Error) as error:
        print(f"Error executing query: {error}")
        raise error


def execute(sql: str, params: tuple = None) -> None:
    ensure_db_connection()
    try:
        with get_db_connection(is_read_operation=False) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
    except (Exception, psycopg2.Error) as error:
        print(f"Error executing query: {error}")
        raise error
