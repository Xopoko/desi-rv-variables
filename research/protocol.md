# Protocol

Status: internally frozen before inspecting ranked DESI source IDs in this
repository. The protocol and first aggregate builder were committed together;
this is not a formal preregistration.

## Research Question

After source-disjoint correction of residual `PROGRAM:NIGHT` velocity offsets,
which sources remain inconsistent with constant radial velocity under the
frozen first-pass screening rule, and what fraction of the original strict
screening candidates changes classification after applying source-disjoint
diagnostic corrections?

## Primary Outcome

The primary outcome is the mutually exclusive classification transition table
for frozen strict screening candidates after out-of-fold `PROGRAM:NIGHT`
correction:

```text
BEFORE_CLASS x OOF_CLASS
```

The headline scalar is defined only on the complete, single-component OOF
cohort:

```text
oof_reclassification_fraction =
  N(BEFORE outlier, OOF not outlier)
  / N(BEFORE outlier, complete OOF cohort)
```

Reported diagnostics also separate:

```text
coverage_attrition_fraction
before_rule_reconciliation_fraction
new_oof_outlier_fraction
```

This avoids attributing unscorable sources or rule-reconciliation differences
to a calibration effect.

A candidate-level full-pipeline permutation control starts from the audit's
exposure-level shuffled-night assignment, refits every fold-specific offset
model, applies that realization to the same physical candidate epochs, and
repeats source-level scoring. One exposure receives one shuffled night in every
pair where it appears. This produces the declared null distribution for
`OUTLIER -> BELOW_SCREENING_THRESHOLD` transitions among the frozen candidates.
The older within-table offset shuffle is retained only as a heuristic diagnostic
and is not used as primary evidence.

The primary outcome is reported overall and, where sample sizes support it, by:

- dominant DESI program;
- number of good epochs;
- number of nights;
- time baseline;
- S/N bin;
- `TEFF`, `LOGG`, and `[Fe/H]` bins;
- Gaia grouping versus `TARGETID` fallback grouping.

## Frozen Inputs

The first MAIN run uses:

- `rvpix_exp-main-backup.fits`;
- `rvpix_exp-main-bright.fits`;
- `rvpix_exp-main-dark.fits`;
- published DESI DR1 backup correction `backup_correction.fits`;
- diagnostic `PROGRAM:NIGHT` fold offsets, full-pipeline permutation models,
  exposure maps, and source-bootstrap models from `desi-rv-audit` v0.3.0;
- frozen strict screening list from the audit run.

The frozen build validates SHA-256 values for the three DESI FITS inputs, the
published backup correction, every diagnostic offset-model input, and the
strict candidate list. It also validates the runtime fold fixture before
applying out-of-fold offsets.

No source ID is inspected before this protocol and the first bundle builder are
committed.

## OOF Correction Rule

For each epoch:

```text
fold = hash(GROUP_ID) mod 5
label = PROGRAM + ":" + NIGHT
PROGRAM_NIGHT_OFFSET_OOF = offset_table[fold, label]
VRAD_CORRECTED_OOF = VRAD_ADOPTED - PROGRAM_NIGHT_OFFSET_OOF
```

If no fold offset exists for the label, the epoch is marked as not
OOF-correctable and excluded from primary source-level scoring.

The audit offset table also contains a connected-component identifier. Offset
differences are mathematically defined only within a train component. Therefore
primary scoring requires:

```text
N_OOF_COMPONENTS == 1
OOF_EPOCH_COVERAGE_FRACTION == 1.0
```

Sources with multiple OOF components are labelled
`CROSS_COMPONENT_UNSCORABLE`. Sources with partial OOF coverage are reported as
secondary coverage cases, not primary before/after evidence.

The epoch uncertainty used for the first pass is the audit adopted uncertainty:

```text
VRAD_ERROR_CALIBRATED = sqrt(VRAD_ERR^2 + published_program_floor^2)
```

This keeps the first selection conservative. Future analyses may re-estimate
post-correction floors on training folds, but that must be a separate protocol
amendment.

