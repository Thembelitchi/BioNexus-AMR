"""End-to-end ingest: parse, validate, transform, and (optionally) load."""

from __future__ import annotations

import logging
from pathlib import Path

from .db import GraphClient
from .etl import read_csv, transform
from .loader import derive_isolate_origin, load_isolates, load_movements
from .models import IngestReport
from .privacy import Pseudonymiser

log = logging.getLogger(__name__)

Source = str | Path | bytes


def ingest(
    client: GraphClient | None,
    clinical: Source,
    genomic: Source | None = None,
    movements: Source | None = None,
    *,
    batch_size: int = 500,
    dry_run: bool = False,
    pseudonymiser: Pseudonymiser | None = None,
) -> IngestReport:
    """Validate the files and load accepted records unless ``dry_run``."""
    result = transform(
        read_csv(clinical),
        read_csv(genomic) if genomic is not None else (),
        read_csv(movements) if movements is not None else (),
        pseudonymiser=pseudonymiser,
    )
    if not dry_run:
        if client is None:
            raise ValueError("a graph client is required unless dry_run is set")
        load_isolates(client, result.isolates, batch_size)
        load_movements(client, result.movements, batch_size)
        derive_isolate_origin(client)
    report = IngestReport(
        dry_run=dry_run,
        pseudonymised=pseudonymiser is not None,
        rows_read=result.rows_read,
        rows_rejected=result.rows_rejected,
        isolates=len(result.isolates),
        patients=len({record.patient_id for record in result.isolates}),
        movements=len(result.movements),
        sequenced_isolates=sum(record.genotype_status != "not_sequenced" for record in result.isolates),
        issues=result.issues,
    )
    log.info("ingest complete: %d isolates, %d issues, dry_run=%s", report.isolates, len(report.issues), dry_run)
    return report
