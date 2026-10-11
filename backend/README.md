# BioNexus AMR graph backend

An ontology-grounded, event-sourced knowledge graph for antimicrobial
resistance surveillance on Neo4j, with a FastAPI service and CLI for
ingestion and outbreak analytics. It replaces the browser-side string
matching in the prototype frontend.

## Graph model

```
(:Patient {sex})-[:HAD_ENCOUNTER]->(:Encounter {age_years})-[:GENERATED_EVENT]->(:LocationEvent)-[:AT_LOCATION]->(:Ward)-[:PART_OF]->(:Facility {province})
(:Encounter)-[:ISOLATED]->(:Isolate)-[:IDENTIFIED_AS]->(:Pathogen)
(:Encounter)-[:TREATED_WITH]->(:Antibiotic)
(:Isolate)-[:EXHIBITS {sir, mic, mic_qualifier, mic_unit, guideline}]->(:Antibiotic)
(:Isolate)-[:BELONGS_TO {clone_designation}]->(:SequenceType)
(:Isolate)-[:CARRIES {context}]->(:Gene)
(:Isolate)-[:CARRIES]->(:MobileGeneticElement)-[:HARBORS]->(:Gene)
```

| Node | Key (unique constraint) | Grounding |
|---|---|---|
| Pathogen | `ncbi_taxid` | NCBI Taxonomy, e.g. 1280 = *S. aureus*. Lab shorthand such as "MRSA"/"CRE" is split off into `Isolate.phenotype_labels`. |
| Antibiotic | `atc_code` | WHO ATC, e.g. J01DH02 = meropenem |
| Gene | `aro_id` | CARD ARO, e.g. ARO:3000589 = NDM-1 |
| SequenceType | `key` (`scheme:STn`) | PubMLST scheme as named by the `mlst` tool, e.g. `klebsiella:ST307` |
| Ward | `key` (`FACILITY:ward`, or the bare ward name without a facility) | source identifiers; ward names repeat across hospitals |
| Facility | `code` | source identifiers, with name and province |
| Patient / Encounter / LocationEvent / Isolate / MobileGeneticElement | `id` / `key` | source identifiers |

MIC values are stored as numbers with a separate qualifier (`>16` becomes
`mic: 16.0, mic_qualifier: ">"`), kept apart from the reported category
(S, I, SDD or R; SDD is CLSI's susceptible-dose-dependent category).

### Where the identifiers come from

Every identifier is checked against its authoritative source by
`tools/verify_vocabulary.py` (install the `verify` extra first):

| Vocabulary | Source |
|---|---|
| NCBI Taxonomy IDs | NCBI's taxdb name index (NCBI's BLAST database bucket on AWS) |
| Species names | LPSN, via the AMR package |
| CARD ARO accessions | CARD's `aro.owl` (github.com/arpcard/aro) |
| WHO ATC codes | the AMR package's antimicrobials table |
| MLST schemes and STs | PubMLST profiles in the Bioconda `mlst` package |
| CLSI 2025 MIC breakpoints | the AMR package's clinical_breakpoints table |

```bash
pip install -e ".[verify]"
python tools/verify_vocabulary.py --dataset data/demo --report vocabulary_report.md
```

The latest report is committed at `docs/vocabulary_verification.md`.
The tool exits non-zero on any mismatch; planted errors (a wrong ARO,
ATC code or taxid) are caught.
* The vocabulary is deliberately closed. An unknown organism, drug, gene or
  phenotype label rejects the row with a line-numbered error; extend
  `ontology.py` to accept it.

### Deliberate departures from the original blueprint

1. **Mobile genetic elements are per isolate.** A shared node such as
   "IncX3 plasmid" connected to every gene seen on any IncX3 would make
   isolate B appear to carry isolate A's NDM-1. Each isolate therefore gets its
   own element node (`key = isolate:type:replicon`). Cross-isolate comparison
   uses the `replicon` property, which is indexed. A test covers this case.
2. **USA100/USA300 are PFGE clone names, not MLST STs.** They map to ST5 and
   ST8, and the original label is kept as `BELONGS_TO.clone_designation`.
3. **oprD loss is a chromosomal mutation** (ARO:3003686), stored with
   `acquired: false`. It is excluded from HGT analysis and cannot sit on a
   mobile element.
4. **Encounters.** The sample CSVs have no admission data, so each specimen
   collection is treated as one encounter (`PatientID:YYYYMMDD`) with null
   `admitted`/`discharged`. Supply `EncounterID`, `AdmitDate` and
   `DischargeDate` columns, plus a movements file, to use real ADT encounters.
5. **Genotype status is explicit:** `not_sequenced`,
   `no_determinant_detected` ("None"/"Wild Type") or `determinants_detected`.

