# Four review fixes and file organization

All changes were tested against temporary databases and generated PDFs. No original DB, PDF, backup, CSV or audit history was updated. Each bug has its own commit; this guide and readability cleanup are separate.

| Bug | Commit | Fix and regression evidence |
| --- | --- | --- |
| Conflicting instructor confirmations create repeated records | `d9808a6` | Reject conflicting duplicate exact keys before migration or writes. Collapse identical duplicates; repeat application remains idempotent. A conflicting two-name fixture failed before the fix and is now rejected atomically. |
| Historical review items attach to the wrong term/College/PDF | `13b1d98` | Reject supplied term, College or source-hash mismatches before generating output. Mark incomplete legacy provenance `review_association=unverified`; do not label it verified evidence. Multiple items and original input bytes remain preserved. |
| Locked public CSV leaves ambiguous partial completion | `9b2c88a` | Preserve a uniquely named current export even when Excel locks the convenience filename. Record refresh state, warn explicitly and expose an export-only retry. The old locked file is not called current. |
| Equivalent College names falsely conflict | `a6c08d4` | Compare full College names using the header validator's canonicalization. Keep stored source metadata byte-for-byte unchanged. Different year/College identities still fail. |

## Public export files and recovery

`data/public_exports/<unique-id>.csv` contains an immutable snapshot generated from the current validated database view. `data/public_export_status.json` identifies that snapshot and whether `public_grade_sections.csv` was refreshed:

- `ready`: the convenience file was refreshed.
- `pending`: the database operation completed, and a fresh immutable CSV is available at `snapshot`, but the convenience filename could not be refreshed. Do not use the old convenience file as current.

Import and revalidation return structured export state. Their CLI exits with code **2** for a pending convenience-file refresh, explicitly distinguishing partial completion from a failed database transaction. Neither an Excel lock nor retrying CSV export requires another import.

Close Excel or other CSV readers, then run:

```powershell
py pipeline.py export-csv --db data/maroonway.db
```

This command only reads the database and writes export files/status. It does not migrate, revalidate, modify section records or add import/audit rows. It creates a fresh immutable snapshot on every execution, including a header-only file when no rows qualify. Historical import/validation CSVs and the original `grade_sections.csv` remain unchanged. Export snapshots/status are excluded from Git.

Filesystem-wide failures such as a full disk can prevent even the immutable snapshot or status file from being written. Do not assume the database transaction rolled back after an export error; inspect the command output, resolve filesystem access, then use export-only recovery. The API reads the validated DB view and does not serve the stale convenience CSV.

## Review CSV provenance

A historical review item is `verified` only when its supplied `term`, `college` and `source_sha256` all match the selected PDF. Any supplied mismatch is rejected. Missing context is retained as `unverified` for compatibility with older `section_code,issue` CSVs; that association is not validated source evidence and does not grant publication. Investigation status and historical association are separate concepts.

## Organization

The root API/pipeline/storage modules, existing scripts and all tests retain their entry paths. The report script now keeps historical-input validation in a named helper and formats each output field separately for easier review. No speculative folders were added and no source/data files were deleted. See the updated [file guide](project-structure.md) for current module responsibilities.

The complete suite includes all original tests plus regressions for conflicting/identical duplicate inputs, wrong review provenance, legacy provenance labels, locked export recovery and unchanged metadata. Final local and cross-platform results are recorded in the completion report.
