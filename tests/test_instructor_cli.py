from contextlib import closing,redirect_stdout
import csv
import io
import os
import shutil
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import pipeline as p
from pdf_fixture import write_pdf
from test_integrity import GOOD
from test_metadata import HEADER

class InstructorCLITests(unittest.TestCase):
    def test_explicit_confirmations_cli_does_not_modify_original_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'fixture.db';pdf=root/'source.pdf'
            write_pdf(pdf,HEADER+GOOD.replace('STAT-211-200','STAT-201-504').replace('SMITH B','HERNANDEZ'))
            with patch.object(p,'DATA',root),patch.object(p,'DB_PATH',db),redirect_stdout(io.StringIO()):p.import_pdf(pdf)
            (root/'scripts').mkdir()
            script=root/'scripts/apply_name_reviews.py'
            shutil.copy2(p.ROOT/'scripts/apply_name_reviews.py',script)
            environment=dict(os.environ,PYTHONPATH=str(p.ROOT))
            result=subprocess.run([sys.executable,str(script),'--db',str(db),'--confirmations',str(p.ROOT/'data/user_confirmed_instructors.csv')],capture_output=True,text=True,env=environment)
            self.assertEqual(result.returncode,0,result.stderr)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('select instructor_as_reported from grade_sections').fetchone()[0],'HERNANDEZ')
                # Confirmation alone must not skip fresh source validation.
                self.assertEqual(con.execute('select count(*) from public_grade_sections').fetchone()[0],0)
            import storage
            result=storage.revalidate(db)
            self.assertEqual(result['checks_passed'],1)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('select instructor_display_name from public_grade_sections').fetchone()[0],'HERNANDEZ I')
