"""MaroonWay: validated undergraduate grade-report imports and audits.

Educational prototype. Uses only registrar reports; DOES NOT try to identify
professors from abbreviated names or access Rate My Professors.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from report_metadata import validate_metadata, SUPPORTED_TERMS

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
DB_PATH = DATA / "maroonway.db"
PDF_PATH = REPORTS / "spring_2026_arts_and_sciences.pdf"
OFFICIAL_URL = "https://web-as.tamu.edu/gradereports/Report?year=2026&term=SPRING&college=AT"
TERM = "2026-SPRING"
COLLEGE = "AT"  # Arts & Sciences; verify this on downloaded PDF
COUNT_FIELDS = ("a", "b", "c", "d", "f", "af_total", "i_count", "s_count", "u_count", "q_count", "x_count", "enrollment_total")

# The registrar includes course-section lines such as MATH-151-500.
SECTION_START = re.compile(r"^([A-Z]{2,8})-(\d{3,4}[A-Z]?)-([A-Z0-9]+)\b")
PERCENT_ONLY = re.compile(r"^-?\d+(?:\.\d+)?%$")
INSTRUCTOR_TEXT = re.compile(r"^[A-Z][A-Z .,'\-]*$")


@dataclass
class Parsed:
    source_page: int
    raw_row: str
    subject: str
    number: str
    section: str
    instructor_raw: str
    a: int
    b: int
    c: int
    d: int
    f: int
    af_total: int
    gpa: float | None
    i_count: int
    s_count: int
    u_count: int
    q_count: int
    x_count: int
    enrollment_total: int
    issues: list[str]


def normalize_line(s: str) -> str:
    return " ".join(s.strip().split())


def decode_row(text: str, page: int) -> Parsed | None:
    """Strictly parse the registrar's count/GPA/count/name row format.

    Returns None on uncertain structure. Never invents missing values.
    """
    cleaned = normalize_line(text)
    # Some PDF extraction modes place percentages inline with grade counts.
    cleaned = normalize_line(re.sub(r"(?<!\S)-?\d+(?:\.\d+)?%(?!\S)", " ", cleaned))
    parts = cleaned.split(" ")
    if len(parts) < 15:
        return None
    head = SECTION_START.fullmatch(parts[0])
    if not head:
        return None
    subject, number, section = head.groups()
    try:
        first_six = [int(x) for x in parts[1:7]]
        raw_gpa = parts[7]
        if raw_gpa.upper() in {"N/A", "NA", "--"}:
            gpa = None
        else:
            gpa = float(raw_gpa)
            if not math.isfinite(gpa):
                return None
        last_six = [int(x) for x in parts[8:14]]
    except ValueError:
        return None
    name = " ".join(parts[14:]).strip()
    if not name or not INSTRUCTOR_TEXT.fullmatch(name) or len(name) > 75:
        return None

    a, b, c, d, f, af_total = first_six
    i_count, s_count, u_count, q_count, x_count, enrollment_total = last_six
    issues = []
    for field, value in zip(COUNT_FIELDS, first_six + last_six):
        if value < 0:
            issues.append(f"Negative count: {field}")
    if sum(first_six[:5]) != af_total:
        issues.append("A-F count does not equal reported A-F total")
    if af_total + i_count + s_count + u_count + q_count + x_count != enrollment_total:
        issues.append("Grade counts do not equal reported enrollment total")
    if enrollment_total < 5:
        issues.append("Under-five enrollment: check source and privacy rules")
    if gpa is None:
        issues.append("GPA missing from report")
    elif not 0 <= gpa <= 4:
        issues.append("GPA outside 0-4 scale")
    elif af_total:
        calculated = (4 * a + 3 * b + 2 * c + d) / af_total
        # TAMU truncates reported GPA to three decimals, not always rounds.
        if abs(calculated - gpa) > 0.002:
            issues.append("Reported GPA does not match A-F counts")
    else:
        issues.append("No letter-graded students to compute GPA")
    if name in {"STAFF", "TBA", "TBD", "UNKNOWN"}:
        issues.append("Instructor is not identified")
    elif not re.search(r"\s[A-Z]$", name):
        issues.append("Instructor name lacks an identifiable final initial")
    if section in {"ALL", "TOTAL", "TOT"}:
        issues.append("Summary row, not an individual section")

    return Parsed(page, text, subject, number, section, name,
                  a, b, c, d, f, af_total, gpa,
                  i_count, s_count, u_count, q_count, x_count,
                  enrollment_total, issues)


def parse_pages(pages: list[str]):
    """Finalize at section/page boundaries, never at a partial instructor name.

    Unknown trailing text is retained in review rather than silently discarded.
    Page-spanning rows remain uncertain; no name is guessed across headers.
    """
    found, review = [], []
    for page_number, text in enumerate(pages, start=1):
        active = []

        def finish():
            if not active:
                return
            raw = "\n".join(active)
            code = normalize_line(active[0]).split()[0]
            record = decode_row(raw, page_number)
            if record is None:
                review.append((page_number, code, "Could not parse section row; manual review required", raw))
            elif 100 <= int(re.match(r"\d+", record.number).group()) <= 499:
                found.append(record)
            active.clear()

        for original_line in text.splitlines():
            line = normalize_line(original_line)
            if not line:
                continue
            if re.match(r"^(?:COURSE|DEPARTMENT|COLLEGE) TOTAL\s*:", line):
                finish()
            elif SECTION_START.match(line):
                finish()
                active.append(original_line)
            elif active:
                active.append(original_line)
        finish()
    unique = {}
    for row in found:
        key = (row.subject, row.number, row.section)
        if key in unique:
            issue = "Duplicate section identity"
            unique[key].issues.append(issue)
            review.append((row.source_page, "-".join(key), issue, row.raw_row))
        else:
            unique[key] = row
    return list(unique.values()), review


def read_pdf_pages(path: Path) -> list[str]:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise RuntimeError("Install the PDF reader first: python -m pip install -r requirements.txt") from exc
    try:
        with fitz.open(str(path)) as document:
            return [page.get_text("text", sort=True) for page in document]
    except Exception as exc:
        raise RuntimeError(f"Could not read PDF: {exc}") from exc


def setup_db(connection: sqlite3.Connection):
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))


def import_pdf(path: Path, *, year=2026, semester="SPRING", college="AT", college_name="Arts & Sciences") -> None:
    from storage import migrate, register_source, token, snapshot
    import json
    if not path.is_file():
        raise FileNotFoundError(f"Not found: {path}. Download the official report first.")
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise RuntimeError("Input is not a PDF")
    pages = read_pdf_pages(path)
    metadata = validate_metadata(pages, year=year, semester=semester, college=college, college_name=college_name)
    rows, rejected = parse_pages(pages)
    # Validation precedes all DB writes, including migrations.
    DATA.mkdir(exist_ok=True)
    migrate(DB_PATH)
    run_id = token()
    review_dir = DATA / "import_reviews"
    review_dir.mkdir(exist_ok=True)
    quality_path = review_dir / f"{run_id}.csv"
    source_dir = DATA / "sources"
    source_dir.mkdir(exist_ok=True)
    pdf_hash = hashlib.sha256(data).hexdigest()
    archived = source_dir / f"{pdf_hash}.pdf"
    if archived.exists():
        if archived.read_bytes() != data:
            raise RuntimeError("Archived source checksum mismatch; import stopped")
    else:
        with archived.open("xb") as handle:
            handle.write(data)
    quality = list(rejected)
    if not rows:
        quality.append((0, "", "No supported undergraduate section rows found", ""))
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        register_source(con, data, metadata)
        con.execute("insert into import_runs values (?,?,?,?,?,?,?)", (run_id, datetime.now(timezone.utc).isoformat(), pdf_hash, metadata.term, metadata.college, len(rows), str(quality_path)))
        con.execute("insert into validation_runs values (?,?,?)", (run_id, datetime.now(timezone.utc).isoformat(), str(quality_path)))
        for row in rows:
            status = "needs_review" if row.issues else "checks_passed"
            fields = ("term", "college", "subject", "course_number", "section", "instructor_as_reported", *COUNT_FIELDS, "gpa_reported", "quality_status", "source_url", "source_sha256", "source_page", "raw_row")
            values = (metadata.term, metadata.college, row.subject, row.number, row.section, row.instructor_raw, *(getattr(row, k) for k in COUNT_FIELDS), row.gpa, status, metadata.source_url, pdf_hash, row.source_page, row.raw_row)
            candidate = dict(zip(fields, values))
            previous = con.execute("select * from grade_sections where term=? and college=? and subject=? and course_number=? and section=?", (metadata.term, metadata.college, row.subject, row.number, row.section)).fetchone()
            issues = list(row.issues)
            if previous:
                # Formatting differences do not replace legacy raw evidence.
                compare = [k for k in fields if k not in {"raw_row", "quality_status"}]
                if any(previous[k] != candidate[k] for k in compare):
                    issue = "Existing section differs; manual comparison required"
                    issues.append(issue)
                    con.execute("insert into import_conflicts (grade_section_id,run_id,detail) values (?,?,?)", (previous['id'], run_id, snapshot(candidate)))
                grade_id = previous['id']
                stored = previous
            else:
                cursor = con.execute(f"insert into grade_sections ({','.join(fields)}) values ({','.join('?' for _ in fields)})", values)
                grade_id = cursor.lastrowid
                stored = con.execute("select * from grade_sections where id=?", (grade_id,)).fetchone()
            con.execute("insert into import_records (run_id,grade_section_id,snapshot_json) values (?,?,?)", (run_id, grade_id, snapshot(candidate)))
            if con.execute("select 1 from import_conflicts where grade_section_id=?", (grade_id,)).fetchone():
                issues.append("Unresolved conflicting import; original row retained")
            from storage import row_issues
            issues.extend(row_issues(stored))
            issues = list(dict.fromkeys(issues))
            con.execute("insert into grade_validations (run_id,grade_section_id,status,issues_json,snapshot_json) values (?,?,?,?,?)", (run_id,grade_id,"needs_review" if issues else "checks_passed",json.dumps(issues),snapshot(stored)))
            for issue in issues:
                quality.append((row.source_page, f"{row.subject}-{row.number}-{row.section}", issue, row.raw_row))
        con.executemany("insert into import_review_items (run_id,source_page,section_code,issue,raw_text) values (?,?,?,?,?)", [(run_id,*item) for item in quality])
        with quality_path.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["source_page", "section_code", "issue", "raw_extracted_text"])
            writer.writerows(quality)
    export_csv()
    print(f"Import {run_id}: {len(rows)} undergraduate rows; {len(quality)} review items.")
    print(f"Review CSV (preserved per import): {quality_path}")
    print("Original instructor identities and source evidence are retained; only validated rows are public.")
    if not rows:
        raise RuntimeError("No undergraduate rows imported; review history was retained")


def export_csv(db_path=None) -> None:
    """Refresh a public snapshot atomically; never replace the legacy evidence CSV."""
    import os
    import tempfile
    path = Path(db_path) if db_path is not None else DB_PATH
    fields = ("term", "college", "subject", "course_number", "section", "instructor_as_reported", *COUNT_FIELDS, "gpa_reported", "source_page", "source_url", "source_sha256")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as con:
        records = con.execute(f"SELECT {','.join(fields)} FROM public_grade_sections ORDER BY term,college,subject,course_number,section").fetchall()
    target = path.parent / "public_grade_sections.csv"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".csv.tmp", delete=False, newline="", encoding="utf-8") as handle:
            temporary = Path(handle.name)
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerows(records)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def show() -> None:
    if not DB_PATH.exists():
        print("No database yet. Run 'python pipeline.py download' and 'python pipeline.py import-pdf'.")
        return
    with sqlite3.connect(DB_PATH) as con:
        for subject, count, flag_count in con.execute("""
            SELECT subject, COUNT(*), SUM(quality_status='needs_review')
            FROM grade_sections GROUP BY subject ORDER BY subject"""):
            print(f"{subject}: {count} sections ({flag_count} with data checks needing review)")
        print("\nFirst 10 section rows (instructor identity NOT verified):")
        for sub, number, sec, instructor, gpa, status in con.execute("""
            SELECT subject, course_number, section, instructor_as_reported,
                   gpa_reported, quality_status FROM grade_sections
            ORDER BY subject, course_number, section LIMIT 10"""):
            print(f"  {sub} {number}-{sec:<5} {instructor:<25} GPA={gpa!s:<5}  {status}")


def download() -> None:
    REPORTS.mkdir(exist_ok=True)
    if PDF_PATH.exists():
        raise RuntimeError(f"Source PDF already exists; refusing to overwrite {PDF_PATH}")
    print(f"Downloading official registrar report: {OFFICIAL_URL}")
    req = urllib.request.Request(OFFICIAL_URL, headers={"User-Agent": "MaroonWay-education-pilot/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Automatic download failed. Open https://web-as.tamu.edu/gradereports/ in your browser, select 2026 / Spring / Arts & Sciences / Grade Distribution, and save the PDF to reports/spring_2026_arts_and_sciences.pdf.") from exc
    if not content.startswith(b"%PDF-"):
        raise RuntimeError("Website did not return a PDF. Use the manual download instructions in README.md.")
    try:
        with PDF_PATH.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise RuntimeError(f"Source PDF already exists; refusing to overwrite {PDF_PATH}") from exc
    print(f"Saved {PDF_PATH} ({len(content):,} bytes)")


def main():
    parser = argparse.ArgumentParser(description="MaroonWay undergraduate grades: Fall 2023 through Spring 2026, excluding Summer")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("download", help="Try to fetch the public Arts & Sciences PDF")
    importer = commands.add_parser("import-pdf", help="Parse PDF and create SQLite + CSV")
    importer.add_argument("pdf", nargs="?", default=str(PDF_PATH), help="path to grade distribution PDF")
    importer.add_argument("--year", type=int, default=2026)
    importer.add_argument("--semester", choices=["SPRING", "FALL"], default="SPRING")
    importer.add_argument("--college", default="AT")
    importer.add_argument("--college-name", default="Arts & Sciences")
    audit = commands.add_parser("revalidate", help="Back up, migrate, and audit existing records without replacing source data")
    audit.add_argument("--db", type=Path, default=DB_PATH)
    audit.add_argument("--pdf", type=Path)
    audit.add_argument("--year", type=int, default=2026)
    audit.add_argument("--semester", choices=["SPRING", "FALL"], default="SPRING")
    audit.add_argument("--college", default="AT")
    audit.add_argument("--college-name", default="Arts & Sciences")
    commands.add_parser("show", help="Print a quick database summary")
    args = parser.parse_args()
    try:
        if args.action == "download":
            download()
        elif args.action == "import-pdf":
            import_pdf(Path(args.pdf), year=args.year, semester=args.semester, college=args.college, college_name=args.college_name)
        elif args.action == "revalidate":
            from storage import migrate, register_source, revalidate
            import json
            if not args.db.is_file():
                raise FileNotFoundError(f"No database at {args.db}")
            if args.pdf:
                content = args.pdf.read_bytes()
                metadata = validate_metadata(read_pdf_pages(args.pdf), year=args.year, semester=args.semester, college=args.college, college_name=args.college_name)
                migrate(args.db)
                with sqlite3.connect(args.db) as con:
                    register_source(con, content, metadata)
            print(json.dumps(revalidate(args.db), indent=2))
        elif args.action == "show":
            show()
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
