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
from bionexus.breakpoints import interpret, interpret_disk
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
    """Re-interpret every MIC and every disk zone in the dataset."""
    for row in rows("clinical.csv"):
        organism, _ = ontology.resolve_organism(row["Organism"])
        drug = ontology.resolve_antibiotic(row["Antibiotic"])
        assert row["Guideline"] == "CLSI 2026"
        assert bool(row["MIC"]) != bool(row["Zone"]), row  # exactly one measurement
        if row["Zone"]:
            assert interpret_disk(organism.ncbi_taxid, drug.amr_code, float(row["Zone"])) == row["Result"], row
        else:
            mic, qualifier = parse_mic(row["MIC"])
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


@pytest.mark.integration
def test_clinical_alert_rules_match_independent_computation(loaded_demo):
    from bionexus.alerts import clinical_alerts

    sir, encounter_of, treatments = defaultdict(dict), {}, defaultdict(set)
    for row in rows("clinical.csv"):
        sir[row["SampleID"]][row["Antibiotic"]] = row["Result"]
        encounter_of[row["SampleID"]] = row["EncounterID"]
        if row["Treatment"]:
            treatments[row["EncounterID"]].add(row["Treatment"])
    genes = defaultdict(set)
    for row in rows("genomic.csv"):
        genes[row["SampleID"]].add(row["GeneDetected"])
    carbapenemases = {g.symbol for g in ontology.GENES.values() if g.category == "carbapenemase"}
    expected = {
        "stewardship_mismatch": {s for s in sir if any(sir[s].get(t) == "R" for t in treatments[encounter_of[s]])},
        "carbapenemase_producer": {s for s in genes if genes[s] & carbapenemases},
        "colistin_resistance": {s for s in sir if sir[s].get("Colistin") == "R" or "mcr-1.1" in genes[s]},
        "sentinel_gene": {s for s in genes if genes[s] & {"blaKPC-2", "blaKPC-3", "mcr-1.1"}},
    }
    found = defaultdict(set)
    for alert in clinical_alerts(loaded_demo):
        found[alert.rule].add(alert.isolate_id)
    for rule, isolates in expected.items():
        assert isolates, rule
        assert found[rule] == isolates, rule


@pytest.mark.integration
def test_ward_network_report_lists_its_edges(loaded_demo):
    from bionexus import analytics

    report = analytics.rank_wards(loaded_demo)
    assert len(report.links) == report.edges
    assert sum(link.transfers for link in report.links) == report.transfer_links
    assert sum(link.genomic for link in report.links) == report.genomic_links


def expected_phenotypic_clusters(window_days: int = 14, min_size: int = 2) -> set:
    """Independent pure-Python phenotypic cluster detection over the CSVs."""
    from datetime import datetime

    floors = {rule.flag: rule.min_cluster_size for rule in ontology.PRIORITY_PHENOTYPES}

    resistant, context = defaultdict(set), {}
    for row in rows("clinical.csv"):
        context[row["SampleID"]] = row
        if row["Result"] == "R":
            resistant[row["SampleID"]].add(ontology.resolve_antibiotic(row["Antibiotic"]).atc_code)
    groups = defaultdict(list)
    for sample, row in context.items():
        organism, _ = ontology.resolve_organism(row["Organism"])
        for rule in ontology.PRIORITY_PHENOTYPES:
            if organism.ncbi_taxid in rule.taxids and resistant[sample] & rule.atc_codes and not resistant[sample] & rule.unless:
                groups[(f"{row['Facility']}:{row['Ward']}", organism.species, rule.flag)].append((datetime.fromisoformat(row["Date"]), sample))
    found = set()
    for key, items in groups.items():
        items.sort()
        run: list = []
        for when, sample in items + [(None, None)]:
            if when is not None and (not run or (when - run[-1][0]).days <= window_days):
                run.append((when, sample))
                continue
            if len(run) >= max(min_size, floors[key[2]]):
                found.add((*key, frozenset(s for _, s in run)))
            run = [(when, sample)] if when is not None else []
    return found


