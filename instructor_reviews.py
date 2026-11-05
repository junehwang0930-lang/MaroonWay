"""Append-only, section-specific owner confirmations, separate from PDF facts.

A review is not independent TAMU identity verification. Only a new validation
can use it to resolve the missing-final-initial issue; every other check remains.
"""
from contextlib import closing
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

MISSING_INITIAL = 'Instructor name lacks an identifiable final initial'
KEY_FIELDS = ('term','college','subject','course_number','section','instructor_as_reported')
CSV_FIELDS = ('term','college','section_code','instructor_as_reported','reviewed_instructor_name','initial','name_scope','evidence','review_note')


def install_schema(path):
    """Version 4 preserves all source rows, old audits and the policy-3 guards."""
    from storage import token
    path = Path(path)
    with closing(sqlite3.connect(path)) as con:
        if con.execute('select 1 from schema_migrations where version=4').fetchone():
            return
        backup = path.with_name(path.stem+'.before-v4-'+token()+'.db')
        with closing(sqlite3.connect(backup)) as target:
            con.backup(target)
        with con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('''CREATE TABLE instructor_reviews (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL,
                term TEXT NOT NULL, college TEXT NOT NULL, subject TEXT NOT NULL,
                course_number TEXT NOT NULL, section TEXT NOT NULL,
                instructor_as_reported TEXT NOT NULL, reviewed_instructor_name TEXT NOT NULL,
                initial TEXT NOT NULL, name_scope TEXT NOT NULL CHECK(name_scope IN ('full_name','initial_only')),
                evidence TEXT NOT NULL CHECK(evidence='user_confirmed'), review_note TEXT NOT NULL)''')
            con.execute('CREATE INDEX instructor_reviews_exact ON instructor_reviews(term,college,subject,course_number,section,instructor_as_reported,id)')
            con.execute('''CREATE TABLE grade_validation_instructor_reviews (
                validation_id INTEGER PRIMARY KEY REFERENCES grade_validations(id),
                review_id INTEGER NOT NULL REFERENCES instructor_reviews(id),
                resolved_issue TEXT NOT NULL CHECK(resolved_issue='Instructor name lacks an identifiable final initial'))''')
            for table in ('instructor_reviews','grade_validation_instructor_reviews'):
                for action in ('UPDATE','DELETE'):
                    con.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Instructor review evidence is append-only'); END")
            original=con.execute("select sql from sqlite_master where name='public_grade_sections'").fetchone()[0]
            con.execute('DROP VIEW public_grade_sections')
            con.execute(re.sub(r'CREATE VIEW public_grade_sections', 'CREATE VIEW source_verified_grade_sections', original, count=1, flags=re.I))
            exact=' AND '.join(f'r.{key}=b.{key}' for key in KEY_FIELDS)
            con.execute(f'''CREATE VIEW public_grade_sections AS
                SELECT b.*, COALESCE(r.reviewed_instructor_name,b.instructor_as_reported) AS instructor_display_name,
                    r.evidence AS instructor_review_evidence, r.name_scope AS instructor_review_scope,
                    r.initial AS instructor_initial
                FROM source_verified_grade_sections b
                LEFT JOIN grade_validation_instructor_reviews link ON link.validation_id=
                    (SELECT max(id) FROM grade_validations WHERE grade_section_id=b.id)
                LEFT JOIN instructor_reviews r ON r.id=link.review_id AND {exact}''')
            con.execute('insert into schema_migrations values (4,?)',(datetime.now(timezone.utc).isoformat(),))
            if con.execute('pragma foreign_key_check').fetchall():
                raise RuntimeError('Instructor-review migration foreign-key check failed')


def matching_review(con, row):
    """Literal full source key only: no surname, normalization or fuzzy matching."""
    where=' AND '.join(key+'=?' for key in KEY_FIELDS)
    return con.execute('SELECT id FROM instructor_reviews WHERE '+where+' ORDER BY id DESC LIMIT 1',tuple(row[key] for key in KEY_FIELDS)).fetchone()


def apply_confirmations(db_path, csv_path):
    """Validate the complete input before appending; unmatched rows stay unapplied.

    Returns matched/applied counts and unmatched section keys. This function
    deliberately does not validate or publish sections; run revalidation next.
    """
    from storage import migrate
    db_path=Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    records=[]
    with Path(csv_path).open(newline='',encoding='utf-8-sig') as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames != list(CSV_FIELDS):
            raise ValueError('Confirmation CSV requires columns: '+','.join(CSV_FIELDS))
        for line,row in enumerate(reader,2):
            if any(row.get(k) is None or not row[k].strip() for k in CSV_FIELDS):
                raise ValueError(f'Incomplete confirmation at line {line}')
            section=re.fullmatch(r'([A-Z]{2,5})-(\d{3})-([A-Z0-9]+)',row['section_code'])
            if not section or not re.fullmatch(r'20\d{2}-(SPRING|FALL)',row['term']) or not re.fullmatch('[A-Z]{2}',row['college']):
                raise ValueError(f'Invalid exact section key at line {line}')
            if row['evidence']!='user_confirmed' or row['name_scope'] not in ('full_name','initial_only'):
                raise ValueError(f'Unsupported confirmation evidence or name scope at line {line}')
            if len(row['initial'])!=1 or not row['initial'].isalpha():
                raise ValueError(f'Expected one confirmed initial at line {line}')
            if row['name_scope']=='initial_only' and row['reviewed_instructor_name']!=row['instructor_as_reported']+' '+row['initial']:
                raise ValueError(f'Initial-only confirmation cannot invent a full name at line {line}')
            values=(row['term'],row['college'],*section.groups(),row['instructor_as_reported'],row['reviewed_instructor_name'],row['initial'],row['name_scope'],row['evidence'],row['review_note'])
            records.append((row['section_code'],values))
    migrate(db_path)
    result={'matched':0,'applied':0,'unmatched':[]}
    with closing(sqlite3.connect(db_path)) as con,con:
        con.execute('PRAGMA foreign_keys=ON')
        for code,values in records:
            where=' AND '.join(k+'=?' for k in KEY_FIELDS)
            if not con.execute('select 1 from grade_sections where '+where,values[:6]).fetchone():
                result['unmatched'].append({'term':values[0],'college':values[1],'section_code':code,'instructor_as_reported':values[5]})
                continue
            result['matched']+=1
            fields=(*KEY_FIELDS,'reviewed_instructor_name','initial','name_scope','evidence','review_note')
            previous=con.execute('select '+','.join(fields)+' from instructor_reviews where '+where+' order by id desc limit 1',values[:6]).fetchone()
            if previous==values:
                continue
            con.execute('insert into instructor_reviews (created_at,'+','.join(fields)+') values ('+','.join('?' for _ in range(12))+')',(datetime.now(timezone.utc).isoformat(),*values))
            result['applied']+=1
    return result
