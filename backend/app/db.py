from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .config import settings


_pool: ThreadedConnectionPool | None = None


def pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        common = {
            "connect_timeout": 10,
            "application_name": "ativa_command_center",
        }
        if settings.database_url:
            _pool = ThreadedConnectionPool(1, 8, settings.database_url, **common)
        else:
            _pool = ThreadedConnectionPool(
                1,
                8,
                host=settings.bi_host,
                port=settings.bi_port,
                dbname=settings.bi_database,
                user=settings.bi_user,
                password=settings.bi_password,
                **common,
            )
    return _pool


@contextmanager
def connection(read_only: bool = True) -> Iterator[Any]:
    conn = pool().getconn()
    try:
        conn.set_client_encoding("LATIN1")
        conn.autocommit = False
        with conn.cursor() as cur:
            if read_only:
                cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = %s", (settings.query_timeout_ms,))
        yield conn
        conn.rollback() if read_only else conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool().putconn(conn)


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def rows(cur: Any) -> list[dict[str, Any]]:
    return [{k: json_value(v) for k, v in dict(row).items()} for row in cur.fetchall()]


def query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or {})
            return rows(cur)


def query_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    result = query(sql, params)
    return result[0] if result else {}
