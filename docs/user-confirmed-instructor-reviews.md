# 네 건의 사용자 확인 교수명 적용

이번 확인은 **사용자가 직접 제공한 확인(`user_confirmed`)**입니다. TAMU의 독립 검증이나 `professor_id` 신원 연결을 의미하지 않습니다.

| 학기 / College | Section | 원문 이름 | 표시명 | 확인 범위 |
| --- | --- | --- | --- | --- |
| 2026-SPRING / AT | ECON-202-M01 | VILLAVICENCIO | Xavier Villavicencio | 이름 및 이니셜 X |
| 2026-SPRING / AT | SPAN-102-504 | DE LOS SANTOS | Rodrigo De Los Santos | 이름 및 이니셜 R |
| 2026-SPRING / AT | STAT-201-504 | HERNANDEZ | HERNANDEZ I | 이니셜 I만 확인 |
| 2026-SPRING / AT | STAT-201-507 | HERNANDEZ | HERNANDEZ I | 이니셜 I만 확인 |

## 보존과 검증 원칙

- 기존 `data/manual_instructor_reviews.csv`의 두 candidate 기록은 수정하지 않았습니다. 새 네 건은 `data/user_confirmed_instructors.csv`에 별도로 추가합니다.
- `instructor_as_reported`, `raw_row`, 성적, 원본 PDF, 기존 수동 검토 열은 그대로 둡니다. `quality_status`나 `professor_id`를 직접 수정하지 않습니다.
- 학기, College, 과목 코드, 과목 번호, Section, **원문 이름이 모두 일치**해야 적용됩니다. 성만 같은 다른 교수나 다른 학기는 자동으로 연결하지 않습니다.
- 해결할 수 있는 것은 `Instructor name lacks an identifiable final initial` 하나뿐입니다. 나머지 성적·출처·파싱·중복·충돌 오류는 계속 차단됩니다.
- 확인 기록을 추가하는 것만으로 공개하지 않습니다. 보존된 PDF로 재검증한 새 감사 기록이 필요합니다. 기존 감사 기록은 변경하지 않습니다.
- API와 화면은 표시명과 원문 이름을 구분합니다. HERNANDEZ의 전체 이름은 추측하지 않습니다.

## 파일 역할

| 파일 | 역할 |
| --- | --- |
| `data/user_confirmed_instructors.csv` | 네 건의 사용자 확인 입력; 기존 후보 CSV와 별도 보존 |
| `instructor_reviews.py` | 정확한 키 대조, 추가형 확인 이력, 재검증 시 적용할 확인 조회 |
| `scripts/apply_name_reviews.py` | 기존 수동 도구에 `--confirmations`, `--db`를 명시하는 안전한 적용 경로 추가 |
| `storage.py`, `pipeline.py` | 소스 검증에서 해당 문제만 해결된 것으로 판단하고 감사 기록에 확인 근거 연결 |
| `api.py`, `frontend/app.js` | 검증된 표시명·원문·사용자 확인 근거·initial-only 범위 제공 |
| 새 회귀 테스트 | 네 건의 정확한 적용, 다른 항목 차단, 반복 실행, 원문 보존과 재검증 검증 |

## 로컬 적용: 재수입·초기화 불필요

먼저 서버를 Ctrl+C로 중지하고 Excel 등 CSV를 연 프로그램을 닫습니다. 프로젝트 루트에서 실행합니다. 테스트 복사본은 기존 DB를 SQLite backup API로 별도 생성하고, 기존 파일 이름을 덮어쓰지 마세요. 생성 방법은 [계산 GPA 안내](calculated-gpa-methodology.md)의 복사본 예제를 참고하세요.

```powershell
git pull origin main
py -3.14 -m pip install -r requirements.txt
py -3.14 scripts/apply_name_reviews.py --db data/maroonway-gpa-test.db --confirmations data/user_confirmed_instructors.csv
py -3.14 pipeline.py revalidate --db data/maroonway-gpa-test.db --pdf reports/spring_2026_arts_and_sciences.pdf
py -3.14 -W error::ResourceWarning tests/run_checks.py
node tests/test_frontend.cjs
```

