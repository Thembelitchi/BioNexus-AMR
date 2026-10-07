#!/usr/bin/env python3
"""Generate the BioNexus South African AMR demonstration dataset.

    python tools/generate_demo_dataset.py [--out data/demo] [--seed 2025]

The output is SYNTHETIC: every patient, specimen, facility and result is
generated. What is grounded in reality is the vocabulary (verified by
tools/verify_vocabulary.py), the CLSI 2025 breakpoints used to interpret
every MIC, and the qualitative epidemiology encoded in the parameters
below, which follows patterns reported by South African surveillance
(see data/demo/README.md). Proportions are illustrative, not estimates.

Outputs: clinical.csv, genomic.csv, movements.csv, scenarios.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bionexus import ontology  # noqa: E402
from bionexus.breakpoints import BREAKPOINT_SOURCE, interpret  # noqa: E402

SAST = timezone(timedelta(hours=2))
PERIOD_START, PERIOD_END = date(2025, 7, 1), date(2025, 12, 31)
TOTAL_PATIENTS = 600

# ----------------------------------------------------------------------------
# Facilities (fictional, placed in real provinces)
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Facility:
    code: str
    name: str
    province: str
    wards: dict[str, float]  # ward -> share of this facility's cases


FACILITIES = {
    f.code: f
    for f in (
        Facility("GAH", "Gauteng Academic Hospital (demo)", "Gauteng",
                 {"Adult ICU": 0.24, "Neonatal ICU": 0.16, "Medical": 0.2, "Surgical": 0.16, "Haematology-Oncology": 0.12, "Burns": 0.12}),
        Facility("GDH", "Gauteng District Hospital (demo)", "Gauteng", {"Medical": 0.6, "Paediatrics": 0.4}),
        Facility("KRH", "KwaZulu-Natal Regional Hospital (demo)", "KwaZulu-Natal",
                 {"Adult ICU": 0.3, "Neonatal ICU": 0.2, "Medical": 0.25, "Surgical": 0.25}),
        Facility("WTH", "Western Cape Tertiary Hospital (demo)", "Western Cape",
                 {"Adult ICU": 0.28, "Neonatal ICU": 0.15, "Medical": 0.22, "Surgical": 0.2, "Haematology-Oncology": 0.15}),
    )
}
FACILITY_SHARE = {"GAH": 0.36, "GDH": 0.1, "KRH": 0.26, "WTH": 0.28}

# ----------------------------------------------------------------------------
# Organisms, strains and resistance determinants
# ----------------------------------------------------------------------------

SPECIES = {
    "KP": "Klebsiella pneumoniae",
    "EC": "Escherichia coli",
    "ECL": "Enterobacter cloacae",
    "AB": "Acinetobacter baumannii",
    "PA": "Pseudomonas aeruginosa",
    "SA": "Staphylococcus aureus",
    "EF": "Enterococcus faecium",
}
ENTEROBACTERALES = {"KP", "EC", "ECL"}

# Organism mix by ward type (share of positive cultures).
ORGANISMS_BY_WARD = {
    "Adult ICU": {"AB": 0.28, "KP": 0.26, "PA": 0.12, "SA": 0.13, "EC": 0.08, "ECL": 0.08, "EF": 0.05},
    "Neonatal ICU": {"KP": 0.48, "SA": 0.14, "ECL": 0.13, "EC": 0.1, "AB": 0.1, "EF": 0.05},
    "Medical": {"EC": 0.32, "KP": 0.24, "SA": 0.24, "PA": 0.07, "ECL": 0.07, "EF": 0.06},
    "Surgical": {"SA": 0.25, "EC": 0.22, "KP": 0.22, "PA": 0.12, "ECL": 0.09, "AB": 0.06, "EF": 0.04},
    "Haematology-Oncology": {"EC": 0.25, "KP": 0.22, "PA": 0.15, "EF": 0.15, "SA": 0.13, "ECL": 0.1},
    "Burns": {"PA": 0.3, "AB": 0.25, "SA": 0.25, "KP": 0.15, "ECL": 0.05},
    "Paediatrics": {"KP": 0.3, "SA": 0.3, "EC": 0.3, "ECL": 0.1},
}

# Typical genetic carriers. CARD does not record these, so they are
# literature-based (see the data card); only used when typing resolved them.
CARRIERS = {
    "blaOXA-181": ("Plasmid", "IncX3"),
    "blaNDM-5": ("Plasmid", "IncX3"),
    "blaOXA-48": ("Plasmid", "IncL"),
    "blaOXA-232": ("Plasmid", "ColKP3"),
    "blaKPC-2": ("Transposon", "Tn4401"),
    "blaOXA-23": ("Transposon", "Tn2006"),
    "blaVIM-2": ("Integron", "class 1 integron"),
    "blaGES-5": ("Integron", "class 1 integron"),
    "vanA": ("Transposon", "Tn1546"),
    "mcr-1.1": ("Plasmid", "IncI2"),
}


@dataclass(frozen=True)
class Strain:
    organism: str
    st: int
    genes: tuple[str, ...] = ()


# Background population structure: (weight, candidate STs, genes).
BACKGROUND_STRAINS = {
    "KP": [
        (28, [307], ("blaCTX-M-15",)),
        (7, [307], ("blaCTX-M-15", "blaOXA-181")),
        (4, [101], ("blaCTX-M-15", "blaOXA-48")),
        (2, [101, 14], ("blaOXA-232",)),
        (3, [152], ("blaCTX-M-15", "blaNDM-1")),
        (2, [14], ("blaCTX-M-15", "blaNDM-1")),
        (1, [15], ("blaCTX-M-15", "blaNDM-5")),
        (16, [17, 15], ("blaCTX-M-15",)),
        (37, [17, 14, 15, 101], ()),
    ],
    "EC": [
        (22, [131], ("blaCTX-M-15",)),
        (1.5, [410], ("blaCTX-M-15", "blaOXA-181")),
        (1, [167], ("blaNDM-5",)),
        (75.5, [131, 73, 95, 69, 10], ()),
    ],
    "ECL": [
        (34, [78, 90, 171], ("blaCTX-M-15",)),
        (8, [78], ("blaCTX-M-15", "blaNDM-1")),
        (4, [171], ("blaOXA-181",)),
        (54, [78, 90, 171], ()),
    ],
    "AB": [
        (78, [2], ("blaOXA-23",)),
        (8, [1], ("blaOXA-23",)),
        (14, [2, 1], ()),
    ],
    "PA": [
        (8, [235, 111], ("blaVIM-2",)),
        (3, [235], ("blaGES-5",)),
        (14, [244, 111, 235], ("oprD",)),
        (75, [244, 111, 235, 274], ()),
    ],
    "SA": [
        (11, [612], ("mecA",)),
        (8, [5], ("mecA",)),
        (6, [239], ("mecA", "ermC")),
        (3, [36], ("mecA",)),
        (6, [5, 8, 30], ("ermC",)),
        (66, [5, 8, 15, 30, 121, 152], ()),
    ],
    "EF": [
        (8, [80, 18, 17], ("vanA",)),
        (92, [17, 18, 80, 203], ()),
    ],
}


def draw_background_strain(organism: str, rng: random.Random) -> Strain:
    entries = BACKGROUND_STRAINS[organism]
    weight, sts, genes = rng.choices(entries, weights=[e[0] for e in entries])[0]
    return Strain(organism, rng.choice(sts), genes)


# ----------------------------------------------------------------------------
# Phenotype: genotype -> category probabilities -> CLSI-consistent MIC
# ----------------------------------------------------------------------------

PANELS = {
    "KP": ["AMC", "TZP", "CRO", "CAZ", "FEP", "ETP", "MEM", "IPM", "AMK", "GEN", "CIP", "SXT"],
    "EC": ["AMP", "AMC", "TZP", "CRO", "CAZ", "FEP", "ETP", "MEM", "IPM", "AMK", "GEN", "CIP", "SXT"],
    "ECL": ["TZP", "CRO", "CAZ", "FEP", "ETP", "MEM", "IPM", "AMK", "GEN", "CIP", "SXT"],
    "AB": ["TZP", "CAZ", "FEP", "MEM", "IPM", "AMK", "GEN", "CIP", "SXT"],
    "PA": ["TZP", "CAZ", "FEP", "MEM", "IPM", "CIP"],
    "SA": ["OXA", "FOX", "ERY", "CLI", "SXT", "RIF", "GEN", "CIP", "VAN", "LNZ"],
    "EF": ["AMP", "VAN", "LNZ"],
}
# Reserve agents reported only for carbapenem-non-susceptible isolates (cascade reporting).
CASCADE = {"KP": ["CZA", "COL", "TGC"], "EC": ["CZA", "COL", "TGC"], "ECL": ["CZA", "COL", "TGC"], "AB": ["COL"], "PA": ["CZA", "COL"]}

# Reportable MIC range per drug (automated broth-microdilution style), mg/L.
PANEL_RANGE = {
    "AMP": (2, 32), "AMC": (2, 32), "TZP": (4, 128), "CRO": (1, 64), "CAZ": (1, 64), "FEP": (1, 64),
    "ETP": (0.5, 8), "MEM": (0.25, 16), "IPM": (0.25, 16), "AMK": (2, 64), "GEN": (1, 16), "CIP": (0.25, 4),
    "SXT": (1, 16), "COL": (0.5, 16), "TGC": (0.5, 8), "CZA": (0.5, 16), "OXA": (0.25, 4), "FOX": (2, 16),
    "ERY": (0.25, 8), "CLI": (0.25, 8), "RIF": (0.5, 32), "VAN": (0.5, 32), "LNZ": (0.5, 8),
}
DILUTIONS = [0.008, 0.015, 0.03, 0.06, 0.12, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
CODE_TO_DRUG = {ref.amr_code: ref for ref in ontology.ANTIBIOTICS.values()}

OXA48_LIKE = {"blaOXA-48", "blaOXA-181", "blaOXA-232"}
MBL = {"blaNDM-1", "blaNDM-5", "blaVIM-2"}


def _p(**weights: float) -> dict[str, float]:
    return weights


def category_weights(strain: Strain, code: str) -> dict[str, float]:
    """Probability of each CLSI category for one drug given the genotype."""
    g, o = set(strain.genes), strain.organism
    esbl, oxa48, mbl = "blaCTX-M-15" in g, bool(g & OXA48_LIKE), bool(g & MBL)
    kpc, ges = "blaKPC-2" in g, "blaGES-5" in g
    carbapenemase = oxa48 or mbl or kpc or ges or "blaOXA-23" in g
    # Fluoroquinolone resistance is chromosomal and clone-associated.
    fq_clone = (o, strain.st) in {("EC", 131), ("EC", 410), ("KP", 307), ("KP", 15), ("KP", 14), ("SA", 239), ("SA", 612)}

    if o in ENTEROBACTERALES:
        if code == "AMP":
            return _p(R=1) if esbl or carbapenemase else _p(S=0.4, R=0.6)
        if code == "AMC":
            return _p(R=1) if carbapenemase else _p(S=0.2, I=0.3, R=0.5) if esbl else _p(S=0.85, R=0.15)
        if code == "TZP":
            return _p(R=1) if mbl or kpc else _p(S=0.15, SDD=0.25, R=0.6) if oxa48 else _p(S=0.55, SDD=0.2, R=0.25) if esbl else _p(S=0.97, R=0.03)
        if code in {"CRO", "CAZ", "FEP"}:
            if mbl or kpc or esbl:
                return {"CRO": _p(R=1), "CAZ": _p(S=0.05, I=0.15, R=0.8), "FEP": _p(S=0.1, SDD=0.3, R=0.6)}[code]
            if oxa48:  # OXA-48-like enzymes spare most cephalosporins
                return _p(S=0.7, R=0.3)
            return _p(S=0.97, R=0.03) if code == "CRO" else _p(S=0.98, R=0.02)
        if code == "ETP":
            return _p(R=1) if carbapenemase else _p(S=0.95, I=0.05) if esbl else _p(S=1)
        if code in {"MEM", "IPM"}:
            if mbl or kpc:
                return _p(I=0.05, R=0.95)
            if oxa48:  # low-level hydrolysis: may test susceptible
                return _p(S=0.25, I=0.35, R=0.4)
            return _p(S=1)
        if code == "CZA":
            return _p(R=1) if mbl else _p(S=0.97, R=0.03)
        if code == "AMK":
            return _p(S=0.55, I=0.1, R=0.35) if mbl else _p(S=0.8, I=0.05, R=0.15) if carbapenemase or esbl else _p(S=0.98, R=0.02)
        if code == "GEN":
            return _p(S=0.35, I=0.05, R=0.6) if carbapenemase or esbl else _p(S=0.9, R=0.1)
        if code == "CIP":
            return _p(S=0.1, I=0.05, R=0.85) if fq_clone else _p(S=0.25, I=0.05, R=0.7) if esbl or carbapenemase else _p(S=0.8, I=0.05, R=0.15)
        if code == "SXT":  # co-trimoxazole prophylaxis keeps resistance high
            return _p(S=0.3, R=0.7) if esbl or carbapenemase else _p(S=0.5, R=0.5)
        if code == "COL":  # CLSI has no S category for colistin
            return _p(R=1) if "mcr-1.1" in g else _p(I=0.92, R=0.08) if carbapenemase and o == "KP" else _p(I=0.98, R=0.02)
        if code == "TGC":
            return _p(S=0.75, I=0.15, R=0.1) if carbapenemase else _p(S=0.9, I=0.08, R=0.02)
    if o == "AB":
        crab = "blaOXA-23" in g
        table = {
            "TZP": (_p(R=1), _p(S=0.85, I=0.05, R=0.1)),
            "CAZ": (_p(I=0.1, R=0.9), _p(S=0.8, I=0.1, R=0.1)),
            "FEP": (_p(I=0.15, R=0.85), _p(S=0.8, I=0.1, R=0.1)),
            "MEM": (_p(R=1), _p(S=0.95, I=0.05)),
            "IPM": (_p(R=1), _p(S=0.95, I=0.05)),
            "AMK": (_p(S=0.25, I=0.05, R=0.7), _p(S=0.9, R=0.1)),
            "GEN": (_p(S=0.2, I=0.05, R=0.75), _p(S=0.85, R=0.15)),
            "CIP": (_p(S=0.03, I=0.02, R=0.95), _p(S=0.65, I=0.05, R=0.3)),
            "SXT": (_p(S=0.2, R=0.8), _p(S=0.6, R=0.4)),
            "COL": (_p(I=0.95, R=0.05), _p(I=0.99, R=0.01)),
        }
        return table[code][0 if crab else 1]
    if o == "PA":
        oprd = "oprD" in g
        if code in {"MEM", "IPM"}:
            if mbl:
                return _p(R=1)
            if ges:
                return _p(I=0.3, R=0.7)
            if oprd:
                return _p(I=0.1, R=0.9) if code == "IPM" else _p(S=0.2, I=0.5, R=0.3)
            return _p(S=0.93, I=0.04, R=0.03)
        if code in {"CAZ", "FEP", "TZP"}:
            return _p(R=1) if mbl or ges else _p(S=0.88, I=0.06, R=0.06)
        if code == "CZA":
            return _p(R=1) if mbl else _p(S=0.7, R=0.3) if ges else _p(S=0.95, R=0.05)
        if code == "CIP":
            return _p(S=0.15, I=0.05, R=0.8) if mbl or ges or strain.st == 235 else _p(S=0.8, I=0.07, R=0.13)
        if code == "COL":
            return _p(I=0.97, R=0.03)
    if o == "SA":
        mrsa, erm = "mecA" in g, "ermC" in g
        table = {
            "OXA": (_p(R=1), _p(S=1)),
            "FOX": (_p(R=1), _p(S=1)),
            "ERY": (_p(S=0.4, R=0.6), _p(S=0.85, R=0.15)),
            "CLI": (_p(S=0.6, R=0.4), _p(S=0.93, R=0.07)),
            "SXT": (_p(S=0.9, R=0.1), _p(S=0.95, R=0.05)),
            "RIF": (_p(S=0.88, R=0.12), _p(S=0.98, R=0.02)),
            "GEN": (_p(S=0.6, R=0.4) if strain.st == 239 else _p(S=0.85, R=0.15), _p(S=0.97, R=0.03)),
            "CIP": (_p(S=0.25, I=0.05, R=0.7), _p(S=0.9, R=0.1)),
            "VAN": (_p(S=1), _p(S=1)),  # no vanA-mediated VRSA in this population
            "LNZ": (_p(S=1), _p(S=1)),
        }
        weights = table[code][0 if mrsa else 1]
        if erm and code in {"ERY", "CLI"}:
            return _p(R=1) if code == "ERY" else _p(S=0.5, R=0.5)
        return weights
    if o == "EF":
        if code == "VAN":
            return _p(R=1) if "vanA" in g else _p(S=1)
        if code == "AMP":  # hospital-adapted clonal complex 17 is ampicillin resistant
            return _p(R=1) if "vanA" in g else _p(S=0.1, R=0.9)
        if code == "LNZ":
            return _p(S=0.98, I=0.02)
    raise KeyError(f"no phenotype rule for {o} / {code}")


def choose_mic(taxid: int, code: str, category: str, rng: random.Random) -> tuple[str, str]:
    """An MIC string on the panel's dilution range that CLSI reads as ``category``."""
    low, high = PANEL_RANGE[code]
    options = []
    for value in DILUTIONS:
        if value < low or value > high:
            continue
        qualifier = "<=" if value == low else ">=" if value == high else "="
        result = interpret(taxid, code, value, qualifier)
        if result == category:
            options.append((value, qualifier))
    if not options:
        raise ValueError(f"no dilution on the {code} panel reads {category}")
    # Susceptible isolates cluster at the bottom of the range, resistant ones at the top.
    if category == "S":
        weights = [2.0 ** -i for i in range(len(options))]
    elif category == "R":
        weights = [2.0 ** i for i in range(len(options))]
    else:
        weights = [1.0] * len(options)
    value, qualifier = rng.choices(options, weights=weights)[0]
    text = f"{'' if qualifier == '=' else qualifier}{value:g}"
    return text, category


