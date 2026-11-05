from contextlib import closing
import sqlite3
import csv
from pathlib import Path

# Project file locations
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "maroonway.db"
OUTPUT = ROOT / "data" / "validation_sample.csv"

# Don't overwrite previous validation work
if OUTPUT.exists():
    print("Validation file already exists!")
else:
    with closing(sqlite3.connect(DB_PATH)) as connection:

        query = """
        SELECT
            subject,
            course_number,
            section,
            instructor_as_reported,
            a, b, c, d, f,
            af_total,
            gpa_reported,
            source_page
        FROM grade_sections
        WHERE subject = ?
        ORDER BY RANDOM()
        LIMIT 5;
        """

        rows = []

        for subject in ["MATH", "STAT"]:
            cursor = connection.execute(query, (subject,))
            rows.extend(cursor.fetchall())


    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)

        writer.writerow([
            "subject", "course_number", "section",
            "instructor_as_reported",
            "a", "b", "c", "d", "f",
            "af_total", "gpa_reported", "source_page",
            "pdf_check", "notes"
        ])

        for row in rows:
            writer.writerow(list(row) + ["", ""])

    print("Created validation_sample.csv")

    for row in rows:
        print(row[0], row[1], row[2], "PDF page:", row[11])
