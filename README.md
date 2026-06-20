# DESI RV Variables

[![Tests](https://github.com/Xopoko/desi-rv-variables/actions/workflows/tests.yml/badge.svg)](https://github.com/Xopoko/desi-rv-variables/actions/workflows/tests.yml)

Calibration-aware search infrastructure for DESI DR1 radial-velocity variable
candidates.

## Frozen Question

After source-disjoint correction of residual `PROGRAM:NIGHT` velocity offsets,
which stars remain robustly inconsistent with constant radial velocity, and
what fraction of the original strict screening candidates changes
classification after applying source-disjoint diagnostic corrections?

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

Expected local inputs can be provided via environment variables:

```bash
export DESI_RV_AUDIT_DATA_DIR=/path/to/desi-rv-audit/data
export DESI_RV_AUDIT_ARTIFACT_DIR=/path/to/desi-rv-audit-public/reports/program_night_artifacts
export DESI_RV_STRICT_CANDIDATES=/path/to/candidate_sources_strict.csv
```

If `DESI_RV_STRICT_CANDIDATES` is not set, `scripts/build_local_bundles.sh`
downloads `candidate_sources_strict.csv.gz` from this repository's `v0.1.1`
release and verifies its SHA-256 checksum before building local artifacts.

The DESI DR1 stellar VAC reports 10,012,925 single-epoch spectra with stellar
parameters and radial velocities and 1,718,305 Gaia sources with more than one
RV/stellar-parameter measurement. See the DESI DR1 MWS VAC page:
https://data.desi.lbl.gov/doc/releases/dr1/vac/mws/

## Build Local Bundles

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

scripts/build_local_bundles.sh
```

Outputs:

```text
artifacts/source_summary_oof.parquet
artifacts/candidate_epoch_bundle.parquet
artifacts/strict_candidate_transition_table.csv
artifacts/build_manifest.json
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

The split is source-disjoint, not night-disjoint. This tests transfer across
different stars observed on the same nights. It does not test extrapolation to
unseen nights.

This is an exploratory analysis developed on the public DESI DR1 MAIN sample.
The protocol was internally frozen before ranked source-ID inspection, but it
is not a formal preregistration. Confirmation would require a pre-specified
analysis on an independent data slice or future release.

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
