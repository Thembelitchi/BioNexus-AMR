from collections import Counter

from bionexus.etl import read_csv, transform

from .conftest import CLINICAL_CSV, CLINICAL_HEADER, GENOMIC_CSV, GENOMIC_HEADER, clinical_row, genomic_row, to_csv

KP = "Klebsiella pneumoniae (CRE)"


def run(clinical_rows, genomic_rows=()):
    return transform(read_csv(to_csv(CLINICAL_HEADER, clinical_rows)), read_csv(to_csv(GENOMIC_HEADER, list(genomic_rows))))


def errors(result):
    return [issue for issue in result.issues if issue.severity == "error"]


def test_sample_data_transforms_cleanly():
    result = transform(read_csv(CLINICAL_CSV), read_csv(GENOMIC_CSV))
    assert result.issues == []
    assert len(result.isolates) == 300
    statuses = Counter(record.genotype_status for record in result.isolates)
    assert statuses == {"determinants_detected": 224, "no_determinant_detected": 76}
    assert {record.species for record in result.isolates} == {"Staphylococcus aureus", "Klebsiella pneumoniae", "Pseudomonas aeruginosa"}
    # Phenotype shorthand never leaks into taxonomy.
    assert all("(" not in record.species for record in result.isolates)


def test_ast_rows_for_one_sample_are_grouped():
    result = run(
        [
            clinical_row("S-1", "P-1", KP, Antibiotic="Meropenem", Result="R", MIC=">16"),
            clinical_row("S-1", "P-1", KP, Antibiotic="Colistin", Result="S", MIC="0.5"),
        ]
    )
    [isolate] = result.isolates
    assert {(t.name, t.sir, t.mic) for t in isolate.susceptibility} == {("Meropenem", "R", 16.0), ("Colistin", "S", 0.5)}


def test_contradictory_rows_for_one_sample_reject_the_isolate():
    result = run([clinical_row("S-1", "P-1", KP), clinical_row("S-1", "P-1", KP, Ward="Oncology", Antibiotic="Colistin")])
    assert result.isolates == []
    assert "disagree on ward" in errors(result)[0].message


def test_genomic_patient_mismatch_drops_genomics():
    result = run([clinical_row("S-1", "P-1", KP)], [genomic_row("S-1", "P-999", KP, "ST258", "blaKPC-3")])
    [isolate] = result.isolates
    assert isolate.genotype_status == "not_sequenced" and isolate.direct_genes == []
    assert "does not match clinical PatientID" in errors(result)[0].message


def test_genomic_organism_mismatch_drops_genomics():
    result = run([clinical_row("S-1", "P-1", KP)], [genomic_row("S-1", "P-1", "Pseudomonas aeruginosa", "ST235", "blaVIM-2")])
    assert result.isolates[0].genotype_status == "not_sequenced"
    assert "does not match clinical identification" in errors(result)[0].message


def test_orphan_genomic_rows_are_reported():
    result = run([clinical_row("S-1", "P-1", KP)], [genomic_row("S-404", "P-2", KP, "ST11", "blaNDM-1")])
    assert result.rows_rejected["genomic"] == 1
    assert errors(result)[0].sample_id == "S-404"


def test_wild_type_versus_unsequenced():
    result = run(
        [clinical_row("S-1", "P-1", KP), clinical_row("S-2", "P-2", KP)],
        [genomic_row("S-1", "P-1", KP, "ST11", "None")],
    )
    status = {record.isolate_id: record.genotype_status for record in result.isolates}
    assert status == {"S-1": "no_determinant_detected", "S-2": "not_sequenced"}


def test_genes_are_split_between_mobile_elements_and_direct_calls():
    result = run(
        [clinical_row("S-1", "P-1", "Pseudomonas aeruginosa")],
        [
            genomic_row("S-1", "P-1", "Pseudomonas aeruginosa", "ST235", "blaVIM-2", MGE_Type="Integron", MGE_Replicon="In58"),
            genomic_row("S-1", "P-1", "Pseudomonas aeruginosa", "ST235", "oprD-loss"),
        ],
    )
    [isolate] = result.isolates
    assert [(g.symbol, g.context) for g in isolate.direct_genes] == [("oprD", "chromosomal")]
    [element] = isolate.mobile_elements
    assert (element.key, element.type, [g.symbol for g in element.genes]) == ("S-1:Integron:In58", "Integron", ["blaVIM-2"])
    assert isolate.sequence_type.key == "paeruginosa:ST235"


def test_conflicting_strain_subtypes_omit_sequence_type():
    result = run(
        [clinical_row("S-1", "P-1", KP)],
        [genomic_row("S-1", "P-1", KP, "ST258", "blaKPC-3"), genomic_row("S-1", "P-1", KP, "ST11", "blaNDM-1")],
    )
    assert result.isolates[0].sequence_type is None
    assert "conflicting strain subtypes" in errors(result)[0].message


def test_invalid_rows_are_reported_with_line_numbers():
    result = run([clinical_row("S-1", "P-1", KP), clinical_row("S-2", "P-2", "Bacillus imaginarius")])
    assert len(result.isolates) == 1
    [issue] = errors(result)
    assert issue.line == 3 and issue.sample_id == "S-2" and "taxonomy vocabulary" in issue.message
