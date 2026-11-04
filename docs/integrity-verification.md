# Integrity fixes and verification

Verified against the user-supplied database and Spring 2026 Arts & Sciences PDF on 2026-11-04. Database/PDF/audit artifacts remain local and ignored by Git; the code and this report are versioned.

## Changes and regression evidence

Every fix was preceded by a failing regression test, then verified with the full Python suite. The original seven parser tests are unchanged.

| Problem | Cause and change | Regression coverage |
| --- | --- | --- |
| Negative counts accepted | Added explicit nonnegative checks for all 12 count fields; review-only raw rows remain preserved. Public queries require a matching, successful audit snapshot. | Each negative field, balanced negative totals/GPA, edited stored values, invalid legacy types, API and console publication filters |
| Instructor name lost at line breaks | Buffer until the next section or page boundary; preserve original lines. Known total rows end a section; unknown trailing text is reviewed rather than discarded. | Split initial, multiline surname, percentages, official total rows, uncertain suffixes, duplicate identities; original seven tests |
| Wrong or unknown report metadata | Validate each nonblank page/header before DB writes: Grade Distribution, expected year/semester and College. Only six Spring/Fall terms in the requested range are accepted. Uncoded colleges require a reviewed code/name mapping. | Wrong/unknown term, year, college, GPA report, Summer/range boundaries, conflicting repeated headers, valid page masking bad/headerless pages, arbitrary College code |
| Search response races | Abort prior fetch and use a generation guard after JSON completion and on errors. | Out-of-order success, stale failure, delayed JSON, current failure and prior cancellation: all four failed on old JS and pass now |
| Review history overwritten | Append-only SQLite import/row/review/conflict/audit records; unique per-run CSV paths; preserved PDF bytes/hash. Legacy CSVs remain untouched; a separate atomic public snapshot refreshes even to zero rows. | Repeat imports, immutable legacy files, unique runs, conflicting sources, zero-row public snapshots, metadata failure leaving DB untouched |

Nonfinite GPA tokens are retained as raw parse-review items rather than crashing a whole import. Existing PDFs cannot be overwritten by the download command. SQLite backups use the SQLite backup API. Migration preserves extra manual-review columns, IDs, indexes, triggers, dependent views, autoincrement sequence, and foreign keys; unknown constraints abort safely.

The all-subject migration removes the old STAT/MATH constraint without discarding rows. Section identity continues to include College. Manual review accepts an optional College CSV column and aborts ambiguous cross-college matches.

## Actual 313-record audit

The supplied DB contained 259 MATH and 54 STAT rows. A working copy was migrated and repeatedly audited; the uploaded file was left unchanged.

- Original records: **313**; after migration/audits: **313**.
- Passed all current row/source checks: **311**.
- Needs review and excluded from public API/CSV: **2**.
- Flagged sections: **STAT 201-504 and STAT 201-507**, source PDF **page 281**, instructor text **HERNANDEZ**. The source itself lacks a final initial. No name was guessed, repaired, or promoted from a candidate manual match.
- All original column values are identical before/after, including IDs, raw text, source fields, professor links, and the three manual-review columns.
- SHA-256 of ordered original rows (Python `repr` of `SELECT * FROM grade_sections ORDER BY id`) before and after: `0b570d5e958050e1dc8af5a8648ff0f8a42e97c0bbddde5a92ebb70c195c1cd1`.
- `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: no violations.
- Original supplied DB SHA-256: `4ec67a260ea4d39bce517c9ed5bb1415a3f47d4bb58d0e5730175c611e2d7415`.
- Supplied 291-page PDF SHA-256: `d30c23460553b0adbfe6d02e51f536b16a0e54e50d0ad895db884f9f6ecee270`.

The migrated DB file has a different file hash because it contains new audit tables; the original data rows have not changed. Each audit's detailed CSV is under `data/validation_runs/`, and current validated export is `data/public_grade_sections.csv`.

## Verification commands and outcomes

```bash
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
python -m pip check
python pipeline.py revalidate --pdf reports/spring_2026_arts_and_sciences.pdf
```

- Python: **43 passed**, including the original 7; no skipped tests.
- Node: **4 passed**, no skipped tests. Uses the real frontend event handler with a small DOM harness and deferred network responses, not a full browser.
- Dependency check: no broken requirements.
- Real HTTP smoke: started Uvicorn temporarily; `/app/`, JS asset, `/docs`, OpenAPI and course API returned expected responses. STAT 201 returned 6 validated sections and excluded 504/507; Summer returned 400; an unpopulated earlier-term course returned 404.
- Separate temporary DB real-PDF import: **2,362 undergraduate sections across 44 subjects**, **2,335 public rows**, **29 review issues**. The existing 313-row DB was not expanded or replaced by this smoke test. This is not proof of complete extraction of every section in the source.
- Independent read-only review found six important boundary issues (College mapping, per-page headers, stale CSV, nonfinite GPA, College-ambiguous manual review, dependent views). Each was reproduced, regression-tested, and fixed; the full suite passed afterward.

## Apply safely in local VS Code

Pull the code, stop any import/review writers, and run from the project root on Windows:

```powershell
git pull origin main
py -m pip install -r requirements.txt
py pipeline.py revalidate --pdf reports/spring_2026_arts_and_sciences.pdf
py -m unittest discover -s tests -v
node tests/test_frontend.cjs
py -m uvicorn api:app --reload
```

Do not delete, initialize, or replace the existing database. The first revalidation creates a unique pre-migration backup automatically. Do not use `import-pdf` merely to revalidate existing rows: that command imports all undergraduate subjects found in the selected report.

## Deliberate boundaries

- The schema/parser/API support all undergraduate subjects and the six requested terms; other semesters/colleges are not populated automatically.
- Only the supplied official College's uncoded mapping (`AT` / Arts & Sciences) is verified. Add reviewed official fixtures/mappings for other uncoded College headers. Unknown layouts stop instead of guessing.
- Uncertain page-spanning rows are quarantined; this prioritizes source fidelity over guessing missing names.
- Conflicting imports remain quarantined until explicit manual resolution; no automatic source replacement is provided.
- Source checks are automated comparisons to PDF extraction, not a visual certification of every row or an independent verification of professor identities.
