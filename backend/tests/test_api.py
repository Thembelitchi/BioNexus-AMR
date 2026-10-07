from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bionexus.api import create_app
from bionexus.config import Settings
from bionexus.db import GraphClient, GraphUnavailableError

from .conftest import CLINICAL_CSV, GENOMIC_CSV


def test_unreachable_database_raises_after_retries():
    settings = Settings(neo4j_uri="bolt://127.0.0.1:1", neo4j_user=None, connect_attempts=2, connect_backoff_seconds=0.01)
    with pytest.raises(GraphUnavailableError, match="cannot reach Neo4j"):
        GraphClient(settings).connect()


@pytest.fixture
def api(graph, graph_settings):
    with TestClient(create_app(graph_settings)) as client:
        yield client


@pytest.mark.integration
def test_api_ingest_and_analytics(api):
    health = api.get("/health").json()
    assert health["status"] == "ok" and health["gds_version"]

    dry = api.post(
        "/ingest",
        params={"dry_run": True},
        files={"clinical": CLINICAL_CSV.read_bytes(), "genomic": GENOMIC_CSV.read_bytes()},
    )
    assert dry.status_code == 200 and dry.json()["isolates"] == 300
    assert api.get("/analytics/clusters").json() == []

    loaded = api.post("/ingest", files={"clinical": CLINICAL_CSV.read_bytes(), "genomic": GENOMIC_CSV.read_bytes()})
    assert loaded.status_code == 200
    assert loaded.json()["sequenced_isolates"] == 300

    clusters = api.get("/analytics/clusters", params={"window_days": 14}).json()
    assert clusters and all(c["size"] >= 2 for c in clusters)
    assert api.get("/analytics/hgt", params={"level": "genus"}).json() == []
    wards = api.get("/analytics/wards/centrality").json()
    assert {w["ward"] for w in wards["wards"]} == {"ICU", "General", "Oncology"}


@pytest.mark.integration
def test_api_rejects_bad_input(api):
    assert api.get("/analytics/clusters", params={"window_days": 0}).status_code == 422
    assert api.post("/ingest", files={"clinical": b"\xff\xfe\x00garbage"}).status_code == 422
    report = api.post("/ingest", files={"clinical": b"PatientID,SampleID\nP-1,S-1\n"}).json()
    assert report["isolates"] == 0 and report["rows_rejected"]["clinical"] == 1
