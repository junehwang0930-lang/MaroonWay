-- Original grade evidence is retained; integrity audits control publication.
-- Do not confuse raw instructor initials with verified identities.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS professors (
    professor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    department TEXT,
    verification_note TEXT
);

CREATE TABLE IF NOT EXISTS professor_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_id INTEGER NOT NULL REFERENCES professors(professor_id),
    source_system TEXT NOT NULL,
    name_as_reported TEXT NOT NULL,
    verified_by TEXT,
    verification_note TEXT
);

CREATE TABLE IF NOT EXISTS grade_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    college TEXT NOT NULL,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    section TEXT NOT NULL,
    instructor_as_reported TEXT NOT NULL,
    professor_id INTEGER REFERENCES professors(professor_id), -- NULL until manually verified
    a INTEGER NOT NULL, b INTEGER NOT NULL, c INTEGER NOT NULL,
    d INTEGER NOT NULL, f INTEGER NOT NULL,
    af_total INTEGER NOT NULL,
    gpa_reported REAL,
    i_count INTEGER NOT NULL, s_count INTEGER NOT NULL,
    u_count INTEGER NOT NULL, q_count INTEGER NOT NULL,
    x_count INTEGER NOT NULL,
    enrollment_total INTEGER NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('checks_passed', 'needs_review')),
    source_url TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_page INTEGER NOT NULL,
    raw_row TEXT NOT NULL,
    UNIQUE (term, college, subject, course_number, section)
);

CREATE INDEX IF NOT EXISTS idx_grade_course ON grade_sections(subject, course_number);
CREATE INDEX IF NOT EXISTS idx_grade_instructor_text ON grade_sections(instructor_as_reported);
