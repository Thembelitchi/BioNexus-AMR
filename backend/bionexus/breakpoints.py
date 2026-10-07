"""CLSI MIC breakpoints and S/I/SDD/R interpretation.

The table is a subset of CLSI M100 (2025 edition) as distributed in the
``clinical_breakpoints`` dataset of the AMR package
(github.com/msberends/AMR), restricted to systemic (non-urinary) human MIC
breakpoints for the organism groups and drugs in :mod:`bionexus.ontology`.
``tools/verify_vocabulary.py`` re-checks every entry against that source.

Semantics follow CLSI: susceptible if MIC <= S, resistant if MIC >= R,
otherwise intermediate, or susceptible-dose-dependent (SDD) where CLSI
defines that category. An S breakpoint of 0.0001 means CLSI defines no
susceptible category (e.g. colistin), so low MICs read as intermediate.
"""

from __future__ import annotations

from .models import MicQualifier

BREAKPOINT_SOURCE = "CLSI 2025"

# (AMR-package organism group, AMR-package drug code) -> (S <=, R >=), mg/L
BREAKPOINTS: dict[tuple[str, str], tuple[float, float]] = {
    ("B_ACNTB_BMNN-C", "COL"): (0.0001, 4),
    ("B_ACNTB", "AMK"): (16, 64),
    ("B_ACNTB", "CAZ"): (8, 32),
    ("B_ACNTB", "CIP"): (1, 4),
    ("B_ACNTB", "CRO"): (8, 64),
    ("B_ACNTB", "FEP"): (8, 32),
    ("B_ACNTB", "GEN"): (4, 16),
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
