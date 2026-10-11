"""Epidemiological queries over the surveillance graph.

All isolate-to-ward placement uses the event log: an isolate is attributed
to the ward of the latest LocationEvent of its encounter at or before the
collection time.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict, deque
from datetime import datetime
from typing import Any, Literal

from neo4j import ManagedTransaction
from neo4j.exceptions import ClientError
from pydantic import BaseModel

from .db import GraphClient

log = logging.getLogger(__name__)

# Reusable Cypher fragment: binds `ward` for an isolate `i` and its encounter `e`.
_ISOLATE_WARD = """
CALL (e, i) {
  MATCH (e)-[:GENERATED_EVENT]->(le:LocationEvent)-[:AT_LOCATION]->(ward:Ward)
  WHERE le.timestamp <= i.collected
  RETURN ward ORDER BY le.timestamp DESC LIMIT 1
}
"""

# One row per (isolate, acquired gene) for typed isolates, ordered by
# collection time within each (sequence type, gene) group. Linking logic runs
# over this sorted timeline in O(n) instead of enumerating isolate pairs.
_TYPED_ISOLATE_TIMELINE = f"""
MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter)-[:ISOLATED]->(i:Isolate)-[bt:BELONGS_TO]->(st:SequenceType)
MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene {{acquired: true}})
{_ISOLATE_WARD}
RETURN DISTINCT st.key AS sequence_type, bt.clone_designation AS clone, g.aro_id AS gene_aro_id, g.symbol AS gene,
       ward.key AS ward, [(ward)-[:PART_OF]->(f:Facility) | f.code][0] AS facility,
       i.id AS isolate_id, p.id AS patient_id, i.collected AS collected
