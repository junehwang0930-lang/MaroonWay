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

    def test_official_totals_and_percentages_are_not_part_of_name(self):
        text=GOOD+'\n58.33% 33.33% 8.33% 0.00% 0.00%\nCOURSE TOTAL: 7 4 1 0 0 12 3.500 0 0 0 0 0 12\nDEPARTMENT TOTAL: 7 4 1 0 0 12 3.500 0 0 0 0 0 12'
        rows,review=parse_pages([text])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].instructor_raw,'SMITH B')
        self.assertFalse(review)

    def test_unicode_names_preserve_original_spelling(self):
        for name in ['GONZÁLEZ SOMOZA M', 'GONZA\u0301LEZ SOMOZA M', 'O’NEILL Á', 'MUÑOZ É', 'González Somoza M']:
            with self.subTest(name=name):
                row=decode_row(GOOD.replace('SMITH B',name),1)
                self.assertIsNotNone(row)
                self.assertEqual(row.instructor_raw,name)
                self.assertFalse(row.issues)

    def test_unicode_name_does_not_relax_integrity_checks(self):
        row=decode_row(GOOD.replace('SMITH B','GONZÁLEZ SOMOZA').replace('3.500','0.000'),1)
        self.assertIsNotNone(row)
        self.assertIn('Instructor name lacks an identifiable final initial',row.issues)
        self.assertIn('Reported GPA does not match A-F counts',row.issues)
        self.assertIsNone(decode_row(GOOD.replace('SMITH B','GONZÁLEZ 123 M'),1))

    def test_unicode_symbols_controls_and_unattached_marks_are_rejected(self):
        for name in ['SMITH 😀 B','SMITH\u202e B','SMITH \u0301 B','SMITH <B>','SMITH; B']:
            with self.subTest(name=name):
                self.assertIsNone(decode_row(GOOD.replace('SMITH B',name),1))

    def test_gpa_difference_up_to_five_thousandths_is_inclusive(self):
        for gpa in ['3.498','3.495','3.505']:
            with self.subTest(gpa=gpa):
                row=decode_row(GOOD.replace('3.500',gpa),1)
                self.assertNotIn('Reported GPA does not match A-F counts',row.issues)
                self.assertEqual(row.gpa,float(gpa))

    def test_gpa_difference_above_tolerance_remains_reviewable(self):
        for gpa in ['3.494999','3.505001','0.000']:
            with self.subTest(gpa=gpa):
                row=decode_row(GOOD.replace('3.500',gpa),1)
                self.assertIn('Reported GPA does not match A-F counts',row.issues)

    def test_gpa_tolerance_does_not_clear_missing_initial_or_negative_counts(self):
        row=decode_row(GOOD.replace('3.500','3.505').replace('SMITH B','SMITH'),1)
        self.assertIn('Instructor name lacks an identifiable final initial',row.issues)
        bad=decode_row('STAT-211-200 -1 4 0 0 0 3 2.671 0 2 0 0 0 5 SMITH B',1)
        self.assertIn('Negative count: a',bad.issues)
