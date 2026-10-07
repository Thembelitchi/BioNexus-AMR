#!/usr/bin/env python3
"""Verify every controlled-vocabulary entry against its authoritative source.

    python tools/verify_vocabulary.py [--dataset data/demo] [--report out.md]

Sources (downloaded once into --cache):
  * NCBI Taxonomy  - taxdb.bti/.btd from NCBI's BLAST database bucket on AWS
  * CARD ARO       - aro.owl from github.com/arpcard/aro
  * WHO ATC        - antimicrobials table of the AMR package (github.com/msberends/AMR)
  * LPSN status    - microorganisms table of the AMR package
  * PubMLST        - allele profiles bundled in the Bioconda `mlst` package
  * CLSI/EUCAST    - clinical_breakpoints table of the AMR package

With --dataset, every sequence type, organism, drug and gene used in the
dataset's CSVs is checked as well. Exits non-zero if anything fails.
Requires the `verify` extra (zstandard) to unpack the Bioconda package.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import struct
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bionexus import ontology  # noqa: E402
from bionexus.breakpoints import BREAKPOINTS, BREAKPOINT_SOURCE  # noqa: E402

NCBI_BUCKET = "https://ncbi-blast-databases.s3.amazonaws.com"
CARD_OWL = "https://raw.githubusercontent.com/arpcard/aro/master/aro.owl"
AMR_DATA = "https://raw.githubusercontent.com/msberends/AMR/main/data-raw/datasets"
BIOCONDA = "https://conda.anaconda.org/bioconda/noarch"

csv.field_size_limit(sys.maxsize)


@dataclass
class Report:
    sections: list[tuple[str, list[tuple[bool, str, str]]]] = field(default_factory=list)

    def section(self, title: str) -> list[tuple[bool, str, str]]:
        rows: list[tuple[bool, str, str]] = []
        self.sections.append((title, rows))
        return rows

    @property
    def failures(self) -> int:
        return sum(not ok for _, rows in self.sections for ok, _, _ in rows)

    def markdown(self) -> str:
        out = ["# Vocabulary verification report", ""]
        for title, rows in self.sections:
            passed = sum(ok for ok, _, _ in rows)
            out += [f"## {title} ({passed}/{len(rows)} verified)", "", "| | Entry | Evidence |", "|---|---|---|"]
            out += [f"| {'✅' if ok else '❌'} | {entry} | {evidence} |" for ok, entry, evidence in rows]
            out.append("")
        out.append(f"**{self.failures} failure(s).**")
        return "\n".join(out)


def fetch(url: str, cache: Path, name: str | None = None) -> Path:
    target = cache / (name or url.rsplit("/", 1)[-1])
    if not target.exists():
        print(f"downloading {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=600) as response, open(target.with_suffix(".part"), "wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
        target.with_suffix(".part").rename(target)
    return target


# ---------------------------------------------------------------- sources


def ncbi_names(cache: Path) -> dict[int, str]:
    """Scientific names for the taxids we need, from NCBI's taxdb index."""
    release = urllib.request.urlopen(f"{NCBI_BUCKET}/latest-dir", timeout=60).read().decode().strip()
    bti = fetch(f"{NCBI_BUCKET}/{release}/taxdb.bti", cache).read_bytes()
    btd = fetch(f"{NCBI_BUCKET}/{release}/taxdb.btd", cache).read_bytes()
    magic, count = struct.unpack(">II", bti[:8])
    if magic != 0x8739:
        raise ValueError("unexpected taxdb.bti format")
    records = struct.unpack(f">{count * 2}I", bti[24 : 24 + count * 8])
    taxids, offsets = records[0::2], records[1::2]
    wanted = {ref.ncbi_taxid for ref in ontology.ORGANISMS.values()}
    names = {}
    for i, taxid in enumerate(taxids):
        if taxid in wanted:
            end = offsets[i + 1] if i + 1 < count else len(btd)
            names[taxid] = btd[offsets[i] : end].decode().split("\t")[0]
    names[-1] = release  # type: ignore[assignment]
    return names


