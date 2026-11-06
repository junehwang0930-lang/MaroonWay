"""Versioned, non-destructive SQLite migration and append-only integrity evidence."""
from contextlib import closing
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
COUNTS = ('a','b','c','d','f','af_total','i_count','s_count','u_count','q_count','x_count','enrollment_total')
SOURCE_FIELDS = ('term','college','subject','course_number','section','instructor_as_reported',*COUNTS,'gpa_reported','source_url','source_sha256','source_page','raw_row')


def token():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex


def quote(name):
    return '"'+name.replace('"','""')+'"'


def _migrate_v2(path):
    """Back up before the first migration; preserve IDs, extra columns and SQL objects.

    A supported legacy CHECK is removed by copying into a transactionally rebuilt
    table. An unfamiliar subject constraint aborts instead of guessing. No rows
    are deleted; failure rolls back to the original schema.
    """
    path=Path(path)
    existed=path.is_file()
    con=sqlite3.connect(path)
    try:
        if con.execute("select 1 from sqlite_master where name='schema_migrations'").fetchone():
            if con.execute('select 1 from schema_migrations where version=2').fetchone():
                return
        if existed:
            backup=path.with_name(path.stem+'.before-v2-'+token()+'.db')
            with closing(sqlite3.connect(backup)) as target:
                con.backup(target)
        has_table=con.execute("select sql from sqlite_master where type='table' and name='grade_sections'").fetchone()
        if not has_table:
            con.executescript((ROOT/'schema.sql').read_text())
        con.execute('PRAGMA foreign_keys=OFF')
        con.execute('BEGIN IMMEDIATE')
        if has_table:
            original=has_table[0]
            replacement=re.sub(r"\s+CHECK\s*\(\s*subject\s+IN\s*\(\s*'STAT'\s*,\s*'MATH'\s*\)\s*\)", '', original, flags=re.I)
            if replacement != original:
                objects=con.execute("select sql from sqlite_master where tbl_name='grade_sections' and type in ('index','trigger') and sql is not null").fetchall()
                columns=[r[1] for r in con.execute('pragma table_info(grade_sections)')]
                sequence=con.execute("select seq from sqlite_sequence where name='grade_sections'").fetchone() if 'AUTOINCREMENT' in original.upper() else None
                replacement=re.sub(r'^(CREATE\s+TABLE\s+)(?:"grade_sections"|grade_sections)',r'\1"_grade_sections_v2"',replacement,count=1,flags=re.I)
                con.execute(replacement)
                names=','.join(map(quote,columns))
                con.execute(f'insert into _grade_sections_v2 ({names}) select {names} from grade_sections')
                # Keep dependent view definitions pointing at the stable final
                # table name during the transactional replacement.
                con.execute('PRAGMA legacy_alter_table=ON')
                con.execute('drop table grade_sections')
                con.execute('alter table _grade_sections_v2 rename to grade_sections')
                if sequence:
                    con.execute("update sqlite_sequence set seq=max(seq,?) where name='grade_sections'",sequence)
                for (sql,) in objects: con.execute(sql)
            elif re.search(r'CHECK\s*\([^)]*subject',original,re.I):
                raise RuntimeError('Unknown subject constraint; migration aborted safely')
        statements=[
            'CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)',
            'CREATE TABLE source_documents (sha256 TEXT PRIMARY KEY, content BLOB NOT NULL, metadata_json TEXT NOT NULL)',
            '''CREATE TABLE import_runs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_sha256 TEXT NOT NULL REFERENCES source_documents(sha256), term TEXT NOT NULL, college TEXT NOT NULL, row_count INTEGER NOT NULL, review_path TEXT NOT NULL)''',
            '''CREATE TABLE import_review_items (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES import_runs(run_id), source_page INTEGER, section_code TEXT, issue TEXT NOT NULL, raw_text TEXT NOT NULL)''',
            '''CREATE TABLE import_records (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES import_runs(run_id), grade_section_id INTEGER REFERENCES grade_sections(id), snapshot_json TEXT NOT NULL)''',
            '''CREATE TABLE import_conflicts (id INTEGER PRIMARY KEY, grade_section_id INTEGER NOT NULL REFERENCES grade_sections(id), run_id TEXT NOT NULL REFERENCES import_runs(run_id), detail TEXT NOT NULL)''',
            'CREATE TABLE validation_runs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, report_path TEXT NOT NULL)',
            '''CREATE TABLE grade_validations (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES validation_runs(run_id), grade_section_id INTEGER NOT NULL REFERENCES grade_sections(id), status TEXT NOT NULL, issues_json TEXT NOT NULL, snapshot_json TEXT NOT NULL)''',
            'CREATE INDEX validation_by_section ON grade_validations(grade_section_id,id)',
        ]
        for sql in statements: con.execute(sql)
        # Match the full original evidence against the last audit. Any later edit
        # invalidates publication without needing an application-only hash function.
        match=' AND '.join(f'g.{quote(k)} IS json_extract(v.snapshot_json,\'$.{k}\')' for k in SOURCE_FIELDS)
        nonnegative=' AND '.join(f'typeof(g.{k})=\'integer\' AND g.{k}>=0' for k in COUNTS)
        con.execute(f'''CREATE VIEW public_grade_sections AS SELECT g.* FROM grade_sections g JOIN grade_validations v
            ON v.id=(SELECT max(id) FROM grade_validations WHERE grade_section_id=g.id)
            WHERE v.status='checks_passed' AND {match} AND {nonnegative}
            AND NOT EXISTS (SELECT 1 FROM import_conflicts c WHERE c.grade_section_id=g.id)''')
        con.execute("insert into schema_migrations values (2,?)",(datetime.now(timezone.utc).isoformat(),))
        if con.execute('pragma foreign_key_check').fetchall():
            raise RuntimeError('Migration foreign-key check failed; original schema retained')
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def _migrate_v3(path):
    """Install policy v3 without promoting historical audits or editing source rows."""
    path = Path(path)
    existing_v2 = False
    if path.is_file():
        with closing(sqlite3.connect(path)) as con:
            if con.execute("select 1 from sqlite_master where name='schema_migrations'").fetchone():
                if con.execute('select 1 from schema_migrations where version=3').fetchone():
                    return
                existing_v2 = bool(con.execute('select 1 from schema_migrations where version=2').fetchone())
    _migrate_v2(path)
    with closing(sqlite3.connect(path)) as con:
        if existing_v2:
            backup = path.with_name(path.stem + '.before-v3-' + token() + '.db')
            with closing(sqlite3.connect(backup)) as target:
                con.backup(target)
        with con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('CREATE TABLE grade_validation_policies (validation_id INTEGER PRIMARY KEY REFERENCES grade_validations(id), policy_version INTEGER NOT NULL CHECK(policy_version=3))')
            con.execute('DROP VIEW public_grade_sections')
            match = ' AND '.join(f'g.{quote(k)} IS json_extract(v.snapshot_json,\'$.{k}\')' for k in SOURCE_FIELDS)
            nonnegative = ' AND '.join(f"typeof(g.{k})='integer' AND g.{k}>=0" for k in COUNTS)
            points = '(4.0*g.a+3.0*g.b+2.0*g.c+g.d)'
            calculated = f'({points}/NULLIF(g.af_total,0))'
            # Fresh policy audits retain the parser's exact Fraction comparison.
            # Reuse that evidence so floating point noise cannot alter the boundary.
            discrepancy = "CASE WHEN g.af_total=0 OR g.gpa_reported IS NULL THEN NULL ELSE EXISTS (SELECT 1 FROM json_each(v.issues_json) WHERE value='Reported GPA does not match A-F counts') END"
            con.execute(f'''CREATE VIEW public_grade_sections AS
                SELECT g.*, {calculated} AS gpa_calculated,
                    abs({calculated}-g.gpa_reported) AS gpa_difference,
                    {discrepancy} AS gpa_discrepancy
                FROM grade_sections g JOIN grade_validations v
                ON v.id=(SELECT max(id) FROM grade_validations WHERE grade_section_id=g.id)
                JOIN grade_validation_policies p ON p.validation_id=v.id AND p.policy_version=3
                WHERE v.status='checks_passed' AND {match} AND {nonnegative}
                AND g.a+g.b+g.c+g.d+g.f=g.af_total
                AND g.af_total+g.i_count+g.s_count+g.u_count+g.q_count+g.x_count=g.enrollment_total
                AND NOT EXISTS (SELECT 1 FROM import_conflicts c WHERE c.grade_section_id=g.id)''')
            con.execute('insert into schema_migrations values (3,?)', (datetime.now(timezone.utc).isoformat(),))
            if con.execute('pragma foreign_key_check').fetchall():
                raise RuntimeError('Policy migration foreign-key check failed')


