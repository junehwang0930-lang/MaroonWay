"""Calculated GPA publication requires fresh, source-verified evidence."""
from contextlib import closing, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import api
import pipeline as p
import storage
from pdf_fixture import write_pdf
from test_integrity import GOOD
from test_metadata import HEADER


class CalculatedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'maroonway.db'
        self.pdf = self.root / 'source.pdf'
        for name, value in [('DATA', self.root), ('DB_PATH', self.db)]:
            patcher = patch.object(p, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def import_rows(self, body):
        write_pdf(self.pdf, HEADER + body)
        with redirect_stdout(io.StringIO()):
            p.import_pdf(self.pdf)

    def public(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute('select * from public_grade_sections')]

    def test_reported_zero_is_preserved_and_calculated_is_public(self):
        self.import_rows(GOOD.replace('3.500', '0.000'))
        row = self.public()[0]
        self.assertEqual(row['gpa_reported'], 0)
        self.assertEqual(row['gpa_calculated'], 3.5)
        self.assertEqual(row['gpa_difference'], 3.5)
        self.assertEqual(row['gpa_discrepancy'], 1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertIn('Reported GPA does not match A-F counts', json.loads(con.execute('select issues_json from grade_validations').fetchone()[0]))
        result = storage.revalidate(self.db)
        self.assertEqual(result['checks_passed'], 1)

    def test_matching_and_mismatching_sections_sorted_by_calculated(self):
        self.import_rows(GOOD.replace('3.500', '0.000') + '\n' + GOOD.replace('-200 ', '-201 ').replace('7 4 1 0 0 12 3.500', '6 4 2 0 0 12 4.000'))
        with patch.object(api, 'DB_PATH', self.db):
            rows = api.get_course('STAT', '211')['sections']
        self.assertEqual([r['section'] for r in rows], ['200', '201'])
        self.assertEqual(rows[0]['gpa_calculated'], 3.5)
        self.assertEqual(rows[1]['gpa_calculated'], 40 / 12)

    def test_normal_match_has_no_discrepancy(self):
        self.import_rows(GOOD)
        self.assertEqual(self.public()[0]['gpa_discrepancy'], 0)
        self.assertEqual(self.public()[0]['gpa_difference'], 0)

    def test_zero_af_students_has_null_gpa(self):
        body = GOOD.replace('7 4 1 0 0 12 3.500 0 0 0 0 0 12', '0 0 0 0 0 0 0.000 0 12 0 0 0 12')
        self.import_rows(body)
        row = self.public()[0]
        self.assertIsNone(row['gpa_calculated'])
        self.assertIsNone(row['gpa_difference'])
        self.assertIsNone(row['gpa_discrepancy'])
        self.assertEqual(storage.revalidate(self.db)['checks_passed'], 1)

    def test_zero_af_with_na_reported_is_valid_but_positive_af_na_is_blocked(self):
        body = GOOD.replace('7 4 1 0 0 12 3.500 0 0 0 0 0 12', '0 0 0 0 0 0 N/A 0 12 0 0 0 12')
        self.import_rows(body)
        self.assertIsNone(self.public()[0]['gpa_calculated'])
        self.assertIsNone(self.public()[0]['gpa_reported'])
        self.assertIsNone(self.public()[0]['gpa_discrepancy'])
        self.assertEqual(storage.revalidate(self.db)['checks_passed'], 1)
        self.import_rows(GOOD.replace('-200 ', '-201 ').replace('3.500', 'N/A'))
        self.assertEqual(len(self.public()), 1)

    def test_tolerance_boundary_and_absolute_difference(self):
        self.import_rows(GOOD.replace('3.500', '3.505') + '\n' + GOOD.replace('-200 ', '-201 ').replace('3.500', '3.495') + '\n' + GOOD.replace('-200 ', '-202 ').replace('3.500', '3.506'))
        rows = self.public()
        self.assertEqual([r['gpa_discrepancy'] for r in rows], [0, 0, 1])
        self.assertTrue(all(r['gpa_difference'] > 0 for r in rows))

    def test_discrepancy_uses_exact_audit_boundary(self):
        body = GOOD.replace('7 4 1 0 0 12 3.500 0 0 0 0 0 12', '9 1 0 0 0 10 3.905 0 0 0 0 0 10')
        self.import_rows(body + '\n' + body.replace('-200 ', '-201 ').replace('3.905', '3.90500000000001'))
        rows = self.public()
        self.assertEqual([r['gpa_discrepancy'] for r in rows], [0, 1])

    def test_other_integrity_failures_remain_blocked(self):
        bad = [GOOD.replace('7 4 1', '-1 4 1'), GOOD.replace('7 4 1', '8 4 1'), GOOD.replace('SMITH B', 'SMITH'), GOOD.replace('3.500', '4.500')]
        for index, body in enumerate(bad):
            with self.subTest(body=body):
                self.import_rows(body.replace('-200 ', f'-{200+index} '))
                self.assertEqual(self.public(), [])
        self.assertEqual(storage.revalidate(self.db)['checks_passed'], 0)

    def test_conflicting_reimport_stays_blocked(self):
        self.import_rows(GOOD)
        self.import_rows(GOOD.replace('SMITH B', 'JONES A'))
        self.assertEqual(self.public(), [])

    def test_old_audit_cannot_publish_without_fresh_source_verification(self):
        self.import_rows(GOOD)
        with closing(sqlite3.connect(self.db)) as con, con:
            before = con.execute('select * from grade_sections').fetchall()
            con.execute('drop table grade_validation_policies')
            con.execute('drop view public_grade_sections')
            con.execute('create view public_grade_sections as select * from grade_sections')
            con.execute('delete from schema_migrations where version=3')
        storage.migrate(self.db)
        self.assertEqual(self.public(), [])
        self.assertEqual(len(list(self.root.glob('*.before-v3-*.db'))), 1)
        storage.migrate(self.db)
        self.assertEqual(len(list(self.root.glob('*.before-v3-*.db'))), 1)
        self.assertEqual(storage.revalidate(self.db)['checks_passed'], 1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(), before)
            self.assertEqual(con.execute('select count(*) from grade_validations').fetchone()[0], 2)

    def test_verified_bytes_are_identical_to_archived_bytes(self):
        write_pdf(self.pdf, HEADER + GOOD)
        expected = self.pdf.read_bytes()
        original = p.read_pdf_pages
        with patch.object(p, 'read_pdf_pages', wraps=original) as reader, redirect_stdout(io.StringIO()):
            p.import_pdf(self.pdf)
        self.assertEqual(reader.call_args.args[0], expected)