## Input files

**clinical** (required), one row per susceptibility test:
`PatientID, SampleID, Date, Ward, Specimen, Treatment, Organism, Antibiotic, Result, MIC`
and optionally `EncounterID, AdmitDate, DischargeDate, Guideline, Facility,
FacilityName, Province, Sex, AgeYears`.
When `Guideline` is `CLSI 2025`, each MIC is re-interpreted, and a reported
category that disagrees is flagged as a warning.
Several rows with the same `SampleID` make up one isolate's antibiogram.

**genomic** (optional), one row per determinant call, joined on `SampleID`:
`PatientID, SampleID, Organism, Strain_Subtype, GeneDetected`
and optionally `MGE_Type` (`Plasmid`/`Integron`/`Transposon`) with `MGE_Replicon`.
If `PatientID` or the organism disagrees with the clinical record, that
isolate's genomic data is dropped and the conflict is reported.

**movements** (optional ADT feed): `PatientID, EncounterID, Ward, Timestamp`,
optionally with `Facility, FacilityName, Province`.

A realistic 600-patient South African demonstration dataset with planted
outbreaks lives in `data/demo/`; see its README.

Ingest is idempotent: every write is a `MERGE` on a constrained key, inside
batched `execute_write` transactions. Loading a new genomic report for an
isolate replaces its earlier gene, element and ST calls, so a retracted
call does not linger. A clinical-only reload keeps existing genomics.

## Analytics

| Endpoint / CLI | What it computes |
|---|---|
| `GET /analytics/clusters?window_days=14` / `bionexus clusters` | Isolates in the same ward with the same ST and the same acquired gene variant, collected within the window of each other. A cluster is a connected chain of such links. |
| `GET /analytics/hgt?level=species\|genus` / `bionexus hgt` | One ARO gene variant found in more than one species or genus, with the wards and replicons involved. |
| `GET /analytics/wards/centrality` / `bionexus wards` | GDS weighted PageRank, betweenness and weighted degree over a ward network. Edges are patient transfers plus cross-ward genomic links within the window. |
| `GET /analytics/alerts` / `bionexus alerts` | Clinical alert rules (prescribed agent tests resistant, carbapenemase producer, colistin resistance, sentinel genes); criteria documented in `bionexus/alerts.py`. |

An isolate's ward is the ward of its encounter's latest LocationEvent at or
before collection time. Clusters and ward link counts come from a single
time-sorted pass, so the cost grows roughly linearly with isolates. They were
checked against brute-force pair enumeration: identical results on 20,000
isolates, where clusters take 2.5 s and ward ranking 3.2 s.

## Running it

```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env            # point at your Neo4j (GDS needed for /wards)

bionexus ingest --clinical data/clinical_phenotype.csv --genomic data/genomic_data.csv --dry-run
bionexus ingest --clinical data/clinical_phenotype.csv --genomic data/genomic_data.csv
bionexus clusters --window-days 14
uvicorn --factory bionexus.api:create_app --port 8000   # OpenAPI docs at /docs
```

Or run everything in containers with `docker compose up --build`. This uses
the official `neo4j:2026.09.0` image, which bundles the GDS plugin, so no
plugin download is needed. It has been tested end to end: the healthcheck,
the API, all analytics, and the full test suite run against the
containerised database with authentication enabled.

`tools/export_site_snapshot.py` runs all of these against a live
database and writes the JSON snapshot used by the static dashboard.

## Tests

```bash
pytest                                  # unit tests; integration tests skip
tools/embedded-neo4j/run.sh &           # throwaway Neo4j + GDS (Java 21, Maven)
BIONEXUS_TEST_NEO4J_URI=bolt://127.0.0.1:7687 pytest
```

Integration tests **delete all data** in the target database, so they only
run when `BIONEXUS_TEST_NEO4J_URI` is set explicitly. They check graph
shape, idempotency, ontology grounding, cluster detection against an
independent Python implementation, HGT, mobile-element attribution,
corrected-report replacement, ward attribution with movements, GDS
centrality and the HTTP API.

## Known limitations

* Only CLSI 2025 MIC breakpoints are embedded. Rows with another guideline,
  or none, are stored as reported without re-interpretation. EUCAST is
  available from the same source table if needed.
* The original sample data in `data/*.csv` are synthetic and not biologically consistent. For
  example, 20 of the 32 vancomycin-resistant *S. aureus* isolates carry no
  *vanA*, while 28 MRSA isolates do carry *vanA*, which is clinically very
  rare (VRSA). Treat the analytics output on these files as a demonstration
  only.
* Not yet wired into the React frontend, which still computes everything
  in the browser.
