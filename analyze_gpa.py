from contextlib import closing
import sqlite3
from pathlib import Path

# Find our database
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "maroonway.db"

# Choose a course
subject = "STAT"
course = "211"

# Connect to SQLite
with closing(sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)) as connection:

    # Search for historical sections
    query = """
    SELECT
        section,
        instructor_as_reported,
        gpa_reported,
        af_total
    FROM public_grade_sections
    WHERE subject = ? AND course_number = ?
    ORDER BY gpa_reported DESC;
    """

    cursor = connection.execute(query, (subject, course))

    # Print each result
    for row in cursor:
        print(row)