def card_labels(cache: Path) -> dict[str, str]:
    ns = {"owl": "http://www.w3.org/2002/07/owl#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}
    labels = {}
    for cls in ET.parse(fetch(CARD_OWL, cache)).getroot().findall("owl:Class", ns):
        label = cls.find("rdfs:label", ns)
        about = cls.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about") or ""
        if label is not None and "/ARO_" in about:
            labels[about.rsplit("/ARO_", 1)[1]] = label.text or ""
    return {f"ARO:{key}": value for key, value in labels.items()}


def amr_table(cache: Path, name: str) -> list[dict[str, str]]:
    path = fetch(f"{AMR_DATA}/{name}.txt", cache, f"amr-{name}.txt")
    return list(csv.DictReader(open(path, encoding="utf-8"), delimiter="\t"))


def pubmlst_profiles(cache: Path) -> dict[str, set[int]]:
    import zstandard  # optional dependency, see the `verify` extra

    repodata = json.loads(fetch(f"{BIOCONDA}/repodata.json", cache, "bioconda-noarch.json").read_text())
    packages = {**repodata.get("packages", {}), **repodata.get("packages.conda", {})}
    filename, _ = max(((k, v) for k, v in packages.items() if v["name"] == "mlst"), key=lambda kv: kv[1].get("timestamp", 0))
    archive = zipfile.ZipFile(fetch(f"{BIOCONDA}/{filename}", cache))
    inner = next(n for n in archive.namelist() if n.startswith("pkg-") and n.endswith(".tar.zst"))
    stream = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(archive.read(inner)))
    profiles: dict[str, set[int]] = {}
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            match = re.fullmatch(r".*db/pubmlst/([^/]+)/\1\.txt", member.name)
            if match and member.isfile():
                lines = tar.extractfile(member).read().decode().splitlines()[1:]
                profiles[match[1]] = {int(line.split("\t")[0]) for line in lines if line[:1].isdigit()}
    profiles[""] = {filename}  # type: ignore[assignment]
    return profiles


# ---------------------------------------------------------------- checks


def dataset_usage(path: Path | None) -> tuple[set[tuple[str, int]], set[str], set[str], set[str]]:
    sequence_types, organisms, drugs, genes = set(), set(), set(), set()
    if path is None:
        return sequence_types, organisms, drugs, genes
    for csv_path in sorted(path.glob("*.csv")):
        for row in csv.DictReader(open(csv_path, encoding="utf-8-sig")):
            if row.get("Organism"):
                ref, _ = ontology.resolve_organism(row["Organism"])
                organisms.add(ref.species)
                st = ontology.resolve_sequence_type(row.get("Strain_Subtype"), ref)
                if st:
                    sequence_types.add((st.scheme, st.st_number))
            for column in ("Antibiotic", "Treatment"):
                if row.get(column):
                    drugs.add(ontology.resolve_antibiotic(row[column]).name)
            if row.get("GeneDetected") and not ontology.is_wild_type(row["GeneDetected"]):
                genes.add(ontology.resolve_gene(row["GeneDetected"]).symbol)
    return sequence_types, organisms, drugs, genes


