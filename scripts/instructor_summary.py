from contextlib import closing
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "maroonway.db"

term = "2026-SPRING"
subject = "STAT"
course = "211"

with closing(sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)) as connection:

    query = """
    SELECT
        instructor_as_reported,
        COUNT(*) AS section_count,
        SUM(af_total) AS student_count,
        ROUND(
            (4.0 * SUM(a) + 3.0 * SUM(b)
             + 2.0 * SUM(c) + SUM(d))
            / NULLIF(SUM(af_total), 0),
            3
        ) AS weighted_gpa
    FROM public_grade_sections
    WHERE term = ?
      AND subject = ?
      AND course_number = ?
    GROUP BY instructor_as_reported
    HAVING SUM(af_total) > 0
    ORDER BY weighted_gpa DESC;
    """

    cursor = connection.execute(query, (term, subject, course))

    for row in cursor:
        print(row)
