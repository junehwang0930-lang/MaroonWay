# MaroonWay — Phase 1 (beginner starter kit)

**Goal:** Build a trustworthy database of Texas A&M historical **undergraduate (100–499) grade-section records across all subjects** for **Fall 2023 through Spring 2026, excluding Summer**, using the Registrar's Grade Distribution reports. The project includes a local course-search and section-comparison UI. RMP ratings and automatic professor matching are deferred.

The repository does not distribute a prebuilt database or source PDFs. The supplied Spring 2026 Arts & Sciences PDF has been exercised in an integration smoke test, and the supplied 313-record database was revalidated: **311 passed; 2 require review**. See [the verification report](docs/integrity-verification.md). Other terms and colleges require their own verified source PDFs; support for the date range does not mean those datasets are populated. **Compare 10–20 extracted rows against the original PDF before using the data.**

## Primary GPA metric

Grade Explorer and Section Comparison use **MaroonWay GPA (A-F based)**: `(4*A + 3*B + 2*C + D) / (A+B+C+D+F)`. Zero A-F students displays N/A. TAMU reported GPA remains separate and unchanged. A discrepancy is a warning, not proof of a source error or a reason by itself to hide a source-verified section.

**Existing installations must apply policy v3 and revalidate preserved sources before using the new API.** First test on a database copy; see [methodology, safety rules and local upgrade instructions](docs/calculated-gpa-methodology.md). No existing section records need to be deleted or reimported.

## 1. Install Python (only once)

Install Python 3.11 or later from https://www.python.org/downloads/ and install VS Code if you want an editor: https://code.visualstudio.com/ . On Windows, check **Add Python to PATH** when installing.

## 2. Open the folder in VS Code

Unzip this project, open its folder in VS Code, and open **Terminal → New Terminal**.

Run (Windows):

```powershell
py -m pip install -r requirements.txt
```

Run (Mac or Linux):

```bash
python3 -m pip install -r requirements.txt
```

For the steps below, Windows users can replace `python` with `py`; macOS users may need `python3`.

## 3. Get the official PDF

Go to https://web-as.tamu.edu/gradereports/ and choose the **Grade Distribution** form (not GPA Distribution):

- Year: **2026**
- Semester: **Spring**
- College: **Arts & Sciences**
- Click **Grade Distribution**, then download the PDF.

Save it as `reports/spring_2026_arts_and_sciences.pdf` inside this project. The exact dropdown labels can vary.

Or try the public report download endpoint automatically:

```bash
python pipeline.py download
```

If the download fails (website blocks it or changes), use the manual browser method. Do not bypass access protections.

## 4. Preserve and revalidate an existing database

If you already have `data/maroonway.db`, **do not delete or reset it**. Stop import/review writers, then run from the repository root (Windows: replace `python` with `py`):

```bash
python pipeline.py revalidate --pdf reports/spring_2026_arts_and_sciences.pdf
```

Legacy pre-v2 databases receive a `data/maroonway.before-v2-<unique-id>.db` backup; an existing v2 database receives a `data/maroonway.before-v3-<unique-id>.db` backup before policy v3 is installed. Test the upgrade on a copy first, as described in the methodology guide. It retains every original row, ID, source field, professor link, and manual-review column. The migration removes the old STAT/MATH-only constraint and adds separate source/import/audit tables and a public view. It does not overwrite original values or mark a professor identity as verified.

Each audit writes an immutable CSV under `data/validation_runs/` and reports total/passed/review counts. It verifies the original PDF hash and metadata, numeric checks, and each stored section's fields/page against a fresh extraction. Without the matching PDF, legacy rows remain unpublished. You can use `--db path/to/database.db` to target another existing database. Never substitute a sample DB for your real data.

Repeat the command to audit again; original rows and earlier audit files remain intact. Revalidation refreshes `data/public_grade_sections.csv` with only currently validated rows, including an empty snapshot when none qualify. A raw legacy `quality_status` value alone is not publication approval: use `public_grade_sections` for application queries.