The uncertainty of the estimated `PROGRAM:NIGHT` offset is not added as an
independent term to `VRAD_ERROR_CALIBRATED`, because epochs sharing a label have
correlated correction uncertainty. Source-bootstrap offset realizations are
instead propagated through the complete source-level score. Therefore
`p_const_oof` remains a comparative screening statistic rather than a calibrated
false-discovery probability.

## Source-Level Models

### M0: constant RV

```text
v_i = mu + epsilon_i
```

The score is the Gaussian chi-square against a weighted mean using
`VRAD_CORRECTED_OOF` and `VRAD_ERROR_CALIBRATED`.

### M1: constant RV plus intrinsic jitter

```text
v_i = mu + eta_i + epsilon_i
eta_i ~ Normal(0, s^2)
```

M1 is used after the first bundle build to rank robust residual scatter. Jitter
thresholds are set by injection-recovery simulations, not by looking at the
best real objects.

### M2: Keplerian orbit

M2 is allowed only for objects with adequate epochs and baseline. Sparse
posteriors are reported as posterior constraints, not as unique orbital
solutions.

## Frozen First-Pass Outlier Definition

A source is a first-pass OOF constant-RV outlier if:

- `n_epochs_good_oof >= 3`;
- `time_baseline_days_oof > 1`;
- `p_const_oof < 1e-6`;
- `max_pair_sigma_oof >= 5`;
- at least two nights are represented;
- an OOF offset is available for every good epoch;
- all OOF offsets for the source come from one connected component.

This is a screening definition only.

## Threshold Selection

Any future catalogue threshold must come from injection-recovery simulations:

- null simulations with real cadence, S/N, programs, and errors;
- sinusoidal or Keplerian injections over amplitude, period, eccentricity, and
  phase;
- residual calibration perturbations drawn from train-fold diagnostics.

The current simulator replaces observed velocities with synthetic null or
Keplerian draws on real cadence/error templates. It reports Gaussian and
heavy-tailed noise sensitivities, but it does not by itself establish an
astrophysical prevalence or a catalogue FDR. Numeric thresholds for a final
catalogue are not selected from real candidates.

The cadence-matched inspection-control sample in the first bundle is
outcome-conditioned and is intended for dossier comparison only. The separate
`INJECTION_RECOVERY_BASE_POPULATION` is selected from the primary eligible
population without requiring a stable OOF outcome and is the starting point for
future null and injection-recovery simulations.

## Candidate Robustness Checks

Before any source is described as a high-confidence DESI RV-variable candidate:

1. Leave-one-epoch-out scoring must not eliminate the signal.
2. The signal must not be driven by one observation, one exposure, or one known
   problematic `PROGRAM:NIGHT` label.
3. At least two independent epoch pairs must support the RV change.
4. Fit-quality and posterior-shape fields must not indicate an obvious pipeline
   failure.
5. The underlying DESI spectrum/model must be inspected.
6. Gaia grouping must be checked for possible source-association failure.
7. External catalogues must be checked before claiming novelty.

The automated `ROBUST_DIAGNOSTIC_SUBSET` is only a triage subset satisfying
bootstrap, leave-one-out, disjoint-pair, and within-program checks. Its name is
deliberately not `gold` or `high-confidence`, and it is not a catalogue claim.

## External Crossmatches

Minimum external controls:

- Gaia DR3 non-single-star solutions;
- Gaia DR3 variability tables;
- SpecDis binary candidates;
- SpecDis equal-mass binary candidates are used only as contextual matches,
  not as confirmation of known multi-epoch RV variability;
- SIMBAD;
- International Variable Star Index;
- APOGEE, LAMOST, and GALAH RV catalogues where overlapping.

Final categories:

```text
KNOWN_BINARY
KNOWN_VARIABLE
KNOWN_PULSATOR
KNOWN_RV_VARIABLE
SPECDIS_EQUAL_MASS_BINARY_CANDIDATE
NEW_DESI_RV_VARIABLE_CANDIDATE
LIKELY_PIPELINE_ARTIFACT
UNRESOLVED
```
