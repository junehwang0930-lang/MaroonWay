from contextlib import closing
import contextlib
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

class PublicationTests(unittest.TestCase):
    def setUp(self):
        import api
        self.api=api
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/'test.db'
        self.pdf=self.root/'source.pdf'
        body=GOOD+'\n'+GOOD.replace('-200 ','-201 ').replace('7 4 1 0 0 12 3.500','-1 4 0 0 0 3 2.666').replace('0 0 0 0 0 12','0 2 0 0 0 5')
        write_pdf(self.pdf, HEADER+body)
        with patch.object(p,'DATA',self.root),patch.object(p,'DB_PATH',self.db),patch.object(p,'read_pdf_pages',return_value=[HEADER+body]),contextlib.redirect_stdout(io.StringIO()):
            p.import_pdf(self.pdf)
        self.binding=patch.object(api,'DB_PATH',self.db)
        self.binding.start()
        self.addCleanup(self.binding.stop)

    def test_only_validated_nonnegative_sections_are_public(self):
        data=self.api.get_course('stat','211')
        self.assertEqual([r['section'] for r in data['sections']],['200'])
        self.assertEqual(data['sections'][0]['source_page'],1)

    def test_all_subjects_and_supported_terms(self):
        # A well-formed subject is accepted even when no data was imported.
        with self.assertRaises(self.api.HTTPException) as caught:
            self.api.get_course('CHEM','119',term='2023-FALL')
        self.assertEqual(caught.exception.status_code,404)
        for term in ['2023-SPRING','2025-SUMMER','2026-FALL']:
            with self.subTest(term=term),self.assertRaises(self.api.HTTPException) as caught:
                self.api.get_course('STAT','211',term=term)
            self.assertEqual(caught.exception.status_code,400)

    def test_unmigrated_database_is_503_and_not_modified(self):
        other=self.root/'legacy.db'
        with closing(sqlite3.connect(other)) as con, con:con.execute('create table unrelated (id integer)')
        before=other.read_bytes()
        with patch.object(self.api,'DB_PATH',other),self.assertRaises(self.api.HTTPException) as caught:
            self.api.get_course('STAT','211')
        self.assertEqual(caught.exception.status_code,503)
        self.assertEqual(before,other.read_bytes())

    def test_stored_edit_cannot_reuse_old_validation(self):
        with closing(sqlite3.connect(self.db)) as con, con:con.execute("update grade_sections set a=99")
        with self.assertRaises(self.api.HTTPException) as caught:self.api.get_course('STAT','211')
        self.assertEqual(caught.exception.status_code,404)

    def test_console_summaries_use_only_public_records(self):
        import shutil, subprocess, sys
        for script in ['analyze_gpa.py','course_summary.py','instructor_summary.py']:
            with self.subTest(script=script):
                shutil.copy2(p.ROOT/script,self.root/script)
                (self.root/'data').mkdir(exist_ok=True)
                shutil.copy2(self.db,self.root/'data/maroonway.db')
                result=subprocess.run([sys.executable,str(self.root/script)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                if script=='course_summary.py':
                    self.assertIn('Sections: 1',result.stdout)
                    self.assertIn('Weighted GPA: 3.5',result.stdout)
                elif script=='analyze_gpa.py':
                    self.assertNotIn("'201'",result.stdout)
                else:
                    self.assertIn("'SMITH B', 1, 12, 3.5",result.stdout)
