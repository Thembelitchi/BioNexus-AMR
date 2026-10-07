"""Neo4j driver lifecycle with connection retries.

Managed transactions (``execute_read``/``execute_write``) already retry
transient failures, including dropped connections and leader switches, for
up to ``transaction_retry_seconds``. This module adds a retrying initial
connection and converts exhausted retries into :class:`GraphUnavailableError`
so callers can respond with a clean "service unavailable".
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

from neo4j import Driver, GraphDatabase, ManagedTransaction
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired, TransientError

from .config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T")

_CONNECTION_ERRORS = (ServiceUnavailable, SessionExpired, TransientError, OSError)


class GraphUnavailableError(RuntimeError):
    """The database could not be reached after all retries."""


class GraphClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            raise GraphUnavailableError("graph client is not connected")
        return self._driver

    def connect(self) -> GraphClient:
        s = self.settings
        auth = (s.neo4j_user, s.neo4j_password) if s.neo4j_user and s.neo4j_password else None
        delay = s.connect_backoff_seconds
        for attempt in range(1, s.connect_attempts + 1):
            driver = GraphDatabase.driver(
                s.neo4j_uri,
                auth=auth,
                max_transaction_retry_time=s.transaction_retry_seconds,
                # Optional parts of the model (e.g. HARBORS) legitimately may not
                # exist yet; "unknown label/type" notifications are noise here.
                notifications_disabled_classifications=["UNRECOGNIZED"],
            )
            try:
                driver.verify_connectivity()
            except AuthError:
                driver.close()
                raise
            except _CONNECTION_ERRORS as exc:
                driver.close()
                if attempt == s.connect_attempts:
                    raise GraphUnavailableError(f"cannot reach Neo4j at {s.neo4j_uri}: {exc}") from exc
                log.warning("Neo4j not reachable (attempt %d/%d): %s; retrying in %.1fs", attempt, s.connect_attempts, exc, delay)
                time.sleep(delay)
                delay *= 2
                continue
            self._driver = driver
            log.info("connected to Neo4j at %s (database %r)", s.neo4j_uri, s.neo4j_database)
            return self
        raise AssertionError("unreachable")

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self) -> GraphClient:
        return self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, work: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        return self._run("write", work, *args, **kwargs)

    def read(self, work: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        return self._run("read", work, *args, **kwargs)

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Run a read-only statement and return records as dicts."""

        def work(tx: ManagedTransaction) -> list[dict[str, Any]]:
            return [record.data() for record in tx.run(cypher, params)]

        return self.read(work)

    def _run(self, mode: str, work: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        try:
            with self.driver.session(database=self.settings.neo4j_database) as session:
                execute = session.execute_write if mode == "write" else session.execute_read
                return execute(work, *args, **kwargs)
        except (ServiceUnavailable, SessionExpired) as exc:
            log.error("Neo4j %s transaction failed after retries: %s", mode, exc)
            raise GraphUnavailableError(str(exc)) from exc
