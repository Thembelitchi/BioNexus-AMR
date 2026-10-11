"""The Cypher export in graph/ must reload into an identical graph."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from neo4j.time import DateTime

from bionexus.pipeline import ingest

from .conftest import CLINICAL_CSV, GENOMIC_CSV

BACKEND = Path(__file__).resolve().parent.parent
GRAPH_FILE = BACKEND.parent / "graph" / "bionexus-demo.cypher"

_spec = importlib.util.spec_from_file_location("export_graph", BACKEND / "tools" / "export_graph.py")
export_graph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_graph)


def test_literals_round_trip_awkward_values():
    assert export_graph.literal("O'Brien\\ward;\n//x") == "'O\\'Brien\\\\ward;\\n//x'"
    assert export_graph.literal([1, 2.5, True, None, "a"]) == "[1, 2.5, true, null, 'a']"
    assert export_graph.literal(2.0) == "2.0"  # stays a float
    stamp = DateTime(2025, 7, 1, 7, 45, 0)
    assert export_graph.literal(stamp) == "localdatetime('2025-07-01T07:45:00.000000000')"
    with pytest.raises(ValueError):
        export_graph.literal(float("nan"))


def test_statement_split_ignores_semicolons_inside_strings():
    script = "// header;\nCREATE (n {a: 'x;y'});\nUNWIND [\n  {i: 0, p: {s: 'end;'}}\n] AS row\nRETURN row;\n"
    assert export_graph.statements(script) == ["CREATE (n {a: 'x;y'})", "UNWIND [\n  {i: 0, p: {s: 'end;'}}\n] AS row\nRETURN row"]


def test_committed_demo_graph_matches_the_demo_dataset():
    header = GRAPH_FILE.read_text(encoding="utf-8").split("\n", 4)[:4]
    nodes = dict((label, int(n)) for label, n in re.findall(r"(\w+) (\d+)", header[2].split(":", 1)[1]))
    rels = dict((t, int(n)) for t, n in re.findall(r"(\w+) (\d+)", header[3].split(":", 1)[1]))
    assert nodes["Patient"] == 600 and nodes["Isolate"] == 673 and nodes["Facility"] == 4
    assert rels["EXHIBITS"] == 7391
    # Pseudonymised at ingest: no raw demo patient IDs in the published graph.
    text = GRAPH_FILE.read_text(encoding="utf-8")
    assert "'PT-" not in text and "'ENC-" not in text and "'P-" in text


@pytest.mark.integration
def test_export_reloads_into_an_identical_graph(graph):
    ingest(graph, CLINICAL_CSV, GENOMIC_CSV, batch_size=64)
    first = export_graph.export_cypher(graph)

    graph.write(lambda tx: tx.run("MATCH (n) DETACH DELETE n").consume())
    export_graph.load_cypher(graph, first)
    assert export_graph.export_cypher(graph) == first
    assert graph.query("MATCH (n:BioNexusImport) RETURN count(n) AS n") == [{"n": 0}]

    with pytest.raises(SystemExit, match="not empty"):
        export_graph.load_cypher(graph, first)
