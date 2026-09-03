"""A queued databot invocation.

The scheduler keeps only the bot class and its configuration in the queue.
Constructing the bot - which used to open a database connection and register
the bot - is deferred to the worker that actually executes the job, so pending
jobs no longer occupy database connections.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BotJob:
    bot_name: str
    bot_cls: type
    config: dict[str, Any] = field(default_factory=dict)

    def create_bot(self):
        """Instantiate the bot. Called by a worker, never by the scheduler."""
        return self.bot_cls(config=self.config)