def phenotype(strain: Strain, rng: random.Random, extra: tuple[str, ...] = ()) -> dict[str, tuple[str, str]]:
    """{drug code: (MIC string, category)} for the routine panel, cascades and extra tests."""
    taxid = ontology.ORGANISMS[SPECIES[strain.organism].lower()].ncbi_taxid
    results = {}
    for code in PANELS[strain.organism]:
        weights = category_weights(strain, code)
        category = rng.choices(list(weights), weights=list(weights.values()))[0]
        results[code] = choose_mic(taxid, code, category, rng)
    carbapenem_ns = any(results.get(c, ("", "S"))[1] != "S" for c in ("ETP", "MEM", "IPM"))
    cascade = CASCADE.get(strain.organism, []) if carbapenem_ns else []
    for code in [*cascade, *(c for c in extra if c not in cascade)]:
        weights = category_weights(strain, code)
        category = rng.choices(list(weights), weights=list(weights.values()))[0]
        results[code] = choose_mic(taxid, code, category, rng)
    return results


def lab_labels(organism: str, results: dict[str, tuple[str, str]]) -> list[str]:
    """Phenotypic flags a laboratory would append to the organism name."""
    cat = {code: category for code, (_, category) in results.items()}
    if organism in ENTEROBACTERALES:
        if any(cat.get(c) == "R" for c in ("ETP", "MEM", "IPM")):
            return ["CRE"]
        return ["ESBL"] if cat.get("CRO") == "R" else []
    if organism == "AB":
        return ["CRAB"] if "R" in (cat.get("MEM"), cat.get("IPM")) else []
    if organism == "PA":
        return ["CRPA"] if "R" in (cat.get("MEM"), cat.get("IPM")) else []
    if organism == "SA":
        return ["MRSA"] if cat.get("OXA") == "R" else []
    if organism == "EF":
        return ["VRE"] if cat.get("VAN") == "R" else []
    return []


