"""Pydantic models for raw laboratory rows and graph-ready records.

Raw ``*Row`` models validate one CSV line each and resolve every vocabulary
term through :mod:`bionexus.ontology`. The ``*Record`` models are the
normalised, per-isolate payloads that the loader sends to Neo4j.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from . import ontology

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"

# SDD: susceptible-dose-dependent, a CLSI category for e.g. cefepime.
SIR = Literal["S", "I", "SDD", "R"]
MicQualifier = Literal["=", "<", "<=", ">", ">="]

_MIC_RE = re.compile(r"^\s*(?P<op><=|>=|<|>|=|≤|≥)?\s*(?P<value>\d+(?:\.\d+)?|\.\d+)\s*(?:mg/l|µg/ml|ug/ml)?\s*$", re.IGNORECASE)
_UNICODE_OPS = {"≤": "<=", "≥": ">="}


def parse_timestamp(value: Any) -> datetime:
    """Parse an ISO date or datetime; naive values are taken as UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"invalid ISO-8601 date {value!r}") from exc
    else:
        raise ValueError("a date is required")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_mic(raw: str | None) -> tuple[float | None, MicQualifier | None]:
    """Split ``">16"`` into ``(16.0, ">")``. Blank means not measured."""
    if raw is None or not str(raw).strip():
        return None, None
    match = _MIC_RE.match(str(raw))
    if not match:
        raise ValueError(f"invalid MIC value {raw!r}")
    op = match["op"] or "="
    return float(match["value"]), _UNICODE_OPS.get(op, op)  # type: ignore[return-value]


def canonical_ward(raw: str) -> str:
    name = " ".join((raw or "").split())
    if not name:
        raise ValueError("ward is required")
    if len(name) <= 4:
        return name.upper()
    # Tidy names typed in lowercase; otherwise keep acronyms such as "ICU".
    return name.title() if name.islower() else name


def _blank_to_none(value: Any) -> Any:
    return None if isinstance(value, str) and not value.strip() else value


class _CsvRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True, extra="ignore", frozen=True)


# --------------------------------------------------------------------------
# Raw input rows
# --------------------------------------------------------------------------


class _LocatedRow(_CsvRow):
    """Columns placing an event in a ward, optionally within a facility."""

    ward: str = Field(alias="Ward")
    facility: str | None = Field(default=None, alias="Facility", pattern=IDENTIFIER_PATTERN)
    facility_name: str | None = Field(default=None, alias="FacilityName", max_length=120)
    province: str | None = Field(default=None, alias="Province", max_length=80)

    @field_validator("ward", mode="before")
    @classmethod
    def _ward(cls, value: Any) -> str:
        return canonical_ward(value)

    @field_validator("facility_name", "province", mode="before")
    @classmethod
    def _collapse_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return " ".join(value.split()) or None
        return value

    def ward_ref(self) -> WardRef:
        return WardRef(
            key=f"{self.facility}:{self.ward}" if self.facility else self.ward,
            name=self.ward,
            facility=self.facility,
            facility_name=self.facility_name,
            province=self.province,
        )


_SEX = {"f": "F", "female": "F", "m": "M", "male": "M", "u": "U", "unknown": "U"}


