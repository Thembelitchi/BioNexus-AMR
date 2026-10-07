"""Batched, idempotent Cypher writes for isolate and movement records.

Each batch is one managed write transaction built from ``UNWIND $rows``
with ``MERGE`` on constrained keys, so re-running an ingest updates
properties in place instead of duplicating nodes. Optional parts of a
record (sequence type, genes, mobile elements) are applied with
``FOREACH`` over possibly-empty lists, so a wild-type or unsequenced
isolate simply gets no genomic relationships.
"""

from __future__ import annotations

import logging
from typing import Iterable, Sequence, TypeVar

from neo4j import ManagedTransaction
from pydantic import BaseModel

from .db import GraphClient
from .models import IsolateRecord, MovementRecord

log = logging.getLogger(__name__)

T = TypeVar("T")

UPSERT_ISOLATES = """
UNWIND $rows AS row
MERGE (p:Patient {id: row.patient_id})
MERGE (e:Encounter {id: row.encounter_id})
  SET e.admitted = coalesce(row.admitted, e.admitted),
      e.discharged = coalesce(row.discharged, e.discharged)
MERGE (p)-[:HAD_ENCOUNTER]->(e)

MERGE (w:Ward {name: row.ward})
MERGE (le:LocationEvent {id: row.location_event_id})
  ON CREATE SET le.timestamp = row.collected, le.source = 'specimen_collection'
MERGE (e)-[:GENERATED_EVENT]->(le)
MERGE (le)-[:AT_LOCATION]->(w)

MERGE (i:Isolate {id: row.isolate_id})
  SET i.collected = row.collected,
      i.specimen = row.specimen,
      i.phenotype_labels = row.phenotype_labels,
      // A clinical-only re-ingest must not erase an earlier genomic result.
      i.genotype_status = CASE
        WHEN row.genotype_status = 'not_sequenced' AND i.genotype_status IS NOT NULL THEN i.genotype_status
        ELSE row.genotype_status END
MERGE (e)-[:ISOLATED]->(i)
WITH row, e, i

// New genomic results for an isolate replace its previous calls, so a
// corrected report cannot leave a retracted gene behind.
CALL (row, i) {
  WITH row, i WHERE row.genotype_status <> 'not_sequenced'
  OPTIONAL MATCH (i)-[:CARRIES]->(old:MobileGeneticElement)
  DETACH DELETE old
  WITH DISTINCT i
  OPTIONAL MATCH (i)-[stale:CARRIES|BELONGS_TO]->()
  DELETE stale
}

MERGE (pathogen:Pathogen {ncbi_taxid: row.ncbi_taxid})
  ON CREATE SET pathogen.species = row.species, pathogen.genus = row.genus
MERGE (i)-[:IDENTIFIED_AS]->(pathogen)

FOREACH (drug IN row.treatments |
  MERGE (ab:Antibiotic {atc_code: drug.atc_code}) ON CREATE SET ab.name = drug.name
  MERGE (e)-[:TREATED_WITH]->(ab))

FOREACH (test IN row.susceptibility |
  MERGE (ab:Antibiotic {atc_code: test.atc_code}) ON CREATE SET ab.name = test.name
  MERGE (i)-[x:EXHIBITS]->(ab)
  SET x.sir = test.sir, x.mic = test.mic, x.mic_qualifier = test.mic_qualifier,
      x.mic_unit = test.mic_unit, x.guideline = test.guideline)

FOREACH (st IN CASE WHEN row.sequence_type IS NULL THEN [] ELSE [row.sequence_type] END |
  MERGE (s:SequenceType {key: st.key})
    ON CREATE SET s.scheme = st.scheme, s.st_number = st.st_number
  MERGE (i)-[b:BELONGS_TO]->(s)
  SET b.clone_designation = st.clone_designation)

FOREACH (gene IN row.direct_genes |
  MERGE (g:Gene {aro_id: gene.aro_id})
    ON CREATE SET g.name = gene.name, g.symbol = gene.symbol, g.mechanism = gene.mechanism, g.acquired = gene.acquired
  MERGE (i)-[c:CARRIES]->(g)
  SET c.context = gene.context)

FOREACH (element IN row.mobile_elements |
  MERGE (m:MobileGeneticElement {key: element.key})
    ON CREATE SET m.type = element.type, m.replicon = element.replicon
  MERGE (i)-[:CARRIES]->(m)
  FOREACH (gene IN element.genes |
    MERGE (g:Gene {aro_id: gene.aro_id})
      ON CREATE SET g.name = gene.name, g.symbol = gene.symbol, g.mechanism = gene.mechanism, g.acquired = gene.acquired
    MERGE (m)-[:HARBORS]->(g)))
"""

# Movements attach to an existing Patient/Encounter (created here if the ADT
# feed arrives before the laboratory data).
UPSERT_MOVEMENTS = """
UNWIND $rows AS row
MERGE (p:Patient {id: row.patient_id})
MERGE (e:Encounter {id: row.encounter_id})
MERGE (p)-[:HAD_ENCOUNTER]->(e)
MERGE (w:Ward {name: row.ward})
MERGE (le:LocationEvent {id: row.location_event_id})
  ON CREATE SET le.timestamp = row.timestamp, le.source = 'adt'
MERGE (e)-[:GENERATED_EVENT]->(le)
MERGE (le)-[:AT_LOCATION]->(w)
"""


def _batches(items: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _write_batch(tx: ManagedTransaction, cypher: str, rows: list[dict]) -> None:
    tx.run(cypher, rows=rows).consume()


def _load(client: GraphClient, cypher: str, records: Sequence[BaseModel], label: str, batch_size: int) -> int:
    loaded = 0
    for batch in _batches(records, batch_size):
        rows = [record.model_dump(mode="python") for record in batch]
        client.write(_write_batch, cypher, rows)
        loaded += len(rows)
        log.info("loaded %d/%d %s", loaded, len(records), label)
    return loaded


def load_isolates(client: GraphClient, records: Sequence[IsolateRecord], batch_size: int = 500) -> int:
    return _load(client, UPSERT_ISOLATES, records, "isolates", batch_size)


def load_movements(client: GraphClient, records: Sequence[MovementRecord], batch_size: int = 500) -> int:
    return _load(client, UPSERT_MOVEMENTS, records, "movements", batch_size)
