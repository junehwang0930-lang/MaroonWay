import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import decode_row, parse_pages


class ParsingTests(unittest.TestCase):
    def test_valid_single_line(self):
        row = decode_row("MATH-151-500 12 8 5 4 0 29 2.965 0 0 0 0 0 29 JONES A", 3)
        self.assertEqual((row.subject, row.number, row.section), ("MATH", "151", "500"))
        self.assertEqual((row.gpa, row.instructor_raw), (2.965, "JONES A"))
        self.assertEqual(row.issues, [])

    def test_buffered_lines_and_percentage_skipping(self):
        text = "MATH-151-500 12\n41.38%\n8\n27.59%\n5\n4\n0\n29\n2.965\n0 0 0 0 0 29 JONES A\nSTAT-211-200 7 4 1 0 0 12 3.500 0 0 0 0 0 12 SMITH B"
        found, review = parse_pages([text])
        self.assertEqual(len(found), 2)
        self.assertFalse(review)

    def test_inline_percentages_are_ignored(self):
        row = decode_row("STAT-211-200 7 58.33% 4 33.33% 1 0 0 12 3.500 0 0 0 0 0 12 SMITH B", 1)
        self.assertEqual((row.af_total, row.gpa), (12, 3.5))

    def test_rejects_bad_gpa(self):
        row = decode_row("STAT-211-200 10 0 0 0 0 10 2.000 0 0 0 0 0 10 SMITH B", 1)
        self.assertIn("Reported GPA does not match A-F counts", row.issues)

    def test_loses_no_uncertain_row_silently(self):
        found, review = parse_pages(["STAT-211-200 missing data\nMATH-151-500 12 8 5 4 0 29 2.965 0 0 0 0 0 29 JONES A"])
        self.assertEqual(len(found), 1)
        self.assertTrue(any("Could not parse" in x[2] for x in review))

    def test_no_fake_instructor_match(self):
        row = decode_row("STAT-211-200 7 4 1 0 0 12 3.500 0 0 0 0 0 12 SMITH B", 1)
        self.assertEqual(row.instructor_raw, "SMITH B")
        self.assertFalse(hasattr(row, "professor_id"))

    def test_duplicate_key_is_flagged(self):
        line = "STAT-211-200 7 4 1 0 0 12 3.500 0 0 0 0 0 12 SMITH B"
        found, review = parse_pages([line+"\n"+line])
        self.assertEqual(len(found), 1)
        self.assertTrue(any("Duplicate section" in x[2] for x in review))


if __name__ == "__main__":
    unittest.main()
