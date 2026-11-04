import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException

# Database location
DB_PATH = Path(__file__).resolve().parent / "data" / "maroonway.db"

# Create our API
app = FastAPI(title="MaroonWay API")


@app.get("/")
def home():
    return {"message": "Welcome to MaroonWay!"}


@app.get("/courses/{subject}/{course_number}")
def get_course(subject: str, course_number: str):

    subject = subject.upper()

    if subject not in {"STAT", "MATH"}:
        raise HTTPException(
            status_code=400,
            detail="Only STAT and MATH are supported"
        )

    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Grade database is not available"
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        query = """
        SELECT
            section,
            instructor_as_reported,
            gpa_reported,
            af_total,
            quality_status
        FROM grade_sections
        WHERE term = ?
          AND subject = ?
          AND course_number = ?
        ORDER BY gpa_reported DESC;
        """

        rows = connection.execute(
            query,
            ("2026-SPRING", subject, course_number)
        ).fetchall()

        sections = [dict(row) for row in rows]

    finally:
        connection.close()

    if not sections:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    return {
        "course": f"{subject} {course_number}",
        "term": "2026-SPRING",
        "section_count": len(sections),
        "sections": sections
    }
