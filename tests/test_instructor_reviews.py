"""Exact user confirmations are evidence; they never overwrite PDF data."""
from contextlib import closing, redirect_stdout
import csv
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import pipeline
import storage
from pdf_fixture import write_pdf
from test_integrity import GOOD
from test_metadata import HEADER

FIELDS = 'term college section_code instructor_as_reported reviewed_instructor_name initial name_scope evidence review_note'.split()
REVIEWS = [
    ('ECON-202-M01','VILLAVICENCIO','Xavier Villavicencio','X','full_name'),
    ('SPAN-102-504','DE LOS SANTOS','Rodrigo De Los Santos','R','full_name'),
    ('STAT-201-504','HERNANDEZ','HERNANDEZ I','I','initial_only'),
    ('STAT-201-507','HERNANDEZ','HERNANDEZ I','I','initial_only'),
]

class InstructorReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root/'fixture.db'
        self.csv = self.root/'confirmations.csv'
        self.pdf = self.root/'source.pdf'
        body = '\n'.join(GOOD.replace('STAT-211-200',code).replace('SMITH B',raw) for code,raw,*_ in REVIEWS)
        body += '\n'+GOOD.replace('STAT-211-200','STAT-201-508').replace('SMITH B','HERNANDEZ')
        write_pdf(self.pdf,HEADER+body)
        with patch.object(pipeline,'DATA',self.root), patch.object(pipeline,'DB_PATH',self.db), redirect_stdout(io.StringIO()):
            pipeline.import_pdf(self.pdf)
        self.write_reviews()
        self.original = self.rows('select * from grade_sections')

    def rows(self,sql,args=()):
        with closing(sqlite3.connect(self.db)) as con:
            return con.execute(sql,args).fetchall()

    def write_reviews(self, **override):
        with self.csv.open('w',newline='',encoding='utf-8') as handle:
            writer = csv.DictWriter(handle,fieldnames=FIELDS)
            writer.writeheader()
            for code,raw,name,initial,scope in REVIEWS:
                row=dict(zip(FIELDS,['2026-SPRING','AT',code,raw,name,initial,scope,'user_confirmed','Confirmed by project owner; not independently TAMU verified']))
                row.update(override)
                writer.writerow(row)

    def test_four_exact_reviews_require_fresh_audit_and_preserve_source(self):
        from instructor_reviews import apply_confirmations
        result=apply_confirmations(self.db,self.csv)
        self.assertEqual(result['applied'],4)
        self.assertEqual(self.rows('select count(*) from public_grade_sections')[0][0],0)
        result=storage.revalidate(self.db)
        self.assertEqual(result['checks_passed'],4)
        self.assertEqual(self.rows('select * from grade_sections'),self.original)
        shown=self.rows('select instructor_display_name,instructor_review_evidence,instructor_review_scope,instructor_initial from public_grade_sections order by subject,section')
        self.assertEqual(shown,[(r[2],'user_confirmed',r[4],r[3]) for r in REVIEWS])
        self.assertEqual(storage.revalidate(self.db)['checks_passed'],4)
        self.assertEqual(len(self.rows('select * from grade_validation_instructor_reviews')),8)
        self.assertIn('Instructor name lacks an identifiable final initial',self.rows('select issues_json from grade_validations order by id desc limit 2')[1][0])

    def test_confirmation_never_resolves_other_integrity_failures(self):
        from instructor_reviews import apply_confirmations
        apply_confirmations(self.db,self.csv)
        with closing(sqlite3.connect(self.db)) as con,con:
            con.execute("update grade_sections set a=-1 where subject='ECON'")
        self.assertEqual(storage.revalidate(self.db)['checks_passed'],3)
        self.assertFalse(self.rows("select * from public_grade_sections where subject='ECON'"))

    def test_exact_term_college_original_text_and_section_required(self):
        from instructor_reviews import apply_confirmations
        for changes in ({'term':'2025-FALL'},{'college':'EN'},{'instructor_as_reported':'HERNANDEZ ','reviewed_instructor_name':'HERNANDEZ  I'},{'section_code':'STAT-201-999'}):
            with self.subTest(changes=changes):
                self.write_reviews(**changes)
                result=apply_confirmations(self.db,self.csv)
                self.assertEqual(result['applied'],0)
        self.assertEqual(storage.revalidate(self.db)['checks_passed'],0)

    def test_append_only_idempotent_and_atomic_invalid_evidence(self):
        from instructor_reviews import apply_confirmations
        apply_confirmations(self.db,self.csv)
        self.assertEqual(apply_confirmations(self.db,self.csv)['applied'],0)
        self.assertEqual(len(self.rows('select * from instructor_reviews')),4)
        with closing(sqlite3.connect(self.db)) as con:
            for sql in ('delete from instructor_reviews','update instructor_reviews set initial="Z"'):
                with self.assertRaises(sqlite3.IntegrityError): con.execute(sql)
        self.write_reviews(evidence='tamu_verified')
        with self.assertRaises(ValueError): apply_confirmations(self.db,self.csv)
        self.assertEqual(len(self.rows('select * from instructor_reviews')),4)

    def test_api_separates_reported_name_from_owner_confirmed_display(self):
        import api
        from instructor_reviews import apply_confirmations
        apply_confirmations(self.db,self.csv)
        storage.revalidate(self.db)
        with patch.object(api,'DB_PATH',self.db):
            result=api.get_course('STAT','201',term='2026-SPRING',college='AT')
        self.assertEqual(len(result['sections']),2)
        for row in result['sections']:
            self.assertEqual(row['instructor_as_reported'],'HERNANDEZ')
            self.assertEqual(row['instructor_display_name'],'HERNANDEZ I')
            self.assertEqual(row['instructor_review_scope'],'initial_only')
            self.assertEqual(row['instructor_review_evidence'],'user_confirmed')
            self.assertEqual(row['instructor_initial'],'I')

    def test_reimport_keeps_confirmation_and_all_prior_audits(self):
        from instructor_reviews import apply_confirmations
        apply_confirmations(self.db,self.csv)
        with patch.object(pipeline,'DATA',self.root), patch.object(pipeline,'DB_PATH',self.db), redirect_stdout(io.StringIO()):
            pipeline.import_pdf(self.pdf)
        self.assertEqual(self.rows('select count(*) from public_grade_sections')[0][0],4)
        self.assertEqual(self.rows('select count(*) from instructor_reviews')[0][0],4)
        self.assertEqual(self.rows('select count(*) from grade_validations')[0][0],10)
        self.assertEqual(self.rows('select * from grade_sections'),self.original)

    def test_v4_backup_and_repeat_migration_preserve_source_and_audits(self):
        backups=list(self.root.glob('*.before-v4-*.db'))
        self.assertEqual(len(backups),1)
        with closing(sqlite3.connect(backups[0])) as con:
            self.assertIsNone(con.execute("select name from sqlite_master where name='instructor_reviews'").fetchone())
        audits=self.rows('select * from grade_validations')
        storage.migrate(self.db)
        self.assertEqual(len(list(self.root.glob('*.before-v4-*.db'))),1)
        self.assertEqual(self.rows('select * from grade_sections'),self.original)
        self.assertEqual(self.rows('select * from grade_validations'),audits)
