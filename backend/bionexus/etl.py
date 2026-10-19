"""Transform denormalised laboratory CSVs into per-isolate graph records.

The clinical file is long-format (one row per antimicrobial test); the
genomic file has one row per determinant call. Both are keyed by SampleID,
which becomes the Isolate identity. Rows that fail validation, contradict
each other, or cannot be joined are reported and skipped, never guessed.
"""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from . import breakpoints, ontology
from .privacy import Pseudonymiser, age_band
from .models import (
    AntibioticNode,
    ClinicalRow,
    GeneCall,
    GenomicRow,
    IngestIssue,
    IsolateRecord,
    MobileElementRecord,
    MovementRecord,
    MovementRow,
    SequenceTypeNode,
    SusceptibilityResult,
)

log = logging.getLogger(__name__)

RowT = TypeVar("RowT", bound=BaseModel)


@dataclass
class TransformResult:
    isolates: list[IsolateRecord] = field(default_factory=list)
    movements: list[MovementRecord] = field(default_factory=list)
    rows_read: dict[str, int] = field(default_factory=dict)
    rows_rejected: dict[str, int] = field(default_factory=dict)
    issues: list[IngestIssue] = field(default_factory=list)

    def reject(self, source: str, message: str, *, line: int | None = None, sample_id: str | None = None) -> None:
        self.issues.append(IngestIssue(source=source, line=line, sample_id=sample_id, message=message))

    def warn(self, source: str, message: str, *, line: int | None = None, sample_id: str | None = None) -> None:
        self.issues.append(IngestIssue(source=source, line=line, sample_id=sample_id, severity="warning", message=message))


def read_csv(source: str | Path | bytes) -> list[tuple[int, dict[str, str]]]:
    """Return ``(line_number, row)`` pairs; accepts a path or raw file bytes."""
    if isinstance(source, bytes):
        text = source.decode("utf-8-sig")
    else:
        text = Path(source).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")
    reader.fieldnames = [name.strip() for name in reader.fieldnames]
    rows = []
    for row in reader:
        if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
            continue
        rows.append((reader.line_num, {key: value for key, value in row.items() if key is not None}))
    return rows


def _validate(rows: Iterable[tuple[int, dict[str, str]]], model: type[RowT], source: str, result: TransformResult) -> list[tuple[int, RowT]]:
    valid: list[tuple[int, RowT]] = []
    read = rejected = 0
    for line, raw in rows:
        read += 1
        try:
            valid.append((line, model.model_validate(raw)))
        except ValidationError as exc:
            rejected += 1
            detail = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'row'}: {err['msg']}" for err in exc.errors())
            result.reject(source, detail, line=line, sample_id=(raw.get("SampleID") or None))
    result.rows_read[source] = read
    result.rows_rejected[source] = rejected
    return valid


def _pseudonymise(p: Pseudonymiser, clinical, genomic, movements):
    """Replace direct identifiers before any record is built.

    Exact ages are kept only long enough to derive the age band.
    """
    clinical = [
        (line, row.model_copy(update={
            "patient_id": p.patient(row.patient_id),
            "encounter_id": p.encounter(encounter_key(row)),
            "age_years": None,
            "age_band": age_band(row.age_years),
        }))
        for line, row in clinical
    ]
    genomic = [(line, row.model_copy(update={"patient_id": p.patient(row.patient_id) if row.patient_id else None})) for line, row in genomic]
    movements = [
        (line, row.model_copy(update={"patient_id": p.patient(row.patient_id), "encounter_id": p.encounter(row.encounter_id)}))
        for line, row in movements
    ]
    return clinical, genomic, movements


def encounter_key(row: ClinicalRow) -> str:
    # Without an ADT feed, each specimen collection is its own encounter.
    return row.encounter_id or f"{row.patient_id}:{row.collected:%Y%m%d}"


def location_event_key(encounter_id: str, ward: str, timestamp) -> str:
    return f"{encounter_id}@{ward}@{timestamp.isoformat()}"


