import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "maroonway.db"

subject = "STAT"
course = "211"

connection = sqlite3.connect(DB_PATH)


# Choose a semester and course
term = "2026-SPRING"
subject = "STAT"
course = "211"

# SQL query
query = """
SELECT
    subject,
    course_number,
    COUNT(*) AS section_count,
    SUM(af_total) AS graded_students,
    ROUND(
        (4.0 * SUM(a) + 3.0 * SUM(b)
         + 2.0 * SUM(c) + SUM(d))
        / NULLIF(SUM(af_total), 0),
        3
    ) AS weighted_gpa
FROM grade_sections
WHERE term = ?
  AND subject = ?
  AND course_number = ?
GROUP BY subject, course_number;
"""

cursor = connection.execute(query, (term, subject, course))

row = cursor.fetchone()

if row:
    print("Course:", row[0], row[1])
    print("Sections:", row[2])
    print("Graded students:", row[3])
    print("Weighted GPA:", row[4])
else:
    print("No records found")

connection.close()
