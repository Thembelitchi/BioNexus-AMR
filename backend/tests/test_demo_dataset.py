"""Clinical-validity checks for the South African demonstration dataset.

These encode the medical ontologist's acceptance criteria: every category
agrees with CLSI, every genotype is reflected in the phenotype, laboratory
flags match the antibiogram, the generator is reproducible, and (with a
database) the analytics recover each planted scenario.
"""

from __future__ import annotations

import csv
import filecmp
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from bionexus import ontology
from bionexus.breakpoints import interpret
from bionexus.etl import read_csv, transform
from bionexus.models import parse_mic

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "data" / "demo"


def rows(name: str) -> list[dict[str, str]]:
    return list(csv.DictReader(open(DEMO / name, encoding="utf-8")))


@pytest.fixture(scope="module")
def isolates() -> dict[str, dict]:
    """Per isolate: context, {drug: category} and the set of genes found."""
    by_sample: dict[str, dict] = {}
    for row in rows("clinical.csv"):
        entry = by_sample.setdefault(row["SampleID"], {"row": row, "sir": {}, "genes": set(), "sequenced": False})
        entry["sir"][row["Antibiotic"]] = row["Result"]
    for row in rows("genomic.csv"):
        by_sample[row["SampleID"]]["sequenced"] = True
        if not ontology.is_wild_type(row["GeneDetected"]):
            by_sample[row["SampleID"]]["genes"].add(row["GeneDetected"])
    return by_sample


def test_dataset_ingests_without_errors_or_warnings():
    result = transform(read_csv(DEMO / "clinical.csv"), read_csv(DEMO / "genomic.csv"), read_csv(DEMO / "movements.csv"))
    assert result.issues == []
    assert len({r.patient_id for r in result.isolates}) == 600
    assert len({r.ward.facility for r in result.isolates}) == 4


def test_every_category_matches_clsi_2025():
    for row in rows("clinical.csv"):
        organism, _ = ontology.resolve_organism(row["Organism"])
        drug = ontology.resolve_antibiotic(row["Antibiotic"])
        mic, qualifier = parse_mic(row["MIC"])
        assert row["Guideline"] == "CLSI 2025"
        assert interpret(organism.ncbi_taxid, drug.amr_code, mic, qualifier) == row["Result"], row


GENOTYPE_RULES = [
    # (gene, organisms, drug that must not test susceptible, rationale)
    ("blaOXA-181", None, "Ertapenem", "OXA-48-like carbapenemases raise the ertapenem MIC"),
    ("blaOXA-48", None, "Ertapenem", "OXA-48-like carbapenemases raise the ertapenem MIC"),
    ("blaOXA-232", None, "Ertapenem", "OXA-48-like carbapenemases raise the ertapenem MIC"),
    ("blaNDM-1", None, "Meropenem", "metallo-beta-lactamases hydrolyse carbapenems"),
    ("blaNDM-5", None, "Meropenem", "metallo-beta-lactamases hydrolyse carbapenems"),
    ("blaVIM-2", None, "Meropenem", "metallo-beta-lactamases hydrolyse carbapenems"),
    ("blaKPC-2", None, "Meropenem", "KPC hydrolyses carbapenems"),
    ("blaOXA-23", None, "Meropenem", "OXA-23 confers carbapenem resistance in A. baumannii"),
    ("blaCTX-M-15", None, "Ceftriaxone", "CTX-M-15 hydrolyses third-generation cephalosporins"),
    ("mecA", None, "Oxacillin", "PBP2a confers resistance to anti-staphylococcal penicillins"),
    ("vanA", None, "Vancomycin", "VanA confers high-level vancomycin resistance"),
    ("mcr-1.1", None, "Colistin", "MCR-1 confers colistin resistance"),
]


@pytest.mark.parametrize("gene, _organisms, drug, rationale", GENOTYPE_RULES)
def test_genotype_is_reflected_in_phenotype(isolates, gene, _organisms, drug, rationale):
    carriers = [entry for entry in isolates.values() if gene in entry["genes"]]
    assert carriers, f"no isolate carries {gene}"
    for entry in carriers:
        assert entry["sir"].get(drug, "missing") not in {"S", "missing"}, f"{entry['row']['SampleID']}: {rationale}"


def test_metallo_beta_lactamases_defeat_ceftazidime_avibactam(isolates):
    for entry in isolates.values():
        if entry["genes"] & {"blaNDM-1", "blaNDM-5", "blaVIM-2"} and "Ceftazidime-avibactam" in entry["sir"]:
            assert entry["sir"]["Ceftazidime-avibactam"] == "R"


def test_no_vancomycin_resistant_staphylococcus_aureus(isolates):
    for entry in isolates.values():
        if entry["row"]["Organism"].startswith("Staphylococcus aureus"):
            assert entry["sir"]["Vancomycin"] == "S"


def test_laboratory_flags_match_the_antibiogram(isolates):
    carbapenems = ("Ertapenem", "Meropenem", "Imipenem")
    for entry in isolates.values():
        organism = entry["row"]["Organism"]
        _, labels = ontology.resolve_organism(organism)
        sir = entry["sir"]
        if "MRSA" in labels or organism.startswith("Staphylococcus aureus"):
            assert ("MRSA" in labels) == (sir["Oxacillin"] == "R")
        if organism.startswith("Enterococcus faecium"):
            assert ("VRE" in labels) == (sir["Vancomycin"] == "R")
        if organism.startswith(("Klebsiella", "Escherichia", "Enterobacter")):
            assert ("CRE" in labels) == any(sir.get(c) == "R" for c in carbapenems)
        if organism.startswith("Acinetobacter"):
            assert ("CRAB" in labels) == ("R" in (sir.get("Meropenem"), sir.get("Imipenem")))


