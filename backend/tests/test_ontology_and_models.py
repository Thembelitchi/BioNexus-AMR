import itertools

import pytest
from pydantic import ValidationError

from bionexus import ontology
from bionexus.models import ClinicalRow, GenomicRow, MovementRow, parse_mic

from .conftest import clinical_row


def test_organism_strips_phenotype_labels_from_taxonomy():
    ref, labels = ontology.resolve_organism("Klebsiella pneumoniae (CRE)")
    assert (ref.ncbi_taxid, ref.species, ref.genus) == (573, "Klebsiella pneumoniae", "Klebsiella")
    assert labels == ["CRE"]
    assert ontology.resolve_organism("staphylococcus  aureus")[0].ncbi_taxid == 1280


@pytest.mark.parametrize("raw", ["Bacillus imaginarius", "Staphylococcus aureus (XYZ)", "MRSA", ""])
def test_unknown_organisms_and_labels_are_rejected(raw):
    with pytest.raises(ValueError):
        ontology.resolve_organism(raw)


@pytest.mark.parametrize(
    "raw, expected",
    [(">16", (16.0, ">")), ("<=0.5", (0.5, "<=")), ("≤ 0.25", (0.25, "<=")), ("2", (2.0, "=")), ("8 mg/L", (8.0, "=")), ("", (None, None))],
)
def test_mic_parsing(raw, expected):
    assert parse_mic(raw) == expected


@pytest.mark.parametrize("raw", ["abc", ">>16", "-1", "16-32"])
def test_invalid_mic_is_rejected(raw):
    with pytest.raises(ValueError):
        parse_mic(raw)


def test_gene_aliases_resolve_to_card_accessions():
    assert ontology.resolve_gene("blaNDM-1").aro_id == "ARO:3000589"
    assert ontology.resolve_gene("NDM-1").aro_id == "ARO:3000589"
    assert ontology.resolve_gene("blaVIM-2").aro_id == "ARO:3002272"
    oprd = ontology.resolve_gene("oprD-loss")
    assert oprd.aro_id == "ARO:3003686" and not oprd.acquired
    with pytest.raises(ValueError):
        ontology.resolve_gene("blaFAKE-1")


def test_vocabulary_identifiers_are_well_formed():
    assert all(ontology.ARO_PATTERN.match(gene.aro_id) for gene in ontology.GENES.values())
    assert all(ontology.ATC_PATTERN.match(drug.atc_code) for drug in ontology.ANTIBIOTICS.values())
    assert len({gene.aro_id for gene in ontology.GENES.values()}) == len({gene.symbol for gene in ontology.GENES.values()})


def test_sequence_type_resolution():
    kp = ontology.ORGANISMS["klebsiella pneumoniae"]
    sa = ontology.ORGANISMS["staphylococcus aureus"]
    assert ontology.resolve_sequence_type("ST258", kp).key == "klebsiella:ST258"
    usa300 = ontology.resolve_sequence_type("USA300", sa)
    assert (usa300.key, usa300.clone_designation) == ("saureus:ST8", "USA300")
    assert ontology.resolve_sequence_type("", kp) is None
    with pytest.raises(ValueError):
        ontology.resolve_sequence_type("USA300", kp)


def test_clinical_row_grounding():
    row = ClinicalRow.model_validate(clinical_row("S-1", "P-1", "Staphylococcus aureus (MRSA)", Ward=" general  ", Antibiotic="Oxacillin"))
    assert row.organism.ncbi_taxid == 1280 and row.phenotype_labels == ("MRSA",)
    assert row.antibiotic.atc_code == "J01CF04"
    assert row.ward == "General"
    assert (row.mic, row.mic_qualifier, row.sir) == (16.0, ">", "R")
    assert row.collected.tzinfo is not None


@pytest.mark.parametrize(
    "overrides",
    [{"Result": "X"}, {"Antibiotic": "Unobtainium"}, {"Date": "31/12/2025"}, {"PatientID": ""}, {"Ward": " "}],
)
def test_clinical_row_rejections(overrides):
    with pytest.raises(ValidationError):
        ClinicalRow.model_validate(clinical_row("S-1", "P-1", "Klebsiella pneumoniae", **overrides))


