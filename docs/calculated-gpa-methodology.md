# MaroonWay GPA (A-F based)

## Methodology

MaroonWay's primary metric is a student-count average:

`(4*A + 3*B + 2*C + D) / (A+B+C+D+F)`

The published A–F total must equal that denominator. Zero A–F students means **NULL/N/A**, not a GPA of zero. An all-F section with a positive A–F total legitimately has a calculated GPA of zero.

The value is labeled **MaroonWay GPA (A-F based)** in search and comparison. TAMU reported GPA remains a separate, unchanged source value. The API and public CSV expose both values, absolute difference, and a discrepancy flag. Calculated values are computed by a SQL view, not written over original grade columns. UI rounding is for display only.

A discrepancy means the absolute difference exceeds the existing inclusive 0.005 tolerance. Smaller differences remain visible numerically without receiving the discrepancy warning. The flag does not assert that TAMU made an error. Unavailable comparisons (no calculated or reported value) have a NULL difference/flag rather than claiming agreement.

TAMU's reported GPA can use credit-hour weighting. Variable- or zero-credit registrations can produce different results from an A–F headcount average. We have not verified those circumstances for each historical section. MaroonWay GPA is historical grade information, not a guaranteed measure of difficulty, instructor quality, or a student's future result. Future Top 3 schedule recommendations must use this same A–F formula consistently and also consider availability, conflicts and user constraints; no schedule-recommendation feature is added in this change.

## Publication policy

Only a GPA discrepancy, or the absence of letter-graded students in an otherwise verified section, ceases to be a blocker. Source PDF bytes/checksum, report metadata, original fields/page, every count, A–F sum and enrollment totals still require verification. Negative/non-integer counts, malformed values, source conflicts, duplicate identities, uncertain parsing and missing instructor initials remain blocked.

An N/A reported GPA is expected for a verified zero-A–F section; positive-A–F sections missing a reported GPA remain blocked. Out-of-range or nonfinite reported GPA values remain integrity failures. The official GPA is never replaced, even when it is 0.000.

The main schema version advances from 2 to 3. The migration changes computed/public-view infrastructure only, with a pre-migration SQLite backup and transactional rollback. Original section rows, IDs, reported values, manual-review columns, source documents, imports and historical validations remain intact. GPA investigation tables are unaffected.

Old audits are not silently reinterpreted as permission to publish new rows. A fresh validation under policy 3 is required and separately recorded, using the preserved PDF bytes. Old audit messages remain available, including the original GPA discrepancy. The audit's publication result is distinct from its warning list.

## Safe local application

Do not delete the database, rebuild section records, or reimport the full report merely to change policy. First stop import/review writers and prepare a new test copy using SQLite's backup API. Existing backups must not be overwritten. Inspect and test the upgrade on that copy before using the original.

Detailed copy verification and executable local commands are recorded below after the implementation tests. The cloud's actual `data/maroonway.db`, PDFs and existing histories were not migrated for this task.

## Beginner-friendly change map

| File | What changed and why |
| --- | --- |
| `storage.py` | Adds policy v3, its backup and fresh-audit marker. `blocking_issues` separates GPA warnings from true integrity failures; `record_validation` appends new policy evidence without altering old audits. |
| `pipeline.py` | Verifies the same PDF bytes it preserves; uses the new audit recorder and exports both GPA metrics. Original parse warnings and source columns stay intact. |
| `api.py` | Returns both GPA values, absolute difference and discrepancy; sorts by calculated GPA (N/A last), with stable College/section ties. |
| `frontend/app.js`, `frontend/index.html` | Primary calculated label in search and comparison; original GPA, difference and discrepancy remain visible. Explains weighting and difficulty limits. |
| `scripts/analyze_gpa.py` | Uses calculated GPA for the primary listing/sort and labels the separate reported value. Existing weighted course/instructor summaries already calculate from counts. |
| Tests | New source/publication and UI regressions; existing test methods retained. Sidecar migration version assertion reflects the new main policy version without changing its own schema. |

