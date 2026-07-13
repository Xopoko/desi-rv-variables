# Data Contract

## `source_summary_oof.parquet`

One row per source group with at least three good epochs. Primary scoring is
valid only for rows where `PRIMARY_COHORT == true`.

Required columns:

```text
GROUP_ID
GROUP_KIND
SOURCE_ID
FIRST_TARGETID
N_DISTINCT_TARGETIDS
N_EPOCHS_GOOD_TOTAL
N_NIGHTS_GOOD_TOTAL
N_PROGRAMS_GOOD_TOTAL
N_EPOCHS_GOOD_OOF
N_NIGHTS_GOOD_OOF
N_PROGRAMS_GOOD_OOF
OOF_EPOCH_COVERAGE_FRACTION
N_OOF_COMPONENTS
OOF_SCORING_STATUS
PRIMARY_COHORT
TIME_BASELINE_DAYS_OOF
DOMINANT_PROGRAM
MEDIAN_SN_R
MEDIAN_TEFF
MEDIAN_LOGG
MEDIAN_FEH
CHI2_CONST_BEFORE
P_CONST_BEFORE
LOG_P_CONST_BEFORE
MAX_PAIR_SIGMA_BEFORE
MAX_DELTA_VRAD_BEFORE
CHI2_CONST_OOF
P_CONST_OOF
LOG_P_CONST_OOF
MAX_PAIR_SIGMA_OOF
MAX_DELTA_VRAD_OOF
CLASSIFICATION_BEFORE
CLASSIFICATION_OOF
WAS_STRICT_SCREENING_CANDIDATE
REMAINS_OOF_OUTLIER
N_SIGNIFICANT_PAIRS
N_DISJOINT_SIGNIFICANT_PAIRS
SIGNAL_ONLY_CROSS_PROGRAM
LOO_OUTLIER_FRACTION
LOO_ALL_OUTLIER
JITTER_MLE_KMS
DELTA_LOG_LIKELIHOOD_M1_M0
OOF_OUTLIER_BOOTSTRAP_FRACTION
BOOTSTRAP_ROBUST_95
ROBUST_DIAGNOSTIC_SUBSET
IS_CADENCE_MATCHED_INSPECTION_CONTROL
IS_INJECTION_RECOVERY_BASE_POPULATION
```

Rows with `OOF_SCORING_STATUS == CROSS_COMPONENT_UNSCORABLE` must not be used
for direct before/after velocity comparisons because the audit offset gauge is
only defined within a connected component.

## `candidate_epoch_bundle.parquet`

All epochs for:

- frozen strict screening candidates;
- deterministic cadence-matched inspection-control sources;
- deterministic injection-recovery base-population sources.

Required columns:

```text
BUNDLE_ROLE
GROUP_ID
GROUP_KIND
SOURCE_ID
TARGETID
MJD
NIGHT
EXPID
EXPTIME
SURVEY
PROGRAM
TARGET_RA
TARGET_DEC
GAIA_PHOT_G_MEAN_MAG
PARALLAX
RADIAL_VELOCITY
RADIAL_VELOCITY_ERROR
VRAD
VRAD_ERR
VRAD_OFFSET
VRAD_ADOPTED
VRAD_FLOOR
VRAD_ERR_ADOPTED
PROGRAM_NIGHT_LABEL
PROGRAM_NIGHT_FOLD
PROGRAM_NIGHT_OFFSET_OOF
PROGRAM_NIGHT_COMPONENT_OOF
OOF_OFFSET_AVAILABLE
VRAD_CORRECTED_OOF
VRAD_ERROR_CALIBRATED
IS_CADENCE_MATCHED_INSPECTION_CONTROL
IS_INJECTION_RECOVERY_BASE_POPULATION
GOOD_EPOCH
SN_B
SN_R
SN_Z
TEFF
LOGG
FEH
VSINI
RVS_WARN
SUCCESS
FIBERSTATUS
TILEID
FIBER
RR_SPECTYPE
VRAD_SKEW
VRAD_KURT
CHISQ_TOT
CHISQ_C_TOT
```

## `strict_candidate_transition_table.csv`

Mutually exclusive aggregate transitions for the frozen strict candidates:

```text
BEFORE_CLASS
OOF_CLASS
N
```

Rows where `BEFORE_CLASS == UNSCORABLE` are coverage or component attrition,
not evidence of correction-induced reclassification.

Public transition labels use `BELOW_SCREENING_THRESHOLD` for sources that do
not satisfy the declared first-pass outlier rule. This does not mean the source
is astrophysically stable.

## Public aggregate report artifacts

Tracked aggregate files under `reports/`:

```text
build_manifest_public.json
strict_candidate_transition_table.csv
primary_cohort_transition_table.csv
heuristic_offset_shuffle_null.csv
full_pipeline_permutation_null.csv
program_night_offset_uncertainty.csv
injection_recovery.csv
threshold_sensitivity.csv
metric_shift_summary.csv
```

These files contain no source-level rows or ranked source IDs.
