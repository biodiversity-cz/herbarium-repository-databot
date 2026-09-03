"""Thread-safe, bounded PostgreSQL connection pool (stdlib + psycopg2 only).

Motivation
----------
Databots used to open a ``psycopg2`` connection when the bot object was
constructed and keep it for the whole lifetime of the bot. A single run can
process hundreds of records (S3 download + ML inference per record), and the
scheduler constructed bots already at enqueue time. The database therefore saw
backends sitting in ``idle`` / ``idle in transaction`` for minutes and every
queued bot added one more connection.

This pool checks a connection out for the duration of a single database
operation and always returns it, so the number of server backends is bounded by
``connection.pool.max`` and no connection is ever parked inside an open
transaction.

Production notes
----------------
* Production talks to ``pgsql-pooler-rw`` (a PgBouncer-style pooler). Per
  connection GUCs sent in the startup packet (``options=-c ...``) are not
  reliably applied to a shared server connection in transaction pooling mode,
  so session tuning belongs on the database role, e.g.::

      ALTER ROLE herbarium_databot SET idle_in_transaction_session_timeout = '30s';

* ``statement_timeout`` is disabled by default (``0``) because chart
  aggregations and record selection legitimately run for a long time.
* ``application_name`` is set so backends are recognisable::

      SELECT pid, state, application_name, xact_start, left(query, 100)
      FROM pg_stat_activity
      WHERE application_name = 'herbarium-databot';

* This psycopg2 build (2.9.11) has no ``connection.ping()``, so the health
  check is a cheap ``SELECT 1`` round trip instead.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator

import psycopg2

from config import config

logger = logging.getLogger(__name__)

APPLICATION_NAME = "herbarium-databot"

ConnectionFactory = Callable[[], Any]


class PoolExhausted(RuntimeError):
    """Raised when no connection became available within the checkout timeout."""


def _as_int(value: Any, default: int, what: str) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid integer for %s: %r - falling back to %s", what, value, default)
        return default


def _as_float(value: Any, default: float, what: str) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid number for %s: %r - falling back to %s", what, value, default)
        return default


def _as_bool(value: Any, default: bool, what: str = "") -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    logger.warning("Invalid boolean for %s: %r - falling back to %s", what or "value", value, default)
    return default


def build_connect_kwargs() -> dict[str, Any]:
    """Build the libpq connection arguments from the application configuration."""
    kwargs: dict[str, Any] = {
        "dbname": config.get_database_config("database", "jacq_dev"),
        "user": config.get_database_config("user", "databot"),
        "password": config.get_database_config("password", "databot"),
        "host": config.get_database_config("host", "localhost"),
        "port": config.get_database_config("port", 5433),
        # Never let a connect hang forever - that used to block a whole worker.
        "connect_timeout": _as_int(config.get_pool_config("connect_timeout", 10), 10, "connection.pool.connect_timeout"),
        "application_name": str(config.get_pool_config("application_name", APPLICATION_NAME) or APPLICATION_NAME),
        # Detect silently dropped TCP sessions (LB / NAT idle timeouts) instead
        # of blocking on a dead socket forever.
        "keepalives": 1,
        "keepalives_idle": _as_int(config.get_pool_config("keepalives_idle", 30), 30, "connection.pool.keepalives_idle"),
        "keepalives_interval": _as_int(config.get_pool_config("keepalives_interval", 10), 10, "connection.pool.keepalives_interval"),
        "keepalives_count": _as_int(config.get_pool_config("keepalives_count", 3), 3, "connection.pool.keepalives_count"),
    }

    statement_timeout = _as_int(config.get_pool_config("statement_timeout", 0), 0, "connection.pool.statement_timeout")
    if statement_timeout > 0:
        kwargs["options"] = f"-c statement_timeout={statement_timeout}"

    return kwargs


class DatabasePool:
    """A small, bounded, thread-safe pool of psycopg2 connections.

    A connection is only ever handed to one thread at a time. Connections are
    validated on checkout and always have their transaction finished before
    they go back into the idle list, which is what keeps PostgreSQL from
    accumulating ``idle in transaction`` backends.
    """

    def __init__(
        self,
        min_conn: int = 1,
        max_conn: int = 6,
        checkout_timeout: float = 10.0,
        healthcheck: bool = True,
        max_idle_seconds: float = 300.0,
        connect_kwargs: dict[str, Any] | None = None,
        factory: ConnectionFactory | None = None,
    ):
        min_conn = max(0, _as_int(min_conn, 1, "connection.pool.min"))
        max_conn = max(1, _as_int(max_conn, 6, "connection.pool.max"))
        if min_conn > max_conn:
            logger.warning(
                "connection.pool.min (%s) is greater than connection.pool.max (%s) - using min = max",
                min_conn, max_conn,
            )
            min_conn = max_conn

        self.min_conn = min_conn
        self.max_conn = max_conn
        self.checkout_timeout = max(0.0, _as_float(checkout_timeout, 10.0, "connection.pool.checkout_timeout"))
        self.healthcheck = _as_bool(healthcheck, True, "connection.pool.healthcheck")
        self.max_idle_seconds = max(0.0, _as_float(max_idle_seconds, 300.0, "connection.pool.max_idle"))
        self.connect_kwargs: dict[str, Any] = (
            dict(connect_kwargs) if connect_kwargs is not None else build_connect_kwargs()
        )
        # Injectable for tests; production always uses psycopg2.connect.
        self._factory: ConnectionFactory = factory or self._default_factory

        self._condition = threading.Condition(threading.Lock())
        # Idle connections as [monotonic_timestamp, connection]; LIFO reuse lets
        # the least recently used entries hit max_idle_seconds and be recycled.
        self._idle: list[list[Any]] = []
        self._size = 0          # connections owned by the pool (idle + checked out)
        self._checked_out = 0
        self._closed = False

        self._created = 0
        self._discarded = 0
        self._failed_healthchecks = 0
        self._waits = 0
        self._exhausted = 0

        self._prewarm()

    # ------------------------------------------------------------------
    # Construction / teardown
    # ------------------------------------------------------------------
    def _default_factory(self):
        return psycopg2.connect(**self.connect_kwargs)

    @property
    def closed(self) -> bool:
        return self._closed

    def _prewarm(self) -> None:
        """Open ``connection.pool.min`` connections eagerly, never failing on error."""
        for _ in range(self.min_conn):
            try:
                conn = self._factory()
            except Exception as exc:
                logger.warning("Connection prewarm failed (%s) - connections will be created on demand", exc)
                break
            with self._condition:
                if self._closed:
                    keep = False
                else:
                    self._size += 1
                    self._created += 1
                    self._idle.append([time.monotonic(), conn])
                    keep = True
            if not keep:
                self._close_quietly(conn)

    def closeall(self) -> None:
        """Close every idle connection and refuse further checkouts."""
        with self._condition:
            self._closed = True
            idle, self._idle = self._idle, []
            self._condition.notify_all()

        for _, conn in idle:
            self._close_quietly(conn)
            with self._condition:
                self._size -= 1

        logger.info("Database pool closed (%s idle connections released)", len(idle))

    @staticmethod
    def _close_quietly(conn) -> None:
        try:
            if conn is not None and not getattr(conn, "closed", 0):
                conn.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Ignoring error while closing a connection: %s", exc)

    # ------------------------------------------------------------------
    # Checkout / checkin
    # ------------------------------------------------------------------
    def get_connection(self):
        """Check out a usable connection.

        Blocks up to ``connection.pool.checkout_timeout`` seconds and then
        raises :class:`PoolExhausted` rather than hanging a worker forever.
        """
        deadline = time.monotonic() + self.checkout_timeout

        # A dead connection is dropped and the attempt repeated. The loop is
        # bounded by max_conn + 1 so a pathological pool cannot spin forever.
        for _attempt in range(self.max_conn + 1):
            conn, must_create = self._acquire_slot(deadline)

            if must_create:
                try:
                    conn = self._factory()
                except Exception:
                    self._release_slot()
                    raise
                with self._condition:
                    self._created += 1
                logger.debug("Opened a new database connection (pool size %s)", self._size)
                return conn

            if self._is_healthy(conn):
                return conn

            self.discard(conn)

        self._exhausted += 1
        raise PoolExhausted("no healthy database connection could be checked out")

    def _acquire_slot(self, deadline: float):
        """Reserve a slot, returning ``(idle_connection, False)`` or ``(None, True)``."""
        with self._condition:
            while True:
                if self._closed:
                    raise PoolExhausted("database pool is closed")

                while self._idle:
                    timestamp, conn = self._idle.pop()
                    if self.max_idle_seconds > 0 and (time.monotonic() - timestamp) > self.max_idle_seconds:
                        logger.debug("Recycling a connection idle for more than %ss", self.max_idle_seconds)
                        self._discarded += 1
                        self._size -= 1
                        self._close_quietly(conn)
                        continue
                    self._checked_out += 1
                    return conn, False

                if self._size < self.max_conn:
                    # Reserve the slot before dropping the lock so concurrent
                    # threads cannot exceed max_conn while we connect.
                    self._size += 1
                    self._checked_out += 1
                    return None, True

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._exhausted += 1
                    raise PoolExhausted(
                        f"all {self.max_conn} database connections are in use "
                        f"(waited {self.checkout_timeout:g}s)"
                    )

                self._waits += 1
                logger.debug("Waiting %.1fs for a free database connection", remaining)
                self._condition.wait(remaining)

    def _release_slot(self) -> None:
        """Give back a reserved slot when creating a connection failed."""
        with self._condition:
            self._size -= 1
            self._checked_out -= 1
            self._condition.notify()

    def release(self, conn) -> None:
        """Return a checked out connection, finishing its transaction first."""
        if conn is None:
            return

        broken = False
        if getattr(conn, "closed", 1):
            broken = True
        else:
            try:
                # A connection must never return to the pool inside an open
                # transaction ("idle in transaction"). psycopg2 treats
                # rollback() as a no-op when nothing is in progress.
                conn.rollback()
            except Exception as exc:
                logger.warning("Rollback failed, discarding connection: %s", exc)
                broken = True

        if broken:
            logger.debug("Discarding a broken connection instead of reusing it")
            self.discard(conn)
            return

        with self._condition:
            self._checked_out -= 1
            if self._closed:
                self._size -= 1
                keep = False
            else:
                self._idle.append([time.monotonic(), conn])
                keep = True
            self._condition.notify()

        if not keep:
            self._close_quietly(conn)

    def discard(self, conn) -> None:
        """Close a connection the caller is holding and free its slot."""
        if conn is None:
            return
        self._close_quietly(conn)
        with self._condition:
            self._size -= 1
            self._checked_out -= 1
            self._discarded += 1
            self._condition.notify()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Context manager that always returns the connection to the pool."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            # release() decides whether the connection is reusable, so a failed
            # statement does not drain the pool - only a dead socket does.
            self.release(conn)

    def _is_healthy(self, conn) -> bool:
        if getattr(conn, "closed", 1):
            return False
        if not self.healthcheck:
            return True
        cursor = None
        try:
            # This psycopg2 build has no connection.ping() - a trivial round
            # trip is the portable equivalent.
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
        except Exception as exc:
            with self._condition:
                self._failed_healthchecks += 1
            logger.warning("Discarding an unhealthy database connection: %s", exc)
            return False
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:  # pragma: no cover - defensive
                pass

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        """Pool counters for the status endpoint - never contains credentials."""
        with self._condition:
            return {
                "min": self.min_conn,
                "max": self.max_conn,
                "size": self._size,
                "idle": len(self._idle),
                "checked_out": self._checked_out,
                "spare": max(0, self.max_conn - self._size),
                "created": self._created,
                "discarded": self._discarded,
                "failed_healthchecks": self._failed_healthchecks,
                "waits": self._waits,
                "exhausted": self._exhausted,
                "closed": self._closed,
            }


_pool: DatabasePool | None = None
_pool_lock = threading.Lock()


def get_pool() -> DatabasePool:
    """Return the process wide pool, creating it on first use."""
    global _pool
    if _pool is not None and not _pool.closed:
        return _pool

    with _pool_lock:
        if _pool is None or _pool.closed:
            _pool = DatabasePool(
                min_conn=config.get_pool_config("min", 1),
                max_conn=config.get_pool_config("max", 6),
                checkout_timeout=config.get_pool_config("checkout_timeout", 10),
                healthcheck=config.get_pool_config("healthcheck", True),
                max_idle_seconds=config.get_pool_config("max_idle", 300),
            )
            logger.info(
                "Created database pool (min=%s, max=%s, checkout_timeout=%ss)",
                _pool.min_conn, _pool.max_conn, _pool.checkout_timeout,
            )
        return _pool


def peek_pool() -> DatabasePool | None:
    """Return the current pool without creating one (used by health checks)."""
    return _pool


def close_pool() -> None:
    """Close and forget the process wide pool."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.closeall()