def migrate(path):
    """Install versioned changes with backups, preserving all original rows."""
    _migrate_v3(path)
    from instructor_reviews import install_schema
    install_schema(path)


def blocking_issues(issues, row, con=None):
    """Retain GPA warnings as evidence, but separate them from integrity failures."""
    allowed = {'Reported GPA does not match A-F counts', 'No letter-graded students to compute GPA'}
    if row['af_total'] == 0:
        allowed.add('GPA missing from report')
    if con is not None:
        from instructor_reviews import MISSING_INITIAL, matching_review
        if MISSING_INITIAL in issues and matching_review(con, row):
            allowed.add(MISSING_INITIAL)
    return [issue for issue in issues if issue not in allowed]


def record_validation(con, run_id, row, issues):
    """Append a fresh policy audit; never relabel or overwrite an old audit."""
    status = 'needs_review' if blocking_issues(issues, row, con) else 'checks_passed'
    cursor = con.execute('insert into grade_validations (run_id,grade_section_id,status,issues_json,snapshot_json) values (?,?,?,?,?)',
                         (run_id,row['id'],status,json.dumps(issues),snapshot(row)))
    con.execute('insert into grade_validation_policies values (?,3)', (cursor.lastrowid,))
    from instructor_reviews import MISSING_INITIAL, matching_review
    review = matching_review(con, row) if MISSING_INITIAL in issues else None
    if review:
        con.execute('insert into grade_validation_instructor_reviews values (?,?,?)', (cursor.lastrowid,review[0],MISSING_INITIAL))
    return status