확인 입력을 실제로 적용하는 명령은 다음과 같습니다. 복사본 결과를 확인한 다음 실행하세요. 최초 스키마 변경 전 고유한 SQLite 백업을 만듭니다. `public_grade_sections.csv`는 현재 상태를 나타내는 생성 파일이므로 기존 파일을 남기려면 먼저 고유한 이름으로 복사하세요. Import/Validation의 개별 이력 CSV는 덮어쓰지 않습니다.

```powershell
py -3.14 scripts/apply_name_reviews.py --db data/maroonway.db --confirmations data/user_confirmed_instructors.csv
py -3.14 pipeline.py revalidate --db data/maroonway.db --pdf reports/spring_2026_arts_and_sciences.pdf
py -3.14 -m uvicorn api:app --reload
```

DB에 없는 Section은 `unmatched`로 보고하고 다른 Section에 대신 적용하지 않습니다. 이전 313행 MATH/STAT DB에는 ECON/SPAN 행이 없으므로 STAT 두 건만 적용될 수 있습니다. 전체 학부 Import DB에는 네 건이 모두 있을 수 있습니다. 실제 결과는 명령 출력과 새 검증 보고서로 확인해야 합니다.

원문 이름이 다르거나 다른 차단 사유가 있으면 공개 대상으로 바뀌지 않습니다. `--confirmations` 없는 기존 candidate/verified 도구 실행은 예전 방식이며, 이니셜 누락 해결 근거로 사용되지 않습니다. 이번 네 건에는 위의 명시적인 확인 경로를 사용하세요.

## SQL 구조와 검증 결과

- 스키마 v4 migration은 변경 전 고유 백업을 만들고 한 번만 실행됩니다.
- `instructor_reviews`는 확인 시각, 정확한 대상 키, 원문 이름, 표시명, 이니셜, 확인 범위와 근거를 추가형으로 보관합니다. 같은 내용을 재적용하면 중복 기록을 만들지 않습니다.
- `grade_validation_instructor_reviews`는 새 검증 ID와 실제 사용한 확인 ID, 해결된 이슈 문구를 연결합니다. 원래 이슈는 `grade_validations.issues_json`에 남으므로 사후에 왜 통과했는지 확인할 수 있습니다.
- `source_verified_grade_sections`는 기존 GPA·성적·출처·충돌 검증을 그대로 유지합니다. 공개 View는 그 결과에 확인 표시명만 결합합니다. 원문이나 기존 `quality_status`를 덮어쓰지 않습니다.
- `matching_review`는 전체 키의 문자 그대로 일치를 확인합니다. `apply_confirmations`는 입력을 검증하고 일치한 행의 확인만 기록합니다. 공개 여부는 별도의 재검증에서 결정합니다.

Python 3.12와 3.14에서 기존 테스트를 포함한 **88개**, JavaScript **10개**가 통과했습니다. 처음에는 새 CLI 재검증 및 화면 표시 테스트가 실패했고, 구현 후 통과하는 것을 확인했습니다. 연결 누수와 임시 파일 정리 검사도 유지했습니다.

실제 제공된 PDF를 이용한 임시 검증:

| 대상 | 확인 적용 결과 | 재검증 결과 |
| --- | --- | --- |
| 기존 313행 DB의 임시 복사본 | STAT 두 건 적용; 없는 ECON/SPAN 두 건은 unmatched | 원본 313행 유지, 313행 통과 |
| 전체 PDF로 만든 별도 임시 DB | 네 건 모두 정확히 적용 | 2,364행 유지, 2,364행 공개 가능 |

확인 기록만 추가한 직후에는 이전 차단 상태가 그대로 유지됐습니다. PDF 재검증 후에만 해당 문제를 해결한 새 감사 기록이 생겼습니다. 원본 이름·성적·기존 수동 검토 열과 과거 감사 기록은 전후 비교에서 동일했습니다. 별도의 음수 성적 회귀 사례는 확인 후에도 계속 차단됐습니다. 실제 운영 DB에 네 건을 적용한 것은 아닙니다.

Windows/Linux CI 실행 결과는 완료 응답에서 해당 커밋의 실행 링크로 제공합니다. 로컬 파일은 코드 pull만으로 바뀌지 않으므로 위 명령을 실행한 뒤 결과를 확인하세요.
