# 프로젝트 파일 안내와 정리 내역

이 프로젝트는 **Fall 2023–Spring 2026, Summer 제외, TAMU 전체 학부 과목의 Grade Distribution**을 다룹니다. 이후 AI Schedule Builder를 추가할 수 있지만, 이번 정리에서는 기능이나 폴더를 미리 만들지 않았습니다.

프로젝트 루트에서 실행하는 명령은 그대로입니다:

```bash
python -m uvicorn api:app --reload
python pipeline.py --help
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

Windows에서는 `python` 대신 `py` 또는 `py -3.14`를 사용할 수 있습니다.

## 정리 전

```text
MaroonWay/
├── api.py
├── pipeline.py
├── storage.py
├── report_metadata.py
├── analyze_gpa.py
├── course_summary.py
├── instructor_summary.py
├── schema.sql
├── requirements.txt
├── README.md
├── .gitignore
├── .github/workflows/tests.yml
├── frontend/                  # HTML, CSS, JavaScript
├── scripts/                   # 일부 보조 도구만 위치
│   ├── apply_name_reviews.py
│   ├── explore_db.py
│   └── validate_data.py
├── tests/                     # Python/JavaScript 테스트와 fixture, 실행 도구
├── docs/
│   ├── integrity-verification.md
│   ├── windows-resource-fix.md
│   └── superpowers/plans/2026-11-04-integrity.md
├── data/
│   ├── README.md
│   ├── GENERATED_FILES_HERE.txt
│   ├── manual_instructor_reviews.csv
│   └── [로컬 DB·백업·CSV·Import/Validation 기록]
└── reports/
    ├── README.md
    ├── PUT_PDF_HERE.txt
    └── [로컬 원본 PDF]
```

## 정리 후

```text
MaroonWay/
├── README.md                   # 설치·실행 방법과 시작점
├── api.py                      # FastAPI 실행 진입점
├── pipeline.py                 # PDF Import·재검증 명령 진입점
├── storage.py                  # SQLite 저장·migration·검증 이력
├── report_metadata.py          # PDF 학기·연도·College·종류 검증
├── schema.sql                  # 기존 기본 DB 스키마, 내용 변경 없음
├── requirements.txt            # Python 의존성
├── .gitignore                  # Git에서 제외할 로컬 파일 규칙
├── .github/workflows/tests.yml # Windows/Linux 자동 테스트
├── frontend/
│   ├── index.html              # 웹 화면
│   ├── style.css               # 화면 스타일
│   └── app.js                  # 검색·비교 동작
├── scripts/
│   ├── analyze_gpa.py          # 섹션별 GPA 조회
│   ├── course_summary.py       # 과목별 가중 GPA 요약
│   ├── instructor_summary.py   # 원문 교수명별 요약, 신원 확인 아님
│   ├── explore_db.py           # 원본 DB의 과목별 행 수 확인
│   ├── validate_data.py        # 수동 PDF 대조용 샘플 생성
│   └── apply_name_reviews.py   # 수동 교수명 검토 반영
├── tests/
│   ├── test_pipeline.py        # 최초 7개 파서 테스트
│   ├── test_integrity.py       # 성적 수치·이름 파싱
│   ├── test_metadata.py        # 보고서 메타데이터
│   ├── test_storage.py         # 저장·migration·기록 보존
│   ├── test_api.py             # 공개 API·분석 도구 검증
│   ├── test_resource_lifecycle.py # DB·PDF 연결 종료
│   ├── test_frontend.cjs       # JavaScript 비동기 검색 테스트
│   ├── pdf_fixture.py          # 테스트용 유효한 PDF 생성
│   └── run_checks.py           # 연결 누수까지 검사하는 실행 도구
├── docs/
│   ├── project-structure.md    # 이 문서: 역할·분류·정리 내역
│   ├── integrity-plan.md       # 과거 데이터 무결성 구현 계획·결정 기록
│   ├── integrity-verification.md # 313개 원본 행 검증 기록
│   └── windows-resource-fix.md # Windows 파일 잠금 수정·CI 결과
├── data/
│   ├── README.md
│   ├── manual_instructor_reviews.csv
│   └── [로컬 DB·백업·CSV·Import/Validation 기록 그대로 보존]
└── reports/
    ├── README.md
    └── [로컬 원본 PDF 그대로 보존]
