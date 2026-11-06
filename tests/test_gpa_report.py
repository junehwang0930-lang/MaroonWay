import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from pdf_fixture import write_pdf
from test_metadata import HEADER
from test_integrity import GOOD

ROOT=Path(__file__).resolve().parents[1]
class GPAReportTests(unittest.TestCase):
    def test_readonly_report_unique_paths_sorted_and_zero_total_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pdf=root/'source.pdf';output=root/'reports'
            text=HEADER+GOOD.replace('3.500','0.000')+'\n'+GOOD.replace('-200 ','-201 ').replace('3.500','3.490')+'\n'+GOOD.replace('-200 ','-202 ').replace('7 4 1 0 0 12 3.500 0 0 0 0 0 12','0 0 0 0 0 0 N/A 0 12 0 0 0 12')
            write_pdf(pdf,text);before=pdf.read_bytes()
            command=[sys.executable,str(ROOT/'scripts/investigate_gpa.py'),'--pdf',str(pdf),'--output',str(output)]
            for _ in range(2):
                result=subprocess.run(command,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            files=list(output.glob('*.csv'));self.assertEqual(len(files),2)
            with files[0].open(encoding='utf-8-sig') as handle:rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[0]['section'],'200')
            self.assertEqual(rows[0]['review_status'],'unexplained_mismatch')
            self.assertEqual(rows[-1]['gpa_calculated'],'')
            self.assertEqual(pdf.read_bytes(),before)
            self.assertFalse(list(root.rglob('*.db')))

    def test_multiple_original_review_items_are_separate_and_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pdf=root/'source.pdf';write_pdf(pdf,HEADER+GOOD.replace('3.500','0.000'))
            review=root/'original.csv'
            review.write_text('section_code,issue\nSTAT-211-200,GPA mismatch\nSTAT-211-200,Other source concern\n')
            before=review.read_bytes()
            result=subprocess.run([sys.executable,str(ROOT/'scripts/investigate_gpa.py'),'--pdf',str(pdf),'--output',str(root/'output'),'--review-csv',str(review)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            with next((root/'output').glob('*.csv')).open(encoding='utf-8-sig') as handle:rows=list(csv.DictReader(handle))
            self.assertEqual([r['review_item_number'] for r in rows],['1','2'])
            self.assertEqual([r['review_item'] for r in rows],['GPA mismatch','Other source concern'])
            self.assertEqual(review.read_bytes(),before)

    def test_mismatched_review_context_is_rejected_without_output(self):
        import hashlib
        for context in ['2025-FALL,AT,','2026-SPRING,EN,','2026-SPRING,AT,wrong-hash']:
            with self.subTest(context=context),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);pdf=root/'source.pdf';write_pdf(pdf,HEADER+GOOD)
                review=root/'review.csv';review.write_text('term,college,source_sha256,section_code,issue\n'+context+',STAT-211-200,Old issue\n')
                result=subprocess.run([sys.executable,str(ROOT/'scripts/investigate_gpa.py'),'--pdf',str(pdf),'--review-csv',str(review),'--output',str(root/'out')],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(list(root.glob('out/*.csv')))

    def test_legacy_review_context_is_explicitly_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pdf=root/'source.pdf';write_pdf(pdf,HEADER+GOOD)
            review=root/'review.csv';review.write_text('section_code,issue\nSTAT-211-200,Historical note\n')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/investigate_gpa.py'),'--pdf',str(pdf),'--review-csv',str(review),'--output',str(root/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            with next((root/'out').glob('*.csv')).open(encoding='utf-8-sig') as h:row=next(csv.DictReader(h))
            self.assertEqual(row['review_association'],'unverified')
