"""Conservative recognition of report headers, separate from section data.

Unknown header layouts are rejected. Add fixtures and an explicit recognizer
before supporting another layout; never infer metadata from file names.
"""
from dataclasses import dataclass
import re
from urllib.parse import urlencode

SECTION = re.compile(r'^[A-Z]{2,8}-\d{3,4}[A-Z]?-[A-Z0-9]+\b')
SUPPORTED_TERMS = frozenset({'2023-FALL', '2024-SPRING', '2024-FALL', '2025-SPRING', '2025-FALL', '2026-SPRING'})

@dataclass(frozen=True)
class ReportMetadata:
    year: int
    semester: str
    college: str
    college_name: str

    @property
    def term(self):
        return f'{self.year}-{self.semester}'

    @property
    def source_url(self):
        return 'https://web-as.tamu.edu/gradereports/Report?' + urlencode(dict(year=self.year, term=self.semester, college=self.college))


def canonical(text):
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', text.upper().replace('&',' AND ')).split())


def header_lines(pages):
    for page in pages:
        for line in page.splitlines():
            if SECTION.match(line.strip()):
                break
            yield line.strip()


def validate_metadata(pages, *, year, semester, college, college_name):
    semester, college = semester.upper(), college.upper()
    expected = ReportMetadata(year, semester, college, college_name)
    if expected.term not in SUPPORTED_TERMS:
        raise ValueError('Only Spring/Fall from Fall 2023 through Spring 2026 are supported; Summer is excluded')
    if not re.fullmatch(r'[A-Z0-9]{2,8}', college) or not canonical(college_name):
        raise ValueError('An explicit college code and full college name are required')
    lines = list(header_lines(pages))
    text = '\n'.join(lines).upper()
    if re.search(r'\bGPA\s+DISTRIBUTION\b', text) or not re.search(r'\bGRADE\s+DISTRIBUTION\b', text):
        raise ValueError('Cannot verify Grade Distribution report type (GPA Distribution is not accepted)')
    terms = set()
    pattern = r'\b(SPRING|FALL|SUMMER(?:\s+[I12]+)?)\s*[,/-]?\s*(20\d{2})\b|\b(20\d{2})\s*[,/-]?\s*(SPRING|FALL|SUMMER(?:\s+[I12]+)?)\b'
    for m in re.finditer(pattern, text):
        sem, yr = (m[1],m[2]) if m[1] else (m[4],m[3])
        terms.add(f'{yr}-{sem}')
    if terms != {expected.term}:
        raise ValueError(f'Report term is unknown or mismatches expected {expected.term}: {sorted(terms)}')
    colleges = [line for line in lines if re.match(r'^COLLEGE\s*:',line,re.I)]
    if not colleges:
        raise ValueError('Cannot verify College header; expected "College: [code -] full name"')
    for line in colleges:
        value = line.split(':',1)[1].strip()
        coded = re.match(r'^([A-Z0-9]{2,8})\s*[-:]\s*(.+)$',value)
        if coded:
            if coded[1] != college or canonical(coded[2]) != canonical(college_name):
                raise ValueError('Report College code/name mismatches requested College')
        elif canonical(value) != canonical(college_name):
            raise ValueError('Report College name mismatches requested College')
    return expected