@pytest.mark.integration
def test_phenotypic_clusters_match_independent_computation(loaded_demo):
    from bionexus import analytics

    clusters = analytics.detect_phenotypic_clusters(loaded_demo)
    assert {(c.ward, c.species, c.phenotype, frozenset(m.isolate_id for m in c.members)) for c in clusters} == expected_phenotypic_clusters()
    assert all(c.sequenced == sum(1 for m in c.members if m.sequence_type) for c in clusters)


@pytest.mark.integration
def test_discordance_alerts_match_independent_computation(loaded_demo):
    from bionexus.alerts import clinical_alerts

    sir = defaultdict(dict)
    for row in rows("clinical.csv"):
        sir[row["SampleID"]][row["Antibiotic"]] = row["Result"]
    genes, sequenced = defaultdict(set), set()
    for row in rows("genomic.csv"):
        genes[row["SampleID"]].add(row["GeneDetected"])
        sequenced.add(row["SampleID"])
    carbapenemases = {g.symbol for g in ontology.GENES.values() if g.category == "carbapenemase"}
    porins = {g.symbol for g in ontology.GENES.values() if g.category == "porin"}
    expected = {
        "carbapenemase_meropenem_not_r": {s for s in genes if genes[s] & carbapenemases and sir[s].get("Meropenem", "R") != "R"},
        "unexplained_carbapenem_resistance": {
            s for s in sequenced
            if not genes[s] & (carbapenemases | porins) and any(sir[s].get(d) == "R" for d in ("Meropenem", "Imipenem", "Ertapenem"))
        },
    }
    found = defaultdict(set)
    for alert in clinical_alerts(loaded_demo):
        found[alert.rule].add(alert.isolate_id)
    for rule, isolates in expected.items():
        assert isolates, rule
        assert found[rule] == isolates, rule


@pytest.mark.integration
def test_stewardship_counts_match_independent_computation(loaded_demo):
    from bionexus import analytics

    treated, resistant = defaultdict(set), defaultdict(set)
    for row in rows("clinical.csv"):
        if row["Treatment"]:
            treated[row["EncounterID"]].add(row["Treatment"])
        if row["Result"] == "R":
            resistant[row["EncounterID"]].add(row["Antibiotic"])
    report = analytics.prescribing_by_aware(loaded_demo)
    assert sum(r.encounters for r in report) == sum(len(v) for v in treated.values())
    assert sum(r.resistant_encounters for r in report) == sum(len(v & resistant[k]) for k, v in treated.items())
    assert {r.aware for r in report} <= {"Access", "Watch", "Reserve"}


def _samples() -> dict[str, dict]:
    """First clinical row per sample plus its resistant agents and MICs."""
    samples: dict[str, dict] = {}
    for row in rows("clinical.csv"):
        sample = samples.setdefault(row["SampleID"], {"row": row, "resistant": set(), "mic": {}})
        atc = ontology.resolve_antibiotic(row["Antibiotic"]).atc_code
        if row["Result"] == "R":
            sample["resistant"].add(atc)
        if row["MIC"]:
            sample["mic"][atc] = float(row["MIC"].lstrip("<>="))
    return samples


def expected_resistance_rates(facility: str | None = None) -> dict[tuple[str, str], tuple[int, int]]:
    """CLSI M39 / GLASS rates computed straight from the CSV."""
    from datetime import datetime

    first: dict[tuple[str, int], dict] = {}
    for sample in _samples().values():
        row = sample["row"]
        if row["Specimen"].startswith("Rectal swab") or (facility and row["Facility"] != facility):
            continue
        organism, _ = ontology.resolve_organism(row["Organism"])
        key = (row["PatientID"], organism.ncbi_taxid)
        when = (datetime.fromisoformat(row["Date"]), row["SampleID"])
        if key not in first or when < first[key]["when"]:
            first[key] = {"when": when, "sample": sample, "organism": organism}
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for item in first.values():
        for rule in ontology.PRIORITY_PHENOTYPES:
            if item["organism"].ncbi_taxid in rule.taxids:
                cell = counts[(item["organism"].species, rule.flag)]
                cell[0] += 1
                cell[1] += bool(item["sample"]["resistant"] & rule.atc_codes)
    return {key: tuple(value) for key, value in counts.items()}


