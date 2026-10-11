"""End-to-end tests against a real Neo4j (with GDS for ward ranking)."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import pytest

from bionexus import analytics
from bionexus.etl import read_csv, transform
from bionexus.pipeline import ingest

from .conftest import CLINICAL_CSV, CLINICAL_HEADER, GENOMIC_CSV, GENOMIC_HEADER, clinical_row, genomic_row, to_csv

pytestmark = pytest.mark.integration

KP, EC = "Klebsiella pneumoniae (CRE)", "Escherichia coli"


def counts(graph):
    nodes = {r["label"]: r["n"] for r in graph.query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n")}
    rels = {r["type"]: r["n"] for r in graph.query("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n")}
    return nodes, rels


def load_sample(graph):
    return ingest(graph, CLINICAL_CSV, GENOMIC_CSV, batch_size=64)


def test_sample_ingest_builds_normalised_graph_idempotently(graph):
    report = load_sample(graph)
    assert report.isolates == 300 and report.issues == []
    nodes, rels = counts(graph)
    assert nodes == {
        "Patient": 300, "Encounter": 300, "LocationEvent": 300, "Isolate": 300, "Ward": 3,
        "Pathogen": 3, "Antibiotic": 7, "SequenceType": 6, "Gene": 8,
    }
    assert rels["CARRIES"] == 224 and rels["EXHIBITS"] == 300 and rels["BELONGS_TO"] == 300

    load_sample(graph)
    assert counts(graph) == (nodes, rels)


def test_graph_is_grounded_in_ontology_identifiers(graph):
    load_sample(graph)
    pathogens = graph.query("MATCH (p:Pathogen) RETURN p.ncbi_taxid AS taxid, p.species AS species ORDER BY taxid")
    assert pathogens == [
        {"taxid": 287, "species": "Pseudomonas aeruginosa"},
        {"taxid": 573, "species": "Klebsiella pneumoniae"},
        {"taxid": 1280, "species": "Staphylococcus aureus"},
    ]
    [mrsa] = graph.query(
        "MATCH (i:Isolate {id: 'S-20000'})-[x:EXHIBITS]->(a:Antibiotic) "
        "RETURN i.phenotype_labels AS labels, a.atc_code AS atc, x.mic AS mic, x.mic_qualifier AS q, x.sir AS sir"
    )
    assert mrsa == {"labels": ["MRSA"], "atc": "J01XA01", "mic": 16.0, "q": ">", "sir": "R"}
    [usa100] = graph.query("MATCH (:Isolate {id: 'S-20000'})-[b:BELONGS_TO]->(s:SequenceType) RETURN s.key AS key, b.clone_designation AS clone")
    assert usa100 == {"key": "saureus:ST5", "clone": "USA100"}
    # Wild-type isolates have no gene relationships at all.
    assert graph.query("MATCH (i:Isolate {genotype_status: 'no_determinant_detected'})-[:CARRIES]->() RETURN count(*) AS n") == [{"n": 0}]


def reference_clusters(window_days: int) -> set[tuple[str, str, str, frozenset[str]]]:
    """Independent pure-Python cluster detection over the transformed records."""
    records = transform(read_csv(CLINICAL_CSV), read_csv(GENOMIC_CSV)).isolates
    groups = defaultdict(list)
    for record in records:
        if record.sequence_type is None:
            continue
        for gene in record.direct_genes:
            if gene.acquired:
                groups[(record.ward.key, record.sequence_type.key, gene.aro_id)].append(record)
    found = set()
    for key, members in groups.items():
        parent = {m.isolate_id: m.isolate_id for m in members}

        def root(x):
            while parent[x] != x:
                x = parent[x]
            return x

        for a, b in combinations(members, 2):
            if abs((a.collected - b.collected).days) <= window_days:
                parent[root(a.isolate_id)] = root(b.isolate_id)
        components = defaultdict(set)
        for m in members:
            components[root(m.isolate_id)].add(m.isolate_id)
        found |= {(*key, frozenset(c)) for c in components.values() if len(c) >= 2}
    return found


@pytest.mark.parametrize("window_days", [7, 14, 30])
def test_spatiotemporal_clusters_match_reference_implementation(graph, window_days):
    load_sample(graph)
    clusters = analytics.detect_spatiotemporal_clusters(graph, window_days)
    got = {(c.ward, c.sequence_type, c.gene_aro_id, frozenset(m.isolate_id for m in c.members)) for c in clusters}
    assert got == reference_clusters(window_days)
    assert all(c.size == len(c.members) >= 2 for c in clusters)


def test_horizontal_gene_transfer_across_species_and_genera(graph):
    load_sample(graph)
    assert analytics.detect_horizontal_gene_transfer(graph) == []

    clinical = to_csv(CLINICAL_HEADER, [clinical_row("S-HGT-1", "P-HGT-1", EC, Ward="ICU", Date="2025-11-20")])
    genomic = to_csv(GENOMIC_HEADER, [genomic_row("S-HGT-1", "P-HGT-1", EC, "ST131", "blaNDM-1", MGE_Type="Plasmid", MGE_Replicon="IncX3")])
    ingest(graph, clinical, genomic)

    [signal] = analytics.detect_horizontal_gene_transfer(graph)
    assert signal.gene == "blaNDM-1" and signal.gene_aro_id == "ARO:3000589"
    assert signal.taxa == ["Escherichia coli", "Klebsiella pneumoniae"]
    assert signal.replicons == ["Plasmid:IncX3"]
    assert signal.isolate_count == 1 + sum(1 for r in read_csv(GENOMIC_CSV) if r[1]["GeneDetected"] == "blaNDM-1")
    [genus_signal] = analytics.detect_horizontal_gene_transfer(graph, "genus")
    assert genus_signal.taxa == ["Escherichia", "Klebsiella"]
    assert graph.query("MATCH (:Isolate {id: 'S-HGT-1'})-[:BELONGS_TO]->(s) RETURN s.key AS key") == [{"key": "ecoli_achtman_4:ST131"}]


def test_mobile_elements_do_not_leak_genes_between_isolates(graph):
    clinical = to_csv(CLINICAL_HEADER, [clinical_row("S-A", "P-A", KP), clinical_row("S-B", "P-B", KP)])
    genomic = to_csv(
        GENOMIC_HEADER,
        [
            genomic_row("S-A", "P-A", KP, "ST11", "blaNDM-1", MGE_Type="Plasmid", MGE_Replicon="IncX3"),
            genomic_row("S-B", "P-B", KP, "ST11", "blaOXA-48", MGE_Type="Plasmid", MGE_Replicon="IncX3"),
        ],
    )
    ingest(graph, clinical, genomic)
    carried = graph.query(
        "MATCH (i:Isolate)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene) RETURN i.id AS isolate, collect(g.symbol) AS genes ORDER BY isolate"
    )
    assert carried == [{"isolate": "S-A", "genes": ["blaNDM-1"]}, {"isolate": "S-B", "genes": ["blaOXA-48"]}]
    assert graph.query("MATCH (m:MobileGeneticElement {replicon: 'IncX3'}) RETURN count(m) AS n") == [{"n": 2}]


def test_corrected_genomic_report_replaces_previous_calls(graph):
    clinical = to_csv(CLINICAL_HEADER, [clinical_row("S-1", "P-1", KP)])
    ingest(graph, clinical, to_csv(GENOMIC_HEADER, [genomic_row("S-1", "P-1", KP, "ST258", "blaKPC-3", MGE_Type="Transposon", MGE_Replicon="Tn4401")]))
    ingest(graph, clinical, to_csv(GENOMIC_HEADER, [genomic_row("S-1", "P-1", KP, "ST11", "blaNDM-1")]))
    genes = "MATCH (:Isolate {id: 'S-1'})-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene) RETURN collect(g.symbol) AS genes"
    assert graph.query(genes) == [{"genes": ["blaNDM-1"]}]
    assert graph.query("MATCH (:Isolate {id: 'S-1'})-[:BELONGS_TO]->(s) RETURN collect(s.key) AS st") == [{"st": ["klebsiella:ST11"]}]
    assert graph.query("MATCH (m:MobileGeneticElement) RETURN count(m) AS n") == [{"n": 0}]

    # A later clinical-only load must not erase the genomic result.
    ingest(graph, clinical)
    assert graph.query(genes) == [{"genes": ["blaNDM-1"]}]
    assert graph.query("MATCH (i:Isolate {id: 'S-1'}) RETURN i.genotype_status AS s") == [{"s": "determinants_detected"}]


def test_ward_attribution_and_centrality_use_movement_events(graph):
    clinical = to_csv(
        CLINICAL_HEADER,
        [
            clinical_row("S-1", "P-1", KP, Ward="ICU", Date="2025-11-01"),
            clinical_row("S-2", "P-2", KP, Ward="Surgical", Date="2025-11-05"),
            clinical_row("S-3", "P-3", KP, Ward="Renal", Date="2025-11-06"),
        ],
    )
    genomic = to_csv(GENOMIC_HEADER, [genomic_row(f"S-{n}", f"P-{n}", KP, "ST258", "blaKPC-3") for n in (1, 2, 3)])
    # P-1's specimen encounter later moves ICU -> Surgical -> Renal; P-2 moves Surgical -> ICU.
    movements = to_csv(
        ["PatientID", "EncounterID", "Ward", "Timestamp"],
        [
            {"PatientID": "P-1", "EncounterID": "P-1:20251101", "Ward": "Surgical", "Timestamp": "2025-11-03T10:00:00"},
            {"PatientID": "P-1", "EncounterID": "P-1:20251101", "Ward": "Renal", "Timestamp": "2025-11-04T10:00:00"},
            {"PatientID": "P-2", "EncounterID": "P-2:20251105", "Ward": "ICU", "Timestamp": "2025-11-07T09:00:00"},
        ],
    )
    report = ingest(graph, clinical, genomic, movements)
    assert report.movements == 3 and report.issues == []

    # Isolates stay attributed to the ward where they were collected.
    assert analytics.detect_spatiotemporal_clusters(graph) == []

    network = analytics.rank_wards(graph, window_days=14)
    assert network.transfer_links == 3 and network.genomic_links == 3
    by_ward = {w.ward: w for w in network.wards}
    assert set(by_ward) == {"ICU", "Surgical", "Renal"}
    # Surgical carries the most combined transfer + genomic link weight.
    assert by_ward["Surgical"].weighted_degree == max(w.weighted_degree for w in network.wards)
    assert graph.query("CALL gds.graph.list() YIELD graphName RETURN count(*) AS n") == [{"n": 0}]


def test_ward_centrality_on_sample_data(graph):
    load_sample(graph)
    network = analytics.rank_wards(graph)
    assert {w.ward for w in network.wards} == {"ICU", "General", "Oncology"}
    assert network.transfer_links == 0 and network.genomic_links > 0
    assert sum(w.isolates for w in network.wards) == 300


def test_facilities_scope_wards_and_carry_demographics(graph):
    clinical = to_csv(
        CLINICAL_HEADER,
        [
            clinical_row("S-1", "P-1", KP, Ward="ICU", Facility="GAH", FacilityName="Gauteng Academic", Province="Gauteng", Sex="F", AgeYears="0.02"),
            clinical_row("S-2", "P-2", KP, Ward="ICU", Facility="KRH", FacilityName="KZN Regional", Province="KwaZulu-Natal", Sex="M", AgeYears="61"),
        ],
    )
    ingest(graph, clinical)
    wards = graph.query("MATCH (w:Ward)-[:PART_OF]->(f:Facility) RETURN w.key AS key, w.name AS name, f.code AS code, f.province AS province ORDER BY key")
    assert wards == [
        {"key": "GAH:ICU", "name": "ICU", "code": "GAH", "province": "Gauteng"},
        {"key": "KRH:ICU", "name": "ICU", "code": "KRH", "province": "KwaZulu-Natal"},
    ]
    assert graph.query("MATCH (p:Patient {id: 'P-1'})-[:HAD_ENCOUNTER]->(e) RETURN p.sex AS sex, e.age_years AS age") == [{"sex": "F", "age": 0.02}]


def test_phenotypic_clusters_find_outbreaks_without_any_sequencing(graph):
    demo = CLINICAL_CSV.parent / "demo"
    ingest(graph, demo / "clinical.csv", None, demo / "movements.csv")
    assert graph.query("MATCH (i:Isolate) WHERE i.genotype_status <> 'not_sequenced' RETURN count(i) AS n") == [{"n": 0}]
    assert analytics.detect_spatiotemporal_clusters(graph) == []
    clusters = {(c.ward, c.phenotype): c.size for c in analytics.detect_phenotypic_clusters(graph)}
    # Planted outbreaks remain visible from susceptibility results alone.
    assert clusters[("GAH:Neonatal ICU", "CRE")] >= 14
    assert clusters[("WTH:Haematology-Oncology", "VRE")] >= 8
    assert clusters[("GAH:Burns", "MRSA")] >= 6
    assert clusters[("GAH:Adult ICU", "CRE")] >= 6
