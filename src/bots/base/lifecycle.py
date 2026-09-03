"""Lazy lifecycle helpers shared by all databot base classes.

Databots used to open a database connection, register themselves and create an
S3 client inside ``__init__``, and called ``sys.exit(1)`` when registration
failed. That was harmful in three ways:

* the scheduler built a full bot object already when a job was *enqueued*, so a
  connection was held while the job waited in the queue;
* a bot that was constructed but never executed still kept a backend open;
* ``sys.exit(1)`` raised ``SystemExit`` inside a worker thread, which escaped
  ``except Exception`` handling and killed the worker.

Everything that touches the outside world is therefore created lazily here:
``DATABASE`` (pool backed, opens nothing until used), ``DB_ID`` (registers on
first access, i.e. inside ``run()``) and ``s3storage``.
"""

from __future__ import annotations

import logging
from abc import ABC

from core.infrastructure.storage.s3_storage import S3Storage

logger = logging.getLogger(__name__)


class DatabotRegistrationError(RuntimeError):
    """Raised when the databot cannot register itself in the database."""


class DatabotLifecycle(ABC):
    """Lazy resources for databots.

    Concrete base classes must set ``DATABASE_CLASS`` to the database facade the
    bot uses (``Database`` / ``UrlDatabase``).
    """

    NAME: str = None
    DESCRIPTION: str = None
    VERSION: int = None
    DATABASE_CLASS = None

    _database = None
    _db_id: int | None = None
    _s3storage: S3Storage | None = None

    @property
    def DATABASE(self):
        """The bot's database facade (connections are borrowed per operation)."""
        if self._database is None:
            if self.DATABASE_CLASS is None:
                raise TypeError(
                    f"{self.__class__.__name__} must define a DATABASE_CLASS class attribute"
                )
            self._database = self.DATABASE_CLASS()
        return self._database

    @property
    def DB_ID(self) -> int:
        """The database id of this bot; registration happens on first use."""
        if self._db_id is None:
            self._db_id = self._register()
        return self._db_id

    @property
    def s3storage(self) -> S3Storage:
        if self._s3storage is None:
            self._s3storage = S3Storage()
        return self._s3storage

    def _register(self) -> int:
        try:
            db_id = self.DATABASE.register_databot(
                self.NAME, self.DESCRIPTION, self.VERSION, self.ROLE.value
            )
        except Exception as exc:
            logger.error("Registration error for bot '%s': %s", self.NAME, exc)
            raise DatabotRegistrationError(
                f"Registration error for bot '{self.NAME}': {exc}"
            ) from exc

        if db_id is None:
            message = (
                f"Registration of databot '{self.NAME}' v{self.VERSION} failed "
                "- probably a higher version is already registered?"
            )
            logger.error(message)
            raise DatabotRegistrationError(message)

        logger.info("Databot ID:%s name:%s is running...", db_id, self.NAME)
        return db_id
