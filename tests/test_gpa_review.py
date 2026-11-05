"""GPA investigations preserve source evidence and publication controls."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import storage


class AssessmentTests(unittest.TestCase):
    def assess(self, **changes):
        from gpa_review import assess_gpa
        row = dict(a=7, b=4, c=1, d=0, f=0, af_total=12, gpa_reported=3.5)
        row.update(changes)
        return assess_gpa(row)

    def test_normal_and_small_difference_match_without_claiming_cause(self):
        for reported in (3.5, 3.502, 3.505):
            result = self.assess(gpa_reported=reported)
            self.assertEqual(result['gpa_review_status'], 'matches_reported')
            self.assertTrue(result['confirmed'])

    def test_large_and_zero_reported_remain_unexplained(self):
        for reported in (3.4, 0):
            result = self.assess(gpa_reported=reported)
            self.assertEqual(result['gpa_review_status'], 'unexplained_mismatch')
            self.assertEqual(result['gpa_difference'], abs(3.5-reported))
            self.assertFalse(result['confirmed'])

    def test_zero_af_is_not_normal(self):
        result = self.assess(a=0,b=0,c=0,af_total=0,gpa_reported=0)
        self.assertIsNone(result['gpa_calculated'])
        self.assertIsNone(result['gpa_difference'])
        self.assertEqual(result['gpa_review_status'], 'unexplained_mismatch')

    def test_credit_hypotheses_require_documented_official_evidence(self):
        from gpa_review import assess_gpa
        row = dict(a=1,b=0,c=0,d=0,f=0,af_total=1,gpa_reported=0)
        for kind in ('variable', 'zero'):
            self.assertEqual(assess_gpa(row, {'credit_type':kind})['gpa_review_status'], 'unexplained_mismatch')
            evidence = {'credit_type':kind, 'official':True, 'source_url':'https://catalog.tamu.edu/example', 'excerpt':'Fixture official credit listing'}
            result = assess_gpa(row,evidence)
            self.assertEqual(result['gpa_review_status'], 'possible_'+kind+'_credit')
            self.assertFalse(result['confirmed'])
        self.assertEqual(assess_gpa(row, {'official':True,'source_url':'https://example.test','excerpt':'rule','explanation':'claim','confirmed':True})['gpa_review_status'], 'unexplained_mismatch')

    def test_invalid_counts_cannot_be_confirmed_as_numeric_matches(self):
        for changes in (
            dict(a=-1,b=1,c=1,d=0,f=0,af_total=1,gpa_reported=1),
            dict(a=0.5,b=0,c=0,d=0,f=0.5,af_total=1,gpa_reported=2),
            dict(a=1,b=0,c=0,d=0,f=0,af_total=2,gpa_reported=2),
        ):
            with self.subTest(changes=changes):
                result=self.assess(**changes)
                self.assertEqual(result['gpa_review_status'],'unexplained_mismatch')
                self.assertFalse(result['confirmed'])
                self.assertIsNone(result['gpa_calculated'])
                self.assertIn('counts',result['gpa_review_note'])

    def test_zero_reported_with_only_f_students_is_legitimate_numeric_match(self):
        result=self.assess(a=0,b=0,c=0,d=0,f=3,af_total=3,gpa_reported=0)
        self.assertEqual(result['gpa_review_status'],'matches_reported')
        self.assertEqual(result['gpa_calculated'],0)
        self.assertTrue(result['confirmed'])

    def test_count_calculation(self):
        from gpa_review import calculate_gpa
        self.assertEqual(calculate_gpa(1,0,0,0,1),4)
        self.assertIsNone(calculate_gpa(0,0,0,0,0))


class ReviewStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)/'fixture.db'
        storage.migrate(self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            columns = 'id,term,college,subject,course_number,section,instructor_as_reported,a,b,c,d,f,af_total,gpa_reported,i_count,s_count,u_count,q_count,x_count,enrollment_total,quality_status,source_url,source_sha256,source_page,raw_row'
            values = (42,'2026-SPRING','AT','PHYS','291','512','Fixture',1,0,0,0,0,1,0,0,0,0,0,0,1,'needs_review','https://example.test','fixture-hash',1,'original')
            con.execute('insert into grade_sections ('+columns+') values ('+','.join('?' for _ in values)+')', values)
            con.execute("insert into validation_runs values ('existing','today','history.csv')")
            con.execute("insert into grade_validations values (1,'existing',42,'needs_review','[]','{}')")
            self.original = con.execute('select * from grade_sections').fetchall()
            self.public_sql = con.execute("select sql from sqlite_master where name='public_grade_sections'").fetchone()[0]

    def test_migration_backup_and_idempotence_preserve_everything(self):
        from gpa_review import migrate_reviews
        backup = migrate_reviews(self.db)
        self.assertTrue(backup.is_file())
        with closing(sqlite3.connect(backup)) as con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),self.original)
            self.assertIsNone(con.execute("select name from sqlite_master where name='gpa_reviews'").fetchone())
        self.assertIsNone(migrate_reviews(self.db))
        self.assertEqual(len(list(self.db.parent.glob('*.before-gpa-v1-*.db'))),1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),self.original)
            self.assertEqual(con.execute('select count(*) from grade_validations').fetchone()[0],1)
            self.assertEqual(con.execute('select count(*) from validation_runs').fetchone()[0],1)
            self.assertEqual(con.execute('select version from schema_migrations order by version').fetchall(),[(2,),(3,),(4,)])
            self.assertEqual(con.execute('select version from gpa_review_migrations').fetchall(),[(1,)])
            self.assertEqual(con.execute("select sql from sqlite_master where name='public_grade_sections'").fetchone()[0],self.public_sql)

    def test_record_deduplicates_preserves_sources_and_marks_stale(self):
        from gpa_review import migrate_reviews, record_review
        migrate_reviews(self.db)
        first = record_review(self.db,42)
        self.assertEqual(record_review(self.db,42),first)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.row_factory=sqlite3.Row
            review = con.execute('select * from latest_gpa_reviews').fetchone()
            self.assertEqual(review['gpa_reported'],0)
            self.assertEqual(review['gpa_calculated'],4)
            self.assertEqual(review['review_stale'],0)
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)
            self.assertEqual(json.loads(con.execute('select snapshot_json from gpa_reviews').fetchone()[0])['id'],42)
            con.execute('update grade_sections set a=2 where id=42')
            review = con.execute('select * from latest_gpa_reviews').fetchone()
            self.assertEqual(review['review_stale'],1)
            self.assertIsNone(review['gpa_review_status'])
            self.assertIsNone(review['gpa_calculated'])
            self.assertEqual(con.execute('select count(*) from gpa_reviews').fetchone()[0],1)
        self.assertNotEqual(record_review(self.db,42),first)

    def test_verified_exception_requires_explicit_documentation_and_does_not_publish(self):
        from gpa_review import migrate_reviews, record_review
        migrate_reviews(self.db)
        for options in ({}, {'confirmed':True}, {'confirmed':True,'evidence':{'official':True}}):
            with self.assertRaises(ValueError):
                record_review(self.db,42,review_status='verified_exception',**options)
        record_review(self.db,42,review_status='verified_exception',confirmed=True,note='Human reviewed official cause',evidence={'official':True,'source_url':'https://registrar.tamu.edu/fixture','excerpt':'Fixture rule','explanation':'Fixture source explains this section'})
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),self.original)
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_reviews_are_append_only(self):
        from gpa_review import migrate_reviews, record_review
        migrate_reviews(self.db)
        record_review(self.db,42)
        with closing(sqlite3.connect(self.db)) as con:
            for sql in ('update gpa_reviews set confirmed=1','delete from gpa_reviews'):
                with self.assertRaises(sqlite3.IntegrityError): con.execute(sql)

    def test_connections_close_even_on_noop_and_failure(self):
        from gpa_review import migrate_reviews, record_review
        migrate_reviews(self.db)
        real_connect=sqlite3.connect
        connections=[]
        def connect(*args,**kwargs):
            con=real_connect(*args,**kwargs)
            connections.append(con)
            return con
        with patch('gpa_review.sqlite3.connect',side_effect=connect):
            migrate_reviews(self.db)
            record_review(self.db,42)
            with self.assertRaises(ValueError): record_review(self.db,999)
        for con in connections:
            with self.assertRaises(sqlite3.ProgrammingError): con.execute('select 1')
