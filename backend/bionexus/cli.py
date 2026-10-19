"""Command-line entry point: ``bionexus <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from . import alerts, analytics, notifiable
from .config import Settings, configure_logging, pseudonymiser_for
from .db import GraphClient, GraphUnavailableError
from .pipeline import ingest
from .schema import ensure_schema


def _emit(payload) -> None:
    if isinstance(payload, list):
        payload = [item.model_dump(mode="json") for item in payload]
    elif isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bionexus", description="BioNexus AMR knowledge graph")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("schema", help="create constraints and indexes")

    p_ingest = commands.add_parser("ingest", help="validate and load laboratory CSVs")
    p_ingest.add_argument("--clinical", type=Path, required=True)
    p_ingest.add_argument("--genomic", type=Path)
    p_ingest.add_argument("--movements", type=Path)
    p_ingest.add_argument("--dry-run", action="store_true", help="validate only; do not touch the database")

    p_clusters = commands.add_parser("clusters", help="spatiotemporal ST + gene clusters")
    p_clusters.add_argument("--window-days", type=int, default=14)
    p_clusters.add_argument("--min-size", type=int, default=2)
    p_clusters.add_argument("--basis", choices=["genomic", "phenotypic"], default="genomic",
                            help="genomic: same ST and gene; phenotypic: same species and resistance phenotype")

    p_hgt = commands.add_parser("hgt", help="genes shared across species or genera")
    p_hgt.add_argument("--level", choices=["species", "genus"], default="species")

    p_wards = commands.add_parser("wards", help="GDS ward centrality")
    p_wards.add_argument("--window-days", type=int, default=14)

    commands.add_parser("alerts", help="clinical alert rules")
    commands.add_parser("stewardship", help="prescribing by WHO AWaRe group")
    p_resistance = commands.add_parser("resistance", help="first-isolate resistance rates (CLSI M39, WHO GLASS)")
    p_resistance.add_argument("--facility")
    commands.add_parser("notifiable", help="South African Category 4 notifiable conditions")

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    if args.command == "ingest" and args.dry_run:
        report = ingest(None, args.clinical, args.genomic, args.movements, dry_run=True, pseudonymiser=pseudonymiser_for(settings))
        _emit(report)
        return 1 if any(issue.severity == "error" for issue in report.issues) else 0

    try:
        with GraphClient(settings) as client:
            if args.command == "schema":
                ensure_schema(client)
            elif args.command == "ingest":
                ensure_schema(client)
                report = ingest(
                    client, args.clinical, args.genomic, args.movements,
                    batch_size=settings.batch_size, pseudonymiser=pseudonymiser_for(settings),
                )
                _emit(report)
                return 1 if any(issue.severity == "error" for issue in report.issues) else 0
            elif args.command == "clusters":
                detect = analytics.detect_phenotypic_clusters if args.basis == "phenotypic" else analytics.detect_spatiotemporal_clusters
                _emit(detect(client, args.window_days, args.min_size))
            elif args.command == "hgt":
                _emit(analytics.detect_horizontal_gene_transfer(client, args.level))
            elif args.command == "wards":
                _emit(analytics.rank_wards(client, args.window_days))
            elif args.command == "alerts":
                _emit(alerts.clinical_alerts(client))
            elif args.command == "stewardship":
                _emit(analytics.prescribing_by_aware(client))
            elif args.command == "resistance":
                _emit(analytics.resistance_rates(client, facility=args.facility))
            elif args.command == "notifiable":
                _emit(notifiable.notifiable_cases(client))
    except GraphUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except analytics.GdsUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
