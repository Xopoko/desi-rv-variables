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

## v0.2.0

- Replace pandas-dependent fold hashing with the audit's explicit BLAKE2b
  contract and regenerate every OOF offset model.
- Replace the primary candidate null with complete exposure-level night
  permutations refitted independently in every source fold.
- Propagate offset uncertainty through Bayesian source-bootstrap models.
- Add leave-one-epoch-out, independent-pair, intrinsic-jitter, and
  within-program robustness diagnostics.
- Add Gaussian and heavy-tailed Keplerian injection-recovery sensitivity runs.
- Reserve `ROBUST_DIAGNOSTIC_SUBSET` for deterministic triage; no gold sample,
  calibrated FDR, or novelty claim is introduced.

## Exploratory follow-up, 2026-07-13

- Freeze three follow-up questions and thresholds in
  `research/exploratory_experiments_protocol.md` before inspecting their ranked
  source identifiers.
- After the metal-poor external screen, add a post-selection flux-level check
  against the public DR1 `B`, `R`, and `Z` cframe spectra. This is validation,
  not a fourth discovery experiment. Before running the three-arm check, define
  consistency as at least four epochs, catalogue-versus-spectral relative-RV
  correlation at least 0.8, median absolute residual at most 10 km/s, and a
  spectral RV range of at least 20 km/s.
- Add a post-selection context comparison of declared Gaia DR3 or SpecDis
  matches among all high-amplitude-eligible sources. This comparison does not
  alter eligibility or detection thresholds.
