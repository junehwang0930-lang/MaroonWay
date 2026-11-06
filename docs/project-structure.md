# Project file guide and folder cleanup

MaroonWay covers **TAMU undergraduate Grade Distribution records from Fall 2023 through Spring 2026, excluding Summer**. An AI Schedule Builder may be added later; the folder cleanup did not create speculative features or folders.

The root-level commands remain:

```bash
python -m uvicorn api:app --reload
python pipeline.py --help
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

On Windows, use `py` or `py -3.14` instead of `python` if appropriate.

## Before cleanup

```text
MaroonWay/
├── api.py
├── pipeline.py
├── storage.py
├── report_metadata.py
├── analyze_gpa.py
├── course_summary.py
├── instructor_summary.py
├── schema.sql
├── requirements.txt
├── README.md
├── .gitignore
├── .github/workflows/tests.yml
├── frontend/                  # HTML, CSS, JavaScript
├── scripts/                   # Only some helper tools
│   ├── apply_name_reviews.py
│   ├── explore_db.py
│   └── validate_data.py
├── tests/                     # Python/JavaScript tests, fixtures and runner
├── docs/
│   ├── integrity-verification.md
│   ├── windows-resource-fix.md
│   └── superpowers/plans/2026-11-04-integrity.md
├── data/
│   ├── README.md
│   ├── GENERATED_FILES_HERE.txt
│   ├── manual_instructor_reviews.csv
│   └── [Local DBs, backups, CSVs and Import/Validation history]
└── reports/
    ├── README.md
    ├── PUT_PDF_HERE.txt
    └── [Local source PDFs]
```

## After cleanup

This tree records the cleanup's result. Later features may add files documented in the main README.

```text
MaroonWay/
├── README.md                   # Installation, commands and starting point
├── api.py                      # FastAPI entry point
├── pipeline.py                 # PDF import and revalidation CLI
├── storage.py                  # SQLite storage, migrations and audit history
├── report_metadata.py          # PDF term, year, College and report-type checks
├── schema.sql                  # Original base schema; unchanged by cleanup
├── requirements.txt            # Python dependencies
├── .gitignore                  # Local-file exclusion rules
├── .github/workflows/tests.yml # Windows/Linux automated tests
├── frontend/
│   ├── index.html              # Web page
│   ├── style.css               # Page styling
│   └── app.js                  # Search and comparison behavior
├── scripts/
│   ├── analyze_gpa.py          # Section GPA listing
│   ├── course_summary.py       # Weighted course GPA summary
│   ├── instructor_summary.py   # Published-name summary, not identity verification
│   ├── explore_db.py           # Original record counts by subject
│   ├── validate_data.py        # Sample for manual PDF comparison
│   └── apply_name_reviews.py   # Apply manual instructor reviews
├── tests/
│   ├── test_pipeline.py        # Original seven parser tests
│   ├── test_integrity.py       # Count validation and name parsing
│   ├── test_metadata.py        # Report metadata checks
│   ├── test_storage.py         # Storage, migration and history preservation
│   ├── test_api.py             # Public API and analysis-tool checks
│   ├── test_resource_lifecycle.py # SQLite/PDF handle cleanup
│   ├── test_frontend.cjs       # JavaScript request-race tests
│   ├── pdf_fixture.py          # Valid PDF fixtures
│   └── run_checks.py           # Test runner including resource-leak checks
├── docs/
│   ├── project-structure.md    # This file: roles, classification and cleanup
│   ├── integrity-plan.md       # Historical integrity plan and decisions
│   ├── integrity-verification.md # Original 313-row verification record
│   └── windows-resource-fix.md # Windows file-lock fix and CI results
├── data/
│   ├── README.md
│   ├── manual_instructor_reviews.csv
│   └── [Existing local DBs, backups, CSVs and history preserved]
└── reports/
    ├── README.md
    └── [Existing local source PDFs preserved]
```

Bracketed entries under `data/` and `reports/` are descriptive placeholders, not assertions about specific filenames or their presence. Files excluded by `.gitignore` may be invisible on GitHub or in the cloud. **An unseen data file is not a deletion candidate.** Local `.venv/`, `__pycache__/`, `.git/` and personal `.vscode/` settings were not deleted.

## File classification and decisions

| Classification | Files/folders | Decision and reason |
| --- | --- | --- |
| Required | `api.py`, `pipeline.py`, `storage.py`, `report_metadata.py` | Keep at the root to preserve imports and entry points without adding package layers |
| Required | `schema.sql`, `requirements.txt`, `.gitignore`, `README.md` | Keep; cleanup did not change schema, dependencies or Git rules, and updated README paths |
| Required | Three `frontend/` files | Keep existing FastAPI static paths and UI behavior |
| Required | All existing `tests/` files | Keep without deletion or skips; update moved script references only |
| Required | `.github/workflows/tests.yml` | Keep; test entry points and root working directory did not change |
| Required and protected | DBs, backup DBs, source PDFs, all CSVs and Import/Validation history | Preserve contents and paths; do not migrate or revalidate the real DB for folder cleanup |
| Recommended move | Root `analyze_gpa.py`, `course_summary.py`, `instructor_summary.py` | Use `git mv` to gather tools in `scripts/`; adjust only their project-root DB paths |
| Recommended move | `docs/superpowers/plans/2026-11-04-integrity.md` | Use `git mv` to `docs/integrity-plan.md`; preserve content and remove unnecessary nesting |
| Duplicate/deletion candidate: deleted | `data/GENERATED_FILES_HERE.txt` | Confirmed instructional text duplicated by root/data READMEs; also listed older output filenames; not actual data |
| Duplicate/deletion candidate: deleted | `reports/PUT_PDF_HERE.txt` | Same download/save instructions already in root/report READMEs; remove only the redundant notice |
| Deletion candidate: retained | Historical plan and verification documents | Plans, verification evidence and Windows diagnosis have distinct purposes |
| Deletion candidate: retained | Existing analysis/review scripts | Listing, aggregation and manual review have different responsibilities; do not merge or delete them |

The cleanup's only functional-code changes were project-root path adjustments based on `__file__` in the three moved scripts. SQL, database schema, API, PDF parsing and frontend behavior were unchanged by that cleanup.

## Helper commands

Run from the repository root:

```bash
python scripts/analyze_gpa.py
python scripts/course_summary.py
python scripts/instructor_summary.py
python scripts/explore_db.py
python scripts/validate_data.py
python scripts/apply_name_reviews.py
```

Analysis scripts retain their existing in-code term/course selection variables. Manual review requires the existing database and review inputs. **Folder cleanup does not require running these tools on real user data.**

The three moved scripts resolve the project root from their own file locations regardless of the calling terminal's directory. Tests run relocated scripts against temporary databases rather than substituting the real DB.
