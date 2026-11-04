import unittest
from pipeline import decode_row, parse_pages

GOOD = 'STAT-211-200 7 4 1 0 0 12 3.500 0 0 0 0 0 12 SMITH B'

class RowIntegrityTests(unittest.TestCase):
    def test_every_count_field_rejects_negative(self):
        for index in [*range(1, 7), *range(8, 14)]:
            with self.subTest(index=index):
                parts = GOOD.split()
                parts[index] = '-1'
                row = decode_row(' '.join(parts), 1)
                self.assertTrue(any('negative' in issue.lower() for issue in row.issues))

    def test_negative_balanced_counts_cannot_pass(self):
        row = decode_row('STAT-211-200 -1 4 0 0 0 3 2.666 0 2 0 0 0 5 SMITH B', 1)
        self.assertTrue(row.issues)

    def test_split_instructor_initial_is_preserved(self):
        rows, review = parse_pages([GOOD.replace('SMITH B', 'SMITH\nB')])
        self.assertEqual(rows[0].instructor_raw, 'SMITH B')
        self.assertFalse(review)
        self.assertFalse(rows[0].issues)

    def test_multiline_surname_is_preserved(self):
        rows, _ = parse_pages([GOOD.replace('SMITH B', 'DE LA\nCRUZ\nB')])
        self.assertEqual(rows[0].instructor_raw, 'DE LA CRUZ B')

    def test_uncertain_trailing_content_is_not_silently_lost(self):
        rows, review = parse_pages([GOOD + '\n??? UNKNOWN FOOTER'])
        self.assertTrue(review)
        self.assertTrue('??? UNKNOWN FOOTER' in review[0][3])
        self.assertFalse(rows)

    def test_all_undergraduate_subjects(self):
        rows, _ = parse_pages([GOOD.replace('STAT-211', 'CHEM-119')])
        self.assertEqual(len(rows), 1)

    def test_duplicate_marks_retained_row_as_uncertain(self):
        rows, review = parse_pages([GOOD + '\n' + GOOD.replace('SMITH B','JONES A')])
        self.assertTrue(review)
        self.assertTrue(rows[0].issues)
