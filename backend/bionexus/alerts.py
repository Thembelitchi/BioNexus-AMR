"""Clinical alert rules evaluated over the surveillance graph.

Each rule is a documented criterion, so a clinical reviewer can check what
fires and why:

* ``stewardship_mismatch`` (high): an agent prescribed during the encounter
  is one the isolate tests resistant to. Treatment is recorded per
  admission, so a drug noted with one culture also applies to the patient's
  other cultures in that admission.
* ``carbapenemase_producer`` (high): the isolate carries a carbapenemase
  gene (CARD-grounded category), whatever its phenotype; OXA-48-like
  producers can still test meropenem-susceptible.
* ``colistin_resistance`` (critical): colistin tests resistant, or a
  plasmid-mediated colistin resistance gene (mcr) is present.
* ``sentinel_gene`` (critical): a gene the local programme treats as
  unexpected, so each case warrants investigation. The default set suits
  South Africa, where KPC is uncommon; adjust ``SENTINEL_GENES`` per setting.

Genotype-phenotype discordance (needs a sequenced isolate):

* ``carbapenemase_meropenem_not_r`` (high): a carbapenemase gene is
  present but meropenem does not test resistant. OXA-48-like enzymes, the
  commonest carbapenemases in South Africa, often look like this; the
  isolate should be managed as a carbapenemase producer regardless.
* ``unexplained_carbapenem_resistance`` (high): a carbapenem tests
  resistant in a sequenced isolate with no carbapenemase gene and no known
  porin mutation, so the mechanism is unexplained (e.g. AmpC or ESBL plus
  porin loss, efflux, or an enzyme the pipeline does not detect).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .analytics import _ISOLATE_WARD
from .db import GraphClient
from .ontology import CARBAPENEM_ATC

log = logging.getLogger(__name__)

SENTINEL_GENES = frozenset({"blaKPC-2", "blaKPC-3", "mcr-1.1"})
COLISTIN_ATC = "J01XB01"
MEROPENEM_ATC = "J01DH02"
SEVERITY_ORDER = {"critical": 0, "high": 1}

RULES: dict[str, tuple[str, str]] = {
    "stewardship_mismatch": ("high", "Prescribed agent tests resistant"),
    "carbapenemase_producer": ("high", "Carbapenemase gene detected"),
    "colistin_resistance": ("critical", "Colistin resistant (phenotype or mcr gene)"),
    "sentinel_gene": ("critical", "Sentinel resistance gene detected"),
    "carbapenemase_meropenem_not_r": ("high", "Carbapenemase gene, meropenem not resistant"),
    "unexplained_carbapenem_resistance": ("high", "Carbapenem resistance without a known mechanism"),
}


class ClinicalAlert(BaseModel):
    rule: str
    severity: Literal["critical", "high"]
    title: str
    detail: str
    isolate_id: str
    patient_id: str
    ward: str
    facility: str | None
    collected: datetime
    species: str


_CONTEXT = f"""
MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter)-[:ISOLATED]->(i:Isolate)-[:IDENTIFIED_AS]->(pathogen:Pathogen)
{_ISOLATE_WARD}
WITH p, e, i, pathogen, ward, [(ward)-[:PART_OF]->(f:Facility) | f.code][0] AS facility
"""

_RETURN = """
RETURN i.id AS isolate_id, p.id AS patient_id, ward.key AS ward, facility,
       i.collected AS collected, pathogen.species AS species, detail
"""

_MIC_TEXT = """CASE WHEN x.mic IS NULL THEN coalesce(toString(x.zone_mm) + ' mm', 'no value')
     ELSE CASE WHEN x.mic_qualifier IS NULL OR x.mic_qualifier = '=' THEN '' ELSE x.mic_qualifier END + toString(x.mic) + ' mg/L' END"""

_QUERIES = {
    "stewardship_mismatch": _CONTEXT + """
MATCH (e)-[:TREATED_WITH]->(drug:Antibiotic)<-[x:EXHIBITS {sir: 'R'}]-(i)
WITH *, drug.name + ' prescribed; isolate tests R (' + """ + _MIC_TEXT + """ + ')' AS detail
""" + _RETURN,
    "carbapenemase_producer": _CONTEXT + """
MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene {category: 'carbapenemase'})
WITH p, e, i, pathogen, ward, facility, collect(DISTINCT g.symbol) AS genes
WITH *, reduce(s = '', x IN genes | s + CASE WHEN s = '' THEN '' ELSE ', ' END + x) AS detail
""" + _RETURN,
    "colistin_resistance": _CONTEXT + """
OPTIONAL MATCH (i)-[x:EXHIBITS {sir: 'R'}]->(:Antibiotic {atc_code: $colistin})
OPTIONAL MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene {category: 'colistin'})
WITH p, e, i, pathogen, ward, facility, x, collect(DISTINCT g.symbol) AS genes
WHERE x IS NOT NULL OR size(genes) > 0
WITH *, CASE WHEN x IS NULL THEN 'colistin not tested' ELSE 'colistin R (' + """ + _MIC_TEXT + """ + ')' END +
        CASE WHEN size(genes) > 0 THEN '; ' + genes[0] ELSE '' END AS detail
""" + _RETURN,
    "sentinel_gene": _CONTEXT + """
MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene)
WHERE g.symbol IN $sentinels
WITH p, e, i, pathogen, ward, facility, collect(DISTINCT g.symbol) AS genes
WITH *, reduce(s = '', x IN genes | s + CASE WHEN s = '' THEN '' ELSE ', ' END + x) AS detail
""" + _RETURN,
    "carbapenemase_meropenem_not_r": _CONTEXT + """
MATCH (i)-[x:EXHIBITS]->(:Antibiotic {atc_code: $meropenem})
WHERE x.sir <> 'R'
MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene {category: 'carbapenemase'})
WITH p, e, i, pathogen, ward, facility, x, collect(DISTINCT g.symbol) AS genes
WITH *, reduce(s = '', y IN genes | s + CASE WHEN s = '' THEN '' ELSE ', ' END + y) +
        '; meropenem ' + x.sir + ' (' + """ + _MIC_TEXT + """ + ')' AS detail
""" + _RETURN,
    "unexplained_carbapenem_resistance": _CONTEXT + """
WHERE i.genotype_status IN ['determinants_detected', 'no_determinant_detected']
  AND NOT EXISTS { MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene) WHERE g.category IN ['carbapenemase', 'porin'] }
MATCH (i)-[x:EXHIBITS {sir: 'R'}]->(drug:Antibiotic)
WHERE drug.atc_code IN $carbapenems
WITH p, e, i, pathogen, ward, facility, collect(drug.name + ' R') AS results
WITH *, reduce(s = '', y IN results | s + CASE WHEN s = '' THEN '' ELSE ', ' END + y) + '; no carbapenemase or porin mutation found' AS detail
""" + _RETURN,
}


def clinical_alerts(client: GraphClient, sentinel_genes: frozenset[str] = SENTINEL_GENES) -> list[ClinicalAlert]:
    alerts: list[ClinicalAlert] = []
    for rule, cypher in _QUERIES.items():
        severity, title = RULES[rule]
        params = {"colistin": COLISTIN_ATC, "sentinels": sorted(sentinel_genes), "meropenem": MEROPENEM_ATC, "carbapenems": sorted(CARBAPENEM_ATC)}
        for row in client.query(cypher, **params):
            alerts.append(
                ClinicalAlert(
                    rule=rule,
                    severity=severity,
                    title=title,
                    detail=row["detail"],
                    isolate_id=row["isolate_id"],
                    patient_id=row["patient_id"],
                    ward=row["ward"],
                    facility=row["facility"],
                    collected=row["collected"].to_native(),
                    species=row["species"],
                )
            )
    alerts.sort(key=lambda a: (SEVERITY_ORDER[a.severity], -a.collected.timestamp(), a.rule, a.isolate_id, a.detail))
    log.info("evaluated %d alert rules: %d alerts", len(_QUERIES), len(alerts))
    return alerts
