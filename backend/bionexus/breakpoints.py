"""CLSI MIC and disk-diffusion breakpoints and S/I/SDD/R interpretation.

The table is a subset of CLSI M100 (2026, 36th edition) as distributed in the
``clinical_breakpoints`` dataset of the AMR package
(github.com/msberends/AMR), restricted to systemic (non-urinary) human MIC
breakpoints for the organism groups and drugs in :mod:`bionexus.ontology`.
``tools/verify_vocabulary.py`` re-checks every entry against that source.

Semantics follow CLSI: susceptible if MIC <= S, resistant if MIC >= R,
otherwise intermediate, or susceptible-dose-dependent (SDD) where CLSI
defines that category. For disk diffusion the direction reverses:
susceptible if the zone diameter >= S, resistant if <= R. CLSI gives no
disk breakpoint where disk testing is unreliable (colistin, vancomycin in
staphylococci), so those agents need an MIC method. An S breakpoint of 0.0001 means CLSI defines no
susceptible category (e.g. colistin), so low MICs read as intermediate.
"""

from __future__ import annotations

from .models import MicQualifier

BREAKPOINT_SOURCE = "CLSI 2026"

# (AMR-package organism group, AMR-package drug code) -> (S <=, R >=), mg/L
BREAKPOINTS: dict[tuple[str, str], tuple[float, float]] = {
    ("B_ACNTB_BMNN-C", "COL"): (0.0001, 4),
    ("B_ACNTB", "AMK"): (8, 32),
    ("B_ACNTB", "CAZ"): (8, 32),
    ("B_ACNTB", "CIP"): (1, 4),
    ("B_ACNTB", "CRO"): (8, 64),
    ("B_ACNTB", "FEP"): (8, 32),
    ("B_ACNTB", "GEN"): (2, 8),
    ("B_ACNTB", "IPM"): (2, 8),
    ("B_ACNTB", "MEM"): (2, 8),
    ("B_ACNTB", "SXT"): (2, 4),
    ("B_ACNTB", "TZP"): (16, 128),
    ("B_ENTRC", "AMP"): (8, 16),
    ("B_ENTRC", "ERY"): (0.5, 8),
    ("B_ENTRC", "LNZ"): (2, 8),
    ("B_ENTRC", "RIF"): (1, 4),
    ("B_ENTRC", "VAN"): (4, 32),
    ("B_PSDMN_AERG", "CAZ"): (8, 32),
    ("B_PSDMN_AERG", "CIP"): (0.5, 2),
    ("B_PSDMN_AERG", "COL"): (0.0001, 4),
    ("B_PSDMN_AERG", "CZA"): (8, 16),
    ("B_PSDMN_AERG", "FEP"): (8, 32),
    ("B_PSDMN_AERG", "IPM"): (2, 8),
    ("B_PSDMN_AERG", "MEM"): (2, 8),
    ("B_PSDMN_AERG", "TZP"): (16, 64),
    ("B_STPHY", "CIP"): (1, 4),
    ("B_STPHY", "CLI"): (0.5, 4),
    ("B_STPHY", "ERY"): (0.5, 8),
    ("B_STPHY", "GEN"): (4, 16),
    ("B_STPHY", "LNZ"): (4, 8),
    ("B_STPHY", "OXA"): (0.5, 1),
    ("B_STPHY", "RIF"): (1, 4),
    ("B_STPHY", "SXT"): (2, 4),
    ("B_STPHY", "VAN"): (4, 32),
    ("B_STPHY_AURS", "FOX"): (4, 8),
    ("B_STPHY_AURS", "OXA"): (2, 4),
    ("B_STPHY_AURS", "VAN"): (2, 16),
    ("B_[ORD]_ENTRBCTR", "AMC"): (8, 32),
    ("B_[ORD]_ENTRBCTR", "AMK"): (4, 16),
    ("B_[ORD]_ENTRBCTR", "AMP"): (8, 32),
    ("B_[ORD]_ENTRBCTR", "CAZ"): (4, 16),
    ("B_[ORD]_ENTRBCTR", "CIP"): (0.25, 1),
    ("B_[ORD]_ENTRBCTR", "COL"): (0.0001, 4),
    ("B_[ORD]_ENTRBCTR", "CRO"): (1, 4),
    ("B_[ORD]_ENTRBCTR", "CZA"): (8, 16),
    ("B_[ORD]_ENTRBCTR", "ETP"): (0.5, 2),
    ("B_[ORD]_ENTRBCTR", "FEP"): (2, 16),
    ("B_[ORD]_ENTRBCTR", "FOX"): (8, 32),
    ("B_[ORD]_ENTRBCTR", "GEN"): (2, 8),
    ("B_[ORD]_ENTRBCTR", "IPM"): (1, 4),
    ("B_[ORD]_ENTRBCTR", "MEM"): (1, 4),
    ("B_[ORD]_ENTRBCTR", "SXT"): (2, 4),
    ("B_[ORD]_ENTRBCTR", "TGC"): (2, 8),
    ("B_[ORD]_ENTRBCTR", "TZP"): (8, 32),
}

