"""South African notifiable medical conditions (NMC) found by the laboratory.

The NMC regulations under the National Health Act (gazetted 15 December
2017) list Category 4 conditions that public and private laboratories must
notify to the Department of Health within one month of diagnosis. The
antimicrobial-resistant organisms among them, and the criterion used here:

* ``cpe`` Carbapenemase-producing Enterobacteriaceae: an Enterobacterales
  isolate carrying a carbapenemase gene. A carbapenem-resistant isolate that
  was not sequenced is listed with status ``confirm_carbapenemase``, because
  carbapenem resistance alone does not prove a carbapenemase.
* ``vre`` Vancomycin-resistant enterococci: an *Enterococcus* isolate that
  tests vancomycin resistant.
* ``colistin_resistant`` Colistin-resistant *P. aeruginosa* or
  *A. baumannii*: colistin tests resistant.
* ``gisa`` *S. aureus* with reduced vancomycin susceptibility (hGISA/GISA):
  vancomycin MIC of 4 mg/L or more.

A case is one patient and one condition, dated by the first qualifying
isolate, so repeat cultures do not create repeat notifications. Recording
that a notification was sent is outside this graph; the report gives each
case its legal due date so that it can be checked.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from .analytics import _ISOLATE_WARD
from .db import GraphClient
from .ontology import CARBAPENEM_ATC, ENTEROBACTERALES_TAXIDS

log = logging.getLogger(__name__)

COLISTIN_ATC = "J01XB01"
VANCOMYCIN_ATC = "J01XA01"

CONDITIONS: dict[str, str] = {
    "cpe": "Carbapenemase-producing Enterobacteriaceae",
    "vre": "Vancomycin-resistant enterococci",
    "colistin_resistant": "Colistin-resistant P. aeruginosa or A. baumannii",
    "gisa": "S. aureus with reduced vancomycin susceptibility (hGISA/GISA)",
}


class NotifiableCase(BaseModel):
    condition: str
    title: str
    status: Literal["notify", "confirm_carbapenemase"]
    patient_id: str
    isolate_id: str
    species: str
    facility: str | None
    ward: str
    collected: datetime
    due: date
    evidence: str


_CONTEXT = """
MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter)-[:ISOLATED]->(i:Isolate)-[:IDENTIFIED_AS]->(pathogen:Pathogen)
"""

# Every query returns qualifying isolates; the earliest per patient wins.
_RETURN = f"""
WITH p, e, i, pathogen, status, evidence
{_ISOLATE_WARD}
RETURN p.id AS patient_id, i.id AS isolate_id, pathogen.species AS species,
       [(ward)-[:PART_OF]->(f:Facility) | f.code][0] AS facility, ward.key AS ward,
       i.collected AS collected, status, evidence
"""

_QUERIES: dict[str, str] = {
    "cpe": _CONTEXT + """
WHERE pathogen.ncbi_taxid IN $enterobacterales
OPTIONAL MATCH (i)-[:CARRIES]->()-[:HARBORS*0..1]->(g:Gene {category: 'carbapenemase'})
WITH p, e, i, pathogen, collect(DISTINCT g.symbol) AS genes,
     [(i)-[x:EXHIBITS {sir: 'R'}]->(d:Antibiotic) WHERE d.atc_code IN $carbapenems | d.name] AS carbapenems_r
WHERE size(genes) > 0 OR (i.genotype_status = 'not_sequenced' AND size(carbapenems_r) > 0)
WITH p, e, i, pathogen,
     CASE WHEN size(genes) > 0 THEN 'notify' ELSE 'confirm_carbapenemase' END AS status,
     CASE WHEN size(genes) > 0 THEN reduce(s = '', x IN genes | s + CASE WHEN s = '' THEN '' ELSE ', ' END + x)
          ELSE reduce(s = '', x IN carbapenems_r | s + CASE WHEN s = '' THEN '' ELSE ', ' END + x + ' R') + '; not sequenced'
     END AS evidence
""" + _RETURN,
    "vre": _CONTEXT + """
WHERE pathogen.genus = 'Enterococcus'
MATCH (i)-[x:EXHIBITS {sir: 'R'}]->(:Antibiotic {atc_code: $vancomycin})
WITH p, e, i, pathogen, 'notify' AS status, 'vancomycin R' AS evidence
""" + _RETURN,
    "colistin_resistant": _CONTEXT + """
WHERE pathogen.ncbi_taxid IN [287, 470]
MATCH (i)-[x:EXHIBITS {sir: 'R'}]->(:Antibiotic {atc_code: $colistin})
WITH p, e, i, pathogen, 'notify' AS status, 'colistin R' AS evidence
""" + _RETURN,
    "gisa": _CONTEXT + """
WHERE pathogen.ncbi_taxid = 1280
MATCH (i)-[x:EXHIBITS]->(:Antibiotic {atc_code: $vancomycin})
WHERE x.mic >= 4
WITH p, e, i, pathogen, 'notify' AS status, 'vancomycin MIC ' + toString(x.mic) + ' mg/L' AS evidence
""" + _RETURN,
}


def one_month_after(day: date) -> date:
    """The same day next month, or that month's last day when it is shorter."""
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def notifiable_cases(client: GraphClient) -> list[NotifiableCase]:
    """Category 4 NMC cases, one per patient and condition, earliest first."""
    params = {
        "enterobacterales": sorted(ENTEROBACTERALES_TAXIDS),
        "carbapenems": sorted(CARBAPENEM_ATC),
        "vancomycin": VANCOMYCIN_ATC,
        "colistin": COLISTIN_ATC,
    }
    cases: list[NotifiableCase] = []
    for condition, cypher in _QUERIES.items():
        first: dict[str, dict] = {}
        for row in client.query(cypher, **params):
            row["collected"] = row["collected"].to_native()
            known = first.get(row["patient_id"])
            # A confirmed case outranks an unconfirmed one; then the earliest isolate.
            rank = (row["status"] != "notify", row["collected"], row["isolate_id"])
            if known is None or rank < (known["status"] != "notify", known["collected"], known["isolate_id"]):
                first[row["patient_id"]] = row
        for row in first.values():
            cases.append(
                NotifiableCase(
                    condition=condition,
                    title=CONDITIONS[condition],
                    due=one_month_after(row["collected"].date()),
                    **row,
                )
            )
    cases.sort(key=lambda c: (c.collected, c.condition, c.patient_id))
    log.info("found %d notifiable cases", len(cases))
    return cases
