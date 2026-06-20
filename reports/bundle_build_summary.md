# Bundle Build Summary

Generated from local DESI DR1 MAIN FITS files using the frozen protocol,
`desi-rv-audit` v0.2.1 diagnostic `PROGRAM:NIGHT` fold offsets, and the
component-aware `desi-rv-variables` v0.1.1 bundle builder.

This report contains aggregate counts only. It intentionally does not list or
rank source IDs.

## Local Run

Runtime: 113.21 s

Maximum resident set size: 13.00 GB

Swaps: 0

The runtime includes SHA-256 hashing of the three input FITS files for the
local manifest.

## Artifacts

```text
artifacts/source_summary_oof.parquet                 318,834 rows, 53 MB
artifacts/candidate_epoch_bundle.parquet              89,180 rows, 21 MB
artifacts/strict_candidate_transition_table.csv            4 rows, 136 B
artifacts/build_manifest.json
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
builder now preserves `PROGRAM_NIGHT_COMPONENT_OOF` and marks any such source
as `CROSS_COMPONENT_UNSCORABLE`.

## Primary Transition Table

Frozen strict screening candidates from `desi-rv-audit`: 12,141.

| Before class | OOF class | Sources |
| --- | --- | ---: |
| OUTLIER | OUTLIER | 10,540 |
| OUTLIER | STABLE | 1,540 |
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
screening candidates, or 12.75%, change from `OUTLIER` to `STABLE` after
source-disjoint OOF diagnostic correction. This is a classification change
under the declared first-pass rule, not proof of a causal calibration
contamination rate.

## Bundle Roles

Unique source groups in `candidate_epoch_bundle.parquet`:

| Bundle role | Sources |
| --- | ---: |
| STRICT_SCREENING_CANDIDATE | 12,141 |
| CADENCE_MATCHED_INSPECTION_AND_INJECTION_BASE | 12,070 |
| INJECTION_RECOVERY_BASE_POPULATION | 32 |
| CADENCE_MATCHED_INSPECTION_CONTROL | 30 |

The cadence-matched inspection controls are outcome-conditioned and are for
dossier comparison only. The injection-recovery base population is selected
from the primary eligible population without requiring a stable OOF outcome.

This is not a final variable-star catalogue. It is the starting point for
injection-recovery calibration, external crossmatches, and object-level
exclusion checks.
