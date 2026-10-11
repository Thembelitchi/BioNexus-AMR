"""Pseudonymisation at ingest, in support of POPIA compliance.

Patient and encounter identifiers are replaced by keyed hashes
(HMAC-SHA256) before anything reaches the graph, and exact ages are
replaced by age bands. The same key always yields the same pseudonym, so
files still join and re-ingests stay idempotent, while re-identification
requires the key, which only the responsible party holds.

This is pseudonymisation, not anonymisation: under POPIA the graph still
holds personal information, so access control and the lawful-processing
conditions still apply. Laboratory accession numbers (SampleID) are kept so
the laboratory can trace specimens; treat them as identifiers too.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

MIN_KEY_BYTES = 16

# (upper bound in years, exclusive; label)
AGE_BANDS: tuple[tuple[float, str], ...] = (
    (28 / 365.25, "0-27 days"),
    (1, "28 days-<1 year"),
    (5, "1-4 years"),
    (15, "5-14 years"),
    (25, "15-24 years"),
    (35, "25-34 years"),
    (45, "35-44 years"),
    (55, "45-54 years"),
    (65, "55-64 years"),
    (75, "65-74 years"),
    (float("inf"), "75+ years"),
)


def age_band(age_years: float | None) -> str | None:
    if age_years is None:
        return None
    for upper, label in AGE_BANDS:
        if age_years < upper:
            return label
    raise AssertionError("unreachable")


class Pseudonymiser:
    def __init__(self, key: str | bytes):
        raw = key.encode() if isinstance(key, str) else key
        if len(raw) < MIN_KEY_BYTES:
            raise ValueError(f"pseudonymisation key must be at least {MIN_KEY_BYTES} bytes")
        self._key = raw

    def _token(self, kind: str, value: str) -> str:
        digest = hmac.new(self._key, f"{kind}:{value}".encode(), hashlib.sha256).digest()
        return base64.b32encode(digest).decode()[:16]

    def patient(self, patient_id: str) -> str:
        return f"P-{self._token('patient', patient_id)}"

    def encounter(self, encounter_id: str) -> str:
        return f"E-{self._token('encounter', encounter_id)}"
