# Bundle Build Summary

Generated from local DESI DR1 MAIN FITS files using the frozen protocol and
`desi-rv-audit` v0.2.1 diagnostic `PROGRAM:NIGHT` fold offsets.

This report contains aggregate counts only. It intentionally does not list or
rank source IDs.

## Local Run

Runtime: 93.33 s  
Maximum resident set size: 14.62 GB  
Swaps: 0

## Artifacts

```text
artifacts/source_summary_oof.parquet        317,201 rows, 51 MB
artifacts/candidate_epoch_bundle.parquet     89,098 rows, 21 MB
artifacts/build_manifest.json
```

## First Aggregate Counts

Frozen strict screening candidates from `desi-rv-audit`: 12,141.

OOF-scorable strict screening candidates in `source_summary_oof`: 12,103.

Among those:

- 10,558 remain first-pass OOF constant-RV outliers;
- 1,541 become stable-like under the OOF-corrected first-pass rule;
- 4 are not outliers under either exact before/OOF scoring in this builder;
- 1 is stable-like before under this exact OOF-scorable subset but becomes an
  OOF outlier;
- 38 strict screening candidates are not OOF-scorable in this bundle.

These small label differences relative to the original strict screening layer
exist because this builder scores only OOF-correctable epochs and uses the
frozen first-pass source rule on the rebuilt epoch table.

The first-pass OOF survival fraction relative to the frozen 12,141 strict
screening candidates is 87.0%.

The first-pass removed-or-unscorable fraction is 13.0%.

This is not a final variable-star catalogue. It is the starting point for
injection-recovery calibration and object-level exclusion checks.
