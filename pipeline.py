"""MaroonWay Phase 1: one-semester, two-subject grade-report pilot.

Educational prototype. Uses only registrar reports; DOES NOT try to identify
professors from abbreviated names or access Rate My Professors.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
            if SECTION_START.match(line):
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
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("Install the PDF reader first: python -m pip install -r requirements.txt") from exc
    try:
        with fitz.open(str(path)) as document:
            return [page.get_text("text", sort=True) for page in document]
    except Exception as exc:
        raise RuntimeError(f"Could not read PDF: {exc}") from exc


def setup_db(connection: sqlite3.Connection):
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))


def import_pdf(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Not found: {path}. Download the official report first.")
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise RuntimeError("Input is not a PDF. The Registrar may have returned an error page.")
    pdf_hash = hashlib.sha256(data).hexdigest()
    rows, rejected = parse_pages(read_pdf_pages(path))
    DATA.mkdir(exist_ok=True)
    if not rows:
        raise RuntimeError("No STAT/MATH rows found. Confirm this is Spring 2026 Arts & Sciences grade distribution (not GPA Distribution); inspect the PDF format.")

    quality = []
    with sqlite3.connect(DB_PATH) as con:
        setup_db(con)
        for row in rows:
            status = "needs_review" if row.issues else "checks_passed"
            arguments = (TERM, COLLEGE, row.subject, row.number, row.section,
                         row.instructor_raw, row.a, row.b, row.c, row.d, row.f,
                         row.af_total, row.gpa, row.i_count, row.s_count, row.u_count,
                         row.q_count, row.x_count, row.enrollment_total,
                         status, OFFICIAL_URL, pdf_hash, row.source_page, row.raw_row)
            try:
                con.execute("""
                    INSERT INTO grade_sections
                    (term, college, subject, course_number, section,
                     instructor_as_reported, a, b, c, d, f, af_total, gpa_reported,
                     i_count, s_count, u_count, q_count, x_count, enrollment_total,
                     quality_status, source_url, source_sha256, source_page, raw_row)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, arguments)
            except sqlite3.IntegrityError:
                previous = con.execute("""SELECT raw_row, source_sha256
                    FROM grade_sections WHERE term=? AND college=? AND subject=?
                    AND course_number=? AND section=?""",
                    (TERM, COLLEGE, row.subject, row.number, row.section)).fetchone()
                if previous != (row.raw_row, pdf_hash):
                    quality.append((row.source_page, f"{row.subject}-{row.number}-{row.section}",
                                    "Existing section differs; manual comparison required", row.raw_row))
            for issue in row.issues:
                quality.append((row.source_page, f"{row.subject}-{row.number}-{row.section}", issue, row.raw_row))
        con.commit()
    quality.extend(rejected)
    quality_path = DATA / "quality_review.csv"
    with quality_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source_page", "section_code", "issue", "raw_extracted_text"])
        writer.writerows(quality)
    export_csv()
    print(f"Found {len(rows)} unique STAT/MATH section rows; {len(quality)} issues for review.")
    if len(rows) < 10:
        print("WARNING: Very few rows found. Inspect the source PDF and the extraction format.")
    print(f"Database: {DB_PATH}")
    print(f"Grade CSV: {DATA / 'grade_sections.csv'}")
    print(f"Review CSV: {quality_path}")
    print("IMPORTANT: Names are saved AS REPORTED; they are not linked to real professor identities.")
    print("Check parsed rows against the PDF before publishing them.")


def export_csv() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        records = con.execute("""SELECT term, subject, course_number, section,
                    instructor_as_reported, a, b, c, d, f, af_total, gpa_reported,
                    i_count, s_count, u_count, q_count, x_count, enrollment_total,
                    quality_status, source_page, source_url
                    FROM grade_sections ORDER BY subject, course_number, section""").fetchall()
        if not records:
            return
        with (DATA / "grade_sections.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(records[0].keys())
            writer.writerows([tuple(r) for r in records])


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
    print(f"Downloading official registrar report: {OFFICIAL_URL}")
    req = urllib.request.Request(OFFICIAL_URL, headers={"User-Agent": "MaroonWay-education-pilot/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Automatic download failed. Open https://web-as.tamu.edu/gradereports/ in your browser, select 2026 / Spring / Arts & Sciences / Grade Distribution, and save the PDF to reports/spring_2026_arts_and_sciences.pdf.") from exc
    if not content.startswith(b"%PDF-"):
        raise RuntimeError("Website did not return a PDF. Use the manual download instructions in README.md.")
    PDF_PATH.write_bytes(content)
    print(f"Saved {PDF_PATH} ({len(content):,} bytes)")


def main():
    parser = argparse.ArgumentParser(description="MaroonWay Spring 2026 STAT/MATH grade reports")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("download", help="Try to fetch the public Arts & Sciences PDF")
    importer = commands.add_parser("import-pdf", help="Parse PDF and create SQLite + CSV")
    importer.add_argument("pdf", nargs="?", default=str(PDF_PATH), help="path to grade distribution PDF")
    commands.add_parser("show", help="Print a quick database summary")
    args = parser.parse_args()
    try:
        if args.action == "download":
            download()
        elif args.action == "import-pdf":
            import_pdf(Path(args.pdf))
        elif args.action == "show":
            show()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
