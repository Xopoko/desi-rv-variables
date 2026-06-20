# Bundle Build Summary

Generated from local DESI DR1 MAIN FITS files using the frozen protocol,
`desi-rv-audit` diagnostic `PROGRAM:NIGHT` fold offsets from commit
`6b3c116cd77cc0254c9f26fd0e98fdebdaa4807b`, and the component-aware
`desi-rv-variables` v0.1.2 bundle builder.

This report contains aggregate counts only. It intentionally does not list or
rank source IDs.

## Local Run

Runtime: 157.81 s

Maximum resident set size: 15.78 GB

Swaps: 0

The runtime includes SHA-256 validation of the three input FITS files, the
published backup correction, the diagnostic offset table, and the strict
candidate list, plus 20 candidate-level shuffled-offset controls.

## Artifacts

```text
artifacts/source_summary_oof.parquet                 318,834 rows, 53 MB
artifacts/candidate_epoch_bundle.parquet              89,180 rows, 23 MB
artifacts/strict_candidate_transition_table.csv            4 rows, 155 B
artifacts/primary_cohort_transition_table.csv              5 rows, 233 B
artifacts/candidate_shuffle_transition_null.csv           20 rows, 962 B
artifacts/threshold_sensitivity.csv                       18 rows, 1.1 KB
artifacts/metric_shift_summary.csv                         6 rows, 1.0 KB
artifacts/build_manifest.json
```

Tracked public aggregate files:

```text
reports/build_manifest_public.json
reports/strict_candidate_transition_table.csv
reports/primary_cohort_transition_table.csv
reports/candidate_shuffle_transition_null.csv
reports/threshold_sensitivity.csv
reports/metric_shift_summary.csv
```

## OOF Coverage

`source_summary_oof.parquet` includes every source group with at least three
good epochs:

| OOF scoring status | Sources |
| --- | ---: |
| COMPLETE_SINGLE_COMPONENT | 316,744 |
| INSUFFICIENT_OOF_EPOCHS | 1,633 |
| PARTIAL_COVERAGE | 457 |

For the frozen strict screening candidates:

| OOF scoring status | Sources |
| --- | ---: |
| COMPLETE_SINGLE_COMPONENT | 12,080 |
| INSUFFICIENT_OOF_EPOCHS | 38 |
| PARTIAL_COVERAGE | 23 |

No strict candidate in this run required cross-component exclusion, but the
builder preserves `PROGRAM_NIGHT_COMPONENT_OOF` and marks any such source as
`CROSS_COMPONENT_UNSCORABLE`.

## Strict Candidate Transitions

Frozen strict screening candidates from `desi-rv-audit`: 12,141.

| Before class | OOF class | Sources |
| --- | --- | ---: |
| OUTLIER | OUTLIER | 10,540 |
| OUTLIER | BELOW_SCREENING_THRESHOLD | 1,540 |
| UNSCORABLE | INSUFFICIENT_OOF_EPOCHS | 38 |
| UNSCORABLE | PARTIAL_COVERAGE | 23 |

Headline fractions:

```text
coverage_attrition_fraction:          0.0050
before_rule_reconciliation_fraction:  0.0000
oof_reclassification_fraction:        0.1275
new_oof_outlier_fraction:             0.0017
```

The primary measurable result is that 1,540 of 12,080 complete-case strict
screening candidates, or 12.75%, move below the frozen first-pass screening
threshold after source-disjoint OOF diagnostic correction. This is a
classification change under the declared rule, not proof of a causal
calibration-contamination rate.

## Candidate-Level Shuffled Control

The shuffled control randomly permutes `PROGRAM:NIGHT` offsets within each
`FOLD x PROGRAM` block while preserving OOF label coverage and connected
components.

| Metric | Value |
| --- | ---: |
| Shuffles | 20 |
| Real `OUTLIER -> BELOW_SCREENING_THRESHOLD` | 1,540 |
| Shuffled minimum | 578 |
| Shuffled median | 711 |
| Shuffled maximum | 913 |
| Shuffles at or above real count | 0 |

This is a coarse null control, not a final p-value. With 20 shuffles, the
resolution is limited, but the real transition count is outside the observed
shuffled range.

## Primary-Cohort Transitions

All 316,744 complete single-component primary sources:

| Before class | OOF class | Sources |
| --- | --- | ---: |
| BELOW_SCREENING_THRESHOLD | BELOW_SCREENING_THRESHOLD | 290,916 |
| BELOW_SCREENING_THRESHOLD | OUTLIER | 509 |
| INSUFFICIENT_BASELINE | INSUFFICIENT_BASELINE | 13,239 |
| OUTLIER | BELOW_SCREENING_THRESHOLD | 1,540 |
| OUTLIER | OUTLIER | 10,540 |

The 509 `BELOW_SCREENING_THRESHOLD -> OUTLIER` transitions are reported
explicitly because one-sided survival fractions are affected by selection on a
previous extreme statistic.

## Threshold Sensitivity

At the frozen threshold (`p < 1e-6`, `max_pair_sigma >= 5`):

| Cohort | Before outliers | OOF outliers | Outlier to below | Below to outlier |
| --- | ---: | ---: | ---: | ---: |
| PRIMARY_ALL | 12,080 | 11,049 | 1,540 | 509 |
| FROZEN_STRICT_CANDIDATES | 12,080 | 10,540 | 1,540 | 0 |

The full one-at-a-time threshold table is in
`reports/threshold_sensitivity.csv`.

## Bundle Roles

Exclusive source roles in `candidate_epoch_bundle.parquet`:

| Bundle role | Sources |
| --- | ---: |
| STRICT_SCREENING_CANDIDATE | 12,141 |
| CADENCE_MATCHED_INSPECTION_AND_INJECTION_BASE | 12,070 |
| INJECTION_RECOVERY_BASE_POPULATION | 32 |
| CADENCE_MATCHED_INSPECTION_CONTROL | 30 |

Non-exclusive membership totals:

| Membership | Sources |
| --- | ---: |
| Cadence-matched inspection controls | 12,100 |
| Injection-recovery base population | 12,102 |
| In both control sets | 12,070 |

The two control sets are separately defined and substantially overlapping. The
cadence-matched inspection controls are outcome-conditioned and are for dossier
comparison only. The injection-recovery base population does not require a
stable OOF outcome and is intended for future simulations where real RVs are
replaced or perturbed under a declared null/injection model.

## Limitations

`VRAD_ERROR_CALIBRATED` does not include uncertainty in the estimated
`PROGRAM:NIGHT` offsets. Therefore `p_const_oof` is a screening statistic, not
a fully calibrated probability or false-discovery-rate estimate.

This is not a final variable-star catalogue. It is the starting point for
injection-recovery calibration, external crossmatches, and object-level
exclusion checks.
