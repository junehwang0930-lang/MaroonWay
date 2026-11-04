import sqlite3
import re
from report_metadata import SUPPORTED_TERMS
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi import FastAPI, HTTPException


# Database location
DB_PATH = Path(__file__).resolve().parent / "data" / "maroonway.db"

# Create our API
app = FastAPI(title="MaroonWay API")
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

app.mount(
    "/app",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend"
)


@app.get("/")
def home():
    return {"message": "Welcome to MaroonWay!"}


@app.get("/courses/{subject}/{course_number}")
def get_course(subject: str, course_number: str, term: str = "2026-SPRING", college: str | None = None):

    subject = subject.upper()

    if not re.fullmatch(r"[A-Z]{2,8}", subject) or not re.fullmatch(r"[1-4]\d{2}[A-Z]?", course_number):
        raise HTTPException(
            status_code=400,
            detail="Use a valid subject and undergraduate course number (100–499)"
        )

    if term not in SUPPORTED_TERMS:
        raise HTTPException(status_code=400, detail="Unsupported term; Summer is excluded")
    if college is not None:
        college = college.upper()
        if not re.fullmatch(r"[A-Z0-9]{2,8}", college):
            raise HTTPException(status_code=400, detail="Invalid college code")

    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Grade database is not available"
        )

    connection = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    try:
        query = """
        SELECT
            college,
            section,
            instructor_as_reported,
            gpa_reported,
            af_total,
            a,
            b,
            c,
            d,
            f,
            q_count,
            enrollment_total,
            'checks_passed' AS quality_status,
            source_url,
            source_sha256,
            source_page
        FROM public_grade_sections
        WHERE term = ?
        AND subject = ?
        AND course_number = ?
        AND (? IS NULL OR college = ?)
        ORDER BY gpa_reported DESC;
        """

        rows = connection.execute(
            query,
            (term, subject, course_number, college, college)
        ).fetchall()

        sections = [dict(row) for row in rows]

    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Grade database requires migration/revalidation or repair") from exc
    finally:
        connection.close()

    if not sections:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    return {
        "course": f"{subject} {course_number}",
        "term": term,
        "section_count": len(sections),
        "sections": sections
    }