SDD_BREAKPOINTS = frozenset({("B_[ORD]_ENTRBCTR", "FEP"), ("B_[ORD]_ENTRBCTR", "TZP")})

# (group, drug) -> (S if zone >= , R if zone <= , disk content)
DISK_BREAKPOINTS: dict[tuple[str, str], tuple[float, float, str]] = {
    ("B_ACNTB", "AMK"): (20, 16, "30 mcg"),
    ("B_ACNTB", "CAZ"): (18, 14, "30 mcg"),
    ("B_ACNTB", "CIP"): (21, 15, "5 mcg"),
    ("B_ACNTB", "CRO"): (21, 13, "30 mcg"),
    ("B_ACNTB", "FEP"): (18, 14, "30 mcg"),
    ("B_ACNTB", "GEN"): (19, 13, "10 mcg"),
    ("B_ACNTB", "IPM"): (22, 18, "10 mcg"),
    ("B_ACNTB", "MEM"): (18, 14, "10 mcg"),
    ("B_ACNTB", "SXT"): (16, 10, "1.25/23.75 mcg"),
    ("B_ACNTB", "TZP"): (21, 17, "100/10 mcg"),
    ("B_ENTRC", "AMP"): (17, 16, "10 mcg"),
    ("B_ENTRC", "ERY"): (23, 13, "15 mcg"),
    ("B_ENTRC", "LNZ"): (23, 20, "30 mcg"),
    ("B_ENTRC", "RIF"): (20, 16, "5 mcg"),
    ("B_ENTRC", "VAN"): (17, 14, "30 mcg"),
    ("B_PSDMN_AERG", "CAZ"): (18, 14, "30 mcg"),
    ("B_PSDMN_AERG", "CIP"): (25, 18, "5 mcg"),
    ("B_PSDMN_AERG", "CZA"): (21, 20, "30 mcg"),
    ("B_PSDMN_AERG", "FEP"): (18, 14, "30 mcg"),
    ("B_PSDMN_AERG", "IPM"): (19, 15, "10 mcg"),
    ("B_PSDMN_AERG", "MEM"): (19, 15, "10 mcg"),
    ("B_PSDMN_AERG", "TZP"): (22, 17, "100/10 mcg"),
    ("B_STPHY", "CIP"): (21, 15, "5 mcg"),
    ("B_STPHY", "CLI"): (21, 14, "2 mcg"),
    ("B_STPHY", "ERY"): (23, 13, "15 mcg"),
    ("B_STPHY", "FOX"): (25, 24, "30 mcg"),
    ("B_STPHY", "GEN"): (15, 12, "10 mcg"),
    ("B_STPHY", "LNZ"): (26, 22, "30 mcg"),
    ("B_STPHY", "RIF"): (20, 16, "5 mcg"),
    ("B_STPHY", "SXT"): (16, 10, "1.25/23.75 mcg"),
    ("B_STPHY_AURS", "FOX"): (22, 21, "30 mcg"),
    ("B_[ORD]_ENTRBCTR", "AMC"): (18, 13, "20/10 mcg"),
    ("B_[ORD]_ENTRBCTR", "AMK"): (20, 16, "30 mcg"),
    ("B_[ORD]_ENTRBCTR", "AMP"): (17, 13, "10 mcg"),
    ("B_[ORD]_ENTRBCTR", "CAZ"): (21, 17, "30 mcg"),
    ("B_[ORD]_ENTRBCTR", "CIP"): (26, 21, "5 mcg"),
    ("B_[ORD]_ENTRBCTR", "CRO"): (23, 19, "30 mcg"),
    ("B_[ORD]_ENTRBCTR", "CZA"): (21, 20, "30/20 mcg"),
    ("B_[ORD]_ENTRBCTR", "ETP"): (22, 18, "10 mcg"),
    ("B_[ORD]_ENTRBCTR", "FEP"): (25, 18, "30 mcg"),
    ("B_[ORD]_ENTRBCTR", "FOX"): (18, 14, "30 mcg"),
    ("B_[ORD]_ENTRBCTR", "GEN"): (18, 14, "10 mcg"),
    ("B_[ORD]_ENTRBCTR", "IPM"): (23, 19, "10 mcg"),
    ("B_[ORD]_ENTRBCTR", "MEM"): (23, 19, "10 mcg"),
    ("B_[ORD]_ENTRBCTR", "SXT"): (16, 10, "1.25/23.75 mcg"),
    ("B_[ORD]_ENTRBCTR", "TGC"): (19, 14, "15 mcg"),
    ("B_[ORD]_ENTRBCTR", "TZP"): (25, 20, "100/10 mcg"),
}

