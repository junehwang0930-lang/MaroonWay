"""Opt-in, append-only GPA investigations; never changes publication approval.

Calculated GPA is an A-F headcount average, not the Registrar's official GPA.
This module performs no migration or writes when imported or assessing a row.
"""
from contextlib import closing
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from uuid import uuid4

from pipeline import GPA_TOLERANCE
from storage import SOURCE_FIELDS, quote, snapshot

REVIEW_STATUSES = (
    'matches_reported', 'possible_variable_credit', 'possible_zero_credit',
    'unexplained_mismatch', 'source_or_parser_issue', 'verified_exception',
)


def calculate_gpa(a, b, c, d, af_total):
    """Return the simple A-F headcount average, or None for no A-F students."""
    if af_total == 0:
        return None
    return (4*a + 3*b + 2*c + d) / af_total


def _documented(evidence):
    return (isinstance(evidence, dict) and evidence.get('official') is True
            and all(isinstance(evidence.get(k), str) and evidence[k].strip()
                    for k in ('source_url', 'excerpt')))


def assess_gpa(row, evidence=None):
    """Assess numbers only; official credit evidence can suggest an unconfirmed cause.

    Evidence is a JSON-compatible dict. Credit hypotheses require official=True,
    source_url, excerpt and credit_type ('variable' or 'zero'). No evidence can
    automatically establish a verified_exception; record_review requires a human
    decision for that state. Numeric match confirmation says nothing about cause.
    """
    evidence = {} if evidence is None else evidence
    if not isinstance(evidence, dict):
        raise ValueError('Evidence must be a dictionary')
    counts = [row[k] for k in ('a','b','c','d','f','af_total')]
    valid_counts = (all(type(value) is int and value >= 0 for value in counts)
                    and sum(counts[:5]) == counts[5])
    calculated = calculate_gpa(row['a'],row['b'],row['c'],row['d'],row['af_total']) if valid_counts else None
    reported = row['gpa_reported']
    difference = None
    status = 'unexplained_mismatch'
    note = 'Cause is not established; manual source and official-rule review is needed.'
    confirmed = False
    if not valid_counts:
        note = 'Invalid A-F counts: require nonnegative integers and a total equal to A+B+C+D+F; manual source review is needed.'
    elif calculated is None:
        note = 'No A-F students; the simple headcount GPA is N/A.'
    elif reported is not None and math.isfinite(float(reported)):
        # Match the pipeline exactly, including the inclusive 0.005 boundary.
        exact = Fraction(4*row['a']+3*row['b']+2*row['c']+row['d'],row['af_total'])
        difference = abs(calculated-float(reported))
        if abs(exact-Fraction(str(reported))) <= GPA_TOLERANCE:
            status = 'matches_reported'
            note = 'Numeric agreement within the pipeline absolute tolerance (0.005); no cause is asserted.'
            confirmed = True
        elif _documented(evidence) and evidence.get('credit_type') in ('variable','zero'):
            status = 'possible_'+evidence['credit_type']+'_credit'
            note = 'Official credit listing supports a possibility; this does not establish the cause of this GPA difference.'
    return dict(gpa_calculated=calculated,gpa_difference=difference,
                gpa_review_status=status,gpa_review_note=note,
                gpa_review_evidence=evidence,confirmed=confirmed)


def _encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False)


