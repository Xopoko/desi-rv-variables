# Protocol Amendments

This file records changes after the initial protocol and aggregate builder.
The project uses an internal freeze before ranked source-ID inspection, not a
formal preregistration.

## v0.1.1

- Preserve the audit `COMPONENT` field for `PROGRAM:NIGHT` offsets.
- Restrict the primary cohort to sources whose good epochs are fully
  OOF-correctable and belong to one connected component.
- Replace the single survival fraction with a mutually exclusive
  `BEFORE_CLASS x OOF_CLASS` transition table.
- Separate coverage attrition, before-rule reconciliation, OOF
  reclassification, and new OOF-outlier fractions.
- Split controls into cadence-matched inspection controls and an independently
  selected injection-recovery base population.
- Publish the frozen strict candidate input as a checksummed release asset
  rather than requiring an untracked generated file from another checkout.

## v0.1.2

- Rename public transition label `STABLE` to
  `BELOW_SCREENING_THRESHOLD`.
- Add candidate-level shuffled-offset controls for strict-candidate
  `OUTLIER -> BELOW_SCREENING_THRESHOLD` transitions.
- Validate frozen FITS, backup-correction, offset-table, and strict-candidate
  checksums before building.
- Validate the runtime fold fixture before applying OOF offsets.
- Publish sanitized manifest and aggregate CSVs under `reports/`.
- Clarify that the injection-recovery base population is separately defined
  but substantially overlaps with inspection controls.
- Remove DESI website disclaimer text and state that this repository is an
  independent exploratory analysis.

## v0.1.3

- Include the pinned clean-clone instruction in the immutable release tag.
- Point the default strict-candidate release asset URL at `v0.1.3`.