def verify(cache: Path, dataset: Path | None) -> Report:
    report = Report()
    used_sts, used_orgs, used_drugs, used_genes = dataset_usage(dataset)
    organisms = sorted(set(ontology.ORGANISMS.values()), key=lambda r: r.species)
    drugs = sorted(set(ontology.ANTIBIOTICS.values()), key=lambda r: r.name)
    genes = sorted(set(ontology.GENES.values()), key=lambda r: r.symbol.lower())

    names = ncbi_names(cache)
    rows = report.section(f"NCBI Taxonomy IDs (NCBI taxdb release {names[-1]})")
    for ref in organisms:
        got = names.get(ref.ncbi_taxid)
        rows.append((got == ref.species, f"{ref.species} → {ref.ncbi_taxid}", f"NCBI name: {got!r}"))

    microbes = {r["fullname"].lower(): r for r in amr_table(cache, "microorganisms")}
    rows = report.section("Species names and genera (LPSN via AMR package)")
    for ref in organisms:
        r = microbes.get(ref.species.lower())
        ok = r is not None and r["status"] == "accepted" and r["genus"] == ref.genus
        rows.append((ok, f"{ref.species} (genus {ref.genus})", f"status={r['status'] if r else 'absent'}, LPSN {r['lpsn'] if r else '-'}"))

    aro = card_labels(cache)
    rows = report.section("Resistance determinants (CARD ARO)")
    for ref in genes:
        label = aro.get(ref.aro_id)
        rows.append((label == ref.name, f"{ref.symbol} → {ref.aro_id}", f"ARO label: {label!r}"))

    atc = {r["ab"]: r for r in amr_table(cache, "antimicrobials")}
    rows = report.section("Antimicrobials (WHO ATC via AMR package)")
    for ref in drugs:
        r = atc.get(ref.amr_code)
        codes = r["atc"].split(",") if r else []
        rows.append((ref.atc_code in codes, f"{ref.name} → {ref.atc_code} ({ref.amr_code})", f"AMR package: {r['name'] if r else 'absent'} {codes[:3]}"))

    profiles = pubmlst_profiles(cache)
    rows = report.section(f"MLST schemes and sequence types (PubMLST via Bioconda {next(iter(profiles['']))})")
    for ref in organisms:
        if ref.mlst_scheme:
            known = profiles.get(ref.mlst_scheme)
            rows.append((known is not None, f"{ref.species} → scheme `{ref.mlst_scheme}`", f"{len(known or [])} profiles"))
    for (scheme, clone), st in sorted(ontology._CLONE_TO_ST.items()):
        rows.append((st in profiles.get(scheme, set()), f"{clone} → {scheme} ST{st}", "ST present" if st in profiles.get(scheme, set()) else "ST absent"))
    for scheme, st in sorted(used_sts):
        rows.append((st in profiles.get(scheme, set()), f"dataset: {scheme} ST{st}", "ST present" if st in profiles.get(scheme, set()) else "ST absent"))

    rows = report.section(f"Breakpoints ({BREAKPOINT_SOURCE})")
    reference = {}
    for r in amr_table(cache, "clinical_breakpoints"):
        if r["guideline"] == BREAKPOINT_SOURCE and r["method"] == "MIC" and r["type"] == "human" and r["uti"] == "FALSE" and r["breakpoint_S"] and r["breakpoint_R"]:
            reference.setdefault((r["mo"], r["ab"]), set()).add((float(r["breakpoint_S"]), float(r["breakpoint_R"])))
    for (group, drug), (s, r_) in sorted(BREAKPOINTS.items()):
        options = reference.get((group, drug), set())
        rows.append(((s, r_) in options, f"{group} / {drug}: S≤{s:g}, R≥{r_:g}", f"AMR package: {sorted(options) or 'absent'}"))

    if dataset is not None:
        rows = report.section(f"Dataset coverage ({dataset})")
        rows.append((bool(used_orgs), "organisms used", ", ".join(sorted(used_orgs))))
        rows.append((bool(used_drugs), "antimicrobials used", ", ".join(sorted(used_drugs))))
        rows.append((bool(used_genes), "genes used", ", ".join(sorted(used_genes))))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "bionexus-vocabulary")
    parser.add_argument("--dataset", type=Path, help="directory of CSVs to check usage against the sources")
    parser.add_argument("--report", type=Path, help="write the markdown report here")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    report = verify(args.cache, args.dataset)
    text = report.markdown()
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