def test_intrinsic_resistance_is_not_reported_as_susceptible(isolates):
    # Agents to which an organism is intrinsically resistant are not on its panel.
    intrinsic = {
        "Klebsiella pneumoniae": {"Ampicillin"},
        "Enterobacter cloacae": {"Ampicillin", "Amoxicillin-clavulanate", "Cefoxitin"},
        "Pseudomonas aeruginosa": {"Ampicillin", "Amoxicillin-clavulanate", "Ceftriaxone", "Ertapenem", "Trimethoprim-sulfamethoxazole", "Tigecycline"},
        "Acinetobacter baumannii": {"Ampicillin", "Amoxicillin-clavulanate", "Ertapenem"},
    }
    for entry in isolates.values():
        species = entry["row"]["Organism"].split(" (")[0]
        assert not intrinsic.get(species, set()) & set(entry["sir"]), entry["row"]["SampleID"]


def test_clinical_context_is_coherent(isolates):
    for entry in isolates.values():
        row = entry["row"]
        assert row["AdmitDate"] <= row["Date"]
        assert not row["DischargeDate"] or row["Date"] <= row["DischargeDate"]
        age = float(row["AgeYears"])
        if row["Ward"] == "Neonatal ICU":
            assert age <= 28 / 365.25 + 1e-6
        if row["Ward"] in {"Adult ICU", "Medical", "Surgical", "Haematology-Oncology"}:
            assert age >= 18


def test_movements_place_each_isolate_in_its_reported_ward():
    events = defaultdict(list)
    for row in rows("movements.csv"):
        events[row["EncounterID"]].append((row["Timestamp"], f"{row['Facility']}:{row['Ward']}"))
    for sample, entry in {r["SampleID"]: r for r in rows("clinical.csv")}.items():
        prior = sorted(e for e in events[entry["EncounterID"]] if e[0] <= entry["Date"])
        assert prior, f"{sample} has no admission before collection"
        assert prior[-1][1] == f"{entry['Facility']}:{entry['Ward']}", sample


def test_generator_is_reproducible(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_demo_dataset.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    for name in ("clinical.csv", "genomic.csv", "movements.csv", "scenarios.json"):
        assert filecmp.cmp(DEMO / name, tmp_path / name, shallow=False), f"{name} differs from a fresh generation"


# --------------------------------------------------------------------------- recovery


@pytest.fixture(scope="module")
def loaded_demo(graph_client):
    from bionexus.pipeline import ingest

    graph_client.write(lambda tx: tx.run("MATCH (n) DETACH DELETE n").consume())
    report = ingest(graph_client, DEMO / "clinical.csv", DEMO / "genomic.csv", DEMO / "movements.csv")
    assert report.issues == []
    return graph_client


SCENARIOS = json.loads((DEMO / "scenarios.json").read_text())


@pytest.mark.integration
@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_analytics_recover_planted_scenario(loaded_demo, key):
    from bionexus import analytics

    expect = SCENARIOS[key]["expect"]
    if "cluster" in expect:
        want = expect["cluster"]
        clusters = analytics.detect_spatiotemporal_clusters(loaded_demo)
        matching = [
            c for c in clusters
            if (c.ward == want["ward"] if "ward" in want else c.ward.endswith(want["ward_suffix"]))
            and c.sequence_type == want["sequence_type"] and c.gene == want["gene"]
        ]
        assert matching and max(c.size for c in matching) >= want["min_size"], (key, [(c.ward, c.size) for c in matching])
    if "hgt" in expect:
        want = expect["hgt"]
        signals = {s.gene: s for s in analytics.detect_horizontal_gene_transfer(loaded_demo)}
        assert want["gene"] in signals
        assert set(want["taxa_include"]) <= set(signals[want["gene"]].taxa)
        assert want["replicon"] in signals[want["gene"]].replicons
    if "transfer_edge" in expect:
        want = expect["transfer_edge"]
        rows_ = loaded_demo.query(
            "MATCH (p:Patient)-[:HAD_ENCOUNTER]->(:Encounter)-[:GENERATED_EVENT]->(le)-[:AT_LOCATION]->(w:Ward) "
            "WITH p, le, w ORDER BY le.timestamp WITH p, collect(w.key) AS path "
            "UNWIND range(0, size(path) - 2) AS k WITH path[k] AS a, path[k + 1] AS b WHERE a <> b "
            "RETURN a, b, count(*) AS n"
        )
        transfers = sum(r["n"] for r in rows_ if sorted([r["a"], r["b"]]) == sorted(want["wards"]))
        assert transfers >= want["min_transfers"]
    if "gene_present" in expect:
        found = loaded_demo.query("MATCH (:Isolate)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene {symbol: $s}) RETURN count(*) AS n", s=expect["gene_present"])
        assert found[0]["n"] >= 1


@pytest.mark.integration
def test_ward_network_spans_facilities(loaded_demo):
    from bionexus import analytics

    report = analytics.rank_wards(loaded_demo)
    facilities = {w.facility for w in report.wards}
    assert facilities == {"GAH", "GDH", "KRH", "WTH"}
    assert report.transfer_links > 0 and report.genomic_links > 0
