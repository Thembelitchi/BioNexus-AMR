# BioNexus knowledge graph files

The Neo4j knowledge graph behind the demo dashboard: the 600-patient
synthetic South African dataset in `backend/data/demo/`, ingested by the
BioNexus backend with POPIA pseudonymisation switched on. The published demo
key is `bionexus-public-demo-key-not-secret`. Every cluster, gene-transfer
signal, ward ranking and alert on the dashboard was computed from this
graph.

| File | What it is | Use it with |
|---|---|---|
| `bionexus-demo.dump` | Neo4j database dump (`neo4j-admin database dump`), about 1 MB | Neo4j **2026.09 or later** (Desktop, server or Docker) |
| `bionexus-demo.cypher` | The same graph as a readable Cypher script: schema, then every node and relationship with all properties | Any Neo4j **5 or later**, including Aura, through `cypher-shell` or the backend's loader |

**Contents:** 3,373 nodes and 13,092 relationships.

| Nodes | Count | | Relationships | Count |
|---|---|---|---|---|
| Patient | 600 | | HAD_ENCOUNTER | 606 |
| Encounter | 606 | | GENERATED_EVENT | 1,320 |
| LocationEvent | 1,320 | | AT_LOCATION | 1,320 |
| Ward | 17 | | PART_OF (Ward → Facility) | 17 |
| Facility | 4 | | ISOLATED | 673 |
| Isolate | 673 | | IDENTIFIED_AS | 673 |
| Pathogen | 7 | | EXHIBITS (Isolate → Antibiotic) | 7,391 |
| Antibiotic | 24 | | TREATED_WITH | 594 |
| SequenceType | 31 | | BELONGS_TO | 197 |
| Gene | 14 | | CARRIES | 224 |
| MobileGeneticElement | 77 | | HARBORS | 77 |

[`MODEL.md`](MODEL.md) explains the model for developers new to knowledge graphs or AMR: every relationship and its direction, design decisions, a query cookbook and a glossary.
The data is **synthetic** and not for clinical use.

## Load the dump

Neo4j Desktop: add the file to a project, then choose
**Create new database from dump** (Neo4j 2026.09 or later).

Docker:

```bash
mkdir -p neo4j-data load && cp graph/bionexus-demo.dump load/neo4j.dump
docker run --rm -v "$PWD/neo4j-data:/data" -v "$PWD/load:/load" neo4j:2026.09.0 \
  neo4j-admin database load neo4j --from-path=/load --overwrite-destination=true
docker run -p 7474:7474 -p 7687:7687 -v "$PWD/neo4j-data:/data" \
  -e NEO4J_AUTH=neo4j/change-me-please -e NEO4J_PLUGINS='["graph-data-science"]' \
  neo4j:2026.09.0
```

Then open http://localhost:7474. A dump cannot be loaded into an older Neo4j
version; use the Cypher script for those.

## Load the Cypher script

Into an **empty** database:

```bash
cypher-shell -a neo4j://localhost:7687 -u neo4j -p <password> -f graph/bionexus-demo.cypher
# or, without cypher-shell:
cd backend && python tools/export_graph.py load
```

Loading takes about a minute. The script creates the BioNexus constraints and
indexes first, then the nodes and relationships. While it runs, nodes carry a
temporary `BioNexusImport` label so relationships can find their endpoints.
The script removes that label at the end.

## Things to try in Neo4j Browser

```cypher
// The neonatal ICU outbreak (scenario S1): OXA-181 K. pneumoniae ST307
MATCH (w:Ward {key: 'GAH:Neonatal ICU'})<-[:AT_LOCATION]-(:LocationEvent)<-[:GENERATED_EVENT]-(e:Encounter)
      -[:ISOLATED]->(i:Isolate)-[:BELONGS_TO]->(st:SequenceType {key: 'klebsiella:ST307'})
MATCH (i)-[:CARRIES]->(:MobileGeneticElement)-[:HARBORS]->(g:Gene {symbol: 'blaOXA-181'})
RETURN w, e, i, st, g;

// One plasmid gene across genera (scenario S3): NDM-5 on IncX3
MATCH (g:Gene {symbol: 'blaNDM-5'})<-[:HARBORS]-(m:MobileGeneticElement)<-[:CARRIES]-(i:Isolate)-[:IDENTIFIED_AS]->(p:Pathogen)
RETURN g, m, i, p;

// Reserve antibiotics prescribed, with the patient's result for that drug
MATCH (e:Encounter)-[:TREATED_WITH]->(a:Antibiotic {aware: 'Reserve'})
OPTIONAL MATCH (e)-[:ISOLATED]->(i:Isolate)-[x:EXHIBITS]->(a)
RETURN a.name AS drug, count(DISTINCT e) AS encounters, collect(DISTINCT x.sir) AS results;
```

The backend's analytics (`bionexus clusters`, `hgt`, `wards`, `alerts`,
`stewardship`) run against either loaded copy and give the same results as
the dashboard. Ward ranking also needs the Graph Data Science plugin.

## Regenerate

From a disposable database (this **wipes** it):

```bash
cd backend
BIONEXUS_PSEUDONYMISATION_KEY=bionexus-public-demo-key-not-secret \
  python tools/export_site_snapshot.py --load     # ingest the demo dataset and refresh the dashboard snapshot
python tools/export_graph.py export                # write graph/bionexus-demo.cypher
# stop Neo4j, then: neo4j-admin database dump neo4j --to-path=<dir>  ->  graph/bionexus-demo.dump
```

The Cypher export is deterministic: the same graph always gives a
byte-identical file. Both files were checked by loading each into a fresh
Neo4j 2026.09 and re-exporting. The graph was identical, and every
analytic matched the dashboard snapshot.