def register_source(con, content, metadata):
    digest=hashlib.sha256(content).hexdigest()
    encoded=json.dumps(vars(metadata),sort_keys=True)
    existing=con.execute('select content,metadata_json from source_documents where sha256=?',(digest,)).fetchone()
    if existing and (existing[0]!=content or existing[1]!=encoded):
        raise ValueError('Same source hash has conflicting metadata; import stopped')
    con.execute('insert or ignore into source_documents values (?,?,?)',(digest,content,encoded))
    return digest


def snapshot(row):
    values = {k:row[k] for k in SOURCE_FIELDS}
    for key, value in values.items():
        if isinstance(value, float) and not math.isfinite(value):
            values[key] = repr(value)
    return json.dumps(values,sort_keys=True,allow_nan=False)


def row_issues(row):
    """Recheck stored numeric values as well as original raw text."""
    from pipeline import decode_row
    from report_metadata import SUPPORTED_TERMS
    issues=[]
    for name in COUNTS:
        value=row[name]
        if not isinstance(value,int) or value < 0:
            issues.append(f'Invalid nonnegative integer count: {name}')
    decoded=decode_row(row['raw_row'],row['source_page']) if isinstance(row['raw_row'], str) else None
    if decoded is None:
        issues.append('Original row cannot be parsed with current parser')
    else:
        issues.extend(decoded.issues)
        expected={'subject':decoded.subject,'course_number':decoded.number,'section':decoded.section,'instructor_as_reported':decoded.instructor_raw,'gpa_reported':decoded.gpa,**{k:getattr(decoded,k) for k in COUNTS}}
        if any(row[k]!=value for k,value in expected.items()):
            issues.append('Stored fields differ from original parsed row')
    if row['term'] not in SUPPORTED_TERMS:
        issues.append('Unsupported term')
    if not re.fullmatch(r'[A-Z]{2,8}',str(row['subject'])) or not re.fullmatch(r'[1-4]\d{2}[A-Z]?',str(row['course_number'])):
        issues.append('Not a supported undergraduate course code')
    if not isinstance(row['source_page'],int) or row['source_page'] < 1:
        issues.append('Invalid source page')
    return issues


