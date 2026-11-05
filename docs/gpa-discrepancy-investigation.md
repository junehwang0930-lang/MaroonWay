# GPA discrepancy investigation and safe handling

## Scope and actual available evidence

The supplied Spring 2026 Arts & Sciences PDF (291 pages, SHA-256 `d30c23460553b0adbfe6d02e51f536b16a0e54e50d0ad895db884f9f6ecee270`) and the original 313-record pilot database are present in this cloud checkout. The requested latest `data/import_reviews/` CSV is **not present**. The 313-record pilot DB is not the later 2,364-section all-subject import. We did not migrate, reimport, revalidate, or modify the real database or its old CSV/history files.

The earlier 29 items represented 23 GPA flags, four missing initials, and two ASCII-only Unicode-name parser failures. The name parser has since been corrected: original-PDF re-parsing finds 2,364 undergraduate sections and no name-parser rejections. Under the user-approved inclusive absolute tolerance **0.005**, there are **22 current GPA mismatches**. BIOL-491-500 has a 0.002 difference and is a numerical match under that policy, not a verified explanation of why the source differs. The historical 23-case table is preserved in [the earlier source report](spring-2026-import-review.md).

## What is and is not established

- All 23 historical reported GPAs, A/B/C/D/F counts, A–F totals, calculated simple averages, differences and source page numbers are in the earlier report and the new investigation CSV when `--include-section BIOL-491-500` is supplied.
- Nine current mismatches display 0.000 in the PDF itself. A positive letter-grade count does not authorize replacing the official GPA with 4.000. Zero GPA alone is not an error; a row whose simple average is also zero can match normally.
- PHYS-291-512: page 251, A=9, B=C=D=F=0, A–F total=9, reported=0.000, count-based average=4.000, absolute difference=4.000. **Zero-credit eligibility and the GPA treatment of actual registrations are unverified.**
- ANTH-484-502: page 6, A=11, F=1, other counts=0, total=12, reported=3.636, simple average=3.666667, difference≈0.030667. **Variable credit is not established by the course number.**
- BIOL-491-500: page 41, A=18, B=2, other counts=0, total=20, reported=3.902, simple average=3.900, difference=0.002. Within the current tolerance; the reason for the small source difference remains unknown.
- COMM-210-502, ENGL-313-500, HIST-280-901, PBSI-315-501, PBSI-316-500: original reported values and counts are retained. Changing the denominator until a value looks close is **not evidence** of a missing student. No count or denominator was changed.
- Four missing-initial names remain unresolved. No candidate professor identity or initial was invented.

Official catalog, Student Rules, and Registrar access failed through the enforced network proxy (CONNECT 403). **Credit hours are unknown for all 23 historical cases; no zero/variable credit cause or official decimal/truncation rule was verified.** See [access evidence and course-by-course verification checklist](gpa-official-evidence.md). Candidate links are not retrieved evidence. Credit-weighted GPA can differ mathematically from a student-count average, but that general possibility does not establish any section's cause.

## Classification result

For the explicit historical 23-case cohort:

| Status | Cases | Meaning |
| --- | ---: | --- |
| matches_reported | 1 | BIOL-491-500 is within the approved 0.005 policy only |
| unexplained_mismatch | 22 | Source comparison differs beyond tolerance; cause unknown |
| possible_variable_credit | 0 | No verified course-credit evidence available |
| possible_zero_credit | 0 | No verified zero-credit evidence available |
| source_or_parser_issue | 0 | No current GPA-source/parser fault demonstrated |
| verified_exception | 0 | No sufficient official explanation verified |

The two corrected Unicode parser defects are documented historical parser issues, not explanations of GPA differences. `possible_*` classifications require an official citation/quotation about course credit, but do not assert actual section registration details. A reviewer must provide sufficient evidence and explicit confirmation before recording `verified_exception`; even that status does not change public eligibility.

## Data design

`gpa_review.py` owns an **opt-in, separate migration** and investigation table. Original `grade_sections` columns and `public_grade_sections` SQL are not changed. Reported GPA/counts remain source evidence. Computed GPA is a simple A–F count average, never an official replacement; zero A–F total yields NULL/N/A.

The sidecar review stores the source snapshot, computed values, classification, note, evidence, review time and confirmation. Reviews are append-only; an identical review for the same source snapshot is deduplicated. A new review does not overwrite prior notes. A current-review view ignores stale source snapshots. Migration backs up an existing SQLite database first, runs transactionally and is safe to repeat. It is not called by API startup, import or ordinary reporting.

No investigation status grants publication. The existing public view still requires its original audit checks and remains the only API source.

## Read-only report command (safe for existing DB)

From the repository root:

```powershell
py scripts/investigate_gpa.py --pdf reports/spring_2026_arts_and_sciences.pdf --include-section BIOL-491-500
```

