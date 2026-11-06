# Apply four user-confirmed instructor reviews

These confirmations were **provided personally by the user (`user_confirmed`)**. They do not represent independent TAMU verification or an identity link through `professor_id`.

| Term / College | Section | Original reported name | Display name | Confirmed scope |
| --- | --- | --- | --- | --- |
| 2026-SPRING / AT | ECON-202-M01 | VILLAVICENCIO | Xavier Villavicencio | Name and initial X |
| 2026-SPRING / AT | SPAN-102-504 | DE LOS SANTOS | Rodrigo De Los Santos | Name and initial R |
| 2026-SPRING / AT | STAT-201-504 | HERNANDEZ | HERNANDEZ I | Initial I only |
| 2026-SPRING / AT | STAT-201-507 | HERNANDEZ | HERNANDEZ I | Initial I only |

## Preservation and validation rules

- The two candidate records in `data/manual_instructor_reviews.csv` remain unchanged. The four new confirmations are supplied separately in `data/user_confirmed_instructors.csv`.
- Preserve `instructor_as_reported`, `raw_row`, grades, source PDFs and existing manual-review columns. Do not directly modify `quality_status` or `professor_id`.
- The term, College, subject, course number, section and **original instructor text must all match exactly**. Do not link other instructors or semesters merely because they share a surname.
- Only `Instructor name lacks an identifiable final initial` can be resolved by these confirmations. Other grade, source, parsing, duplicate and conflict failures remain blocking.
- Recording a confirmation does not publish a section. A new audit using the preserved PDF must revalidate the source. Existing audit records remain unchanged.
- The API and UI distinguish display names from original reported names. Do not infer a full first name for HERNANDEZ.

## File responsibilities

| File | Purpose |
| --- | --- |
| `data/user_confirmed_instructors.csv` | Four user-confirmed inputs, separate from the preserved candidate CSV |
| `instructor_reviews.py` | Exact-key matching, append-only confirmations and lookup during revalidation |
| `scripts/apply_name_reviews.py` | Explicit `--confirmations` and `--db` options in the existing manual-review workflow |
| `storage.py`, `pipeline.py` | Resolve only the specified issue during source validation and link confirmation evidence to the audit |
| `api.py`, `frontend/app.js` | Expose display names, original text, user-confirmation evidence and initial-only scope separately |
| New regression tests | Verify exact scope, other blockers, repeat execution, source preservation and revalidation |

## Local application: no reimport or reset required

Stop the server with Ctrl+C and close programs such as Excel that have generated CSVs open. Run commands from the repository root. Create a separate test copy using SQLite's backup API without overwriting an existing file. See the copy example in the [calculated GPA guide](calculated-gpa-methodology.md).

```powershell
git pull origin main
py -3.14 -m pip install -r requirements.txt
py -3.14 scripts/apply_name_reviews.py --db data/maroonway-gpa-test.db --confirmations data/user_confirmed_instructors.csv
py -3.14 pipeline.py revalidate --db data/maroonway-gpa-test.db --pdf reports/spring_2026_arts_and_sciences.pdf
py -3.14 -W error::ResourceWarning tests/run_checks.py
node tests/test_frontend.cjs
```

After inspecting the test-copy results, use these commands to apply the confirmations locally. A unique SQLite backup is created before the first schema change. `public_grade_sections.csv` is a generated current snapshot: copy it to a unique name first if you want to retain its previous contents. Individual Import/Validation history CSVs are not overwritten.

```powershell
py -3.14 scripts/apply_name_reviews.py --db data/maroonway.db --confirmations data/user_confirmed_instructors.csv
py -3.14 pipeline.py revalidate --db data/maroonway.db --pdf reports/spring_2026_arts_and_sciences.pdf
py -3.14 -m uvicorn api:app --reload
```

Sections absent from the database are reported as `unmatched`; no other section is substituted. The earlier 313-row MATH/STAT database has no ECON/SPAN rows, so only the two STAT confirmations may apply there. A full undergraduate import may contain all four. Check the command output and new validation report for the actual result.

A different original name or another blocking issue prevents publication. Running the existing candidate/verified workflow without `--confirmations` retains its legacy behavior and does not resolve the missing-initial issue. Use the explicit confirmation workflow above for these four records.

## SQL structure and verification results

- Schema v4 creates a unique pre-migration backup and installs once.
- `instructor_reviews` stores the timestamp, exact source key, original name, display name, initial, scope and evidence as append-only records. Reapplying identical content does not create duplicates.
- `grade_validation_instructor_reviews` links a new validation ID to the confirmation ID used and the resolved issue text. The original issue remains in `grade_validations.issues_json`, allowing later inspection of why the section passed.
- `source_verified_grade_sections` retains the existing GPA, count, source and conflict guards. The public view adds the confirmed display name to those results without overwriting source text or `quality_status`.
- `matching_review` requires literal equality of the complete key. `apply_confirmations` validates the input and records only matching confirmations. Publication is decided separately during revalidation.

All **88 Python tests** passed on Python 3.12 and 3.14, along with **10 JavaScript tests**. The new CLI revalidation and display tests failed before implementation and passed afterward. Connection-leak and temporary-file cleanup checks remain enabled.

Temporary verification using the supplied real PDF:

| Target | Confirmation result | Revalidation result |
| --- | --- | --- |
| Temporary copy of the existing 313-row DB | Applied two STAT records; missing ECON/SPAN records reported unmatched | Preserved all 313 original rows; 313 passed |
| Separate temporary DB imported from the full PDF | Applied all four exact confirmations | Preserved 2,364 rows; 2,364 eligible for publication |

Adding confirmations alone left the previous publication blocks in place. Only PDF revalidation created fresh audits resolving the issue. Original names, grades, existing manual-review columns and prior audit entries were identical before and after. A separate negative-count regression remained blocked even with a matching confirmation. These four confirmations were not applied to the actual operational database during implementation.

The completion report links the Windows/Linux CI run for the implementation commit. Pulling code does not update local data automatically; run the explicit commands above and inspect their results.
