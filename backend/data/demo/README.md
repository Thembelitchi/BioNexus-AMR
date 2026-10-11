# BioNexus demo dataset: South African hospital AMR surveillance

**Synthetic data.** Every patient, specimen, result and facility here is
generated. Facility names carry a "(demo)" suffix and do not refer to real
hospitals. Do not use this dataset for clinical or epidemiological decisions.

Regenerate it byte-for-byte with:

```bash
python tools/generate_demo_dataset.py --seed 2025
```

## At a glance

| | |
|---|---|
| Patients | 600 |
| Isolates | 673 (197 sequenced) |
| Susceptibility results | 7,391, interpreted with **CLSI 2025**: 6,765 MICs and 626 disk diffusion zones (GDH) |
| ADT events | 647 admissions and transfers |
| Facilities | 4 fictional hospitals in Gauteng, KwaZulu-Natal and the Western Cape |
| Period | 1 July – 31 December 2025 (timestamps in SAST, UTC+02:00) |

| Organism | Isolates | Lab flag | Flagged |
|---|---|---|---|
| *Klebsiella pneumoniae* | 215 | CRE | 27% |
| | | ESBL (non-CRE) | 40% |
| *Staphylococcus aureus* | 135 | MRSA | 34% |
| *Escherichia coli* | 114 | ESBL | 25% |
| | | CRE | 6% |
| *Acinetobacter baumannii* | 64 | CRAB | 91% |
| *Enterobacter cloacae* | 61 | CRE | 18% |
| *Pseudomonas aeruginosa* | 42 | CRPA | 33% |
| *Enterococcus faecium* | 42 | VRE | 24% |

These rates include the planted outbreaks below, so they are higher than
the background rates. For example, 8 of the 10 VRE isolates are the
haematology-oncology outbreak.

## What is real and what is synthetic

**Verified against authoritative sources.** `python tools/verify_vocabulary.py --dataset data/demo`
re-checks all of this:

* **Organisms:** NCBI Taxonomy IDs, checked against NCBI's own taxdb files. Species
  names are currently accepted (LPSN).
* **Resistance genes:** CARD ARO accessions, matched by label in `aro.owl`.
* **Antimicrobials:** WHO ATC codes.
* **Sequence types:** every ST used exists in PubMLST, with schemes named as
  the `mlst` tool names them (for example *E. coli* uses the Achtman scheme).
* **Interpretation:** every S/I/SDD/R follows CLSI M100 2025 MIC or disk
  breakpoints, as distributed in the AMR package. `tests/test_demo_dataset.py`
  re-interprets all 7,391 results.

**Grounded in published South African surveillance, qualitatively.** The
patterns below follow what the NICD (GERMS-SA and AMR reference laboratory
reporting) and the South African literature describe. The exact proportions
are illustrative choices, not estimates.

* Among carbapenemase-producing Enterobacterales, OXA-48-like enzymes
  (mostly OXA-181) dominate, NDM is second, and KPC is rare.
* *K. pneumoniae* is the leading CPE species. ST307 is a prominent
  high-risk clone and commonly co-carries CTX-M-15.
* Carbapenem-resistant *A. baumannii* with OXA-23 in international clone II
  (Pasteur ST2) is endemic in adult ICUs.
* MRSA lineages include ST612, ST5, ST239 and ST36. Vancomycin-resistant
  *S. aureus* is absent.
* Neonatal units suffer *K. pneumoniae* bloodstream outbreaks.
* Co-trimoxazole resistance is high, consistent with widespread HIV
  prophylaxis.
* Patients move from district to tertiary hospitals through the referral
  system.

**Literature-based, not machine-verified.** The typical genetic carriers
(OXA-181 and NDM-5 on IncX3 plasmids, OXA-48 on IncL, vanA on Tn1546, KPC
on Tn4401, OXA-23 on Tn2006, VIM-2 and GES-5 in class 1 integrons, mcr-1 on
IncI2) are well documented, but CARD does not encode them, so they could
not be checked automatically.

**Laboratory realism.**
* Panels follow automated broth microdilution reporting ranges at three
  hospitals. The district hospital (GDH) reports disk diffusion zones
  instead, as many smaller South African laboratories do, except for
  colistin, oxacillin and vancomycin, where CLSI has no reliable disk
  breakpoint and an MIC is reported.
* Agents to which a species is intrinsically resistant are not reported.
* Reserve agents (ceftazidime-avibactam, colistin, tigecycline) are
  cascade-reported only for carbapenem-non-susceptible isolates. The
  exception is the mcr-1 case, which carries a reference-laboratory
  colistin MIC.
* OXA-48-like producers can test meropenem-susceptible while
  ertapenem-resistant, as they do in practice. This applies to 14 of the 50 in
  the dataset.
