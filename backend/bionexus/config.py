from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str | None = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"
    batch_size: int = 500
    connect_attempts: int = 5
    connect_backoff_seconds: float = 2.0
    transaction_retry_seconds: float = 30.0
    max_upload_bytes: int = 50 * 1024 * 1024
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        return cls(
            neo4j_uri=env.get("NEO4J_URI", cls.neo4j_uri),
            neo4j_user=env.get("NEO4J_USER", cls.neo4j_user) or None,
            neo4j_password=env.get("NEO4J_PASSWORD") or None,
            neo4j_database=env.get("NEO4J_DATABASE", cls.neo4j_database),
            batch_size=int(env.get("BIONEXUS_BATCH_SIZE", cls.batch_size)),
            connect_attempts=int(env.get("BIONEXUS_CONNECT_ATTEMPTS", cls.connect_attempts)),
            connect_backoff_seconds=float(env.get("BIONEXUS_CONNECT_BACKOFF", cls.connect_backoff_seconds)),
            transaction_retry_seconds=float(env.get("BIONEXUS_TX_RETRY_SECONDS", cls.transaction_retry_seconds)),
            max_upload_bytes=int(env.get("BIONEXUS_MAX_UPLOAD_BYTES", cls.max_upload_bytes)),
            cors_origins=tuple(o.strip() for o in env.get("BIONEXUS_CORS_ORIGINS", ",".join(cls.cors_origins)).split(",") if o.strip()),
            log_level=env.get("BIONEXUS_LOG_LEVEL", cls.log_level).upper(),
        )


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # The driver logs every retried transaction at INFO; keep it to warnings.
    logging.getLogger("neo4j").setLevel(logging.WARNING)
