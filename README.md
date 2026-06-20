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

## Data Boundary

Raw DESI FITS files and derived Parquet bundles are intentionally ignored by
git. Build them locally from public DESI DR1 files and the public
`desi-rv-audit` artifacts.

The frozen offset table is the one published in `desi-rv-audit` `v0.2.1`.
For a clean checkout, clone the audit repository at that tag:

```bash
git clone --branch v0.2.1 https://github.com/Xopoko/desi-rv-audit.git
git clone --branch v0.1.3 https://github.com/Xopoko/desi-rv-variables.git
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
from this repository's `v0.1.3` release and verify its SHA-256 checksum before
building local artifacts.

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
artifacts/candidate_shuffle_transition_null.csv
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
transition tables, shuffled-candidate null control, threshold sensitivity, and
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

`VRAD_ERROR_CALIBRATED` does not include uncertainty in the estimated
`PROGRAM:NIGHT` offsets. The resulting `p_const_oof` values are screening
statistics, not fully calibrated posterior probabilities or FDR estimates.

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
