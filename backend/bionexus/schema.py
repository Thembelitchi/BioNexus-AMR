"""Uniqueness constraints and indexes backing every MERGE key."""

from __future__ import annotations

import logging

from .db import GraphClient

log = logging.getLogger(__name__)

CONSTRAINTS = {
    "patient_id": "FOR (n:Patient) REQUIRE n.id IS UNIQUE",
    "encounter_id": "FOR (n:Encounter) REQUIRE n.id IS UNIQUE",
    "location_event_id": "FOR (n:LocationEvent) REQUIRE n.id IS UNIQUE",
    "ward_name": "FOR (n:Ward) REQUIRE n.name IS UNIQUE",
    "isolate_id": "FOR (n:Isolate) REQUIRE n.id IS UNIQUE",
    "pathogen_taxid": "FOR (n:Pathogen) REQUIRE n.ncbi_taxid IS UNIQUE",
    "antibiotic_atc": "FOR (n:Antibiotic) REQUIRE n.atc_code IS UNIQUE",
    "sequence_type_key": "FOR (n:SequenceType) REQUIRE n.key IS UNIQUE",
    "gene_aro": "FOR (n:Gene) REQUIRE n.aro_id IS UNIQUE",
    "mge_key": "FOR (n:MobileGeneticElement) REQUIRE n.key IS UNIQUE",
}

INDEXES = {
    "isolate_collected": "FOR (n:Isolate) ON (n.collected)",
    "location_event_timestamp": "FOR (n:LocationEvent) ON (n.timestamp)",
    "mge_replicon": "FOR (n:MobileGeneticElement) ON (n.replicon)",
}


def ensure_schema(client: GraphClient) -> None:
    def work(tx):
        for name, body in CONSTRAINTS.items():
            tx.run(f"CREATE CONSTRAINT {name} IF NOT EXISTS {body}")

    def indexes(tx):
        for name, body in INDEXES.items():
            tx.run(f"CREATE INDEX {name} IF NOT EXISTS {body}")

    # Schema statements are kept out of data transactions; every statement is
    # IF NOT EXISTS, so this is safe to run at every startup.
    client.write(work)
    client.write(indexes)
    log.info("schema ensured: %d constraints, %d indexes", len(CONSTRAINTS), len(INDEXES))
