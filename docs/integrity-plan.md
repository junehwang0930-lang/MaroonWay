# MaroonWay integrity implementation plan

Goal: preserve SQLite records and source evidence while fixing five integrity defects; support all undergraduate subjects, Fall 2023 through Spring 2026, excluding Summer.
Architecture: shared row validation; conservative PDF header and row parsing; versioned SQLite migration with backup; immutable import and validation history; read-only public view restricted to validated rows; latest-request-only browser rendering.
Spec: user request in this session (five fixes, regression tests first, original seven tests, no reset, 313 real rows revalidated when supplied).

## Constraints and decisions
- Existing checkout is already isolated. Do not create a worktree.
- Never delete an existing DB or replace source values; preserve extended manual-review columns, IDs and provenance during migration.
- Unknown/conflicting PDF headers stop import before DB writes. Unsupported header layouts require explicit parser support, never a bypass flag.
- Real DB/PDF absent at start. Synthetic migration tests cannot substitute for the requested 313-row audit.

## Tasks (each RED → GREEN → full suite → commit)
1. Counts/names: regression tests for all 12 negative count fields, split/multiline names, uncertain trailing content, duplicate ambiguity, all undergraduate subjects. Share row checks with legacy revalidation.
2. Source validation: tests for Spring/Fall boundaries, Summer rejection, wrong/unknown year, college, GPA report, conflicting repeated headers. Introduce explicit year/semester/college/college-name options and source evidence. Parse headers outside section rows only.
3. Persistence: tests with legacy SQLite including review columns and IDs; migrate subject constraint transactionally, preserve records and backup. Persist source bytes, import runs and review items, unique CSV per run, retain legacy CSV; never overwrite existing rows on conflict. Add repeatable revalidation command with immutable audit reports.
4. Publication/API: tests prove bad/unverified data cannot be returned; use a validated public view and parameterized term/subject filters. Preserve raw records and expose provenance. API unavailable until migration is run.
5. Frontend: Node regression tests with deferred responses (out-of-order success, error, delayed JSON), then cancel requests plus generation guard. Enable arbitrary subject and supported term selection.
6. Docs and verification: run all Python/Node tests and a real PDF-library smoke test; inspect migration preservation and readonly API. Revalidate provided DB/PDF; otherwise document exact missing prerequisite. Fresh review, fix important findings, commit and push.

## Review focus
Metadata must not be inferred from a filename or row body. Unexpected database extensions must survive migration or abort safely. Conflicting imports must quarantine rather than overwrite. Revalidation must not promote unsupported legacy provenance. Stale errors and delayed JSON must not mutate current browser state.

## Execution record
- Counts/names RED → GREEN: original 7 retained; 14 tests passed after first fix.
- Metadata RED → GREEN: 20 tests passed.
- Persistence/migration RED → GREEN: 29 tests passed.
- Publication/API RED → GREEN: 33 tests passed.
- Frontend RED → GREEN: 4 Node regressions passed; Python suite remained green.
- Supplied files received and working copies prepared; original313 values fingerprint identical after migration/audits, 311 passed/2 reviewed.
- Independent review: six important findings reproduced and fixed with RED → GREEN tests; dependent views, ambiguous College review, and malformed legacy values included.
- Final suite: Python43/43 and Node4/4; real PDF and HTTP integration checks passed as recorded in docs/integrity-verification.md.
- Ruling: Unknown uncoded colleges are rejected until a reviewed code/name mapping is added — supplied PDF verifies only AT — wider ingestion waits for official fixtures.
- Ruling: Legacy CSVs remain archival evidence and a separate public CSV is refreshed — prevents overwriting user files — consumers must switch to public_grade_sections.csv or the public view.
- Ruling: Uncertain/page-spanning rows and import conflicts remain quarantined — original evidence takes priority over inferred correction — some valid records may require manual resolution.