```

`data/`와 `reports/`의 대괄호 항목은 파일 이름이나 존재 여부를 단정하는 목록이 아닙니다. `.gitignore`로 제외된 파일은 GitHub 또는 클라우드에서 안 보일 수 있습니다. **안 보이는 데이터는 삭제 대상으로 판단하지 않습니다.** 로컬 `.venv/`, `__pycache__/`, `.git/`, 개인 `.vscode/` 설정도 이번 작업에서 삭제하지 않았습니다.

## 파일 분류와 결정

| 분류 | 파일/폴더 | 결정과 이유 |
| --- | --- | --- |
| 필수 | `api.py`, `pipeline.py`, `storage.py`, `report_metadata.py` | 루트에 유지. 기존 import와 실행 진입점을 보존하고 추가 패키지 계층을 만들지 않음 |
| 필수 | `schema.sql`, `requirements.txt`, `.gitignore`, `README.md` | 유지. 스키마·의존성·Git 규칙은 변경하지 않고 README 경로만 갱신 |
| 필수 | `frontend/`의 세 파일 | 유지. FastAPI의 기존 정적 파일 경로와 UI 동작 보존 |
| 필수 | `tests/`의 모든 기존 파일 | 유지. 테스트 삭제·skip 없음. 이동한 분석 도구 경로만 수정 |
| 필수 | `.github/workflows/tests.yml` | 유지. 테스트 진입점과 루트 작업 디렉터리가 그대로여서 명령 변경 불필요 |
| 필수·보호 대상 | DB, 백업 DB, 원본 PDF, 모든 CSV와 Import/Validation 기록 | 내용·위치 보존. 실제 DB를 열어 migration하거나 재검증하지 않음 |
| 이동 권장 | 루트의 `analyze_gpa.py`, `course_summary.py`, `instructor_summary.py` | `git mv`로 `scripts/`에 이동. 기존 보조 도구와 한곳에 모으고 DB 경로만 프로젝트 루트 기준으로 보정 |
| 이동 권장 | `docs/superpowers/plans/2026-11-04-integrity.md` | `git mv`로 `docs/integrity-plan.md`에 이동. 내용은 보존하고 불필요한 중첩만 제거 |
| 중복·삭제 후보 → 삭제 | `data/GENERATED_FILES_HERE.txt` | 생성 파일 안내가 루트·data README에 중복되고 과거 출력 파일명도 포함. 실제 데이터가 아닌 안내문임을 내용 확인 후 삭제 |
| 중복·삭제 후보 → 삭제 | `reports/PUT_PDF_HERE.txt` | 동일한 다운로드·저장 안내가 `reports/README.md`와 루트 README에 이미 있어 안내문만 삭제 |
| 삭제 후보 → 보존 | 과거 구현 계획·검증 문서 | 계획·검증 결과·Windows 원인 설명은 역할이 달라 중복으로 보지 않음 |
| 삭제 후보 → 보존 | 기존 분석/검토 스크립트 | 조회·집계·수동 검토 역할이 달라 합치거나 삭제하지 않음 |

이번 정리에서 기능 코드의 변경은 이동한 세 스크립트의 `__file__` 기반 DB 경로 보정뿐입니다. SQL, DB 스키마, API, PDF 파싱, 프론트엔드 기능은 바꾸지 않았습니다.

## 보조 도구 실행

프로젝트 루트에서 실행하세요:

```bash
python scripts/analyze_gpa.py
python scripts/course_summary.py
python scripts/instructor_summary.py
python scripts/explore_db.py
python scripts/validate_data.py
python scripts/apply_name_reviews.py
```

분석 도구의 선택 학기·과목은 기존처럼 스크립트 안의 변수로 지정합니다. 수동 검토 도구는 기존 DB와 검토 입력이 필요합니다. **폴더 정리를 위해 이 도구들을 실제 사용자 데이터에 실행할 필요는 없습니다.**

세 분석 스크립트는 호출한 터미널 위치와 무관하게 자기 파일 위치에서 프로젝트 루트를 찾습니다. 테스트도 임시 DB로 이동된 스크립트를 실행하며, 실제 DB를 대신 사용하지 않습니다.
