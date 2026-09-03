import json
import logging
import math
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Any, Iterator

from core.domain.ResultStatus import ResultStatus
from core.infrastructure.database.connection_pool import DatabasePool, get_pool
from utils.types import Score

logger = logging.getLogger(__name__)


class BaseDatabase:
    """PostgreSQL access on top of the shared, bounded connection pool.

    Every public method checks a connection out for the duration of a single
    operation and returns it afterwards, so keeping a bot object (or a Flask
    request) alive no longer pins a database backend, and no connection is left
    "idle in transaction" between calls.

    The public API (fetchone / fetchall / execute / close) is unchanged.
    """

    def __init__(self, pool: DatabasePool | None = None):
        self._pool = pool if pool is not None else get_pool()

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------
    @contextmanager
    def _cursor(self, commit: bool = False) -> Iterator[tuple[Any, Any]]:
        """Yield a (cursor, connection) pair borrowed from the pool."""
        with self._pool.connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                yield cursor, conn
                if commit:
                    conn.commit()
            except BaseException:
                try:
                    conn.rollback()
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Rolling back the failed operation failed")
                raise
            finally:
                try:
                    cursor.close()
                except Exception:  # pragma: no cover - defensive
                    pass

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Run several statements as one atomic unit of work.

        Usage::

            with db.transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(...)
        """
        with self._pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except BaseException:
                try:
                    conn.rollback()
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Rolling back the failed transaction failed")
                raise

    def pool_stats(self) -> dict:
        """Connection pool counters (useful for logs and the status endpoint)."""
        return self._pool.stats()

    # ------------------------------------------------------------------
    # Generic query helpers
    # ------------------------------------------------------------------
    def fetchone(self, query: str, params=()):
        with self._cursor(commit=False) as (cur, _conn):
            cur.execute(query, params)
            return cur.fetchone()

    def fetchall(self, query: str, params=()):
        with self._cursor(commit=False) as (cur, _conn):
            cur.execute(query, params)
            return cur.fetchall()

    def execute(self, query: str, params: dict | tuple = (), commit: bool = True):
        with self._cursor(commit=commit) as (cur, _conn):
            cur.execute(query, params)
            try:
                result = cur.fetchall()  # pokud je SELECT/RETURNING
            except psycopg2.ProgrammingError:
                # "no results to fetch" is raised client side, it does not
                # abort the transaction, so the commit below still applies.
                result = None  # pokud není žádný výsledek
        return result

    def close(self) -> None:
        """Kept for backward compatibility.

        Connections now belong to the pool and are returned after every
        operation, so there is nothing to close here and calling it is safe.
        """
        return None

    def register_databot(self, name: str, description: str, version: int, role: str) -> int | None:
        result = self.execute(
            "SELECT databots.register_databot(%s, %s, %s, %s)",
            (name, description, version, role)
        )
        row = result[0] if result else None
        return row["register_databot"] if row else None  # název sloupce podle DB funkce

    def save_success_result(self, databot_id: int, photo_id: int, result: Score):
        """
        Save successful result for databot.
        """
        safe_result = self.sanitize(result)
        json_data = json.dumps(safe_result)
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, result_data) VALUES (%s, %s, %s)",
            (databot_id, photo_id, json_data)
        )

    def upsert_success_result(self, databot_id: int, photo_id: int, result: Score):
        """
        Save successful result for databot.
        """
        safe_result = self.sanitize(result)
        json_data = json.dumps(safe_result)
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, result_data) VALUES (%s, %s, %s) ON CONFLICT (databot_id, photo_id) DO UPDATE SET result_data = EXCLUDED.result_data, lastedit_timestamp = NOW(), message = NULL, status = 'ok'",
            (databot_id, photo_id, json_data)
        )

    def save_error_result(self, databot_id: int, photo_id: int, message: str):
        """
        Save error result for databot.
        """
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, status, message) VALUES (%s, %s, %s, %s) ON CONFLICT (databot_id, photo_id) DO UPDATE SET message = EXCLUDED.message, lastedit_timestamp = NOW()",
            (databot_id, photo_id, ResultStatus.ERROR.value, message)
        )

    def sanitize(self, obj):
        """
        Sanitize object for JSON serialization.
        """
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self.sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self.sanitize(x) for x in obj]
        return obj