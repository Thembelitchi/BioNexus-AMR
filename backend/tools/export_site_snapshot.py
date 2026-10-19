#!/usr/bin/env python3
"""Export a static snapshot of the platform's output for the web dashboard.

    python tools/export_site_snapshot.py [--load] [--out ../public/data/snapshot.json]

Reads isolates and runs every analytic (clusters, gene transfer, GDS ward
centrality, clinical alerts) against a live Neo4j, so the static site
shows exactly what the backend computes. ``--load`` first wipes the
database and ingests the demo dataset; only use it on a disposable
instance (NEO4J_URI etc. come from the environment).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from bionexus import alerts, analytics, notifiable  # noqa: E402
from bionexus import ontology  # noqa: E402
from bionexus.breakpoints import BREAKPOINT_SOURCE  # noqa: E402
from bionexus.config import Settings, configure_logging, pseudonymiser_for  # noqa: E402
from bionexus.db import GraphClient  # noqa: E402
from bionexus.pipeline import ingest  # noqa: E402
from bionexus.schema import ensure_schema  # noqa: E402

DEMO = BACKEND / "data" / "demo"
WINDOW_DAYS = 14

_ISOLATES = f"""
MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter)-[:ISOLATED]->(i:Isolate)-[:IDENTIFIED_AS]->(pathogen:Pathogen)
{analytics._ISOLATE_WARD}
OPTIONAL MATCH (i)-[bt:BELONGS_TO]->(st:SequenceType)
WITH p, e, i, pathogen, ward, st, bt,
     [(ward)-[:PART_OF]->(f:Facility) | f.code][0] AS facility,
     [(e)-[:TREATED_WITH]->(d:Antibiotic) | [d.name, d.aware]] AS treated,
     [(i)-[x:EXHIBITS]->(d:Antibiotic) | {{drug: d.name, atc: d.atc_code, aware: d.aware, sir: x.sir, method: x.method, mic: x.mic, q: x.mic_qualifier, zone: x.zone_mm}}] AS ast,
     [(i)-[c:CARRIES]->(g:Gene) | {{symbol: g.symbol, category: g.category, aro: g.aro_id, carrier: null, context: c.context}}] +
     [(i)-[:CARRIES]->(m:MobileGeneticElement)-[:HARBORS]->(g:Gene) |
        {{symbol: g.symbol, category: g.category, aro: g.aro_id, carrier: m.type + ':' + m.replicon, context: 'mobile'}}] AS genes
RETURN i.id AS id, p.id AS patient, p.sex AS sex, e.age_years AS age, e.age_band AS ageBand, e.id AS encounter,
       i.collected AS collected, facility, ward.key AS ward, ward.name AS wardName, i.specimen AS specimen,
       coalesce(i.screening, false) AS screening, i.origin AS origin, i.hospital_day AS hospitalDay,
       pathogen.species AS species, pathogen.ncbi_taxid AS taxid, i.phenotype_labels AS labels,
       i.genotype_status AS genotype, st.key AS st, bt.clone_designation AS clone,
       treated, ast, genes
ORDER BY collected, id
"""

_FACILITIES = """
MATCH (w:Ward)-[:PART_OF]->(f:Facility)
WITH f, w ORDER BY w.name
RETURN f.code AS code, f.name AS name, f.province AS province, collect({key: w.key, name: w.name}) AS wards
ORDER BY code
"""


def _iso(value) -> str:
    return value.to_native().isoformat() if hasattr(value, "to_native") else value.isoformat()


def _dump(model) -> dict:
    return model.model_dump(mode="json")


def verification_summary() -> list[dict]:
    report = BACKEND / "docs" / "vocabulary_verification.md"
    sections = []
    for line in report.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^## (.+) \((\d+)/(\d+) verified\)$", line)
        if match:
            sections.append({"title": match[1], "verified": int(match[2]), "total": int(match[3])})
    return sections


def export(client: GraphClient, pseudonymised: bool) -> dict:
    isolates = []
    for row in client.query(_ISOLATES):
        row["collected"] = _iso(row["collected"])
        treated = sorted(row.pop("treated"))
        row["treatments"] = [name for name, _ in treated]
        row["treatmentAware"] = [aware for _, aware in treated]
        row["ast"] = sorted(row["ast"], key=lambda t: t["drug"])
        row["genes"] = sorted(row["genes"], key=lambda g: g["symbol"])
        isolates.append(row)
    versions = client.query("CALL dbms.components() YIELD name, versions RETURN name, versions[0] AS version")
    facilities = client.query(_FACILITIES)
    return {
        "meta": {
            "title": "BioNexus AMR surveillance demo",
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset": "Synthetic South African demonstration dataset (backend/data/demo)",
            "guideline": BREAKPOINT_SOURCE,
            "windowDays": WINDOW_DAYS,
            "neo4j": next((v["version"] for v in versions if v["name"] == "Neo4j Kernel"), None),
            "gds": analytics.gds_version(client),
            "pseudonymised": pseudonymised,
        },
        "facilities": facilities,
        "isolates": isolates,
        "clusters": [_dump(c) for c in analytics.detect_spatiotemporal_clusters(client, WINDOW_DAYS)],
        "phenotypicClusters": [_dump(c) for c in analytics.detect_phenotypic_clusters(client, WINDOW_DAYS)],
        "phenotypeRules": [{"flag": r.flag, "meaning": r.meaning} for r in ontology.PRIORITY_PHENOTYPES],
        "prescribing": [_dump(r) for r in analytics.prescribing_by_aware(client)],
        "hgt": {level: [_dump(s) for s in analytics.detect_horizontal_gene_transfer(client, level)] for level in ("species", "genus")},
        "wardNetwork": _dump(analytics.rank_wards(client, WINDOW_DAYS)),
        "alerts": [_dump(a) for a in alerts.clinical_alerts(client)],
        "resistanceRates": {
            key: [_dump(r) for r in analytics.resistance_rates(client, facility=code)]
            for key, code in [("all", None), *((f["code"], f["code"]) for f in facilities)]
        },
        "notifiable": [_dump(c) for c in notifiable.notifiable_cases(client)],
        "notifiableConditions": notifiable.CONDITIONS,
        "alertRules": {rule: {"severity": sev, "title": title} for rule, (sev, title) in alerts.RULES.items()},
        "scenarios": json.loads((DEMO / "scenarios.json").read_text(encoding="utf-8")),
        "verification": verification_summary(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--load", action="store_true", help="wipe the database and ingest the demo dataset first")
    parser.add_argument("--out", type=Path, default=BACKEND.parent / "public" / "data" / "snapshot.json")
    args = parser.parse_args()
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    with GraphClient(settings) as client:
        ensure_schema(client)
        if args.load:
            client.write(lambda tx: tx.run("MATCH (n) DETACH DELETE n").consume())
            report = ingest(client, DEMO / "clinical.csv", DEMO / "genomic.csv", DEMO / "movements.csv",
                            pseudonymiser=pseudonymiser_for(settings))
            if report.issues:
                print(f"demo ingest reported {len(report.issues)} issue(s)", file=sys.stderr)
                return 1
        snapshot = export(client, pseudonymised=settings.pseudonymisation_key is not None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KiB): "
          f"{len(snapshot['isolates'])} isolates, {len(snapshot['clusters'])} clusters, {len(snapshot['alerts'])} alerts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
