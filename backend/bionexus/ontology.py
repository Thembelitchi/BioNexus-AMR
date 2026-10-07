"""Controlled vocabularies used to ground raw laboratory strings.

Every free-text value that reaches the graph is resolved here first. Unknown
values are rejected at validation time rather than silently creating new
nodes, so the vocabulary below is the single place to extend coverage.

Provenance of identifiers
-------------------------
Each identifier below was checked against the source named here. Check any
new entry the same way before adding it.

* Gene accessions (``ARO:``): every entry was resolved by label in CARD's
  ``aro.owl`` (github.com/arpcard/aro).
* ATC codes: every entry matches the WHO-ATC-derived ``antimicrobials``
  table of the AMR package (github.com/msberends/AMR).
* Species names and genera: all are "accepted" names in the LPSN-based
  ``microorganisms`` table of the same package.
* NCBI Taxonomy IDs: 562 (E. coli) and 287 (P. aeruginosa) match
  NCBI-derived GenBank/UniProt records in Biopython's test data; 1280
  (S. aureus) matches PDB entry 5I55. 573 (K. pneumoniae) is the standard
  value but could not be checked against an NCBI-derived source when this
  was written; confirm at https://www.ncbi.nlm.nih.gov/taxonomy.
* MLST scheme names and STs 5, 8, 11, 258, 111, 235 exist in the PubMLST
  profiles shipped with the ``mlst`` tool (Bioconda). USA300 -> ST8 (CC8)
  is stated in the Staphscope lineage table; USA100 -> ST5 rests on USA100
  being the CC5 "New York/Japan" clone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Organisms (NCBI Taxonomy)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OrganismRef:
    ncbi_taxid: int
    species: str
    genus: str
    mlst_scheme: str | None = None


ORGANISMS: dict[str, OrganismRef] = {
    ref.species.lower(): ref
    for ref in (
        OrganismRef(1280, "Staphylococcus aureus", "Staphylococcus", "saureus"),
        OrganismRef(573, "Klebsiella pneumoniae", "Klebsiella", "kpneumoniae"),
        OrganismRef(287, "Pseudomonas aeruginosa", "Pseudomonas", "paeruginosa"),
        # Achtman scheme: the PubMLST "ecoli" scheme is Pasteur, with different ST numbers.
        OrganismRef(562, "Escherichia coli", "Escherichia", "ecoli_achtman_4"),
    )
}

# Phenotypic shorthand that labs append to organism names. These describe the
# isolate's resistance profile, never the taxon, so they are split off.
PHENOTYPE_LABELS = frozenset({"MRSA", "MSSA", "VRSA", "VRE", "CRE", "CPE", "CRAB", "CRPA", "ESBL", "MDR", "XDR", "PDR"})

_ORGANISM_RE = re.compile(r"^\s*(?P<name>[A-Za-z]+\s+[a-z]+)\s*(?:\((?P<labels>[^)]*)\))?\s*$")


def resolve_organism(raw: str) -> tuple[OrganismRef, list[str]]:
    """Split ``"Klebsiella pneumoniae (CRE)"`` into a taxon and phenotype labels."""
    match = _ORGANISM_RE.match(raw or "")
    if not match:
        raise ValueError(f"unparseable organism name {raw!r}")
    ref = ORGANISMS.get(" ".join(match["name"].split()).lower())
    if ref is None:
        raise ValueError(f"organism {match['name']!r} is not in the taxonomy vocabulary")
    labels = [label.strip().upper() for label in (match["labels"] or "").replace("/", ",").split(",") if label.strip()]
    unknown = [label for label in labels if label not in PHENOTYPE_LABELS]
    if unknown:
        raise ValueError(f"unrecognised phenotype label(s) {unknown} in organism {raw!r}")
    return ref, labels


# --------------------------------------------------------------------------
# Antimicrobials (WHO ATC)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AntibioticRef:
    atc_code: str
    name: str


ATC_PATTERN = re.compile(r"^[A-V]\d{2}[A-Z]{2}\d{2}$")

_ANTIBIOTICS = (
    AntibioticRef("J01XA01", "Vancomycin"),
    AntibioticRef("J01XB01", "Colistin"),
    AntibioticRef("J01DD02", "Ceftazidime"),
    AntibioticRef("J01DD52", "Ceftazidime-avibactam"),
    AntibioticRef("J01DH02", "Meropenem"),
    AntibioticRef("J01CF04", "Oxacillin"),
    AntibioticRef("J01MA02", "Ciprofloxacin"),
    AntibioticRef("J01XX08", "Linezolid"),
)
ANTIBIOTICS: dict[str, AntibioticRef] = {ref.name.lower(): ref for ref in _ANTIBIOTICS}
ANTIBIOTICS.update({"ceftazidime-avi": ANTIBIOTICS["ceftazidime-avibactam"], "polymyxin e": ANTIBIOTICS["colistin"]})


def resolve_antibiotic(raw: str) -> AntibioticRef:
    ref = ANTIBIOTICS.get((raw or "").strip().lower())
    if ref is None:
        raise ValueError(f"antibiotic {raw!r} is not in the ATC vocabulary")
    return ref


# --------------------------------------------------------------------------
# Resistance determinants (CARD ARO)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneRef:
    aro_id: str
    name: str
    symbol: str
    mechanism: str
    # False for chromosomal mutations (e.g. porin loss), which cannot move
    # between organisms and are excluded from horizontal-transfer analysis.
    acquired: bool = True
    aliases: tuple[str, ...] = field(default=())


ARO_PATTERN = re.compile(r"^ARO:\d{7}$")

_GENES = (
    GeneRef("ARO:3000617", "mecA", "mecA", "Antibiotic target replacement (PBP2a)"),
    GeneRef("ARO:3000010", "vanA", "vanA", "Antibiotic target alteration (D-Ala-D-Lac)"),
    GeneRef("ARO:3000250", "ErmC", "ermC", "Antibiotic target alteration (23S rRNA methylation)"),
    GeneRef("ARO:3000589", "NDM-1", "blaNDM-1", "Antibiotic inactivation (metallo-beta-lactamase)"),
    GeneRef("ARO:3002313", "KPC-3", "blaKPC-3", "Antibiotic inactivation (serine carbapenemase)"),
    GeneRef("ARO:3001782", "OXA-48", "blaOXA-48", "Antibiotic inactivation (class D carbapenemase)"),
    GeneRef("ARO:3002272", "VIM-2", "blaVIM-2", "Antibiotic inactivation (metallo-beta-lactamase)"),
    GeneRef(
        "ARO:3003686",
        "Pseudomonas aeruginosa oprD with mutation conferring resistance to imipenem",
        "oprD",
        "Reduced permeability (OprD porin loss)",
        acquired=False,
        aliases=("oprd-loss", "oprd loss", "oprd"),
    ),
)
GENES: dict[str, GeneRef] = {}
for _gene in _GENES:
    for _key in (_gene.name, _gene.symbol, *_gene.aliases):
        GENES[_key.lower()] = _gene

# Values the genomic pipeline emits when no acquired determinant was found.
WILD_TYPE_TOKENS = frozenset({"", "none", "wild type", "wildtype", "wt", "not detected", "n/a", "na", "-"})


def is_wild_type(raw: str | None) -> bool:
    return (raw or "").strip().lower() in WILD_TYPE_TOKENS


def resolve_gene(raw: str) -> GeneRef:
    ref = GENES.get((raw or "").strip().lower())
    if ref is None:
        raise ValueError(f"gene {raw!r} is not mapped to a CARD ARO accession")
    return ref


# --------------------------------------------------------------------------
# Strain typing (MLST)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SequenceTypeRef:
    scheme: str
    st_number: int
    clone_designation: str | None = None

    @property
    def key(self) -> str:
        return f"{self.scheme}:ST{self.st_number}"


# PFGE pulsotypes are not sequence types; map the well-characterised US MRSA
# clones to their dominant MLST lineage and keep the original label.
_CLONE_TO_ST = {
    ("saureus", "USA100"): 5,
    ("saureus", "USA300"): 8,
}
_ST_RE = re.compile(r"^\s*ST[-\s]?(\d+)\s*$", re.IGNORECASE)


def resolve_sequence_type(raw: str | None, organism: OrganismRef) -> SequenceTypeRef | None:
    if raw is None or not raw.strip() or raw.strip().lower() in {"unknown", "nt", "none"}:
        return None
    if organism.mlst_scheme is None:
        raise ValueError(f"no MLST scheme configured for {organism.species}")
    match = _ST_RE.match(raw)
    if match:
        return SequenceTypeRef(organism.mlst_scheme, int(match[1]))
    clone = raw.strip().upper()
    st = _CLONE_TO_ST.get((organism.mlst_scheme, clone))
    if st is None:
        raise ValueError(f"strain subtype {raw!r} is neither an MLST ST nor a known clone for {organism.species}")
    return SequenceTypeRef(organism.mlst_scheme, st, clone)


# --------------------------------------------------------------------------
# Mobile genetic elements
# --------------------------------------------------------------------------

MGE_TYPES = {"plasmid": "Plasmid", "integron": "Integron", "transposon": "Transposon"}


def resolve_mge_type(raw: str) -> str:
    value = MGE_TYPES.get((raw or "").strip().lower())
    if value is None:
        raise ValueError(f"mobile element type {raw!r} must be one of {sorted(MGE_TYPES.values())}")
    return value