# ----------------------------------------------------------------------------
# Clinical context
# ----------------------------------------------------------------------------

SPECIMENS = {
    "Adult ICU": {"Blood culture": 0.35, "Tracheal aspirate": 0.3, "Urine": 0.13, "Rectal swab (CPE screen)": 0.1, "Pus swab": 0.12},
    "Neonatal ICU": {"Blood culture": 0.72, "Cerebrospinal fluid": 0.05, "Tracheal aspirate": 0.08, "Rectal swab (CPE screen)": 0.15},
    "Medical": {"Urine": 0.42, "Blood culture": 0.38, "Sputum": 0.12, "Pus swab": 0.08},
    "Surgical": {"Pus swab": 0.4, "Blood culture": 0.25, "Urine": 0.2, "Tissue": 0.15},
    "Haematology-Oncology": {"Blood culture": 0.6, "Urine": 0.2, "Rectal swab (CPE screen)": 0.2},
    "Burns": {"Tissue": 0.45, "Pus swab": 0.3, "Blood culture": 0.25},
    "Paediatrics": {"Blood culture": 0.5, "Urine": 0.3, "Cerebrospinal fluid": 0.05, "Pus swab": 0.15},
}
TREATMENTS = {
    "Adult ICU": {"Meropenem": 0.33, "Piperacillin-tazobactam": 0.25, "Colistin": 0.1, "Vancomycin": 0.1, "Ceftriaxone": 0.1, "Amikacin": 0.05, "": 0.07},
    "Neonatal ICU": {"Ampicillin": 0.22, "Gentamicin": 0.2, "Meropenem": 0.3, "Vancomycin": 0.1, "Colistin": 0.05, "Amikacin": 0.05, "": 0.08},
    "Medical": {"Ceftriaxone": 0.45, "Amoxicillin-clavulanate": 0.25, "Ciprofloxacin": 0.08, "Piperacillin-tazobactam": 0.12, "": 0.1},
    "Surgical": {"Amoxicillin-clavulanate": 0.33, "Ceftriaxone": 0.22, "Piperacillin-tazobactam": 0.22, "Ertapenem": 0.13, "": 0.1},
    "Haematology-Oncology": {"Piperacillin-tazobactam": 0.42, "Meropenem": 0.33, "Vancomycin": 0.15, "Ceftazidime": 0.05, "": 0.05},
    "Burns": {"Piperacillin-tazobactam": 0.33, "Vancomycin": 0.22, "Meropenem": 0.22, "Cloxacillin": 0.15, "": 0.08},
    "Paediatrics": {"Ceftriaxone": 0.45, "Ampicillin": 0.25, "Gentamicin": 0.18, "": 0.12},
}


