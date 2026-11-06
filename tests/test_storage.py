from contextlib import closing
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
from pdf_fixture import write_pdf

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root/'maroonway.db'
        self.pdf = self.root/'source.pdf'
        write_pdf(self.pdf, HEADER+GOOD)
        self.patchers = [patch.object(p,'DATA',self.root),patch.object(p,'DB_PATH',self.db)]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)

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
        with closing(sqlite3.connect(self.db)) as con, con:
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
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select subject from grade_sections').fetchone()[0],'CHEM')

    def test_conflicting_reimport_quarantines_and_preserves_original(self):
        self.import_rows()
        write_pdf(self.pdf, HEADER+GOOD.replace('SMITH B','JONES A'))
        self.import_rows(GOOD.replace('SMITH B','JONES A'))
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select instructor_as_reported from grade_sections').fetchone()[0],'SMITH B')
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_migration_preserves_legacy_extensions_and_ids(self):
        import storage
        schema=(p.ROOT/'schema.sql').read_text()
        # Construct the original restricted schema, even after schema.sql is expanded.
        schema=schema.replace('subject TEXT NOT NULL,',"subject TEXT NOT NULL CHECK (subject IN ('STAT', 'MATH')),")
        with closing(sqlite3.connect(self.db)) as con, con:
            con.executescript(schema)
            con.execute('alter table grade_sections add column reviewed_instructor_name TEXT')
            values=('2026-SPRING','AT','STAT','211','200','SMITH B',7,4,1,0,0,12,3.5,0,0,0,0,0,12,'checks_passed','https://original.example/report','original-sha',1,GOOD)
            columns='term,college,subject,course_number,section,instructor_as_reported,a,b,c,d,f,af_total,gpa_reported,i_count,s_count,u_count,q_count,x_count,enrollment_total,quality_status,source_url,source_sha256,source_page,raw_row'
            con.execute(f'insert into grade_sections (id,{columns},reviewed_instructor_name) values (42,'+','.join('?' for _ in values)+",'Reviewed Name')",values)
            before=con.execute('select * from grade_sections').fetchall()
        storage.migrate(self.db)
        storage.migrate(self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),before)
            self.assertEqual(con.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)
            sql=con.execute("select sql from sqlite_master where name='grade_sections'").fetchone()[0]
            self.assertNotIn("'STAT', 'MATH'",sql)
        self.assertEqual(len(list(self.root.glob('*.before-v2-*.db'))),1)

    def test_legacy_revalidation_preserves_data_and_does_not_invent_metadata(self):
        self.import_rows()
        import storage
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("update grade_sections set a=-1")
            before=con.execute('select * from grade_sections').fetchall()
        report=storage.revalidate(self.db)
        self.assertEqual(report['total'],1)
        self.assertEqual(report['needs_review'],1)
        self.assertTrue(Path(report['report']).is_file())
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),before)
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_revalidation_accepts_equivalent_legacy_raw_formatting(self):
        import storage
        write_pdf(self.pdf, HEADER+GOOD+'\n58.33% 33.33% 8.33% 0.00% 0.00%')
        with contextlib.redirect_stdout(io.StringIO()): p.import_pdf(self.pdf)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute('update grade_sections set raw_row=?',(GOOD,))
        result=storage.revalidate(self.db)
        self.assertEqual(result['checks_passed'],1)

    def test_edit_after_audit_immediately_blocks_publication(self):
        self.import_rows()
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],1)
            con.execute("update grade_sections set a=8")
            self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)

    def test_public_export_preserves_legacy_csv_and_clears_quarantined_rows(self):
        legacy=self.root/'grade_sections.csv';legacy.write_text('original exported evidence\n')
        self.import_rows()
        self.assertEqual(legacy.read_text(),'original exported evidence\n')
        with closing(sqlite3.connect(self.db)) as con, con:con.execute('update grade_sections set a=-1')
        p.export_csv()
        with (self.root/'public_grade_sections.csv').open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))),0)

    def test_revalidation_handles_malformed_legacy_values_without_crashing(self):
        import storage
        self.import_rows()
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute('update grade_sections set source_page=?,gpa_reported=?',('unknown',float('inf')))
        report=storage.revalidate(self.db)
        self.assertEqual(report['needs_review'],1)

    def test_nonfinite_gpa_is_recorded_for_review_without_losing_valid_rows(self):
        self.import_rows(GOOD+'\n'+GOOD.replace('-200 ','-201 ').replace('3.500','NaN'))
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select count(*) from grade_sections').fetchone()[0],1)
            self.assertEqual(con.execute('select count(*) from import_review_items').fetchone()[0],1)

    def test_migration_preserves_dependent_views_indexes_and_triggers(self):
        import storage
        schema=(p.ROOT/'schema.sql').read_text().replace('subject TEXT NOT NULL,',"subject TEXT NOT NULL CHECK (subject IN ('STAT', 'MATH')),")
        with closing(sqlite3.connect(self.db)) as con, con:
            con.executescript(schema)
            con.executescript('CREATE VIEW custom_sections AS SELECT id,subject FROM grade_sections; CREATE INDEX custom_name_index ON grade_sections(instructor_as_reported); CREATE TABLE touched (id INTEGER); CREATE TRIGGER custom_touch AFTER INSERT ON grade_sections BEGIN INSERT INTO touched VALUES (NEW.id); END;')
        storage.migrate(self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('select * from custom_sections').fetchall(),[])
            names={r[0] for r in con.execute('select name from sqlite_master')}
            self.assertTrue({'custom_name_index','custom_touch'}<=names)

    def test_manual_review_rejects_ambiguous_college_and_accepts_explicit_college(self):
        import shutil, subprocess, sys
        self.import_rows()
        # Same section identity legitimately filed under a second College.
        with closing(sqlite3.connect(self.db)) as con, con:
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
        with closing(sqlite3.connect(sandbox/'data/maroonway.db')) as con, con:
            self.assertEqual(con.execute("select college from grade_sections where reviewed_instructor_name='Example Person'").fetchall(),[('EN',)])

    def test_download_never_overwrites_existing_source_pdf(self):
        from io import BytesIO
        original=self.pdf.read_bytes()
        with patch.object(p,'REPORTS',self.root),patch.object(p,'PDF_PATH',self.pdf),patch('urllib.request.urlopen',return_value=BytesIO(b'%PDF-changed-official-report')):
            with self.assertRaises(RuntimeError):p.download()
        self.assertEqual(self.pdf.read_bytes(),original)

    def test_unicode_name_survives_pdf_import_export_and_revalidation(self):
        import storage
        name='GONZÁLEZ SOMOZA M'
        write_pdf(self.pdf,HEADER+GOOD.replace('STAT-211-200','SPAN-101-501').replace('SMITH B',name))
        with contextlib.redirect_stdout(io.StringIO()):p.import_pdf(self.pdf)
        report=storage.revalidate(self.db)
        self.assertEqual(report['checks_passed'],1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('select instructor_as_reported from public_grade_sections').fetchone()[0],name)
        with (self.root/'public_grade_sections.csv').open(encoding='utf-8') as handle:
            self.assertEqual(next(csv.DictReader(handle))['instructor_as_reported'],name)

    def test_locked_public_csv_keeps_a_fresh_snapshot_and_explicit_pending_state(self):
        import os,json
        self.import_rows()
        old=(self.root/'public_grade_sections.csv').read_bytes()
        with closing(sqlite3.connect(self.db)) as con,con:
            con.execute('update grade_sections set a=-1')
        real_replace=os.replace
        def locked(source,target):
            if Path(target).name=='public_grade_sections.csv':raise PermissionError('Excel lock fixture')
            return real_replace(source,target)
        with patch('os.replace',side_effect=locked):result=p.export_csv()
        self.assertEqual(result['status'],'pending')
        self.assertEqual((self.root/'public_grade_sections.csv').read_bytes(),old)
        with Path(result['snapshot']).open() as handle:self.assertEqual(list(csv.DictReader(handle)),[])
        self.assertEqual(json.loads((self.root/'public_export_status.json').read_text())['status'],'pending')
        result=p.export_csv()
        self.assertEqual(result['status'],'ready')
        self.assertEqual(len(list((self.root/'public_exports').glob('*.csv'))),3)

    def test_export_only_cli_reports_partial_refresh_without_touching_database(self):
        import os
        self.import_rows()
        before=self.db.read_bytes()
        real_replace=os.replace
        def locked(source,target):
            if Path(target).name=='public_grade_sections.csv':raise PermissionError('Excel lock fixture')
            return real_replace(source,target)
        with patch('os.replace',side_effect=locked),patch('sys.argv',['pipeline.py','export-csv','--db',str(self.db)]),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as stopped:
            p.main()
        self.assertEqual(stopped.exception.code,2)
        self.assertEqual(self.db.read_bytes(),before)

    def test_equivalent_college_name_reimports_preserve_original_metadata(self):
        import json
        self.import_rows()
        with closing(sqlite3.connect(self.db)) as con:
            original=con.execute('select * from source_documents').fetchall()
            section=con.execute('select * from grade_sections').fetchall()
        with patch.object(p,'read_pdf_pages',return_value=[HEADER+GOOD]),contextlib.redirect_stdout(io.StringIO()):
            p.import_pdf(self.pdf,college_name='ARTS AND SCIENCES')
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('select * from source_documents').fetchall(),original)
            self.assertEqual(con.execute('select * from grade_sections').fetchall(),section)
            self.assertEqual(con.execute('select count(*) from import_conflicts').fetchone()[0],0)

    def test_source_registration_still_rejects_genuine_metadata_conflicts(self):
        from storage import register_source
        from report_metadata import ReportMetadata
        self.import_rows()
        with closing(sqlite3.connect(self.db)) as con:
            for metadata in [ReportMetadata(2025,'SPRING','AT','Arts & Sciences'),ReportMetadata(2026,'SPRING','EN','Engineering')]:
                with self.subTest(metadata=metadata),self.assertRaises(ValueError):
                    register_source(con,self.pdf.read_bytes(),metadata)