ORDER BY sequence_type, gene_aro_id, collected, isolate_id
"""


def _typed_isolate_timeline(client: GraphClient) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Group the timeline by (sequence type, gene), each list sorted by time."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in client.query(_TYPED_ISOLATE_TIMELINE):
        row["collected"] = row["collected"].to_native()
        groups[(row["sequence_type"], row["gene_aro_id"])].append(row)
    return groups


def _days_apart(earlier: datetime, later: datetime) -> int:
    # Whole days, matching Cypher's duration.inDays(...).days for ordered inputs.
    return (later - earlier).days


class ClusterMember(BaseModel):
    isolate_id: str
    patient_id: str
    collected: datetime


class SpatiotemporalCluster(BaseModel):
    ward: str
    facility: str | None = None
    sequence_type: str
    clone_designation: str | None
    gene_aro_id: str
    gene: str
    size: int
    first_collected: datetime
    last_collected: datetime
    members: list[ClusterMember]


class HorizontalTransferSignal(BaseModel):
    gene_aro_id: str
    gene: str
    level: Literal["species", "genus"]
    taxa: list[str]
    isolate_count: int
    wards: list[str]
    replicons: list[str]
    first_collected: datetime
    last_collected: datetime


class WardCentrality(BaseModel):
    ward: str
    facility: str | None = None
    pagerank: float
    betweenness: float
    weighted_degree: float
    isolates: int


class WardEdge(BaseModel):
    source: str
    target: str
    transfers: int
    genomic: int


class WardNetworkReport(BaseModel):
    window_days: int
    edges: int
    transfer_links: int
    genomic_links: int
    wards: list[WardCentrality]
    links: list[WardEdge] = []


def detect_spatiotemporal_clusters(client: GraphClient, window_days: int = 14, min_size: int = 2) -> list[SpatiotemporalCluster]:
    """Clusters of same-ST, same-gene isolates collected in one ward.

    Two isolates are linked when they share ward, sequence type and acquired
    gene variant and were collected no more than ``window_days`` apart. A
    cluster is a connected component of such links, so a chain of isolates
    each within the window of the next forms one cluster even if its total
    span is longer. On a time-sorted list those components are exactly the
    runs with no gap larger than the window.
    """
    clusters: list[SpatiotemporalCluster] = []
    for rows in _typed_isolate_timeline(client).values():
        by_ward: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_ward[row["ward"]].append(row)
        for ward_rows in by_ward.values():
            run: list[dict[str, Any]] = []
            for row in ward_rows + [None]:
                if row is not None and (not run or _days_apart(run[-1]["collected"], row["collected"]) <= window_days):
                    run.append(row)
                    continue
                if len(run) >= min_size:
                    clusters.append(_cluster_from_run(run))
                run = [row] if row is not None else []
    clusters.sort(key=lambda c: (-c.size, c.first_collected, c.ward))
    log.info("found %d spatiotemporal clusters (window %d days)", len(clusters), window_days)
    return clusters


def _cluster_from_run(run: list[dict[str, Any]]) -> SpatiotemporalCluster:
    first = run[0]
    return SpatiotemporalCluster(
        ward=first["ward"],
        facility=first["facility"],
        sequence_type=first["sequence_type"],
        clone_designation=first["clone"],
        gene_aro_id=first["gene_aro_id"],
        gene=first["gene"],
        size=len(run),
        first_collected=run[0]["collected"],
        last_collected=run[-1]["collected"],
        members=[ClusterMember(isolate_id=r["isolate_id"], patient_id=r["patient_id"], collected=r["collected"]) for r in run],
    )


def detect_horizontal_gene_transfer(client: GraphClient, level: Literal["species", "genus"] = "species") -> list[HorizontalTransferSignal]:
    """Acquired gene variants seen in more than one species (or genus).

    The same ARO accession in unrelated taxa within one facility points at
    a shared mobile element rather than clonal spread. Chromosomal
    mutations are excluded because they cannot transfer.
    """
    taxon = "pathogen.genus" if level == "genus" else "pathogen.species"
    cypher = f"""
    MATCH (e:Encounter)-[:ISOLATED]->(i:Isolate)-[:IDENTIFIED_AS]->(pathogen:Pathogen)
    MATCH (i)-[:CARRIES]->(carrier)-[:HARBORS*0..1]->(g:Gene {{acquired: true}})
    {_ISOLATE_WARD}
    WITH g, {taxon} AS taxon, i, ward,
         CASE WHEN carrier:MobileGeneticElement THEN carrier.type + ':' + carrier.replicon END AS replicon
    WITH g, collect(DISTINCT taxon) AS taxa, collect(DISTINCT i) AS isolates,
         collect(DISTINCT ward.key) AS wards, collect(DISTINCT replicon) AS replicons
    WHERE size(taxa) > 1
    UNWIND isolates AS isolate
    WITH g, taxa, wards, replicons, count(isolate) AS isolate_count,
         min(isolate.collected) AS first_collected, max(isolate.collected) AS last_collected
    RETURN g.aro_id AS gene_aro_id, g.symbol AS gene, taxa, isolate_count, wards, replicons,
           first_collected, last_collected
    ORDER BY size(taxa) DESC, isolate_count DESC
    """
    signals = [
        HorizontalTransferSignal(
            level=level,
            gene_aro_id=row["gene_aro_id"],
            gene=row["gene"],
            taxa=sorted(row["taxa"]),
            isolate_count=row["isolate_count"],
            wards=sorted(row["wards"]),
            replicons=sorted(row["replicons"]),
            first_collected=row["first_collected"].to_native(),
            last_collected=row["last_collected"].to_native(),
        )
        for row in client.query(cypher)
    ]
    log.info("found %d horizontal gene transfer signals at %s level", len(signals), level)
    return signals


class GdsUnavailableError(RuntimeError):
    """The Graph Data Science plugin is not installed on the server."""


def _gds_version(client: GraphClient) -> str:
    try:
        return client.query("RETURN gds.version() AS version")[0]["version"]
    except ClientError as exc:
        raise GdsUnavailableError("the Neo4j Graph Data Science plugin is required for ward centrality") from exc


def gds_version(client: GraphClient) -> str | None:
    try:
        return _gds_version(client)
    except GdsUnavailableError:
        return None


# Ward network: an undirected, weighted graph whose edges are
#   * patient transfers (consecutive LocationEvents of one patient in
#     different wards), and
#   * genomic links (pairs of isolates with the same ST and acquired gene,
#     collected within the window, in different wards).
_WARD_TRANSFERS = """
MATCH (p:Patient)-[:HAD_ENCOUNTER]->(:Encounter)-[:GENERATED_EVENT]->(le:LocationEvent)-[:AT_LOCATION]->(w:Ward)
WITH p, le, w ORDER BY le.timestamp
WITH p, collect(w.key) AS path
UNWIND range(0, size(path) - 2) AS k
WITH path[k] AS source, path[k + 1] AS target
WHERE source <> target
RETURN source, target, count(*) AS transfers
"""

_PROJECT_WARD_NETWORK = """
CALL () {
  UNWIND $edges AS edge
  MATCH (source:Ward {key: edge.source}), (target:Ward {key: edge.target})
  RETURN source, target, edge.weight AS weight
  UNION ALL
  MATCH (source:Ward)
  RETURN source, null AS target, null AS weight
}
WITH gds.graph.project(
       $graph_name, source, target,
       {relationshipProperties: CASE WHEN target IS NULL THEN {} ELSE {weight: weight} END},
       {undirectedRelationshipTypes: ['*']}
     ) AS graph
