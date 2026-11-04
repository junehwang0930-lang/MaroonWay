# MaroonWay — Phase 1 (beginner starter kit)

**Goal:** Make a trustworthy database of Spring 2026 **undergraduate (100–499) STAT and MATH** historical grade-section records from the **Texas A&M Registrar's official grade distribution report**. Do **not** add RMP ratings or attempt professor matching yet.

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

These tests use **fictional** instructors and grades. The sample values are not claims about real TAMU classes. They verify basic logic but cannot certify compatibility with the real report.

## 6. Check quality manually

Before building any website UI:

1. Compare **at least 10–20 random rows** in `grade_sections.csv` to the original PDF (course, section, semester, instructor text, each A–F count, GPA, report page).
2. Inspect every row in `quality_review.csv`, especially parse failures, GPA/count mismatches, and duplicates. A parse failure can mean a section is missing from your database.
3. **Do not map abbreviated instructor names to real professors automatically.** The official report can use surname plus initial; different people may share that text.
4. Keep source PDF and SHA-256 as evidence of exactly what you imported.
5. A missing grade record is **unknown**, not an F, not zero GPA, and not proof the course was never taught.

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