def transform(
    clinical: Iterable[tuple[int, dict[str, str]]],
    genomic: Iterable[tuple[int, dict[str, str]]] = (),
    movements: Iterable[tuple[int, dict[str, str]]] = (),
    pseudonymiser: Pseudonymiser | None = None,
) -> TransformResult:
    result = TransformResult()
    clinical_rows = _validate(clinical, ClinicalRow, "clinical", result)
    genomic_rows = _validate(genomic, GenomicRow, "genomic", result)
    movement_rows = _validate(movements, MovementRow, "movements", result)
    if pseudonymiser is not None:
        clinical_rows, genomic_rows, movement_rows = _pseudonymise(pseudonymiser, clinical_rows, genomic_rows, movement_rows)

    by_sample: dict[str, list[tuple[int, ClinicalRow]]] = defaultdict(list)
    for line, row in clinical_rows:
        by_sample[row.sample_id].append((line, row))

    genomic_by_sample: dict[str, list[tuple[int, GenomicRow]]] = defaultdict(list)
    for line, row in genomic_rows:
        if row.sample_id not in by_sample:
            result.reject("genomic", "no clinical record for this SampleID", line=line, sample_id=row.sample_id)
            result.rows_rejected["genomic"] += 1
            continue
        genomic_by_sample[row.sample_id].append((line, row))

    for sample_id, rows in by_sample.items():
        record = _build_isolate(sample_id, rows, genomic_by_sample.get(sample_id, []), result)
        if record is not None:
            result.isolates.append(record)

    for _, row in movement_rows:
        ward = row.ward_ref()
        result.movements.append(
            MovementRecord(
                patient_id=row.patient_id,
                encounter_id=row.encounter_id,
                location_event_id=location_event_key(row.encounter_id, ward.key, row.timestamp),
                ward=ward,
                timestamp=row.timestamp,
            )
        )

    _check_facility_metadata(result)
    log.info(
        "transformed %d isolates and %d movements (%d issues)",
        len(result.isolates),
        len(result.movements),
        len(result.issues),
    )
    return result


def _check_facility_metadata(result: TransformResult) -> None:
    """Warn when one facility code arrives with different names or provinces."""
    seen: dict[str, set[tuple[str | None, str | None]]] = defaultdict(set)
    for ward in [r.ward for r in result.isolates] + [m.ward for m in result.movements]:
        if ward.facility:
            seen[ward.facility].add((ward.facility_name, ward.province))
    for code, variants in sorted(seen.items()):
        named = {v for v in variants if v != (None, None)}
        if len(named) > 1:
            result.warn("clinical", f"facility {code} has conflicting name/province values {sorted(named, key=str)}")


_SPECIMEN_FIELDS = ("patient_id", "collected", "ward", "facility", "specimen", "organism", "encounter_id", "sex", "age_years")


def _build_isolate(
    sample_id: str,
    rows: list[tuple[int, ClinicalRow]],
    genomic: list[tuple[int, GenomicRow]],
    result: TransformResult,
) -> IsolateRecord | None:
    first_line, first = rows[0]
    for line, row in rows[1:]:
        conflicts = [name for name in _SPECIMEN_FIELDS if getattr(row, name) != getattr(first, name)]
        if conflicts:
            result.reject(
                "clinical",
                f"rows for the same SampleID disagree on {', '.join(conflicts)} (first seen on line {first_line}); isolate skipped",
                line=line,
                sample_id=sample_id,
            )
            return None

    susceptibility: dict[str, SusceptibilityResult] = {}
    treatments: dict[str, AntibioticNode] = {}
    labels: set[str] = set()
    admitted = discharged = None
    for line, row in rows:
        labels.update(row.phenotype_labels)
        admitted = admitted or row.admitted
        discharged = discharged or row.discharged
        if row.treatment:
            treatments[row.treatment.atc_code] = AntibioticNode(atc_code=row.treatment.atc_code, name=row.treatment.name, aware=row.treatment.aware)
        test = SusceptibilityResult(
            atc_code=row.antibiotic.atc_code,
            name=row.antibiotic.name,
            aware=row.antibiotic.aware,
            sir=row.sir,
            method="MIC" if row.mic is not None else "DISK" if row.zone_mm is not None else None,
            mic=row.mic,
            mic_qualifier=row.mic_qualifier,
            zone_mm=row.zone_mm,
            guideline=row.guideline or "as reported",
        )
        _check_interpretation(row, sample_id, line, result)
        previous = susceptibility.get(test.atc_code)
        if previous and previous != test:
            result.reject("clinical", f"conflicting duplicate {test.name} result ignored", line=line, sample_id=sample_id)
            continue
        susceptibility[test.atc_code] = test

    sequence_type, genes, mobile, status = _resolve_genotype(sample_id, first, genomic, result)
    encounter_id = encounter_key(first)
    ward = first.ward_ref()
    return IsolateRecord(
        patient_id=first.patient_id,
        encounter_id=encounter_id,
        admitted=admitted,
        discharged=discharged,
        location_event_id=location_event_key(encounter_id, ward.key, first.collected),
        ward=ward,
        sex=first.sex,
        age_years=first.age_years,
        age_band=first.age_band or age_band(first.age_years),
        isolate_id=sample_id,
        collected=first.collected,
        specimen=first.specimen,
        screening=ontology.is_screening_specimen(first.specimen),
        ncbi_taxid=first.organism.ncbi_taxid,
        species=first.organism.species,
        genus=first.organism.genus,
        phenotype_labels=sorted(labels),
        genotype_status=status,
        treatments=list(treatments.values()),
        susceptibility=list(susceptibility.values()),
        sequence_type=sequence_type,
        direct_genes=genes,
        mobile_elements=mobile,
    )