def pick(table: dict[str, float], rng: random.Random) -> str:
    return rng.choices(list(table), weights=list(table.values()))[0]


def age_for(ward: str, rng: random.Random) -> float:
    if ward == "Neonatal ICU":
        # Round down so a 28-day-old stays within the neonatal period.
        return math.floor(rng.randint(0, 28) / 365.25 * 1000) / 1000
    if ward == "Paediatrics":
        return round(rng.uniform(0.1, 12), 1)
    if ward == "Burns":
        return float(int(rng.triangular(1, 70, 30)))
    return float(int(rng.triangular(18, 88, 52)))


def at(day: date, rng: random.Random) -> datetime:
    return datetime(day.year, day.month, day.day, rng.randint(6, 22), rng.choice((0, 15, 30, 45)), tzinfo=SAST)


# ----------------------------------------------------------------------------
# Dataset assembly
# ----------------------------------------------------------------------------


@dataclass
class Isolate:
    sample_id: str
    collected: datetime
    ward: str
    specimen: str
    treatment: str
    strain: Strain
    results: dict[str, tuple[str, str]]
    sequenced: bool
    carriers_resolved: bool
    scenario: str | None


@dataclass
class Encounter:
    encounter_id: str
    facility: str
    admit_ward: str
    admitted: datetime
    discharged: datetime | None
    transfers: list[tuple[datetime, str]] = field(default_factory=list)
    isolates: list[Isolate] = field(default_factory=list)