`public_grade_sections` computes the new fields. No duplicated calculated column was added to `grade_sections`. `grade_validation_policies` links only fresh validation IDs to policy 3; historical audits remain unstamped and cannot silently authorize new publication. The discrepancy flag is derived from the audit's exact fraction comparison, so a SQL floating-point rounding artifact cannot change the threshold decision.

## Windows PowerShell: first test a copy

From the project root, stop API/import/review writers and close Excel files using generated CSVs. Pull the code and install requirements. Then create a new SQLite test copy; this snippet refuses to overwrite a pre-existing copy:

```powershell
git pull origin main
py -3.14 -m pip install -r requirements.txt
@'
from contextlib import closing
from pathlib import Path
import sqlite3
source = Path('data/maroonway.db')
target = Path('data/maroonway-gpa-test.db')
if not source.is_file():
    raise SystemExit('Original database is missing; do not initialize a replacement.')
if target.exists():
    raise SystemExit('Test copy already exists; choose a NEW filename, do not overwrite it.')
with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True)) as src:
    with closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
print(target)
'@ | py -3.14 -
py -3.14 pipeline.py revalidate --db data/maroonway-gpa-test.db --pdf reports/spring_2026_arts_and_sciences.pdf
py -3.14 -W error::ResourceWarning tests/run_checks.py
node tests/test_frontend.cjs
```

The test-copy command adds audit history and a new public CSV snapshot beside that copy; it does not import new sections. The first policy migration backs up the copy before its schema update. Repeated migration is a no-op, while explicit revalidation creates a new audit each time. Existing source rows and old audit entries remain unchanged. For other terms/colleges, supply their verified metadata/PDF options; do not relabel the Spring 2026 PDF.

After inspecting the copy and its results, the same explicit upgrade can be applied locally to the original. First archive any existing `public_grade_sections.csv` to a unique timestamped name and close CSV readers. It is a generated current snapshot and will be refreshed; immutable import/validation CSVs are not replaced. Keep the database backups.

```powershell
py -3.14 pipeline.py revalidate --db data/maroonway.db --pdf reports/spring_2026_arts_and_sciences.pdf
py -3.14 -m uvicorn api:app --reload
```

The new API returns 503 on an old v2 database because the computed fields are not installed. After migration but before a fresh validation, sections are deliberately unpublished. If a source PDF is missing or cannot be verified, keep those rows blocked; do not bypass the audit marker. If a CSV reader prevents snapshot export, close it and rerun the explicit revalidation; source rows are not replaced.

## Observed verification

All real-data operations below used temporary databases; the original DB, backup, PDF, existing CSVs and histories remained byte-for-byte unchanged.

- Temporary copy of the actual 313-record DB: migration initially published zero rows until fresh validation. Revalidation published **311**, retaining **2 missing-initial blockers**. Every original source/manual-review value and every pre-existing history entry matched before/after; the only audit change was appended records. SQLite integrity and foreign keys passed.
- A separate full-source PDF test produced **2,364 sections / 2,360 publishable sections**, including **22 discrepancy warnings**. The four missing-initial sections remained blocked. This did not add those sections to the real 313-row DB.
- PHYS 291-512: reported **0.000**, calculated **4.000**, absolute difference **4.000**, discrepancy flagged and source-verified publication allowed.
- Python 3.12 and 3.14: **80 tests passed**. JavaScript: **9 tests passed**. Coverage includes normal matches, mismatches, reported zero, zero-A–F NULL, expected N/A reported GPA at zero-A–F, negative/inconsistent counts, missing initials, invalid reported GPA, conflicts, old-audit protection, repeat migration, precise tolerance boundaries, retained warning evidence and UI values in both directions.
- A temporary real HTTP API test verified calculated ordering, reported 0.000 preservation, zero-A–F JSON nulls, and the frontend label. Independent read-only review found no blocking regressions.
- Windows/Linux cross-platform CI is run on the committed change; its observed result is linked in the completion report.

Older investigation documents describe the policy at their creation time. They remain historical evidence. This document supersedes earlier advice that a GPA discrepancy alone must block publication; it does not supersede any source, count, metadata or conflict protection.