RETURN graph.nodeCount AS nodes, graph.relationshipCount AS relationships
"""

_CENTRALITY_STEPS = (
    "CALL gds.pageRank.mutate($graph_name, {relationshipWeightProperty: 'weight', mutateProperty: 'pagerank'}) YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
    "CALL gds.betweenness.mutate($graph_name, {mutateProperty: 'betweenness'}) YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
    "CALL gds.degree.mutate($graph_name, {relationshipWeightProperty: 'weight', mutateProperty: 'degree'}) YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
)

_CENTRALITY_SCORES = """
CALL gds.graph.nodeProperties.stream($graph_name, ['pagerank', 'betweenness', 'degree'])
YIELD nodeId, nodeProperty, propertyValue
WITH gds.util.asNode(nodeId) AS ward, collect([nodeProperty, propertyValue]) AS scores
OPTIONAL MATCH (ward)<-[:AT_LOCATION]-(:LocationEvent)<-[:GENERATED_EVENT]-(e:Encounter)-[:ISOLATED]->(i:Isolate)
RETURN ward.key AS ward, [(ward)-[:PART_OF]->(f:Facility) | f.code][0] AS facility,
       scores, count(DISTINCT i) AS isolates
"""


def _edge(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _genomic_ward_links(client: GraphClient, window_days: int) -> Counter[tuple[str, str]]:
    """Count cross-ward isolate pairs per ward pair with a sliding window.

    For each isolate, the wards of earlier isolates still inside the window
    are tallied, so the cost is O(isolates x wards) rather than O(pairs).
    """
    links: Counter[tuple[str, str]] = Counter()
    for rows in _typed_isolate_timeline(client).values():
        window: deque[dict[str, Any]] = deque()
        in_window: Counter[str] = Counter()
        for row in rows:
            while window and _days_apart(window[0]["collected"], row["collected"]) > window_days:
                in_window[window.popleft()["ward"]] -= 1
            for ward, n in in_window.items():
                if n and ward != row["ward"]:
                    links[_edge(ward, row["ward"])] += n
            window.append(row)
            in_window[row["ward"]] += 1
    return links


def rank_wards(client: GraphClient, window_days: int = 14) -> WardNetworkReport:
    """Score wards as transmission hubs with GDS PageRank and betweenness.

    PageRank (weighted by link count) highlights wards that linked cases
    concentrate in; betweenness highlights wards that bridge otherwise
    separate parts of the network. Betweenness is computed unweighted
    because GDS treats relationship weights as distances.
    """
    _gds_version(client)
    transfers: Counter[tuple[str, str]] = Counter()
    for row in client.query(_WARD_TRANSFERS):
        transfers[_edge(row["source"], row["target"])] += row["transfers"]
    genomic = _genomic_ward_links(client, window_days)
    edges = [
        {"source": source, "target": target, "weight": float(transfers[(source, target)] + genomic[(source, target)])}
        for source, target in sorted(set(transfers) | set(genomic))
    ]
    graph_name = f"bionexus-wards-{uuid.uuid4().hex[:12]}"

    def work(tx: ManagedTransaction) -> list[dict[str, Any]]:
        tx.run(_PROJECT_WARD_NETWORK, graph_name=graph_name, edges=edges).consume()
        try:
            for step in _CENTRALITY_STEPS:
                tx.run(step, graph_name=graph_name).consume()
            return [record.data() for record in tx.run(_CENTRALITY_SCORES, graph_name=graph_name)]
        finally:
            tx.run("CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName", graph_name=graph_name).consume()

    wards = []
    for row in client.read(work):
        scores = dict(row["scores"])
        wards.append(
            WardCentrality(
                ward=row["ward"],
                facility=row["facility"],
                pagerank=scores["pagerank"],
                betweenness=scores["betweenness"],
                weighted_degree=scores["degree"],
                isolates=row["isolates"],
            )
        )
    wards.sort(key=lambda w: (-w.pagerank, w.ward))
    report = WardNetworkReport(
        window_days=window_days,
        edges=len(edges),
        transfer_links=sum(transfers.values()),
        genomic_links=sum(genomic.values()),
        wards=wards,
        links=[
            WardEdge(source=e["source"], target=e["target"], transfers=transfers[(e["source"], e["target"])], genomic=genomic[(e["source"], e["target"])])
            for e in edges
        ],
    )
    log.info("ranked %d wards over %d edges", len(report.wards), report.edges)
    return report
