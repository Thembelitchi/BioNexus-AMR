"""Controlled vocabularies used to ground raw laboratory strings.

Every free-text value that reaches the graph is resolved here first. Unknown
values are rejected at validation time rather than silently creating new
nodes, so the vocabulary below is the single place to extend coverage.

Provenance of identifiers
-------------------------
Each identifier below was checked against the source named here.
``tools/verify_vocabulary.py`` repeats every check; run it after any change.

* Gene accessions (``ARO:``): every entry was resolved by label in CARD's
  ``aro.owl`` (github.com/arpcard/aro).
* ATC codes: every entry matches the WHO-ATC-derived ``antimicrobials``
  table of the AMR package (github.com/msberends/AMR).
* Species names and genera: all are "accepted" names in the LPSN-based
  ``microorganisms`` table of the same package.
* NCBI Taxonomy IDs: every entry matches NCBI's own taxdb name index
  (published in NCBI's BLAST database bucket on AWS).
* CLSI breakpoints (``bionexus.breakpoints``): every entry matches the AMR
  package's CLSI 2025 table.
* MLST scheme names, and every ST a dataset uses, exist in the PubMLST
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
    # Scheme identifier as emitted by the `mlst` tool (PubMLST schemes).
    mlst_scheme: str | None = None


ORGANISMS: dict[str, OrganismRef] = {
    ref.species.lower(): ref
    for ref in (
        OrganismRef(1280, "Staphylococcus aureus", "Staphylococcus", "saureus"),
        OrganismRef(573, "Klebsiella pneumoniae", "Klebsiella", "klebsiella"),
        OrganismRef(287, "Pseudomonas aeruginosa", "Pseudomonas", "paeruginosa"),
        # Achtman scheme: the PubMLST "ecoli" scheme is Pasteur, with different ST numbers.
        OrganismRef(562, "Escherichia coli", "Escherichia", "ecoli_achtman_4"),
        # Pasteur scheme, in which international clone II is ST2.
        OrganismRef(470, "Acinetobacter baumannii", "Acinetobacter", "abaumannii_2"),
        OrganismRef(1352, "Enterococcus faecium", "Enterococcus", "efaecium"),
        OrganismRef(550, "Enterobacter cloacae", "Enterobacter", "ecloacae"),
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
    # Antimicrobial code in the AMR package, used to look up breakpoints.
    amr_code: str
    aliases: tuple[str, ...] = field(default=())
    # WHO AWaRe group, filled in below from AWARE.
    aware: str | None = None


ATC_PATTERN = re.compile(r"^[A-V]\d{2}[A-Z]{2}\d{2}$")

_ANTIBIOTICS = (
    AntibioticRef("J01CA01", "Ampicillin", "AMP"),
    AntibioticRef("J01CR02", "Amoxicillin-clavulanate", "AMC", ("amoxicillin/clavulanic acid", "co-amoxiclav")),
    AntibioticRef("J01CR05", "Piperacillin-tazobactam", "TZP", ("piperacillin/tazobactam",)),
    AntibioticRef("J01CF02", "Cloxacillin", "CLO"),
    AntibioticRef("J01CF04", "Oxacillin", "OXA"),
    AntibioticRef("J01DC01", "Cefoxitin", "FOX"),
    AntibioticRef("J01DD04", "Ceftriaxone", "CRO"),
    AntibioticRef("J01DD02", "Ceftazidime", "CAZ"),
    AntibioticRef("J01DD52", "Ceftazidime-avibactam", "CZA", ("ceftazidime/avibactam", "ceftazidime-avi")),
    AntibioticRef("J01DE01", "Cefepime", "FEP"),
    AntibioticRef("J01DH03", "Ertapenem", "ETP"),
    # WHO assigns imipenem the combination code with cilastatin.
    AntibioticRef("J01DH51", "Imipenem", "IPM", ("imipenem-cilastatin", "imipenem/cilastatin")),
    AntibioticRef("J01DH02", "Meropenem", "MEM"),
    AntibioticRef("J01GB06", "Amikacin", "AMK"),
    AntibioticRef("J01GB03", "Gentamicin", "GEN"),
    AntibioticRef("J01MA02", "Ciprofloxacin", "CIP"),
    AntibioticRef("J01EE01", "Trimethoprim-sulfamethoxazole", "SXT", ("co-trimoxazole", "cotrimoxazole", "trimethoprim/sulfamethoxazole")),
    AntibioticRef("J01XB01", "Colistin", "COL", ("polymyxin e",)),
    AntibioticRef("J01AA12", "Tigecycline", "TGC"),
    AntibioticRef("J01XA01", "Vancomycin", "VAN"),
    AntibioticRef("J01XA02", "Teicoplanin", "TEC"),
    AntibioticRef("J01XX08", "Linezolid", "LNZ"),
    AntibioticRef("J01FA01", "Erythromycin", "ERY"),
    AntibioticRef("J01FF01", "Clindamycin", "CLI"),
    AntibioticRef("J04AB02", "Rifampicin", "RIF", ("rifampin",)),
)
# WHO AWaRe classification (2023 list), keyed by AMR-package code.
# Hand-curated: no machine-readable WHO source was reachable when this was
# written, so confirm against the current WHO AWaRe list before relying on
# it. Agents we could not place with confidence (rifampicin, cefoxitin) are
# deliberately left unclassified rather than guessed.
AWARE: dict[str, str] = {
    "AMP": "Access",
    "AMC": "Access",
    "TZP": "Watch",
    "CLO": "Access",
    "OXA": "Access",
    "CRO": "Watch",
    "CAZ": "Watch",
    "CZA": "Reserve",
    "FEP": "Watch",
    "ETP": "Watch",
    "IPM": "Watch",
    "MEM": "Watch",
    "AMK": "Access",
    "GEN": "Access",
    "CIP": "Watch",
    "SXT": "Access",
    "COL": "Reserve",
    "TGC": "Reserve",
    "VAN": "Watch",
    "TEC": "Watch",
    "LNZ": "Reserve",
    "ERY": "Watch",
    "CLI": "Access",
}
AWARE_GROUPS = ("Access", "Watch", "Reserve")

ANTIBIOTICS: dict[str, AntibioticRef] = {}
for _drug in _ANTIBIOTICS:
    _drug = AntibioticRef(_drug.atc_code, _drug.name, _drug.amr_code, _drug.aliases, AWARE.get(_drug.amr_code))
    for _key in (_drug.name, *_drug.aliases):
        ANTIBIOTICS[_key.lower()] = _drug


def resolve_antibiotic(raw: str) -> AntibioticRef:
    ref = ANTIBIOTICS.get((raw or "").strip().lower())
    if ref is None:
        raise ValueError(f"antibiotic {raw!r} is not in the ATC vocabulary")
    return ref


# --------------------------------------------------------------------------
# Priority resistance phenotypes (derived from susceptibility results)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PhenotypeRule:
    """An isolate has ``flag`` when it tests R to any of ``atc_codes``."""

    flag: str
    meaning: str
    taxids: frozenset[int]
    atc_codes: frozenset[str]


ENTEROBACTERALES_TAXIDS = frozenset({573, 562, 550})
CARBAPENEM_ATC = frozenset({"J01DH02", "J01DH51", "J01DH03"})  # meropenem, imipenem, ertapenem

# Defined from results, not from the flag a lab may append to the organism
# name, so the same definition applies to every laboratory.
PRIORITY_PHENOTYPES = (
    PhenotypeRule("CRE", "carbapenem-resistant Enterobacterales", ENTEROBACTERALES_TAXIDS, CARBAPENEM_ATC),
    PhenotypeRule("CRAB", "carbapenem-resistant Acinetobacter baumannii", frozenset({470}), frozenset({"J01DH02", "J01DH51"})),
    PhenotypeRule("CRPA", "carbapenem-resistant Pseudomonas aeruginosa", frozenset({287}), frozenset({"J01DH02", "J01DH51"})),
    PhenotypeRule("MRSA", "methicillin-resistant Staphylococcus aureus", frozenset({1280}), frozenset({"J01CF04", "J01CF02", "J01DC01"})),
    PhenotypeRule("VRE", "vancomycin-resistant Enterococcus faecium", frozenset({1352}), frozenset({"J01XA01"})),
)


# --------------------------------------------------------------------------
# Resistance determinants (CARD ARO)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneRef:
    aro_id: str
    name: str
    symbol: str
    mechanism: str
    # Resistance category used by alert and concordance rules.
    category: str
    # False for chromosomal mutations (e.g. porin loss), which cannot move
    # between organisms and are excluded from horizontal-transfer analysis.
    acquired: bool = True
    aliases: tuple[str, ...] = field(default=())


ARO_PATTERN = re.compile(r"^ARO:\d{7}$")
GENE_CATEGORIES = frozenset({"carbapenemase", "esbl", "methicillin", "glycopeptide", "macrolide", "colistin", "porin"})

_GENES = (
    GeneRef("ARO:3000617", "mecA", "mecA", "Antibiotic target replacement (PBP2a)", "methicillin"),
    GeneRef("ARO:3000010", "vanA", "vanA", "Antibiotic target alteration (D-Ala-D-Lac)", "glycopeptide"),
    GeneRef("ARO:3000013", "vanB", "vanB", "Antibiotic target alteration (D-Ala-D-Lac)", "glycopeptide"),
    GeneRef("ARO:3000250", "ErmC", "ermC", "Antibiotic target alteration (23S rRNA methylation)", "macrolide", aliases=("erm(c)",)),
    GeneRef("ARO:3000589", "NDM-1", "blaNDM-1", "Antibiotic inactivation (metallo-beta-lactamase)", "carbapenemase"),
    GeneRef("ARO:3000467", "NDM-5", "blaNDM-5", "Antibiotic inactivation (metallo-beta-lactamase)", "carbapenemase"),
    GeneRef("ARO:3002272", "VIM-2", "blaVIM-2", "Antibiotic inactivation (metallo-beta-lactamase)", "carbapenemase"),
    GeneRef("ARO:3002312", "KPC-2", "blaKPC-2", "Antibiotic inactivation (class A serine carbapenemase)", "carbapenemase"),
    GeneRef("ARO:3002313", "KPC-3", "blaKPC-3", "Antibiotic inactivation (class A serine carbapenemase)", "carbapenemase"),
    GeneRef("ARO:3002334", "GES-5", "blaGES-5", "Antibiotic inactivation (class A carbapenemase)", "carbapenemase"),
    GeneRef("ARO:3001782", "OXA-48", "blaOXA-48", "Antibiotic inactivation (class D carbapenemase, OXA-48-like)", "carbapenemase"),
    GeneRef("ARO:3001784", "OXA-181", "blaOXA-181", "Antibiotic inactivation (class D carbapenemase, OXA-48-like)", "carbapenemase"),
    GeneRef("ARO:3001778", "OXA-232", "blaOXA-232", "Antibiotic inactivation (class D carbapenemase, OXA-48-like)", "carbapenemase"),
    GeneRef("ARO:3001418", "OXA-23", "blaOXA-23", "Antibiotic inactivation (class D carbapenemase, OXA-23 group)", "carbapenemase"),
    GeneRef("ARO:3001878", "CTX-M-15", "blaCTX-M-15", "Antibiotic inactivation (class A extended-spectrum beta-lactamase)", "esbl"),
    GeneRef(
        "ARO:3003689",
        "MCR-1.1",
        "mcr-1.1",
        "Antibiotic target alteration (lipid A phosphoethanolamine transferase)",
        "colistin",
        aliases=("mcr-1",),
    ),
    GeneRef(
        "ARO:3003686",
        "Pseudomonas aeruginosa oprD with mutation conferring resistance to imipenem",
        "oprD",
        "Reduced permeability (OprD porin loss)",
        "porin",
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
