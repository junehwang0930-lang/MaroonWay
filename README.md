# MaroonWay — Phase 1 (beginner starter kit)

**Goal:** Make a trustworthy database of Spring 2026 **undergraduate (100–499) STAT and MATH** historical grade-section records from the **Texas A&M Registrar's official grade distribution report**. The project includes a local course-search and section-comparison UI. RMP ratings and automatic professor matching are deferred.

This kit contains **working starter code**, NOT predownloaded TAMU data. The authoring environment could not access the actual PDF file, so the parser has been tested against *synthetic report-format examples*, not verified on the Spring 2026 Registrar PDF. **You must verify the first 10–20 extracted rows against the original PDF before using the data.**

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

## 4. Turn the PDF into a database

```bash
python pipeline.py import-pdf
python pipeline.py show
```

This creates:

| File | Meaning |
| --- | --- |
| `data/maroonway.db` | SQLite database (can query later with SQL) |
| `data/grade_sections.csv` | Parsed grade records, one row per course section |
| `data/quality_review.csv` | Rows/values to inspect by hand |

Read `quality_review.csv` **before** trusting any database entries. Every record includes `source_page` and a `source_url` so you can check the original PDF.

## 5. Test the code on sample patterns first

```bash
python -m unittest discover -s tests -v
```

These tests use **fictional** instructors and grades. The sample values are not claims about real TAMU classes. The current suite covers parser patterns only; it does not verify the API, browser UI, full PDF import workflow, or compatibility with the official report. A passing suite is not certification of imported data.

## 6. Check quality manually

Before trusting or sharing data through the website:

1. Compare **at least 10–20 random rows** in `grade_sections.csv` to the original PDF (course, section, semester, instructor text, each A–F count, GPA, report page).
2. Inspect every row in `quality_review.csv`, especially parse failures, GPA/count mismatches, and duplicates. A parse failure can mean a section is missing from your database.
3. **Do not map abbreviated instructor names to real professors automatically.** The official report can use surname plus initial; different people may share that text.
4. Keep source PDF and SHA-256 as evidence of exactly what you imported.
5. A missing grade record is **unknown**, not an F, not zero GPA, and not proof the course was never taught.

## 7. Run the API and website locally

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

The API currently supports MATH and STAT for Spring 2026. An unsupported subject returns HTTP 400, a missing database returns 503, and a course without records returns 404. A welcome response alone does not verify database access. After import, search for a course present in `grade_sections.csv` and check its sections against that export.

## Current data and UI limitations

- The importer assigns Spring 2026 / Arts & Sciences metadata without validating the PDF header. Confirm the year, semester, college, and report type yourself before importing.
- Negative grade counts are not explicitly rejected, and instructor names split across extracted lines may be truncated. Inspect counts and instructor text against the original PDF even when a row says `checks_passed`.
- Each import overwrites `quality_review.csv`; archive review results before reimporting. Existing conflicting database rows are retained and flagged rather than automatically replaced.
- Overlapping browser searches are not cancelled. Wait for one search to finish before submitting another to avoid mixed results.
- GPA summaries include rows needing review. Instructor summaries group by the published name text, which does not establish a shared professor identity.

## Why we designed the database this way

`schema.sql` creates three tables:

- `grade_sections`: the official *historical* grade counts, term, source, section, and instructor text **as published**.
- `professors`: a future table for verified professor identities.
- `professor_aliases`: future audited mappings of name variants to specific professor IDs.

Every `grade_sections.professor_id` starts `NULL`. That is intentional and stops a `SMITH J` record from being treated as proof about a particular John/Jane Smith.

**Important limitations:** The Registrar suppresses sections with fewer than five students. Its reports are term-specific point-in-time snapshots and may not reflect grade changes made after publication. A historical section record says nothing about whether a class will be available during registration. The script only reads the Arts & Sciences college report, so sections filed in another college report may be absent.

## Our next milestone

Once the import is clean, we can build a **verified-instructor matching workflow** and then add a separate **current course schedule** dataset. RMP is deferred until access/redisplay permission is resolved.

Sources:
- Official Registrar: https://web-as.tamu.edu/gradereports/
- Example open-source parser documentation (for understanding report format): https://github.com/IvanKuria/reveille-ratings/blob/main/scripts/build-grades/README.md

This is an independent student project, not an official TAMU product.

## Repository layout

```text
MaroonWay/
├── pipeline.py          # Main download, import, and summary CLI
├── api.py               # FastAPI endpoints and frontend hosting
├── frontend/            # Course-search and section-comparison UI
├── analyze_gpa.py       # Section GPAs for the hard-coded course
├── course_summary.py    # Weighted GPA for the hard-coded term/course
├── instructor_summary.py # Summaries grouped by published instructor text
├── schema.sql           # SQLite schema
├── requirements.txt     # Python dependencies
├── scripts/             # Database exploration and manual review tools
├── tests/               # Parser tests
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
- Keep one review per term and section. Preserve existing entries and quote CSV fields containing commas.

The script creates `data/maroonway_before_name_reviews.db` once and writes a separate `data/grade_sections_reviewed.csv`. It adds review fields without changing the original instructor text, quality status, or `professor_id`. The existing backup is not refreshed on later runs. The API currently displays the original instructor text, not the reviewed name.

For console summaries, run `python analyze_gpa.py`, `python course_summary.py`, or `python instructor_summary.py` after import. These scripts currently select STAT 211 in code; edit their selection variables when exploring another course. `analyze_gpa.py` does not filter by semester, while the other two select Spring 2026.
