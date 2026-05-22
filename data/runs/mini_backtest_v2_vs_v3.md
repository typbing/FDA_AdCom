# Mini Backtest v2 vs v3 Comparison

## Summary
| Metric | v2 | v3 | Change |
|---|---:|---:|---:|
| labeled_analyzed_count | 8 | 8 | +0 |
| actionable_count | 7 | 7 | +0 |
| correct_count | 5 | 5 | +0 |
| accuracy | 0.7143 | 0.7143 | +0.0000 |

## Newly Added Labeled Cases

- None

## False Positives

- None

## False Negatives

- 6df8a6a4aa29769e | REGN | STRONG_NEGATIVE -> target positive | January 9, 2023 Meeting of the Dermatologic and Ophthalmic Drugs Advisory Committee- FDA Briefing Document
- 2252b7c3b1118d54 |  | STRONG_NEGATIVE -> target positive | May 9-10, 2023 Joint Meeting of the Nonprescription Drugs Advisory Committee and the Obstetrics, Reproductive and Urologic Drugs Advisory Committee- FDA Briefing Document

## STRONG_NEGATIVE Errors

- 6df8a6a4aa29769e | REGN | STRONG_NEGATIVE -> target positive | January 9, 2023 Meeting of the Dermatologic and Ophthalmic Drugs Advisory Committee- FDA Briefing Document
- 2252b7c3b1118d54 |  | STRONG_NEGATIVE -> target positive | May 9-10, 2023 Joint Meeting of the Nonprescription Drugs Advisory Committee and the Obstetrics, Reproductive and Urologic Drugs Advisory Committee- FDA Briefing Document

## STRONG_POSITIVE Errors

- None

## Key Lessons

- v3 is unchanged from v2 because no new verified outcomes were populated; unverified gaps were marked TODO_SOURCE_NEEDED instead of guessed.
- The labeled set remains too positive-heavy to validate signal quality.
- The two current actionable misses are negative calls on ultimately positive outcomes, matching the known REGN / Opill blind spot.

## Next Data Gaps

- Add verified negative, CRL, withdrawn, mixed vote, and split vote cases.
- Fill missing outcome_source before using any row for backtest conclusions.
- Capture briefing document release dates separately from AdCom meeting dates.