def _check_interpretation(row: ClinicalRow, sample_id: str, line: int, result: TransformResult) -> None:
    """Warn when a reported category contradicts the MIC or zone under the stated guideline."""
    if row.guideline != breakpoints.BREAKPOINT_SOURCE:
        return
    taxid, drug = row.organism.ncbi_taxid, row.antibiotic.amr_code
    checks = []
    if row.mic is not None:
        mic = f"{row.mic_qualifier if row.mic_qualifier != '=' else ''}{row.mic:g}"
        checks.append((breakpoints.interpret(taxid, drug, row.mic, row.mic_qualifier), f"MIC {mic} mg/L"))
    if row.zone_mm is not None:
        checks.append((breakpoints.interpret_disk(taxid, drug, row.zone_mm), f"zone {row.zone_mm:g} mm"))
    for expected, measurement in checks:
        if expected is not None and expected != row.sir:
            result.warn(
                "clinical",
                f"{row.antibiotic.name} reported {row.sir} but {measurement} reads {expected} under {row.guideline}",
                line=line,
                sample_id=sample_id,
            )


def _resolve_genotype(sample_id, clinical: ClinicalRow, genomic: list[tuple[int, GenomicRow]], result: TransformResult):
    if not genomic:
        return None, [], [], "not_sequenced"

    for line, row in genomic:
        if row.patient_id and row.patient_id != clinical.patient_id:
            result.reject(
                "genomic",
                f"PatientID {row.patient_id} does not match clinical PatientID {clinical.patient_id}; genomic data dropped",
                line=line,
                sample_id=sample_id,
            )
            return None, [], [], "not_sequenced"
        if row.organism and row.organism.ncbi_taxid != clinical.organism.ncbi_taxid:
            result.reject(
                "genomic",
                f"organism {row.organism.species} does not match clinical identification {clinical.organism.species}; genomic data dropped",
                line=line,
                sample_id=sample_id,
            )
            return None, [], [], "not_sequenced"

    subtypes = {row.strain_subtype for _, row in genomic if row.strain_subtype}
    sequence_type = None
    if len(subtypes) > 1:
        result.reject("genomic", f"conflicting strain subtypes {sorted(subtypes)}; sequence type omitted", sample_id=sample_id)
    elif subtypes:
        try:
            st = ontology.resolve_sequence_type(subtypes.pop(), clinical.organism)
        except ValueError as exc:
            result.reject("genomic", str(exc), line=genomic[0][0], sample_id=sample_id)
            st = None
        if st is not None:
            sequence_type = SequenceTypeNode(key=st.key, scheme=st.scheme, st_number=st.st_number, clone_designation=st.clone_designation)

    direct: dict[str, GeneCall] = {}
    elements: dict[tuple[str, str], dict[str, GeneCall]] = defaultdict(dict)
    for _, row in genomic:
        gene = row.gene
        if gene is None:
            continue
        if row.mge_type and row.mge_replicon:
            elements[(row.mge_type, row.mge_replicon)][gene.aro_id] = _gene_call(gene, "mobile")
        else:
            direct[gene.aro_id] = _gene_call(gene, "unresolved" if gene.acquired else "chromosomal")

    # A gene placed on an element is not also a free-floating call.
    for genes in elements.values():
        for aro_id in genes:
            direct.pop(aro_id, None)

    mobile = [
        MobileElementRecord(key=f"{sample_id}:{mge_type}:{replicon}", type=mge_type, replicon=replicon, genes=list(genes.values()))
        for (mge_type, replicon), genes in elements.items()
    ]
    status = "determinants_detected" if direct or mobile else "no_determinant_detected"
    return sequence_type, list(direct.values()), mobile, status


def _gene_call(gene: ontology.GeneRef, context: str) -> GeneCall:
    return GeneCall(
        aro_id=gene.aro_id,
        name=gene.name,
        symbol=gene.symbol,
        mechanism=gene.mechanism,
        category=gene.category,
        acquired=gene.acquired,
        context=context,
    )