class ClinicalRow(_LocatedRow):
    """One antimicrobial susceptibility test result for one specimen."""

    patient_id: str = Field(alias="PatientID", pattern=IDENTIFIER_PATTERN)
    sample_id: str = Field(alias="SampleID", pattern=IDENTIFIER_PATTERN)
    collected: datetime = Field(validation_alias=AliasChoices("Date", "CollectedAt", "collected"))
    specimen: str = Field(validation_alias=AliasChoices("Specimen", "SpecimenSource", "specimen"), min_length=1)
    treatment: ontology.AntibioticRef | None = Field(default=None, alias="Treatment")
    organism: ontology.OrganismRef = Field(alias="Organism")
    phenotype_labels: tuple[str, ...] = ()
    antibiotic: ontology.AntibioticRef = Field(alias="Antibiotic")
    sir: SIR = Field(alias="Result")
    mic: float | None = None
    mic_qualifier: MicQualifier | None = None
    guideline: str | None = Field(default=None, alias="Guideline")
    encounter_id: str | None = Field(default=None, alias="EncounterID", pattern=IDENTIFIER_PATTERN)
    admitted: datetime | None = Field(default=None, alias="AdmitDate")
    discharged: datetime | None = Field(default=None, alias="DischargeDate")
    sex: Literal["F", "M", "U"] | None = Field(default=None, alias="Sex")
    age_years: float | None = Field(default=None, alias="AgeYears", ge=0, le=125)

    @model_validator(mode="before")
    @classmethod
    def _split_compound_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = {key: _blank_to_none(value) for key, value in data.items()}
        organism = data.get("Organism", data.get("organism"))
        if isinstance(organism, str):
            ref, labels = ontology.resolve_organism(organism)
            data["Organism"], data["phenotype_labels"] = ref, tuple(labels)
            data.pop("organism", None)
        if "MIC" in data:
            data["mic"], data["mic_qualifier"] = parse_mic(data.pop("MIC"))
        return data

    @field_validator("collected", "admitted", "discharged", mode="before")
    @classmethod
    def _timestamp(cls, value: Any) -> Any:
        return None if value is None else parse_timestamp(value)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.strip().lower() not in _SEX:
                raise ValueError(f"sex must be F, M or U, not {value!r}")
            return _SEX[value.strip().lower()]
        return value

    @field_validator("antibiotic", "treatment", mode="before")
    @classmethod
    def _antibiotic(cls, value: Any) -> Any:
        return ontology.resolve_antibiotic(value) if isinstance(value, str) else value

    @field_validator("sir", mode="before")
    @classmethod
    def _sir(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_consistency(self) -> ClinicalRow:
        if self.admitted and self.discharged and self.discharged < self.admitted:
            raise ValueError("DischargeDate precedes AdmitDate")
        return self


class GenomicRow(_CsvRow):
    """One resistance determinant call (or a wild-type call) for one specimen."""

    sample_id: str = Field(alias="SampleID", pattern=IDENTIFIER_PATTERN)
    patient_id: str | None = Field(default=None, alias="PatientID", pattern=IDENTIFIER_PATTERN)
    organism: ontology.OrganismRef | None = Field(default=None, alias="Organism")
    strain_subtype: str | None = Field(default=None, validation_alias=AliasChoices("Strain_Subtype", "SequenceType", "ST"))
    gene: ontology.GeneRef | None = Field(default=None, alias="GeneDetected")
    mge_type: str | None = Field(default=None, alias="MGE_Type")
    mge_replicon: str | None = Field(default=None, alias="MGE_Replicon", max_length=64)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = {key: _blank_to_none(value) for key, value in data.items()}
        organism = data.get("Organism")
        if isinstance(organism, str):
            # Phenotype labels in the genomic file are informational only.
            data["Organism"] = ontology.resolve_organism(organism)[0]
        gene = data.get("GeneDetected")
        if gene is None or (isinstance(gene, str) and ontology.is_wild_type(gene)):
            data["GeneDetected"] = None
        elif isinstance(gene, str):
            data["GeneDetected"] = ontology.resolve_gene(gene)
        return data

    @field_validator("mge_type", mode="before")
    @classmethod
    def _mge_type(cls, value: Any) -> Any:
        return ontology.resolve_mge_type(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _mge_requires_gene(self) -> GenomicRow:
        if (self.mge_type is None) != (self.mge_replicon is None):
            raise ValueError("MGE_Type and MGE_Replicon must be given together")
        if self.mge_type and self.gene is None:
            raise ValueError("a mobile genetic element was given without a gene")
        if self.mge_type and self.gene and not self.gene.acquired:
            raise ValueError(f"{self.gene.symbol} is a chromosomal mutation and cannot sit on a mobile element")
        return self


class MovementRow(_LocatedRow):
    """An admission/transfer/discharge (ADT) event placing a patient in a ward."""

    patient_id: str = Field(alias="PatientID", pattern=IDENTIFIER_PATTERN)
    encounter_id: str = Field(alias="EncounterID", pattern=IDENTIFIER_PATTERN)
    timestamp: datetime = Field(alias="Timestamp")

    @field_validator("timestamp", mode="before")
    @classmethod
    def _timestamp(cls, value: Any) -> datetime:
        return parse_timestamp(value)


# --------------------------------------------------------------------------
# Graph-ready records
# --------------------------------------------------------------------------


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True)


class WardRef(_Record):
    key: str
    name: str
    facility: str | None = None
    facility_name: str | None = None
    province: str | None = None


class AntibioticNode(_Record):
    atc_code: str = Field(pattern=ontology.ATC_PATTERN.pattern)
    name: str


class SusceptibilityResult(AntibioticNode):
    sir: SIR
    mic: float | None = Field(default=None, ge=0)
    mic_qualifier: MicQualifier | None = None
    mic_unit: Literal["mg/L"] = "mg/L"
    guideline: str = "as reported"


class GeneCall(_Record):
    aro_id: str = Field(pattern=ontology.ARO_PATTERN.pattern)
    name: str
    symbol: str
    mechanism: str
    category: str
    acquired: bool
    context: Literal["chromosomal", "mobile", "unresolved"]


class MobileElementRecord(_Record):
    key: str
    type: Literal["Plasmid", "Integron", "Transposon"]
    replicon: str
    genes: list[GeneCall]


class SequenceTypeNode(_Record):
    key: str
    scheme: str
    st_number: int = Field(gt=0)
    clone_designation: str | None = None


GenotypeStatus = Literal["not_sequenced", "no_determinant_detected", "determinants_detected"]


class IsolateRecord(_Record):
    patient_id: str
    encounter_id: str
    admitted: datetime | None
    discharged: datetime | None
    location_event_id: str
    ward: WardRef
    sex: Literal["F", "M", "U"] | None = None
    age_years: float | None = None
    isolate_id: str
    collected: datetime
    specimen: str
    ncbi_taxid: int
    species: str
    genus: str
    phenotype_labels: list[str]
    genotype_status: GenotypeStatus
    treatments: list[AntibioticNode]
    susceptibility: list[SusceptibilityResult]
    sequence_type: SequenceTypeNode | None
    direct_genes: list[GeneCall]
    mobile_elements: list[MobileElementRecord]


class MovementRecord(_Record):
    patient_id: str
    encounter_id: str
    location_event_id: str
    ward: WardRef
    timestamp: datetime


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


class IngestIssue(BaseModel):
    source: str
    line: int | None = None
    sample_id: str | None = None
    severity: Literal["error", "warning"] = "error"
    message: str


class IngestReport(BaseModel):
    dry_run: bool
    rows_read: dict[str, int]
    rows_rejected: dict[str, int]
    isolates: int
    patients: int
    movements: int
    sequenced_isolates: int
    issues: list[IngestIssue]