@dataclass
class Patient:
    patient_id: str
    sex: str
    age_years: float
    encounters: list[Encounter] = field(default_factory=list)


class Builder:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.patients: list[Patient] = []
        self.scenarios: dict[str, dict] = {}
        self._ids: dict[str, set[int]] = {"PT": set(), "ENC": set(), "LAB": set()}

    def new_id(self, prefix: str, digits: int = 6) -> str:
        while True:
            n = self.rng.randrange(10 ** (digits - 1), 10**digits)
            if n not in self._ids[prefix]:
                self._ids[prefix].add(n)
                return f"{prefix}-{n}" if prefix != "LAB" else f"LAB25-{n}"

    def isolate(self, day: datetime, ward: str, strain: Strain, *, scenario: str | None = None,
                specimen: str | None = None, treatment: str | None = None, extra: tuple[str, ...] = ()) -> Isolate:
        rng = self.rng
        results = phenotype(strain, rng, extra)
        labels = lab_labels(strain.organism, results)
        if scenario:
            sequenced = True
        elif strain.organism in ENTEROBACTERALES | {"PA"} and any(results.get(c, ("", "S"))[1] != "S" for c in ("ETP", "MEM", "IPM")):
            sequenced = rng.random() < 0.9  # carbapenem-non-susceptible isolates referred for sequencing
        elif "CRAB" in labels:  # targeted ICU surveillance sequences most ICU CRAB
            sequenced = rng.random() < (0.6 if ward == "Adult ICU" else 0.3)
        elif "MRSA" in labels:
            sequenced = rng.random() < 0.5
        elif "VRE" in labels:
            sequenced = True
        else:
            sequenced = rng.random() < 0.08
        return Isolate(
            sample_id=self.new_id("LAB"),
            collected=day,
            ward=ward,
            specimen=specimen or pick(SPECIMENS[ward], rng),
            treatment=pick(TREATMENTS[ward], rng) if treatment is None else treatment,
            strain=strain,
            results=results,
            sequenced=sequenced,
            carriers_resolved=bool(scenario) or rng.random() < 0.6,
            scenario=scenario,
        )

    def admit(self, facility: str, ward: str, collected: datetime, *, pre_icu: bool = True) -> Encounter:
        rng = self.rng
        admitted = collected - timedelta(days=rng.randint(1, 12), hours=rng.randint(0, 10))
        admitted = max(admitted, datetime.combine(PERIOD_START - timedelta(days=14), datetime.min.time(), SAST))
        discharge_day = collected + timedelta(days=rng.randint(2, 30))
        discharged = discharge_day if discharge_day.date() <= PERIOD_END else None
        encounter = Encounter(self.new_id("ENC"), facility, ward, admitted, discharged)
        # Many ICU patients are admitted to a general ward first.
        if pre_icu and ward == "Adult ICU" and rng.random() < 0.35:
            encounter.admit_ward = rng.choice([w for w in FACILITIES[facility].wards if w in {"Medical", "Surgical"}])
            transfer = admitted + (collected - admitted) * rng.uniform(0.2, 0.7)
            encounter.transfers.append((transfer, ward))
        return encounter

    def new_patient(self, ward: str) -> Patient:
        sex = "M" if self.rng.random() < (0.55 if ward in {"Adult ICU", "Burns", "Surgical"} else 0.5) else "F"
        patient = Patient(self.new_id("PT"), sex, age_for(ward, self.rng))
        self.patients.append(patient)
        return patient

    def random_day(self, start: date = PERIOD_START, end: date = PERIOD_END) -> datetime:
        return at(start + timedelta(days=self.rng.randint(0, (end - start).days)), self.rng)

    # -- planted scenarios -------------------------------------------------

    def scenario(self, key: str, **manifest) -> None:
        self.scenarios[key] = manifest

    def outbreak(self, key: str, facility: str, ward: str, start: date, days: int, strains: list[Strain], *,
                 specimens: dict[str, float] | None = None, treatment_bias: dict[str, float] | None = None,
                 extra: tuple[str, ...] = ()) -> None:
        rng = self.rng
        offsets = sorted(rng.sample(range(days), len(strains)))
        for offset, strain in zip(offsets, strains):
            day = at(start + timedelta(days=offset), rng)
            patient = self.new_patient(ward)
            encounter = self.admit(facility, ward, day, pre_icu=False)
            treatment = pick(treatment_bias, rng) if treatment_bias else None
            specimen = pick(specimens, rng) if specimens else None
            encounter.isolates.append(self.isolate(day, ward, strain, scenario=key, specimen=specimen, treatment=treatment, extra=extra))
            patient.encounters.append(encounter)

    def build(self) -> None:
        rng = self.rng
        st307_oxa181 = ("blaCTX-M-15", "blaOXA-181")

        # S1: neonatal unit outbreak of OXA-181-producing K. pneumoniae ST307.
        self.outbreak("S1", "GAH", "Neonatal ICU", date(2025, 8, 4), 42, [Strain("KP", 307, st307_oxa181)] * 14,
                      specimens={"Blood culture": 0.8, "Rectal swab (CPE screen)": 0.2},
                      treatment_bias={"Meropenem": 0.6, "Ampicillin": 0.2, "Colistin": 0.2})
        self.scenario("S1", title="Neonatal ICU outbreak: OXA-181 K. pneumoniae ST307", facility="GAH", ward="GAH:Neonatal ICU",
                      period=["2025-08-04", "2025-09-15"], patients=14, expect={"cluster": {"ward": "GAH:Neonatal ICU", "sequence_type": "klebsiella:ST307", "gene": "blaOXA-181", "min_size": 14}})

        # S3: NDM-5 on an IncX3 plasmid spreading across three genera on one ward.
        ndm5 = [Strain("EC", 410, ("blaNDM-5",))] * 4 + [Strain("KP", 15, ("blaCTX-M-15", "blaNDM-5"))] * 3 + [Strain("ECL", 78, ("blaNDM-5",))] * 2
        rng.shuffle(ndm5)
        self.outbreak("S3", "KRH", "Surgical", date(2025, 10, 1), 50, ndm5,
                      treatment_bias={"Ertapenem": 0.3, "Piperacillin-tazobactam": 0.4, "Meropenem": 0.3})
        self.scenario("S3", title="Plasmid-mediated NDM-5 spread (IncX3) across E. coli, K. pneumoniae and E. cloacae", facility="KRH",
                      ward="KRH:Surgical", period=["2025-10-01", "2025-11-20"], patients=9,
                      expect={"hgt": {"gene": "blaNDM-5", "taxa_include": ["Enterobacter cloacae", "Escherichia coli", "Klebsiella pneumoniae"], "replicon": "Plasmid:IncX3"}})

        # S4: vanA E. faecium ST80 on a haematology-oncology unit.
        self.outbreak("S4", "WTH", "Haematology-Oncology", date(2025, 11, 3), 42, [Strain("EF", 80, ("vanA",))] * 8,
                      specimens={"Rectal swab (CPE screen)": 0.5, "Blood culture": 0.5},
                      treatment_bias={"Vancomycin": 0.5, "Piperacillin-tazobactam": 0.3, "Meropenem": 0.2})
        self.scenario("S4", title="VRE (vanA) E. faecium ST80 on haematology-oncology", facility="WTH", ward="WTH:Haematology-Oncology",
                      period=["2025-11-03", "2025-12-15"], patients=8,
                      expect={"cluster": {"ward": "WTH:Haematology-Oncology", "sequence_type": "efaecium:ST80", "gene": "vanA", "min_size": 8}})

        # S5: referral importation from a district hospital into the GAH adult ICU,
        # followed by onward ICU transmission.
        offsets = sorted(rng.sample(range(40), 6))
        for offset in offsets:
            referral = at(date(2025, 9, 1) + timedelta(days=offset), rng)
            patient = self.new_patient("Adult ICU")
            district = Encounter(self.new_id("ENC"), "GDH", "Medical", referral - timedelta(days=rng.randint(2, 6)), referral)
            tertiary = Encounter(self.new_id("ENC"), "GAH", "Adult ICU", referral + timedelta(hours=rng.randint(2, 8)), None)
            day = tertiary.admitted + timedelta(days=rng.randint(1, 3))
            tertiary.discharged = day + timedelta(days=rng.randint(5, 25))
            tertiary.isolates.append(self.isolate(day, "Adult ICU", Strain("KP", 307, st307_oxa181), scenario="S5",
                                                  specimen="Rectal swab (CPE screen)", treatment="Meropenem"))
            patient.encounters += [district, tertiary]
        self.outbreak("S5", "GAH", "Adult ICU", date(2025, 9, 20), 35, [Strain("KP", 307, st307_oxa181)] * 4,
                      treatment_bias={"Meropenem": 0.5, "Colistin": 0.3, "Piperacillin-tazobactam": 0.2})
        self.scenario("S5", title="Referral importation of OXA-181 K. pneumoniae ST307 from a district hospital into an adult ICU",
                      facility="GDH -> GAH", ward="GAH:Adult ICU", period=["2025-09-01", "2025-10-25"], patients=10,
                      expect={"transfer_edge": {"wards": ["GAH:Adult ICU", "GDH:Medical"], "min_transfers": 6},
                              "cluster": {"ward": "GAH:Adult ICU", "sequence_type": "klebsiella:ST307", "gene": "blaOXA-181", "min_size": 6}})

        # S6: MRSA ST612 cluster in the burns unit.
        self.outbreak("S6", "GAH", "Burns", date(2025, 7, 7), 40, [Strain("SA", 612, ("mecA",))] * 6,
                      treatment_bias={"Cloxacillin": 0.4, "Vancomycin": 0.4, "Piperacillin-tazobactam": 0.2})
        self.scenario("S6", title="MRSA ST612 cluster in a burns unit", facility="GAH", ward="GAH:Burns", period=["2025-07-07", "2025-08-15"],
                      patients=6, expect={"cluster": {"ward": "GAH:Burns", "sequence_type": "saureus:ST612", "gene": "mecA", "min_size": 6}})

        # Sentinel events: rare, alert-worthy single cases.
        self.outbreak("S7", "WTH", "Adult ICU", date(2025, 10, 14), 1, [Strain("KP", 258, ("blaKPC-2",))],
                      treatment_bias={"Meropenem": 1.0})
        self.scenario("S7", title="Sentinel: KPC-2 K. pneumoniae ST258 (uncommon in South Africa; possible importation)", facility="WTH",
                      ward="WTH:Adult ICU", period=["2025-10-14", "2025-10-14"], patients=1, expect={"gene_present": "blaKPC-2"})
        # Colistin broth microdilution from the reference laboratory accompanies the referral.
        self.outbreak("S8", "KRH", "Medical", date(2025, 11, 26), 1, [Strain("EC", 10, ("mcr-1.1",))], treatment_bias={"Ceftriaxone": 1.0},
                      extra=("COL",))
        self.scenario("S8", title="Sentinel: plasmid-mediated colistin resistance (mcr-1) in E. coli", facility="KRH", ward="KRH:Medical",
                      period=["2025-11-26", "2025-11-26"], patients=1, expect={"gene_present": "mcr-1.1"})

        # S2 and the background: endemic hospital flora, including CRAB in ICUs.
        self.scenario("S2", title="Endemic carbapenem-resistant A. baumannii (OXA-23, IC2/ST2) in adult ICUs", facility="all",
                      ward="*:Adult ICU", period=["2025-07-01", "2025-12-31"], patients=None,
                      expect={"cluster": {"ward_suffix": ":Adult ICU", "sequence_type": "abaumannii_2:ST2", "gene": "blaOXA-23", "min_size": 2}})
        while len(self.patients) < TOTAL_PATIENTS:
            facility = pick(FACILITY_SHARE, rng)
            ward = pick(FACILITIES[facility].wards, rng)
            organism = pick(ORGANISMS_BY_WARD[ward], rng)
            strain = draw_background_strain(organism, rng)
            day = self.random_day()
            patient = self.new_patient(ward)
            encounter = self.admit(facility, ward, day)
            encounter.isolates.append(self.isolate(day, ward, strain))
            if rng.random() < 0.15:  # repeat culture later in the same admission
                later = day + timedelta(days=rng.randint(3, 14))
                if later.date() <= PERIOD_END:
                    repeat = strain if rng.random() < 0.6 else draw_background_strain(pick(ORGANISMS_BY_WARD[ward], rng), rng)
                    encounter.isolates.append(self.isolate(later, ward, repeat))
                    if encounter.discharged and encounter.discharged < later:
                        encounter.discharged = later + timedelta(days=rng.randint(1, 10))
            patient.encounters.append(encounter)


