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