* Sequencing is selective, as in practice: most carbapenem-non-susceptible
  Enterobacterales and *P. aeruginosa*, all VRE, half of MRSA, most ICU
  CRAB, and a small random sample of the rest.

## Planted scenarios

`scenarios.json` is the machine-readable ground truth. The test suite
asserts that the analytics recover every scenario.

| ID | Scenario | Where | Recovered by the analytics as |
|---|---|---|---|
| S1 | Neonatal outbreak, OXA-181 *K. pneumoniae* ST307 (14 neonates) | GAH Neonatal ICU, Aug–Sep | 14-isolate same-ward cluster |
| S2 | Endemic CRAB, OXA-23 ST2 | Adult ICUs, all tertiary sites | Clusters in GAH, KRH and WTH adult ICUs |
| S3 | NDM-5 on an IncX3 plasmid across *E. coli* ST410, *K. pneumoniae* ST15 and *E. cloacae* ST78 | KRH Surgical, Oct–Nov | Cross-genus HGT signal with the shared IncX3 replicon |
| S4 | VRE (vanA) *E. faecium* ST80 (8 patients) | WTH Haematology-Oncology, Nov–Dec | 8-isolate cluster |
| S5 | Referral importation of OXA-181 *K. pneumoniae* ST307, then onward ICU spread | GDH Medical → GAH Adult ICU, Sep–Oct | ICU cluster plus GDH→GAH transfer edges; GAH Adult ICU ranks first on PageRank |
| S6 | MRSA ST612 (6 patients) | GAH Burns, Jul–Aug | 6-isolate cluster |
| S7 | Sentinel: KPC-2 *K. pneumoniae* ST258 (uncommon locally; possible importation) | WTH Adult ICU | Gene present |
| S8 | Sentinel: plasmid-mediated colistin resistance (mcr-1) in *E. coli* | KRH Medical | Gene present, colistin R |

Without any sequencing, laboratory-phenotype clustering
(`bionexus clusters --basis phenotypic`) still recovers S1, S4, S5 and S6.

136 isolates (36 of them on meropenem) come from patients prescribed an
agent the isolate tests resistant to. These are intentional
antimicrobial-stewardship alert cases.

## Files

| File | Grain | Key columns |
|---|---|---|
| `clinical.csv` | One row per isolate × antimicrobial | PatientID, EncounterID, SampleID, Date, Facility, FacilityName, Province, Ward, Sex, AgeYears, AdmitDate, DischargeDate, Specimen, Treatment, Organism (with lab flags), Antibiotic, MIC, Result, Guideline |
| `genomic.csv` | One row per determinant call (or "None") for sequenced isolates | PatientID, SampleID, Organism, Strain_Subtype, GeneDetected, Mechanism, MGE_Type, MGE_Replicon |
| `movements.csv` | One row per admission or transfer | PatientID, EncounterID, EventType, Facility, FacilityName, Province, Ward, Timestamp |
| `scenarios.json` | Ground truth for planted scenarios | expected cluster, HGT, transfer and gene signals |

Identifiers in the CSV files are synthetic and stored as generated. The
public dashboard snapshot was exported with pseudonymisation switched on,
using the published demo key `bionexus-public-demo-key-not-secret`. That key
is public by design; a real deployment must use its own secret key
(`BIONEXUS_PSEUDONYMISATION_KEY`).

Load it with:

```bash
bionexus ingest --clinical data/demo/clinical.csv --genomic data/demo/genomic.csv --movements data/demo/movements.csv
```

## Review checklist by role

| Role | What to review | Automated evidence |
|---|---|---|
| Tech Lead / Graph Architect | Facility→Ward→LocationEvent model; ward keys are unique per facility; idempotent load; analytics cost at scale | `tests/test_integration.py`; the demo loads to 13,092 relationships with no rejected rows |
| Bioinformatics Backend Engineer | Genomic columns follow `mlst` scheme names and `bla`-prefixed gene symbols, but converters from real caller output are not built yet; MGE fields; ADT feed | `tests/test_etl.py`; ST and scheme checks in the verifier |
| Front-End Visualization Developer | 4 facilities, 17 wards, 47 inter-ward transfers and 229 genomic ward links give a non-trivial network; scenarios give known shapes to render | `scenarios.json`; `/analytics/*` endpoints |
| Medical Ontologist | Vocabulary provenance; CLSI interpretation; genotype→phenotype rules; intrinsic resistance; lab flags; clinical coherence (ages, dates, wards) | `tools/verify_vocabulary.py`; `tests/test_demo_dataset.py` |

Items that need a human expert, because no automated check can settle them:
* whether the illustrative proportions suit the intended audience;
* whether CLSI (rather than EUCAST) matches the target laboratories;
* that the literature-based carrier associations are acceptable.