def test_genomic_row_wild_type_and_mobile_elements():
    wild = GenomicRow.model_validate({"SampleID": "S-1", "GeneDetected": "None", "Mechanism": "Wild Type"})
    assert wild.gene is None
    mobile = GenomicRow.model_validate({"SampleID": "S-1", "GeneDetected": "blaNDM-1", "MGE_Type": "plasmid", "MGE_Replicon": "IncX3"})
    assert mobile.mge_type == "Plasmid"
    with pytest.raises(ValidationError, match="chromosomal mutation"):
        GenomicRow.model_validate({"SampleID": "S-1", "GeneDetected": "oprD-loss", "MGE_Type": "Plasmid", "MGE_Replicon": "IncP"})
    with pytest.raises(ValidationError, match="together"):
        GenomicRow.model_validate({"SampleID": "S-1", "GeneDetected": "blaNDM-1", "MGE_Type": "Plasmid"})


def test_movement_row():
    row = MovementRow.model_validate({"PatientID": "P-1", "EncounterID": "E-1", "Ward": "icu", "Timestamp": "2025-11-01T08:30:00+02:00"})
    assert row.ward == "ICU" and row.timestamp.utcoffset().total_seconds() == 7200


@pytest.mark.parametrize("raw, expected", [("icu", "ICU"), (" general  ", "General"), ("Neonatal ICU", "Neonatal ICU"), ("haematology-oncology", "Haematology-Oncology")])
def test_ward_names_keep_acronyms(raw, expected):
    from bionexus.models import canonical_ward

    assert canonical_ward(raw) == expected


def test_disk_diffusion_interpretation_follows_clsi():
    from bionexus.breakpoints import interpret_disk

    assert interpret_disk(573, "MEM", 24) == "S"  # Enterobacterales meropenem: S >= 23 mm
    assert interpret_disk(573, "MEM", 21) == "I"
    assert interpret_disk(573, "MEM", 19) == "R"  # R <= 19 mm
    assert interpret_disk(573, "FEP", 20) == "SDD"
    assert interpret_disk(1280, "FOX", 21) == "R"  # cefoxitin screen for MRSA
    # CLSI gives no disk breakpoint where disk testing is unreliable.
    assert interpret_disk(573, "COL", 20) is None
    assert interpret_disk(1280, "VAN", 20) is None


def test_aware_groups():
    groups = {d.name: d.aware for d in set(ontology.ANTIBIOTICS.values())}
    assert {n for n, g in groups.items() if g == "Reserve"} == {"Colistin", "Ceftazidime-avibactam", "Linezolid", "Tigecycline"}
    assert groups["Meropenem"] == "Watch" and groups["Ampicillin"] == "Access"
    assert groups["Cefoxitin"] == groups["Rifampicin"] == "Watch"
    assert all(g in ontology.AWARE_GROUPS for g in groups.values())


def test_priority_phenotype_rules_never_flag_one_isolate_twice():
    rules = ontology.PRIORITY_PHENOTYPES
    for rule in rules:
        assert all(ontology.ATC_PATTERN.match(code) for code in rule.atc_codes | rule.unless)
    for a, b in itertools.combinations(rules, 2):
        # Rules for the same taxa must be mutually exclusive via ``unless``.
        if a.taxids & b.taxids:
            assert a.atc_codes <= b.unless or b.atc_codes <= a.unless, (a.flag, b.flag)
    assert {r.flag for r in rules} == {"CRE", "3GC-R", "CRAB", "CRPA", "MRSA", "VRE"}


def test_pseudonymiser():
    from bionexus.privacy import Pseudonymiser, age_band

    p = Pseudonymiser("a-sufficiently-long-key")
    assert p.patient("PT-1") == p.patient("PT-1") != p.patient("PT-2")
    assert p.patient("PT-1") != Pseudonymiser("another-long-key-here").patient("PT-1")
    assert p.patient("X") != p.encounter("X") and p.patient("X").startswith("P-")
    with pytest.raises(ValueError):
        Pseudonymiser("short")
    assert [age_band(a) for a in (0.01, 0.5, 3, 30, 80, None)] == ["0-27 days", "28 days-<1 year", "1-4 years", "25-34 years", "75+ years", None]


def test_screening_specimens():
    assert ontology.is_screening_specimen("Rectal swab (CPE screen)")
    assert ontology.is_screening_specimen("MRSA screening nasal swab")
    assert not ontology.is_screening_specimen("Blood culture")
    assert not ontology.is_screening_specimen("Pus swab")


def test_notification_due_one_month_later():
    from datetime import date

    from bionexus.notifiable import one_month_after

    assert one_month_after(date(2025, 1, 31)) == date(2025, 2, 28)
    assert one_month_after(date(2025, 12, 15)) == date(2026, 1, 15)