def migrate_reviews(db_path):
    """Explicitly back up an existing SQLite DB and add review schema version 1.

    Returns the backup Path, or None when already migrated. Does not call the
    main migration, modify grade_sections, or touch public_grade_sections.
    """
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with closing(sqlite3.connect(path)) as con:
        if con.execute("select 1 from sqlite_master where name='gpa_review_migrations'").fetchone():
            if con.execute('select 1 from gpa_review_migrations where version=1').fetchone():
                return None
        if not con.execute("select 1 from sqlite_master where type='table' and name='grade_sections'").fetchone():
            raise ValueError('Existing grade_sections table is required')
        backup = path.with_name(path.stem+'.before-gpa-v1-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex+'.db')
        with closing(sqlite3.connect(backup)) as target:
            con.backup(target)
        con.execute('PRAGMA foreign_keys=ON')
        try:
            con.execute('BEGIN IMMEDIATE')
            con.execute('CREATE TABLE gpa_review_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
            states = ','.join("'"+s+"'" for s in REVIEW_STATUSES)
            con.execute(f'''CREATE TABLE gpa_reviews (
                id INTEGER PRIMARY KEY, grade_section_id INTEGER NOT NULL REFERENCES grade_sections(id),
                snapshot_json TEXT NOT NULL, gpa_reported REAL,
                gpa_calculated REAL, gpa_difference REAL,
                gpa_review_status TEXT NOT NULL CHECK (gpa_review_status IN ({states})),
                gpa_review_note TEXT NOT NULL, gpa_review_evidence TEXT NOT NULL,
                reviewed_at TEXT NOT NULL, confirmed INTEGER NOT NULL CHECK (confirmed IN (0,1)),
                credit_hours REAL, credit_type TEXT, fingerprint TEXT NOT NULL UNIQUE)''')
            con.execute('CREATE INDEX gpa_review_by_section ON gpa_reviews(grade_section_id,id)')
            for operation in ('UPDATE','DELETE'):
                con.execute(f'''CREATE TRIGGER gpa_reviews_no_{operation.lower()} BEFORE {operation} ON gpa_reviews
                    BEGIN SELECT RAISE(ABORT,'GPA reviews are append-only'); END''')
            match = ' AND '.join(f'g.{quote(k)} IS json_extract(r.snapshot_json,\'$.{k}\')' for k in ('id',*SOURCE_FIELDS))
            fields = ('gpa_calculated','gpa_difference','gpa_review_status','gpa_review_note','gpa_review_evidence','reviewed_at','confirmed','credit_hours','credit_type')
            projections = ','.join(f'CASE WHEN {match} THEN r.{k} END AS {k}' for k in fields)
            con.execute(f'''CREATE VIEW latest_gpa_reviews AS SELECT g.*,r.id AS gpa_review_id,
                CASE WHEN r.id IS NULL THEN NULL WHEN {match} THEN 0 ELSE 1 END AS review_stale,
                {projections} FROM grade_sections g LEFT JOIN gpa_reviews r
                ON r.id=(SELECT max(id) FROM gpa_reviews WHERE grade_section_id=g.id)''')
            con.execute('INSERT INTO gpa_review_migrations VALUES (1,?)',(datetime.now(timezone.utc).isoformat(),))
            con.commit()
        except BaseException:
            con.rollback()
            raise
    return backup


def record_review(db_path, section_id, *, evidence=None, review_status=None,
                  note=None, confirmed=None, credit_hours=None, credit_type=None):
    """Append an explicit review to a previously migrated DB; return its integer ID.

    Identical content for the same source snapshot returns the prior review ID.
    verified_exception additionally requires confirmed=True, a nonempty human
    note, and official evidence containing source_url, excerpt and explanation.
    source_or_parser_issue requires documented evidence of the extraction issue.
    Neither this function nor any review state grants permission to publish.
    """
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with closing(sqlite3.connect(path)) as con:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM grade_sections WHERE id=?',(section_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown grade section ID')
            result = assess_gpa(row,evidence)
            if review_status is not None:
                if review_status not in REVIEW_STATUSES:
                    raise ValueError('Unknown GPA review status')
                if review_status == 'verified_exception':
                    if not (confirmed is True and note and note.strip() and _documented(evidence)
                            and isinstance(evidence.get('explanation'),str) and evidence['explanation'].strip()):
                        raise ValueError('Verified exceptions require a human confirmation, note and sufficient official evidence with explanation')
                elif review_status == 'source_or_parser_issue':
                    if not (isinstance(evidence,dict) and evidence.get('source_url') and evidence.get('excerpt') and evidence.get('parser_issue')):
                        raise ValueError('Source/parser issue requires documented source and extraction evidence')
                elif review_status != result['gpa_review_status']:
                    raise ValueError('Requested status is not supported by numeric or credit evidence')
                result['gpa_review_status'] = review_status
            if confirmed is True and result['gpa_review_status'] not in ('matches_reported','verified_exception'):
                raise ValueError('Unresolved hypotheses cannot be confirmed')
            result['confirmed'] = result['confirmed'] if confirmed is None else bool(confirmed)
            if note is not None:
                result['gpa_review_note'] = note
            source = json.loads(snapshot(row))
            source['id'] = row['id']
            content = dict(grade_section_id=section_id,snapshot_json=_encode(source),
                           gpa_reported=source['gpa_reported'],**result,
                           credit_hours=credit_hours,credit_type=credit_type)
            fingerprint = hashlib.sha256(_encode(content).encode('utf-8')).hexdigest()
            content['gpa_review_evidence'] = _encode(content['gpa_review_evidence'])
            content.update(fingerprint=fingerprint,reviewed_at=datetime.now(timezone.utc).isoformat())
            columns = ','.join(content)
            con.execute('INSERT OR IGNORE INTO gpa_reviews ('+columns+') VALUES ('+','.join('?' for _ in content)+')',tuple(content.values()))
            review_id = con.execute('SELECT id FROM gpa_reviews WHERE fingerprint=?',(fingerprint,)).fetchone()[0]
            con.commit()
            return review_id
        except BaseException:
            con.rollback()
            raise
