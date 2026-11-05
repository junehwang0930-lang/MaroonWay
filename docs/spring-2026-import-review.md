# Spring 2026 Arts & Sciences: Unicode and GPA review

Source: supplied original 291-page PDF, SHA-256 `d30c23460553b0adbfe6d02e51f536b16a0e54e50d0ad895db884f9f6ecee270`. Page numbers below are 1-based PDF pages. This is a separate analysis document; no existing DB, PDF, CSV, or Import/Validation history was modified.

## Parser correction versus unresolved source issues

- Two parse failures were caused by ASCII-only instructor validation: SPAN-101-501 (page 166) and SPAN-304-500 (page 169), both `GONZÁLEZ SOMOZA M`. Unicode letters and attached combining marks now validate; source spelling/raw text remain unchanged. Digits, controls, emoji, arbitrary symbols, and unattached combining marks remain rejected. English-name and numeric integrity checks are retained.
- Re-parsing the original PDF now yields **2,364 undergraduate rows**, **zero parser failures**, **23 GPA mismatch flags**, and **4 missing-initial flags**. Accepting a name does not independently verify professor identity.
- Missing initials remain unresolved: ECON-202-M01 (`VILLAVICENCIO`, page 102), SPAN-102-504 (`DE LOS SANTOS`, page 166), STAT-201-504 and STAT-201-507 (`HERNANDEZ`, page 281). No initials or identities were inferred.

## GPA comparison

Calculated diagnostic GPA = `(4*A + 3*B + 2*C + D) / af_total`. This is a consistency check based on published student counts, not a replacement for the Registrar's GPA or proof that every section uses equal credit weights. All original reported values and validation policy are retained.

Nine flagged rows show **0.000 in the original PDF** despite positive A–F counts. They are ARSC-289-500 and eight PHYS sections listed below. Rendered source rows for ARSC-289-500 and PHYS-291-580 were visually checked: the printed counts and 0.000 agree with extraction. All 23 cases were enumerated from source extraction. A search of the supplied PDF did not locate an explanatory grade-point/credit-hour exclusion rule or note. This does not establish whether another official policy explains the discrepancy. **Cause remains unconfirmed; do not replace 0.000 or other reported GPAs with calculated values.**

Grouped by absolute difference (GPA points):

| Absolute difference | Cases |
| --- | ---: |
| > 0.5 | 9 |
| > 0.1 and ≤ 0.5 | 5 |
| > 0.05 and ≤ 0.1 | 1 |
| > 0.01 and ≤ 0.05 | 6 |
| ≤ 0.01 | 2 |

## All 23 flagged rows, descending absolute difference

Counts column is A/B/C/D/F. Calculated/difference values are diagnostic and rounded to six decimals in this table only.

| Section | PDF page | A/B/C/D/F | A–F total | Reported GPA | Calculated GPA | Absolute difference |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| ARSC-289-500 | 77 | 10/0/0/0/0 | 10 | 0.000 | 4.000000 | 4.000000 |
| PHYS-291-512 | 251 | 9/0/0/0/0 | 9 | 0.000 | 4.000000 | 4.000000 |
| PHYS-291-563 | 251 | 9/0/0/0/0 | 9 | 0.000 | 4.000000 | 4.000000 |
| PHYS-291-581 | 251 | 15/0/0/0/0 | 15 | 0.000 | 4.000000 | 4.000000 |
| PHYS-291-582 | 251 | 15/0/0/0/0 | 15 | 0.000 | 4.000000 | 4.000000 |
| PHYS-291-583 | 251 | 5/0/0/0/0 | 5 | 0.000 | 4.000000 | 4.000000 |
| PHYS-491-563 | 254 | 7/0/0/0/0 | 7 | 0.000 | 4.000000 | 4.000000 |
| PHYS-491-582 | 254 | 9/0/0/0/0 | 9 | 0.000 | 4.000000 | 4.000000 |
| PHYS-291-580 | 251 | 7/1/1/0/0 | 9 | 0.000 | 3.666667 | 3.666667 |
| HIST-280-901 | 175 | 7/3/0/0/0 | 10 | 3.363 | 3.700000 | 0.337000 |
| ASTR-491-503 | 229 | 4/1/0/0/0 | 5 | 4.000 | 3.800000 | 0.200000 |
| PHYS-491-502 | 254 | 4/2/0/0/0 | 6 | 3.857 | 3.666667 | 0.190333 |
| ENGL-313-500 | 121 | 21/4/0/0/2 | 27 | 3.428 | 3.555556 | 0.127556 |
| COMM-210-502 | 84 | 17/7/0/0/2 | 26 | 3.296 | 3.423077 | 0.127077 |
| PBSI-491-502 | 268 | 7/1/0/0/0 | 8 | 3.818 | 3.875000 | 0.057000 |
| ANTH-484-502 | 6 | 11/0/0/0/1 | 12 | 3.636 | 3.666667 | 0.030667 |
| PBSI-316-500 | 263 | 28/53/23/1/1 | 106 | 2.971 | 3.000000 | 0.029000 |
| PBSI-491-537 | 269 | 7/1/0/0/0 | 8 | 3.857 | 3.875000 | 0.018000 |
| PBSI-315-501 | 263 | 192/16/7/0/2 | 217 | 3.807 | 3.824885 | 0.017885 |
| PBSI-483-500 | 267 | 73/2/0/0/0 | 75 | 3.958 | 3.973333 | 0.015333 |
| PBSI-485-502 | 267 | 7/3/0/0/0 | 10 | 3.714 | 3.700000 | 0.014000 |
| PBSI-491-543 | 269 | 13/1/0/0/0 | 14 | 3.920 | 3.928571 | 0.008571 |
| BIOL-491-500 | 41 | 18/2/0/0/0 | 20 | 3.902 | 3.900000 | 0.002000 |

### Threshold boundary

BIOL-491-500 has an exact decimal difference of **0.002** (3.902 versus 3.900). The existing float comparison can represent that difference slightly above 0.002 and flag it. Thus the 23 flags include **22 above the mathematical tolerance and one boundary case**. This numerical boundary issue is documented separately from an unexplained source discrepancy; the GPA tolerance and stored values were not changed as part of the Unicode fix.

## Verification

Python 3.12 and 3.14: 52 tests passed, including all previous 48. Node: 4 tests passed. New coverage includes precomposed/decomposed Unicode spelling, Unicode initials, mixed-case names, invalid control/symbol/mark rejection, unchanged GPA/missing-initial checks, and a valid-PDF → SQLite → CSV → revalidation Unicode round trip. Existing data/report fingerprints were checked for preservation.
