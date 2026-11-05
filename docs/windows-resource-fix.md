# Windows SQLite/PDF resource cleanup fix

## Cause

A database connection is an open file handle. Windows normally refuses to delete a file while another handle still owns it. Linux can remove an open file from its directory, so an apparently passing Linux cleanup did not prove that the connection had been closed.

`with sqlite3.connect(...) as con:` handles transaction commit/rollback. It **does not call `con.close()`**. The previous import, backup, audit, and test code relied on that context manager or garbage collection to release connections. Python 3.14 reports these leaked connections as `ResourceWarning`; Windows exposes them as `WinError 32` during temporary-directory cleanup. A cleanup error is separate from a failed grade-data assertion, although a real application leak can cause both.

## Changes

- `pipeline.py` and `storage.py`: wrap connection ownership in `contextlib.closing`; retain the connection transaction context so commit/rollback still happens before close, even on exceptions. Close backup targets too. The migration/API's existing `finally: close()` paths remain explicit.
- Console summaries and `scripts/`: close connections when queries or validation raise, not only at the successful end of the script. Manual-review backup source and destination connections both close.
- `tests/test_api.py` and `tests/test_storage.py`: explicitly close their own connections. Register patch and temporary-directory cleanup with `addCleanup`, so partial setup failure is handled too. Patches are restored before removing temporary files.
- `tests/pdf_fixture.py`: generate valid, small PDFs in memory. Normal test setup no longer registers invalid `%PDF-...` placeholder bytes as a source document. Existing parser stubs remain where a test specifically controls extraction behavior.
- PDF reading: read the file bytes through Python, then give bytes to PyMuPDF. Archived PDF revalidation reads the stored bytes directly instead of creating a temporary PDF. Even failed MuPDF opens cannot retain a handle to a source file.
- `tests/test_resource_lifecycle.py`: five additional tests check explicit handle closure after import/export, existing-DB migration/backup, revalidation, an import exception/rollback, and corrupt-PDF rejection/removal. Connection tracking works on Linux too, without relying on whether unlink happens to succeed.
- `tests/run_checks.py`: run the complete suite and fail on resource warnings, including exceptions raised during garbage collection. `-W error` alone may only print destructor exceptions without changing unittest's exit status; the runner records those as failures too.
- `.github/workflows/tests.yml`: execute the Python and frontend suites on Windows and Ubuntu with Python 3.12 and 3.14. No tests are skipped.

The transaction/ownership pattern is:

```python
from contextlib import closing

with closing(sqlite3.connect(path)) as con, con:
    # Commit on success / rollback on error, then close in both cases.
    con.execute(...)
```

The deliberately corrupt-PDF test remains: invalid input must still be rejected. We fixed its file-handle ownership rather than hiding the exception or skipping the test.

## Verification

All original 43 test method names are retained. With the five new lifecycle regressions, the suite now contains 48 tests.

- Linux Python 3.12: **48 passed**, no skips or resource warnings.
- Linux Python 3.14.8: **48 passed**, no skips or resource warnings.
- Frontend Node suite: **4 passed**.
- Original `data/maroonway.db` and source report: SHA-256 fingerprints unchanged before/after this fix. No migration, revalidation, deletion, or modification was run on those real files for this task. Tests use temporary databases and generated PDFs.

**Real GitHub Actions Windows validation passed** for Python 3.14 and 3.12, together with both Ubuntu jobs: [successful cross-platform CI run](https://github.com/junehwang0930-lang/MaroonWay/actions/runs/41938421590), tested commit `ddf47fe`. The Windows/Python 3.14 job runs the full strict 48-test Python suite and the four frontend tests. The successful run was checked on GitHub after completion; it is not inferred from the local Linux results. GitHub emitted action-runtime deprecation warnings; these were not SQLite/PDF ResourceWarnings or test failures.

## Windows PowerShell commands

From the project folder, with no local changes being overwritten:

```powershell
git pull origin main
py -3.14 -m pip install -r requirements.txt
py -3.14 -m unittest discover -s tests -v
py -3.14 -W error::ResourceWarning tests/run_checks.py
node tests/test_frontend.cjs
```

Expected Python count is now **48**, including all 43 original tests. These test commands do not alter the real database or report. There is no need to delete `data/maroonway.db` or the PDF to address the previous cleanup errors.
