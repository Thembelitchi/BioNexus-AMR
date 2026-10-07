from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
CLINICAL_CSV = DATA / "clinical_phenotype.csv"
GENOMIC_CSV = DATA / "genomic_data.csv"

CLINICAL_HEADER = ["PatientID", "SampleID", "Date", "Ward", "Specimen", "Treatment", "Organism", "Antibiotic", "Result", "MIC"]
GENOMIC_HEADER = ["PatientID", "SampleID", "Organism", "Strain_Subtype", "GeneDetected", "Mechanism", "ClinicalImpact", "MGE_Type", "MGE_Replicon"]


def to_csv(header: list[str], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return buffer.getvalue().encode()


def clinical_row(sample: str, patient: str, organism: str, **overrides: str) -> dict[str, str]:
    row = {
        "PatientID": patient,
        "SampleID": sample,
        "Date": "2025-11-01",
        "Ward": "ICU",
        "Specimen": "Blood Culture",
        "Treatment": "Meropenem",
        "Organism": organism,
        "Antibiotic": "Meropenem",
        "Result": "R",
        "MIC": ">16",
    }
    row.update(overrides)
    return row


def genomic_row(sample: str, patient: str, organism: str, st: str, gene: str, **overrides: str) -> dict[str, str]:
    row = {"PatientID": patient, "SampleID": sample, "Organism": organism, "Strain_Subtype": st, "GeneDetected": gene}
    row.update(overrides)
    return row


@pytest.fixture(scope="session")
def graph_settings():
    """Settings for a disposable test database.

    Integration tests delete every node, so they only run when
    BIONEXUS_TEST_NEO4J_URI explicitly names a throwaway instance.
    """
    uri = os.environ.get("BIONEXUS_TEST_NEO4J_URI")
    if not uri:
        pytest.skip("set BIONEXUS_TEST_NEO4J_URI to run integration tests against a disposable Neo4j")
    from bionexus.config import Settings

    return Settings(
        neo4j_uri=uri,
        neo4j_user=os.environ.get("BIONEXUS_TEST_NEO4J_USER") or None,
        neo4j_password=os.environ.get("BIONEXUS_TEST_NEO4J_PASSWORD") or None,
        neo4j_database=os.environ.get("BIONEXUS_TEST_NEO4J_DATABASE", "neo4j"),
        connect_attempts=2,
        connect_backoff_seconds=0.5,
        batch_size=64,
    )


@pytest.fixture(scope="session")
def graph_client(graph_settings):
    from bionexus.db import GraphClient
    from bionexus.schema import ensure_schema

    with GraphClient(graph_settings) as client:
        ensure_schema(client)
        yield client


@pytest.fixture
def graph(graph_client):
    graph_client.write(lambda tx: tx.run("MATCH (n) DETACH DELETE n").consume())
    return graph_client