def matches_source(row, actual):
    expected = {'instructor_as_reported': actual.instructor_raw, 'gpa_reported': actual.gpa,
                **{k: getattr(actual, k) for k in COUNTS}}
    return all(row[k] == value for k, value in expected.items())


def revalidate(path):
    """Audit all records without changing any original or manual-review columns."""
    from pipeline import parse_pages, read_pdf_pages
    from report_metadata import ReportMetadata, validate_metadata
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(f'No database at {path}')
    migrate(path)
    run_id=token()
    report=path.parent/'validation_runs'/f'{run_id}.csv'
    report.parent.mkdir(exist_ok=True)
    cache={}
    with closing(sqlite3.connect(path)) as con, con:
        con.row_factory=sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        for doc in con.execute('select * from source_documents'):
            digest=doc['sha256']
            content=doc['content']
            try:
                if hashlib.sha256(content).hexdigest()!=digest: raise ValueError('Source checksum mismatch')
                meta=ReportMetadata(**json.loads(doc['metadata_json']))
                # Read preserved bytes, not an arbitrary current file at the old path.
                pages=read_pdf_pages(content)
                validate_metadata(pages,**vars(meta))
                parsed,_=parse_pages(pages)
                cache[digest]=(meta,{(r.subject,r.number,r.section):r for r in parsed})
            except (ValueError,RuntimeError,TypeError):
                cache[digest]=None
        con.execute('insert into validation_runs values (?,?,?)',(run_id,datetime.now(timezone.utc).isoformat(),str(report)))
        results=[]
        for row in con.execute('select * from grade_sections order by id').fetchall():
            issues=row_issues(row)
            source=cache.get(row['source_sha256'])
            if not source:
                issues.append('Source PDF metadata not verified; supply original PDF')
            else:
                meta,parsed=source
                actual=parsed.get((row['subject'],row['course_number'],row['section']))
                if meta.term!=row['term'] or meta.college!=row['college']:
                    issues.append('Source metadata differs from stored term/college')
                if not actual or blocking_issues(actual.issues, row, con) or actual.source_page!=row['source_page'] or not matches_source(row, actual):
                    issues.append('Stored row differs from verified PDF extraction or source row needs review')
            if con.execute('select 1 from import_conflicts where grade_section_id=?',(row['id'],)).fetchone():
                issues.append('Unresolved conflicting import; original row retained')
            issues = list(dict.fromkeys(issues))
            status = record_validation(con, run_id, row, issues)
            results.append((row['id'],row['term'],row['college'],row['subject'],row['course_number'],row['section'],status,'; '.join(issues),row['source_sha256'],row['source_page']))
        # An exclusive file prevents accidental audit-history overwrite.
        with report.open('x',newline='',encoding='utf-8') as handle:
            writer=csv.writer(handle)
            writer.writerow(['id','term','college','subject','course_number','section','status','issues','source_sha256','source_page'])
            writer.writerows(results)
    from pipeline import export_csv
    public_export=export_csv(path)
    passed=sum(r[6]=='checks_passed' for r in results)
    return dict(run_id=run_id,total=len(results),checks_passed=passed,needs_review=len(results)-passed,report=str(report),public_export=public_export)
