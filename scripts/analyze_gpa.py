from contextlib import closing
import sqlite3
from pathlib import Path

# Find our database
ROOT = Path(__file__).resolve().parents[1]
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
        gpa_calculated,
        af_total,
        gpa_reported
    FROM public_grade_sections
    WHERE subject = ? AND course_number = ?
    ORDER BY gpa_calculated DESC;
    """

    cursor = connection.execute(query, (subject, course))

    # Keep the calculated metric primary and the unmodified source GPA separate.
    print("Section | Instructor | MaroonWay GPA (A-F based) | A-F students | TAMU Reported GPA")
    for row in cursor:
        print(row)
