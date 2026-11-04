import contextlib
import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pipeline as p
from test_integrity import GOOD
from test_metadata import HEADER

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root/'maroonway.db'
        self.pdf = self.root/'source.pdf'
        self.pdf.write_bytes(b'%PDF-synthetic integration fixture')
        self.patchers = [patch.object(p,'DATA',self.root),patch.object(p,'DB_PATH',self.db)]
        for item in self.patchers: item.start()

    def tearDown(self):
        for item in self.patchers: item.stop()
        self.tmp.cleanup()

    def import_rows(self, body=GOOD):
        with patch.object(p,'read_pdf_pages',return_value=[HEADER+body]), contextlib.redirect_stdout(io.StringIO()):
            p.import_pdf(self.pdf)

    def test_import_preserves_existing_review_and_unique_run_history(self):
        legacy=self.root/'quality_review.csv'; legacy.write_text('existing review work\n')
        self.import_rows(GOOD+'\nMATH-151-500 missing data')
        self.import_rows()
        self.assertEqual(legacy.read_text(),'existing review work\n')
        reports=list((self.root/'import_reviews').glob('*.csv'))
        self.assertEqual(len(reports),2)
        sizes=[]
        for f in reports:
            with f.open() as handle: sizes.append(len(list(csv.DictReader(handle))))
        self.assertEqual(sorted(sizes),[0,1])
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select count(*) from import_runs').fetchone()[0],2)
            self.assertEqual(con.execute('select count(*) from grade_sections').fetchone()[0],1)
            self.assertEqual(con.execute('select count(*) from import_review_items').fetchone()[0],1)
        self.assertEqual(len(list((self.root/'sources').glob('*.pdf'))),1)

    def test_metadata_failure_leaves_database_untouched(self):
        self.import_rows()
        before=self.db.read_bytes()
        with patch.object(p,'read_pdf_pages',return_value=[GOOD]):
            with self.assertRaises(ValueError): p.import_pdf(self.pdf)
        self.assertEqual(before,self.db.read_bytes())

    def test_other_subject_supported_in_database(self):
        self.import_rows(GOOD.replace('STAT-211','CHEM-119'))
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select subject from grade_sections').fetchone()[0],'CHEM')

    def test_conflicting_reimport_quarantines_and_preserves_original(self):
        self.import_rows()
        self.pdf.write_bytes(b'%PDF-new-source-fixture')
        self.import_rows(GOOD.replace('SMITH B','JONES A'))
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select instructor_as_reported from grade_sections').fetchone()[0],'SMITH B')
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_migration_preserves_legacy_extensions_and_ids(self):
        import storage
        schema=(p.ROOT/'schema.sql').read_text()
        # Construct the original restricted schema, even after schema.sql is expanded.
        schema=schema.replace('subject TEXT NOT NULL,',"subject TEXT NOT NULL CHECK (subject IN ('STAT', 'MATH')),")
        with sqlite3.connect(self.db) as con:
            con.executescript(schema)
            con.execute('alter table grade_sections add column reviewed_instructor_name TEXT')
            values=('2026-SPRING','AT','STAT','211','200','SMITH B',7,4,1,0,0,12,3.5,0,0,0,0,0,12,'checks_passed','https://original.example/report','original-sha',1,GOOD)
            columns='term,college,subject,course_number,section,instructor_as_reported,a,b,c,d,f,af_total,gpa_reported,i_count,s_count,u_count,q_count,x_count,enrollment_total,quality_status,source_url,source_sha256,source_page,raw_row'
            con.execute(f'insert into grade_sections (id,{columns},reviewed_instructor_name) values (42,'+','.join('?' for _ in values)+",'Reviewed Name')",values)
            before=con.execute('select * from grade_sections').fetchall()
        storage.migrate(self.db)
        storage.migrate(self.db)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),before)
            self.assertEqual(con.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)
            sql=con.execute("select sql from sqlite_master where name='grade_sections'").fetchone()[0]
            self.assertNotIn("'STAT', 'MATH'",sql)
        self.assertEqual(len(list(self.root.glob('*.before-v2-*.db'))),1)

    def test_legacy_revalidation_preserves_data_and_does_not_invent_metadata(self):
        self.import_rows()
        import storage
        with sqlite3.connect(self.db) as con:
            con.execute("update grade_sections set a=-1")
            before=con.execute('select * from grade_sections').fetchall()
        report=storage.revalidate(self.db)
        self.assertEqual(report['total'],1)
        self.assertEqual(report['needs_review'],1)
        self.assertTrue(Path(report['report']).is_file())
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),before)
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_revalidation_accepts_equivalent_legacy_raw_formatting(self):
        import pymupdf
        import storage
        doc=pymupdf.open(); page=doc.new_page()
        page.insert_text((30,40),HEADER+GOOD+'\n58.33% 33.33% 8.33% 0.00% 0.00%',fontsize=8)
        doc.save(self.pdf); doc.close()
        with contextlib.redirect_stdout(io.StringIO()): p.import_pdf(self.pdf)
        with sqlite3.connect(self.db) as con:
            con.execute('update grade_sections set raw_row=?',(GOOD,))
        result=storage.revalidate(self.db)
        self.assertEqual(result['checks_passed'],1)

    def test_edit_after_audit_immediately_blocks_publication(self):
        self.import_rows()
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],1)
            con.execute("update grade_sections set a=8")
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_public_export_preserves_legacy_csv_and_clears_quarantined_rows(self):
        legacy=self.root/'grade_sections.csv';legacy.write_text('original exported evidence\n')
        self.import_rows()
        self.assertEqual(legacy.read_text(),'original exported evidence\n')
        with sqlite3.connect(self.db) as con:con.execute('update grade_sections set a=-1')
        p.export_csv()
        with (self.root/'public_grade_sections.csv').open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))),0)

    def test_revalidation_handles_malformed_legacy_values_without_crashing(self):
        import storage
        self.import_rows()
        with sqlite3.connect(self.db) as con:
            con.execute('update grade_sections set source_page=?,gpa_reported=?',('unknown',float('inf')))
        report=storage.revalidate(self.db)
        self.assertEqual(report['needs_review'],1)

    def test_nonfinite_gpa_is_recorded_for_review_without_losing_valid_rows(self):
        self.import_rows(GOOD+'\n'+GOOD.replace('-200 ','-201 ').replace('3.500','NaN'))
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select count(*) from grade_sections').fetchone()[0],1)
            self.assertEqual(con.execute('select count(*) from import_review_items').fetchone()[0],1)

    def test_migration_preserves_dependent_views_indexes_and_triggers(self):
        import storage
        schema=(p.ROOT/'schema.sql').read_text().replace('subject TEXT NOT NULL,',"subject TEXT NOT NULL CHECK (subject IN ('STAT', 'MATH')),")
        with sqlite3.connect(self.db) as con:
            con.executescript(schema)
            con.executescript('CREATE VIEW custom_sections AS SELECT id,subject FROM grade_sections; CREATE INDEX custom_name_index ON grade_sections(instructor_as_reported); CREATE TABLE touched (id INTEGER); CREATE TRIGGER custom_touch AFTER INSERT ON grade_sections BEGIN INSERT INTO touched VALUES (NEW.id); END;')
        storage.migrate(self.db)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('select * from custom_sections').fetchall(),[])
            names={r[0] for r in con.execute('select name from sqlite_master')}
            self.assertTrue({'custom_name_index','custom_touch'}<=names)

    def test_manual_review_rejects_ambiguous_college_and_accepts_explicit_college(self):
        import shutil, subprocess, sys
        self.import_rows()
        # Same section identity legitimately filed under a second College.
        with sqlite3.connect(self.db) as con:
            cols=[r[1] for r in con.execute('pragma table_info(grade_sections)') if r[1]!='id']
            values=list(con.execute('select '+','.join(cols)+' from grade_sections').fetchone())
            values[cols.index('college')]='EN'
            con.execute('insert into grade_sections ('+','.join(cols)+') values ('+','.join('?' for _ in cols)+')',values)
        sandbox=self.root/'manual'; (sandbox/'scripts').mkdir(parents=True)
        (sandbox/'data').mkdir()
        shutil.copy2(p.ROOT/'scripts/apply_name_reviews.py',sandbox/'scripts/apply_name_reviews.py')
        shutil.copy2(self.db,sandbox/'data/maroonway.db')
        csv_path=sandbox/'data/manual_instructor_reviews.csv'
        csv_path.write_text('term,section_code,instructor_as_reported,reviewed_instructor_name,review_status,review_note\n2026-SPRING,STAT-211-200,SMITH B,Example Person,candidate,fixture\n')
        command=[sys.executable,str(sandbox/'scripts/apply_name_reviews.py')]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('College',result.stderr)
        csv_path.write_text('college,'+csv_path.read_text().replace('\n2026-SPRING','\nEN,2026-SPRING'))
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with sqlite3.connect(sandbox/'data/maroonway.db') as con:
            self.assertEqual(con.execute("select college from grade_sections where reviewed_instructor_name='Example Person'").fetchall(),[('EN',)])