## 5. Import a report

```bash
python pipeline.py import-pdf
python pipeline.py show
```

The default command is for Spring 2026 Arts & Sciences. For a different supported term/college, supply the expected metadata explicitly:

```bash
python pipeline.py import-pdf reports/fall_2023_arts_and_sciences.pdf --year 2023 --semester FALL --college AT --college-name "Arts & Sciences"
```

Supported terms: `2023-FALL`, `2024-SPRING`, `2024-FALL`, `2025-SPRING`, `2025-FALL`, `2026-SPRING`. Summer and out-of-range terms are rejected. Every nonblank PDF page must have a recognized Grade Distribution report header with the requested term and College; GPA Distribution, mismatches, and unknown layouts stop import before DB changes. Filenames are not evidence.

For uncoded College headers, a reviewed code/name mapping is required in `report_metadata.py` (`AT` / Arts & Sciences is verified against the supplied PDF). An explicit code/name header must match both requested values. Add official header fixtures and a reviewed mapping before accepting another uncoded college. Do not bypass validation to add a college. The legacy `download` command remains a Spring 2026 Arts & Sciences convenience; obtain other reports from the official form.

Each successful import retains all undergraduate subjects found in that report. Existing section identities are never overwritten: conflicts are recorded and quarantined pending manual resolution, including on later repeat imports. No automatic conflict-resolution command is provided.

This creates:

| File | Meaning |
| --- | --- |
| `data/maroonway.db` | SQLite database (can query later with SQL) |
| `data/public_grade_sections.csv` | Current validated public snapshot, with College and source hash |
| `data/import_reviews/<unique-run-id>.csv` | Review items preserved for each import |
| `data/sources/<sha256>.pdf` | Preserved input PDF; bytes also retained in SQLite |
| `data/validation_runs/<unique-run-id>.csv` | Review results for each revalidation |

Inspect the import/audit CSVs before trusting results. Legacy `grade_sections.csv`, `grade_sections_reviewed.csv`, and `quality_review.csv` are preserved as historical evidence, not refreshed as public output. Import and validation manifests, row snapshots, issues, and conflicts are also retained in SQLite. Each source record preserves its page, URL, hash, and original extracted text.

## 6. Run regression tests