# ----------------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------------

CLINICAL_COLUMNS = ["PatientID", "EncounterID", "SampleID", "Date", "Facility", "FacilityName", "Province", "Ward", "Sex", "AgeYears",
                    "AdmitDate", "DischargeDate", "Specimen", "Treatment", "Organism", "Antibiotic", "MIC", "Result", "Guideline"]
GENOMIC_COLUMNS = ["PatientID", "SampleID", "Organism", "Strain_Subtype", "GeneDetected", "Mechanism", "MGE_Type", "MGE_Replicon"]
MOVEMENT_COLUMNS = ["PatientID", "EncounterID", "EventType", "Facility", "FacilityName", "Province", "Ward", "Timestamp"]


def iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def write(builder: Builder, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    clinical, genomic, movements = [], [], []
    for patient in builder.patients:
        for enc in patient.encounters:
            fac = FACILITIES[enc.facility]
            place = {"Facility": fac.code, "FacilityName": fac.name, "Province": fac.province}
            movements.append({"PatientID": patient.patient_id, "EncounterID": enc.encounter_id, "EventType": "Admission",
                              **place, "Ward": enc.admit_ward, "Timestamp": iso(enc.admitted)})
            for when, ward in enc.transfers:
                movements.append({"PatientID": patient.patient_id, "EncounterID": enc.encounter_id, "EventType": "Transfer",
                                  **place, "Ward": ward, "Timestamp": iso(when)})
            for iso_ in enc.isolates:
                species = SPECIES[iso_.strain.organism]
                labels = lab_labels(iso_.strain.organism, iso_.results)
                organism = f"{species} ({', '.join(labels)})" if labels else species
                for code, (mic, category) in iso_.results.items():
                    clinical.append({
                        "PatientID": patient.patient_id, "EncounterID": enc.encounter_id, "SampleID": iso_.sample_id,
                        "Date": iso(iso_.collected), **place, "Ward": iso_.ward, "Sex": patient.sex, "AgeYears": f"{patient.age_years:g}",
                        "AdmitDate": iso(enc.admitted), "DischargeDate": iso(enc.discharged), "Specimen": iso_.specimen,
                        "Treatment": iso_.treatment, "Organism": organism, "Antibiotic": CODE_TO_DRUG[code].name,
                        "MIC": mic, "Result": category, "Guideline": BREAKPOINT_SOURCE,
                    })
                if iso_.sequenced:
                    base = {"PatientID": patient.patient_id, "SampleID": iso_.sample_id, "Organism": species,
                            "Strain_Subtype": f"ST{iso_.strain.st}"}
                    if not iso_.strain.genes:
                        genomic.append({**base, "GeneDetected": "None", "Mechanism": "Wild type", "MGE_Type": "", "MGE_Replicon": ""})
                    for symbol in iso_.strain.genes:
                        gene = ontology.resolve_gene(symbol)
                        carrier = CARRIERS.get(symbol) if iso_.carriers_resolved else None
                        genomic.append({**base, "GeneDetected": gene.symbol, "Mechanism": gene.mechanism,
                                        "MGE_Type": carrier[0] if carrier else "", "MGE_Replicon": carrier[1] if carrier else ""})
    clinical.sort(key=lambda r: (r["Date"], r["SampleID"], r["Antibiotic"]))
    movements.sort(key=lambda r: (r["Timestamp"], r["PatientID"]))
    for name, columns, rows in (("clinical.csv", CLINICAL_COLUMNS, clinical), ("genomic.csv", GENOMIC_COLUMNS, genomic),
                                ("movements.csv", MOVEMENT_COLUMNS, movements)):
        with open(out / name, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    (out / "scenarios.json").write_text(json.dumps(builder.scenarios, indent=2) + "\n", encoding="utf-8")
    return {"patients": len(builder.patients), "isolates": len({r["SampleID"] for r in clinical}),
            "clinical_rows": len(clinical), "genomic_rows": len(genomic), "movements": len(movements)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "demo")
    parser.add_argument("--seed", type=int, default=2025)
    args = parser.parse_args()
    builder = Builder(args.seed)
    builder.build()
    print(json.dumps(write(builder, args.out), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