SDD_DISK_BREAKPOINTS = frozenset({("B_[ORD]_ENTRBCTR", "FEP"), ("B_[ORD]_ENTRBCTR", "TZP")})

# Breakpoint groups to try for each NCBI taxid, most specific first.
GROUPS_BY_TAXID: dict[int, tuple[str, ...]] = {
    573: ("B_[ORD]_ENTRBCTR",),  # Klebsiella pneumoniae
    562: ("B_[ORD]_ENTRBCTR",),  # Escherichia coli
    550: ("B_[ORD]_ENTRBCTR",),  # Enterobacter cloacae
    287: ("B_PSDMN_AERG",),  # Pseudomonas aeruginosa
    470: ("B_ACNTB_BMNN-C", "B_ACNTB"),  # Acinetobacter baumannii (complex, then genus)
    1280: ("B_STPHY_AURS", "B_STPHY"),  # Staphylococcus aureus
    1352: ("B_ENTRC",),  # Enterococcus faecium
}


def breakpoint_for(ncbi_taxid: int, amr_code: str) -> tuple[str, float, float] | None:
    for group in GROUPS_BY_TAXID.get(ncbi_taxid, ()):
        found = BREAKPOINTS.get((group, amr_code))
        if found:
            return group, *found
    return None


def effective_mic(mic: float, qualifier: MicQualifier | None) -> float:
    """Map a qualified MIC onto the dilution series for interpretation.

    ``>x`` means at least the next doubling dilution, ``<x`` at most half.
    """
    if qualifier == ">":
        return mic * 2
    if qualifier == "<":
        return mic / 2
    return mic


def interpret(ncbi_taxid: int, amr_code: str, mic: float, qualifier: MicQualifier | None = None) -> str | None:
    """S, I, SDD or R for an MIC, or None when CLSI gives no breakpoint."""
    found = breakpoint_for(ncbi_taxid, amr_code)
    if found is None:
        return None
    group, susceptible, resistant = found
    value = effective_mic(mic, qualifier)
    if value <= susceptible:
        return "S"
    if value >= resistant:
        return "R"
    return "SDD" if (group, amr_code) in SDD_BREAKPOINTS else "I"


def disk_breakpoint_for(ncbi_taxid: int, amr_code: str) -> tuple[str, float, float, str] | None:
    for group in GROUPS_BY_TAXID.get(ncbi_taxid, ()):
        found = DISK_BREAKPOINTS.get((group, amr_code))
        if found:
            return group, *found
    return None


def interpret_disk(ncbi_taxid: int, amr_code: str, zone_mm: float) -> str | None:
    """S, I, SDD or R for a zone diameter, or None without a CLSI disk breakpoint."""
    found = disk_breakpoint_for(ncbi_taxid, amr_code)
    if found is None:
        return None
    group, susceptible, resistant, _ = found
    if zone_mm >= susceptible:
        return "S"
    if zone_mm <= resistant:
        return "R"
    return "SDD" if (group, amr_code) in SDD_DISK_BREAKPOINTS else "I"