```bash
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

Regression tests use fictional data and temporary databases, including generated PDFs. They cover count/name parsing, metadata rejection, migration preservation, import history, publication filters, API query behavior, and out-of-order frontend requests. Node.js 18+ is needed only for the frontend tests; the UI itself runs in the browser. These are not full browser end-to-end tests or proof of compatibility with every TAMU report layout. A passing suite does not replace source review.

For Windows/Python 3.14 or stricter resource checks, see [the SQLite/PDF cleanup fix](docs/windows-resource-fix.md). All original 43 tests are retained; subsequent integrity and GPA tests are also included. The current total is 80 Python tests and 9 JavaScript tests. To also fail on garbage-collection resource leaks, run:

```bash
python -W error::ResourceWarning tests/run_checks.py
```

## 7. Check quality manually

Before trusting or sharing data through the website:

1. Compare **at least 10–20 random rows** in `public_grade_sections.csv` to the original PDF (course, section, semester, instructor text, each A–F count, GPA, report page).
2. Inspect every issue in the import/audit CSVs, especially parse failures, GPA/count mismatches, and duplicates. A parse failure can mean a section is missing from your database.
3. **Do not map abbreviated instructor names to real professors automatically.** The official report can use surname plus initial; different people may share that text.
4. Keep source PDF and SHA-256 as evidence of exactly what you imported.
5. A missing grade record is **unknown**, not an F, not zero GPA, and not proof the course was never taught.

## 8. Run the API and website locally

After installing dependencies and importing the report, run from the repository root:

```bash
python -m uvicorn api:app --reload
```

Open these paths on the local server (default host `127.0.0.1`, port `8000`):

| Path | Purpose |
| --- | --- |
| `/app/` | Course search and comparison of two sections |
| `/docs` | Interactive API documentation |
| `/courses/STAT/211` | Example course lookup; requires matching imported records |
| `/` | API welcome message |

Serve the frontend through FastAPI; opening `frontend/index.html` directly does not provide the API needed for search. Stop the development server with Ctrl+C. `--reload` is for local development.

The API returns `gpa_calculated` (primary sort metric), unchanged `gpa_reported`, absolute `gpa_difference`, and `gpa_discrepancy` (1/0, or NULL when unavailable). Credit-hour weighting can make the reported value differ from a headcount average. Historical GPA is not a guaranteed difficulty score.

The API accepts all supported-format undergraduate subjects and the six supported terms. The default is Spring 2026; for example, `/courses/CHEM/119?term=2023-FALL&college=AT` selects a term and optional College. The website lets you choose the term and enter a subject. Only audited, unchanged rows without unresolved conflicts are returned. Invalid course/term input returns 400, an unavailable or unmigrated database returns 503, and no publishable matching rows returns 404. Missing or quarantined records are unknown, not zero grades. A welcome response alone does not verify database access.

## Integrity guarantees and remaining limits

- Differences above **0.005** receive a discrepancy warning; exact boundary comparison avoids floating-point misclassification. All source-verified sections use the A-F calculated GPA, regardless of a valid reported GPA discrepancy.
- Negative/non-integer counts, inconsistent totals, malformed/out-of-range GPA, missing initials, duplicate identities, source conflicts and uncertain extraction prevent publication. Raw evidence is retained for review.
- Instructor names are buffered to section/page boundaries. Unknown trailing text and page-spanning partial rows go to review rather than being guessed or dropped. Recognized report summary rows are excluded from section names.
- Each import gets its own UUID/timestamp CSV and database history; legacy review files are never overwritten. Repeated imports do not replace existing source rows. Current public CSV export is an atomic snapshot, not the history store.
- New browser searches cancel the previous request and guard both delayed responses and errors, so only the newest search can update results.
- Automated checks do not independently establish professor identity or prove that all suppressed/missing sections were published. Raw-name summaries group text, not verified people.
- Unknown report layouts and unknown uncoded College mappings stop ingestion. Review and add supported fixtures rather than guessing metadata.

## Why we designed the database this way

`schema.sql` defines the original evidence and identity tables; the versioned migration adds source documents, import runs/records/issues/conflicts, validation history, and the `public_grade_sections` view:

- `grade_sections`: the official *historical* grade counts, term, source, section, and instructor text **as published**.
- `professors`: a future table for verified professor identities.
- `professor_aliases`: future audited mappings of name variants to specific professor IDs.

Every `grade_sections.professor_id` starts `NULL`. That is intentional and stops a `SMITH J` record from being treated as proof about a particular John/Jane Smith.

**Important limitations:** The Registrar suppresses sections with fewer than five students. Its reports are term-specific point-in-time snapshots and may not reflect grade changes made after publication. A historical section record says nothing about whether a class will be available during registration. A single imported college report does not cover courses filed under other colleges. Import each verified report separately; College is part of section identity.

## Our next milestone

Once the import is clean, we can build a **verified-instructor matching workflow** and then add a separate **current course schedule** dataset. RMP is deferred until access/redisplay permission is resolved.

Sources:
- Official Registrar: https://web-as.tamu.edu/gradereports/
- Example open-source parser documentation (for understanding report format): https://github.com/IvanKuria/reveille-ratings/blob/main/scripts/build-grades/README.md

This is an independent student project, not an official TAMU product.

## Repository layout

New to the project? Start with the [file-by-file guide and before/after layout](docs/project-structure.md). Core entry points stay at the root; all helper scripts are in `scripts/`. Run the commands below from the repository root.

```text
MaroonWay/
├── pipeline.py          # Main download, import, and summary CLI
├── api.py               # Read-only API over validated public rows
├── storage.py           # Versioned migration, source preservation, row audits
├── report_metadata.py   # Fail-closed report headers and supported terms
├── frontend/            # Course-search and section-comparison UI
├── schema.sql           # SQLite schema
├── requirements.txt     # Python dependencies
├── scripts/             # All analysis, exploration and manual-review tools
├── tests/               # Python regressions and Node request-race tests
├── docs/                # File guide, implementation history and verification
├── data/                # Generated database, CSV exports, and review inputs
└── reports/             # Official source PDFs
```

Run the helper tools from the repository root after importing a report:

```bash
python scripts/explore_db.py
python scripts/validate_data.py
```

`validate_data.py` creates a sample CSV for manual PDF checks. To apply prepared instructor review notes from `data/manual_instructor_reviews.csv`, run:

```bash
python scripts/apply_name_reviews.py
```

Manual instructor reviews are separate from the original Registrar data. A candidate name is not a verified identity.

The review CSV must contain these exact headers. This example is **fictional**; replace it with a section and raw instructor text actually present in your database:

```csv
term,section_code,instructor_as_reported,reviewed_instructor_name,review_status,review_note
2026-SPRING,STAT-211-200,SMITH B,Example Person,candidate,Fictional example only
```

- `term` and `section_code` identify an existing section.
- `instructor_as_reported` must exactly match the stored source text after trimming whitespace.
- `reviewed_instructor_name` must be nonempty. `review_status` must be `candidate` or `verified`; use `verified` only with independent supporting evidence recorded in `review_note`.
- Keep one review per term, College, and section. Add an optional `college` column (for example `AT`) when needed. Without it, multiple matching colleges abort the review rather than selecting an arbitrary row. Preserve existing entries and quote fields containing commas.

The script creates `data/maroonway_before_name_reviews.db` once and writes a separate `data/grade_sections_reviewed.csv`. It adds review fields without changing the original instructor text, quality status, or `professor_id`. The existing backup is not refreshed on later runs. The API currently displays the original instructor text, not the reviewed name.

For console summaries, run `python scripts/analyze_gpa.py`, `python scripts/course_summary.py`, or `python scripts/instructor_summary.py` after import. These scripts currently select STAT 211 in code; edit their selection variables when exploring another course. All three read the validated public view. `analyze_gpa.py` lists matching sections across imported terms; the other two select Spring 2026. Set selection variables explicitly when comparing periods.

## Spring 2026 source review

See [the Unicode name fix and all 23 GPA comparisons](docs/spring-2026-import-review.md) for the distinction between the two corrected SPAN parsing failures and unresolved source GPA/name issues. Original GPA values and missing initials are not inferred or replaced.

## GPA investigations (read-only by default)

See [the safe investigation guide](docs/gpa-discrepancy-investigation.md) for official-source limitations, the separate opt-in review schema, and explicit test-copy migration instructions. Investigation classifications never grant publication. Current calculated-GPA publication rules are described in the methodology guide above. Generate a new PDF-only CSV without opening a database:

```bash
python scripts/investigate_gpa.py --pdf reports/spring_2026_arts_and_sciences.pdf --include-section BIOL-491-500
```

Calculated GPA means an A–F headcount average, not the Registrar's official GPA. The command never replaces existing reports. Official credit/rule evidence was inaccessible during this investigation; unexplained cases remain unresolved.

## Exact user-confirmed instructor reviews

Four Spring 2026 AT confirmations are provided in `data/user_confirmed_instructors.csv`, separately from the preserved candidate CSV. See [the application and safety guide](docs/user-confirmed-instructor-reviews.md). These are user confirmations, not independent TAMU identity verification. HERNANDEZ has only initial I confirmed. Apply explicitly with `--confirmations` and revalidate sources; no original instructor text, grade data or quality status is overwritten.