@pytest.mark.integration
@pytest.mark.parametrize("facility", [None, "GAH", "GDH"])
def test_resistance_rates_follow_first_isolate_rule(loaded_demo, facility):
    from bionexus import analytics

    rates = analytics.resistance_rates(loaded_demo, facility=facility)
    assert {(r.species, r.phenotype): (r.patients, r.resistant) for r in rates} == expected_resistance_rates(facility)
    assert all(r.percent == round(100 * r.resistant / r.patients, 1) for r in rates)


@pytest.mark.integration
def test_origin_follows_glass_two_calendar_day_rule(loaded_demo):
    from datetime import date, datetime

    first_adt: dict[str, datetime] = {}
    for row in rows("movements.csv"):
        when = datetime.fromisoformat(row["Timestamp"])
        first_adt[row["EncounterID"]] = min(when, first_adt.get(row["EncounterID"], when))
    expected = {}
    for sample in _samples().values():
        row = sample["row"]
        admitted = datetime.fromisoformat(row["AdmitDate"]) if row["AdmitDate"] else first_adt.get(row["EncounterID"])
        if admitted is None:
            expected[row["SampleID"]] = None
            continue
        day = (date.fromisoformat(row["Date"][:10]) - date.fromisoformat(admitted.isoformat()[:10])).days + 1
        expected[row["SampleID"]] = "hospital" if day > 2 else "community"
    graph = {r["id"]: r["origin"] for r in loaded_demo.query("MATCH (i:Isolate) RETURN i.id AS id, i.origin AS origin")}
    assert graph == expected
    assert set(expected.values()) == {"hospital", "community"}


@pytest.mark.integration
def test_notifiable_cases_match_independent_computation(loaded_demo):
    from bionexus import notifiable

    genes: dict[str, set[str]] = defaultdict(set)
    sequenced = set()
    for row in rows("genomic.csv"):
        sequenced.add(row["SampleID"])
        if row["GeneDetected"] != "None":
            genes[row["SampleID"]].add(ontology.resolve_gene(row["GeneDetected"]).category)
    candidates: dict[tuple[str, str], list] = defaultdict(list)
    for sample_id, sample in _samples().items():
        row = sample["row"]
        organism, _ = ontology.resolve_organism(row["Organism"])
        found = []
        if organism.ncbi_taxid in ontology.ENTEROBACTERALES_TAXIDS:
            if "carbapenemase" in genes[sample_id]:
                found.append(("cpe", "notify"))
            elif sample_id not in sequenced and sample["resistant"] & ontology.CARBAPENEM_ATC:
                found.append(("cpe", "confirm_carbapenemase"))
        if organism.genus == "Enterococcus" and "J01XA01" in sample["resistant"]:
            found.append(("vre", "notify"))
        if organism.ncbi_taxid in (287, 470) and "J01XB01" in sample["resistant"]:
            found.append(("colistin_resistant", "notify"))
        if organism.ncbi_taxid == 1280 and sample["mic"].get("J01XA01", 0) >= 4:
            found.append(("gisa", "notify"))
        for condition, status in found:
            candidates[(condition, row["PatientID"])].append((status != "notify", row["Date"], sample_id, status))
    expected = {(condition, patient, *min(items)[2:]) for (condition, patient), items in candidates.items()}

    cases = notifiable.notifiable_cases(loaded_demo)
    assert {(c.condition, c.patient_id, c.isolate_id, c.status) for c in cases} == expected
    assert {c.condition for c in cases} >= {"cpe", "vre", "colistin_resistant"}
    assert all(c.due > c.collected.date() for c in cases)