This reads PDF bytes once, validates header metadata and writes a new UUID/timestamp CSV under `data/gpa_investigations/`. It never opens a DB. Default selection is the current mismatches; the explicit BIOL option retains the historical within-tolerance case for comparison. `--review-csv path/to/review.csv` can attach original review-item numbers and messages, with multiple entries for the same section kept separate. Do not assume that a review CSV missing from the cloud does not exist locally.

CSV includes the requested identity, source page, reported/calculated/difference/total, status/note/evidence columns plus original A/B/C/D/F counts, SHA-256, source URL, unknown credit metadata, timestamp and investigation-completion flag. It sorts descending by difference; non-calculable rows are last. Existing files are not overwritten. `investigation_complete=False` distinguishes numerical calculation from completed causal verification.

## Local database adoption

First inspect the code, test on a **copy** of your local database, and review the generated report. Do not delete or reset your actual DB. The separate migration is explicitly invoked; no real database was changed in this task. Detailed function/CLI instructions and test outcomes are recorded below after implementation verification.

## Publication recommendation

Keep the 22 unexplained mismatches quarantined under existing checks. Do not use a `possible_*` tag or a manually entered name as public approval. Preserve official reported GPA in all future displays; label any calculated value “A–F student-count simple average.” No frontend redesign or API restriction removal is included.

## Functions, SQL and explicit adoption examples

| File/function | Beginner explanation |
| --- | --- |
| `gpa_review.calculate_gpa(a,b,c,d,af_total)` | Calculate an A–F headcount average; no A–F students means `None`, not zero |
| `gpa_review.assess_gpa(row,evidence=None)` | Return diagnostic values/status without reading/writing a DB; invalid count totals do not become numeric matches |
| `gpa_review.migrate_reviews(db_path)` | Explicitly back up an existing DB and transactionally add the separate schema once; does not call the main migration |
| `gpa_review.record_review(db_path,section_id,...)` | Add a reviewer decision/note/evidence tied to an exact source snapshot; identical content returns the existing ID |
| `scripts/investigate_gpa.generate_report(...)` | Produce a uniquely named, sorted PDF-only CSV; no SQLite operations |
| `gpa_reviews` | Append-only investigation history with source snapshot, values, note/evidence, timestamp, confirmation and optional credit metadata |
| `gpa_review_migrations` | Separate version tracking; existing main migration versions remain unchanged |
| `latest_gpa_reviews` | Read the latest review alongside original source data; changed source snapshots mask review values and set `review_stale=1` |

Only on a separately prepared test copy, after stopping writers and preserving the original:

```powershell
py -c "from gpa_review import migrate_reviews; print(migrate_reviews('data/maroonway-review-copy.db'))"
```

The named DB must already exist. Expected first run: a unique `maroonway-review-copy.before-gpa-v1-<timestamp>-<uuid>.db` backup and the new review table/view; second run: `None`, no new backup or duplicate schema. Original grade rows and public-view SQL must be identical. This example was not run against the real DB.

After reviewing the correct row ID in the copy, an unresolved note can be stored with:

```python
from gpa_review import record_review
review_id = record_review('data/maroonway-review-copy.db', section_id,
                          note='Source row checked; cause remains unconfirmed.')
```

Do not execute an undefined example `section_id`; substitute a verified ID only after inspection. `record_review` does not silently migrate the database. Calling the same review with identical content deduplicates it; new notes create new history.

Official-credit evidence is an explicit human-supplied dictionary with `official=True`, `source_url`, `excerpt`, and `credit_type` (`variable` or `zero`). The software does not independently authenticate those statements or fetch the URL. Never set `official=True` merely because a URL looks official. `verified_exception` additionally requires an explicit requested status, nonempty human note, `confirmed=True`, and an evidence `explanation` establishing the actual cause. No such exception was recorded in this investigation. Parser/source classifications similarly require documented extraction evidence.

## Tests and protected inputs

- Initial new regressions failed before implementation. New tests cover match/small/large/zero GPA, zero denominator, invalid counts, official-evidence requirements for credit hypotheses, migration backups and repeat safety, unchanged source rows/public-view SQL/import histories, stale snapshots, deduplication, append-only enforcement, explicit verified exceptions, connection closure, unique report paths, sorting and separate historical review items.
- Python 3.12 and 3.14: **69 tests passed**, including all prior 55. Node: **4 tests passed**. Strict runner checks resource warnings and cleanup errors.
- The original data/report file hashes were compared against their pre-task values; new report output is additional evidence, not a replacement. No production migration was executed.
- Windows/Python 3.14 is covered by the repository's cross-platform CI; check this change's specific run for its observed result rather than inferring Windows success from Linux.

## Remaining external prerequisite

To complete official causal verification, allow HTTPS access to `catalog.tamu.edu`, `student-rules.tamu.edu`, and `registrar.tamu.edu` in the cloud environment, or supply the relevant official course/rule documents. We still need the actual latest Import Review CSV to reconcile the user's local item IDs exactly. Until then, credit information remains unknown and section causes remain unconfirmed.
