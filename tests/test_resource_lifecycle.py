"""Leaks are checked explicitly, even on Linux where unlinking open files succeeds."""
from contextlib import closing, redirect_stdout
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import pymupdf
import pipeline
import storage
from test_integrity import GOOD
from test_metadata import HEADER

class ResourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/'test.db'
        self.pdf=self.root/'source.pdf'
        with pymupdf.open() as doc:
            doc.new_page().insert_text((30,40),HEADER+GOOD,fontsize=8)
            doc.save(self.pdf)
        self.connections=[]
        real_connect=sqlite3.connect
        owner=self
        class TrackedConnection(sqlite3.Connection):
            closed=False
            def close(self):
                self.closed=True
                return super().close()
        def connect(*args,**kwargs):
            kwargs['factory']=TrackedConnection
            connection=real_connect(*args,**kwargs)
            owner.connections.append(connection)
            return connection
        self.addCleanup(self.close_connections)
        binding=patch('sqlite3.connect',side_effect=connect)
        binding.start();self.addCleanup(binding.stop)

    def close_connections(self):
        for con in self.connections:con.close()

    def assert_closed(self):
        self.assertTrue(self.connections)
        self.assertTrue(all(con.closed for con in self.connections),'All SQLite handles must be explicitly closed, including backups')

    def import_pdf(self):
        with patch.object(pipeline,'DATA',self.root),patch.object(pipeline,'DB_PATH',self.db),redirect_stdout(io.StringIO()):
            pipeline.import_pdf(self.pdf)

    def test_import_and_export_close_connections(self):
        self.import_pdf()
        self.assert_closed()

    def test_existing_database_migration_closes_backup_connection(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.executescript((pipeline.ROOT/'schema.sql').read_text())
        storage.migrate(self.db)
        self.assert_closed()

    def test_revalidation_closes_connections_and_reads_pdf_from_bytes(self):
        self.import_pdf()
        with patch.object(pipeline,'read_pdf_pages',wraps=pipeline.read_pdf_pages) as reader:
            result=storage.revalidate(self.db)
        self.assertEqual(result['checks_passed'],1)
        self.assertIsInstance(reader.call_args.args[0],bytes,'No temporary PDF filesystem handle is needed')
        self.assert_closed()

    def test_invalid_pdf_does_not_leave_file_handles(self):
        self.pdf.write_bytes(b'%PDF-intentionally-corrupt')
        with self.assertRaises(RuntimeError):pipeline.read_pdf_pages(self.pdf)
        self.pdf.unlink()
        self.assertFalse(self.pdf.exists())

    def test_import_exception_rolls_back_and_closes_connections(self):
        with patch.object(pipeline,'DATA',self.root),patch.object(pipeline,'DB_PATH',self.db),patch.object(storage,'register_source',side_effect=RuntimeError('fixture failure')):
            with self.assertRaisesRegex(RuntimeError,'fixture failure'):
                pipeline.import_pdf(self.pdf)
        self.assert_closed()
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('select count(*) from grade_sections').fetchone()[0],0)
