# Official GPA and course-credit evidence: verification blocked

Research date: 2026-11-05 UTC. Scope: the 23 historical flags in
[`spring-2026-import-review.md`](spring-2026-import-review.md).

**No current TAMU catalog, Registrar, or Student Rules content was retrieved in
this environment. No official quotation, course-credit range, zero-credit
eligibility, GPA rounding rule, or section-specific explanation has been
verified by this research.** Unknown values must remain unknown; course numbers
such as 291, 484, and 491 are not sufficient evidence of credit type.

## Access evidence

The cloud environment reported current observations and an **enforced restricted**
HTTP network policy. Its allowed destinations contain package-manager and source
hosting domains; `catalog.tamu.edu`, `student-rules.tamu.edu`, and
`registrar.tamu.edu` are absent. The local `/etc/codex/network-policy.json`
agrees. VPN is not configured.

An ordinary sandbox request to the official PHYS catalog URL failed with
`curl: (7) Failed to connect to proxy port 8080`. Retrying with approved command
escalation, while preserving the configured proxy and TLS verification, reached
the proxy but returned:

```text
HTTP/1.1 403 Forbidden
curl: (56) CONNECT tunnel failed, response 403
```

This same CONNECT denial occurred for all three attempted URLs:

| Attempted official URL | Result |
| --- | --- |
| https://catalog.tamu.edu/undergraduate/course-descriptions/phys/ | CONNECT denied, 2026-11-05 00:39:32 UTC |
| https://student-rules.tamu.edu/rule10/ | CONNECT denied, 2026-11-05 00:39:46 UTC |
| https://registrar.tamu.edu/grades-and-transcripts/grades/understanding-your-grades | CONNECT denied, 2026-11-05 00:39:45 UTC |

These are access failures, not a TAMU page response and not evidence that any
page is absent. The paths' current existence/content could not be checked.
No direct-network, alternate-proxy, mirror, or domain-routing bypass was used.
The missing access can be resolved through the environment's supported network
configuration workflow, or with user-provided official catalog/rules documents.

## Credit-hours verification register

Every relevant course and section is included below. The catalog links are
**candidate official sources for follow-up, not retrieved citations**. Other
catalog subjects were not separately requested after the catalog host was
explicitly denied. Fixed/variable/zero credit status remains unverified for
every row. The current catalog would also need to be checked against the
catalog effective for Spring 2026; a current course description alone does not
prove historical section registration hours.

| Course | Historical flagged sections | Credit type/range and zero-credit eligibility | Candidate official catalog |
| --- | --- | --- | --- |
| ARSC 289 | 500 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/arsc/ |
| PHYS 291 | 512, 563, 580, 581, 582, 583 | Unknown; zero-credit hypothesis unverified | https://catalog.tamu.edu/undergraduate/course-descriptions/phys/ |
| PHYS 491 | 502, 563, 582 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/phys/ |
| HIST 280 | 901 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/hist/ |
| ASTR 491 | 503 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/astr/ |
| ENGL 313 | 500 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/engl/ |
| COMM 210 | 502 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/comm/ |
| PBSI 491 | 502, 537, 543 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/pbsi/ |
| ANTH 484 | 502 | Unknown; variable-credit hypothesis unverified | https://catalog.tamu.edu/undergraduate/course-descriptions/anth/ |
| PBSI 316 | 500 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/pbsi/ |
| PBSI 315 | 501 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/pbsi/ |
| PBSI 483 | 500 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/pbsi/ |
| PBSI 485 | 502 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/pbsi/ |
| BIOL 491 | 500 | Unknown | https://catalog.tamu.edu/undergraduate/course-descriptions/biol/ |

## GPA formula and precision: what is and is not established

The project diagnostic is `(4*A + 3*B + 2*C + D) / af_total`, with no value
when `af_total == 0`. It averages A–F student counts. It is not an independently
verified reproduction of the Registrar's section-report calculation.

A credit-weighted average would mathematically use
`sum(grade_points * registered_credit_hours) / sum(eligible_credit_hours)`.
That is a mathematical model, **not a retrieved quotation of TAMU policy**.
Whether and how TAMU includes zero-credit registrations, special grades,
repeats, incomplete grades, and eligibility adjustments in this particular
grade-distribution report remains unverified. A rule about individual transcript
GPA also must not automatically be asserted as the section-report algorithm.

No official rounding or truncation policy was retrieved. Do not state that TAMU
truncates GPAs to three decimal places without a direct official quotation and
applicable context. Pure arithmetic provides a useful limit: rounding to the
nearest 0.001 changes a value by at most 0.0005, and truncating a nonnegative
value to three decimal places changes it by less than 0.001. Thus the historical
differences, all at least 0.002, cannot be explained solely by displaying the
same count-average to three decimal places. This does not identify the true
underlying calculation.

## Decisions for the priority cases

- **PHYS 291-512:** the historical source review records nine A grades and
  reported GPA 0.000. A zero-credit enrollment explanation is a question for
  verification, not a confirmed exception. Even a catalog allowing zero hours
  would not prove that this section's registrations were zero hours or that the
  report emits 0.000 for a zero denominator.
- **ANTH 484-502:** the historical counts imply 3.666667 and the source reports
  3.636. Variable registered credits could affect a credit-weighted GPA, but
  neither course eligibility nor actual credits have been verified here.
- **BIOL 491-500:** 3.902 versus 3.900 is within the project's approved 0.005
  tolerance. Tolerance acceptance is not an explanation of the difference.
  Display rounding/truncation of exactly 3.900 cannot produce 3.902.
- **COMM 210-502, ENGL 313-500, HIST 280-901, PBSI 315-501, PBSI 316-500:** a
  hypothetical extra denominator entry can approximate some reported values.
  This pattern supplies no evidence that any student, grade, or denominator
  entry was omitted. Their course credits, report eligibility rules, and
  section calculation require official confirmation; do not infer a parser
  error or change A–F counts from numerical proximity.
- **Other cases:** course-level credit possibilities alone do not establish
  section-level causation. In particular, an all-A count with a 0.000 report
  remains a preserved unresolved source observation, not permission to write
  4.000.

Without additional official evidence, the 22 historical rows exceeding the
current 0.005 tolerance should remain `unexplained_mismatch`. The BIOL boundary
case may be `matches_reported` under that tolerance, with cause unconfirmed.
No row is substantiated as `verified_exception`, `possible_variable_credit`,
or `possible_zero_credit` by this unsuccessful external research. Hypotheses
may be retained in notes without turning them into verified credit metadata.
No classification grants publication approval.

## Evidence needed to finish official verification

For each course, retain the retrieved catalog edition/effective year, exact
credit-hours quotation, URL, and retrieval time. For GPA policy, retain the
official formula, eligible/excluded grades and hours, and any explicit decimal
processing statement. If precision is unstated, record it as unknown. To move
from a course-level possibility to `verified_exception`, obtain section/report
evidence connecting actual registered hours or report eligibility to the
reported aggregate. Do not collect or publish identifiable student records.

This document adds research notes only. It does not modify a DB, backup,
original PDF, existing CSV, import/validation history, source grades, or public
approval rules. Original numerical observations above refer to the historical
review document; this research did not independently re-render the PDF.
