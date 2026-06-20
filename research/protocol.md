# Protocol

Status: internally frozen before inspecting ranked DESI source IDs in this
repository. The protocol and first aggregate builder were committed together;
this is not a formal preregistration.

## Research Question

After source-disjoint correction of residual `PROGRAM:NIGHT` velocity offsets,
which stars remain robustly inconsistent with constant radial velocity, and
what fraction of the original strict screening candidates changes
classification after applying source-disjoint diagnostic corrections?

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
- diagnostic `PROGRAM:NIGHT` fold offsets from `desi-rv-audit` v0.2.1;
- frozen strict screening list from the audit run.

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

Gold-sample thresholds must come from injection-recovery simulations:

- null simulations with real cadence, S/N, programs, and errors;
- sinusoidal or Keplerian injections over amplitude, period, eccentricity, and
  phase;
- residual calibration perturbations drawn from train-fold diagnostics.

Numeric thresholds for a high-confidence catalogue are not selected from real
candidates.

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
