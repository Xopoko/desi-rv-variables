# DESI RV Variables

[![Tests](https://github.com/Xopoko/desi-rv-variables/actions/workflows/tests.yml/badge.svg)](https://github.com/Xopoko/desi-rv-variables/actions/workflows/tests.yml)

Calibration-aware search infrastructure for DESI DR1 radial-velocity variable
candidates.

This is an independent exploratory analysis and is not an official DESI
Collaboration data product.

## Frozen Question

After source-disjoint correction of residual `PROGRAM:NIGHT` velocity offsets,
which sources remain inconsistent with constant radial velocity under the
frozen first-pass screening rule, and what fraction of the original strict
screening candidates changes classification after applying source-disjoint
diagnostic corrections?

This repository is a protocol-first follow-up to
[`Xopoko/desi-rv-audit`](https://github.com/Xopoko/desi-rv-audit). The audit
repository measures the residual night-associated structure; this repository
uses that diagnostic to prepare reproducible inputs for a future
injection-recovery-calibrated selection function for DESI DR1 radial-velocity
variable candidates.

## Scope

The first result is not "a new binary star." The first result is a quantified
candidate-selection change:

- strict constant-RV screening candidates before source-disjoint
  `PROGRAM:NIGHT` correction;
- remaining outliers in the complete single-component out-of-fold cohort;
- mutually exclusive before/after classification transitions;
- candidate counts as a function of S/N, program, number of epochs, baseline,
  and stellar parameters;
- a compact epoch bundle for the strict screening candidates, cadence-matched
  inspection controls, and an injection-recovery base population.

Candidate labels generated here are screening labels, not confirmed variable
stars. Object-level interpretation requires spectrum/model inspection and
external catalogue checks.

## Aggregate Result

In the complete single-component OOF cohort, 1,540 of 12,080 frozen strict
screening sources (12.75%) move below the first-pass threshold after the real
diagnostic correction; 10,540 remain above it.

The required candidate-level null changes the interpretation. Across 100
exposure-level shuffled-night assignments, each with all five fold models
refitted, the transition count ranges from 405 to 1,976 with median 1,091.
Ten permutations equal or exceed the real count, giving the corrected empirical
estimate `(10 + 1) / (100 + 1) = 0.109`.

Therefore this analysis does **not** show that the real `PROGRAM:NIGHT`
structure causes an excess number of candidate reclassifications. The 12.75%
is an observed classification change, not a calibration-contamination estimate.
The automated 1,140-source robust diagnostic subset is only triage for future
spectrum review and external crossmatches; it is not a variable-star catalogue.

## Exploratory Follow-up Experiments

Three additional questions were threshold-frozen before their ranked source
identifiers were inspected. The aggregate results are published in
[`reports/exploratory_experiments_summary.md`](reports/exploratory_experiments_summary.md),
with the exact protocol in
[`research/exploratory_experiments_protocol.md`](research/exploratory_experiments_protocol.md).

- A repeated high-amplitude rule requiring two disjoint same-program,
  inter-night pairs detects 197 of 953 eligible robust screening sources.
- A strict same-program secular-acceleration search detects 0 of 56 eligible
  sequences; the null result is retained without relaxing its gates.
- Six high-amplitude detections pass a consistent metal-poor screen. Two match
  known variable-star classifications. Four lack a match under the declared
  Gaia DR3, SpecDis-flag, exact-ID SIMBAD, and 2-arcsec VSX rules.
- A post-selection check against all three public DESI cframe arms recovers the
  relative line shifts for all four externally unmatched targets. Their
  catalogue-versus-flux RV correlations are 0.9982 to 0.9998, with per-source
  median absolute residuals of 0.30 to 6.40 km/s.

The last four objects are private follow-up targets, not claimed discoveries.
The flux check uses a common RVSpecFit model shape while fitting shifts directly
to the cframe fluxes; independent spectroscopy and expert review remain
required.

After building the base bundles, the follow-up workflow is:

```bash
python -m pip install -e ".[dev,spectra]"
python -m desi_rv_variables.cli run-experiments
python -m desi_rv_variables.cli crossmatch-experiments \
  --specdis data/external/specdis/iron-yr1-v2.1.fits
python -m desi_rv_variables.cli validate-spectra
python -m desi_rv_variables.cli publish-experiments
```

The frozen SpecDis v2.1 file is available from the official DESI DR1 VAC and
must have SHA-256
`25075043f066c27af6ac25edd381cdff20930ed87f9d337b2d9c2df1403ddf1b`.
Source-level experiment outputs and the downloaded cframes remain ignored by
git; only aggregate tables and sanitized provenance are tracked.

## Data Boundary

Raw DESI FITS files and derived Parquet bundles are intentionally ignored by
git. Build them locally from public DESI DR1 files and the public
`desi-rv-audit` artifacts.

The frozen offset ensemble is published by an immutable `desi-rv-audit`
release. The exact tag, commit, and SHA-256 values are recorded in the public
build manifest. For a clean checkout, clone both matching releases:

```bash
git clone --branch v0.3.0 https://github.com/Xopoko/desi-rv-audit.git
git clone --branch v0.3.0 https://github.com/Xopoko/desi-rv-variables.git
```

Expected local inputs can be provided via environment variables:

```bash
export DESI_RV_AUDIT_DATA_DIR=/path/to/desi-rv-audit/data
export DESI_RV_AUDIT_ARTIFACT_DIR=/path/to/desi-rv-audit/reports/program_night_artifacts
export DESI_RV_STRICT_CANDIDATES=/path/to/candidate_sources_strict.csv
```

PowerShell uses the same variable names:

```powershell
$env:DESI_RV_AUDIT_DATA_DIR = "C:\path\to\desi-rv-audit\data"
$env:DESI_RV_AUDIT_ARTIFACT_DIR = "C:\path\to\desi-rv-audit\reports\program_night_artifacts"
$env:DESI_RV_STRICT_CANDIDATES = "C:\path\to\candidate_sources_strict.csv"
```

If `DESI_RV_STRICT_CANDIDATES` is not set, `scripts/build_local_bundles.sh`
and `scripts/build_local_bundles.ps1` download `candidate_sources_strict.csv.gz`
from this repository's `v0.2.0` release and verify its SHA-256 checksum before
building local artifacts.

The same command downloads the three compressed permutation/bootstrap model
assets from `desi-rv-audit` `v0.3.0` when their uncompressed CSVs are absent.
Both gzip and raw SHA-256 values are checked before any FITS input is loaded.

The DESI DR1 stellar VAC reports 10,012,925 single-epoch spectra with stellar
parameters and radial velocities and 1,718,305 Gaia sources with more than one
RV/stellar-parameter measurement. See the DESI DR1 MWS VAC page:
https://data.desi.lbl.gov/doc/releases/dr1/vac/mws/

## Build Local Bundles

The portable entry point is the Python CLI. It works the same way on Windows,
macOS, and Linux:

```bash
python -m desi_rv_variables.cli build-local-bundles
```

By default it expects the sibling audit checkout layout:

```text
parent/
  desi-rv-audit/
    data/desi_main/rvpix_exp-main-backup.fits
    data/desi_main/rvpix_exp-main-bright.fits
    data/desi_main/rvpix_exp-main-dark.fits
    data/desi_corrections/backup_correction.fits
    reports/program_night_artifacts/diagnostic_offsets_program_night.csv
    reports/program_night_artifacts/program_night_permutation_offsets.csv
    reports/program_night_artifacts/program_night_permutation_exposure_map.csv
    reports/program_night_artifacts/program_night_bootstrap_offsets.csv
  desi-rv-variables/
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
.\scripts\build_local_bundles.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

./scripts/build_local_bundles.sh
```

For the exact tested dependency set, install `requirements-lock.txt` first and
then install the local package with `python -m pip install -e . --no-deps`.

To only download and validate the frozen strict candidate input:

```bash
python -m desi_rv_variables.cli download-strict-candidates
```

Outputs:

```text
artifacts/source_summary_oof.parquet
artifacts/candidate_epoch_bundle.parquet
artifacts/strict_candidate_transition_table.csv
artifacts/primary_cohort_transition_table.csv
artifacts/heuristic_offset_shuffle_null.csv
artifacts/full_pipeline_permutation_null.csv
artifacts/candidate_bootstrap_stability.parquet
artifacts/candidate_robustness.parquet
artifacts/program_night_offset_uncertainty.csv
artifacts/injection_recovery.csv
artifacts/build_manifest.json
reports/build_manifest_public.json
```

`source_summary_oof.parquet` contains source-level before/after constant-RV
metrics for sources with at least three good epochs, including OOF coverage,
component counts, and primary-cohort flags.

`candidate_epoch_bundle.parquet` contains all epochs for the frozen strict
screening candidates plus deterministic control populations. It is for analysis
and inspection, not for public catalog claims.

`strict_candidate_transition_table.csv` is the primary aggregate outcome. It
separates complete-case reclassification from OOF coverage loss and
cross-component exclusions.

The compact tracked files under `reports/` publish the sanitized manifest,
transition tables, full-pipeline permutation control, bootstrap offset
uncertainty, injection-recovery sensitivity, threshold sensitivity, and
metric-shift summaries without source-level rows.

## Method Boundary

The `PROGRAM:NIGHT` offsets are applied out-of-fold:

1. A source's fold is computed from its stable `GROUP_ID`.
2. The offset for `PROGRAM:NIGHT` is taken from the audit fold trained on the
   other sources.
3. The epoch-level corrected velocity is `VRAD_ADOPTED - OFFSET_OOF`.
4. Candidate scoring never uses a final all-source fit.
5. Primary source-level scoring requires all good epochs to have OOF offsets
   from one connected component. Cross-component sources are marked
   `CROSS_COMPONENT_UNSCORABLE`.
6. The runtime fold fixture and frozen input SHA-256 values are checked before
   the build proceeds.

The split is source-disjoint, not night-disjoint. This tests transfer across
different stars observed on the same nights. It does not test extrapolation to
unseen nights.

This is an exploratory analysis developed on the public DESI DR1 MAIN sample.
The protocol was internally frozen before ranked source-ID inspection, but it
is not a formal preregistration. Confirmation would require a pre-specified
analysis on an independent data slice or future release.

The frozen requirements for such a test are recorded in
[`research/confirmation_protocol.md`](research/confirmation_protocol.md).

`VRAD_ERROR_CALIBRATED` does not fold the uncertainty of the estimated
`PROGRAM:NIGHT` offsets into an independent per-epoch error. That uncertainty
is correlated across epochs sharing a label, so the pipeline propagates it by
repeating source-level scoring across source-bootstrap offset realizations.
The resulting `p_const_oof` values remain screening statistics, not fully
calibrated posterior probabilities or FDR estimates.

## References

- DESI DR1 MWS stellar catalogue VAC:
  https://data.desi.lbl.gov/doc/releases/dr1/vac/mws/
- DESI RV audit repository:
  https://github.com/Xopoko/desi-rv-audit
- SpecDis DESI DR1 distance/binary-candidate context:
  https://arxiv.org/abs/2503.02291
- The Joker sparse RV orbit sampler:
  https://arxiv.org/abs/1610.07602
- Gaia DR3 stellar multiplicity:
  https://arxiv.org/abs/2206.05595
