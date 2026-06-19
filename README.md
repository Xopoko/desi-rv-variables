# DESI RV Variables

Calibration-aware search for radial-velocity variables in DESI DR1.

## Frozen Question

After source-disjoint correction of residual `PROGRAM:NIGHT` velocity offsets,
which stars remain robustly inconsistent with constant radial velocity, and
what fraction of the original strict screening candidates was attributable to
calibration-associated residuals?

This repository is a protocol-first follow-up to
[`Xopoko/desi-rv-audit`](https://github.com/Xopoko/desi-rv-audit). The audit
repository measures the residual night-associated structure; this repository
uses that calibration diagnostic to build a reproducible, calibration-aware
selection function for DESI DR1 radial-velocity variable candidates.

## Scope

The first result is not "a new binary star." The first result is a quantified
candidate-selection change:

- strict constant-RV screening candidates before source-disjoint
  `PROGRAM:NIGHT` correction;
- remaining outliers after out-of-fold epoch-level correction;
- candidate counts as a function of S/N, program, number of epochs, baseline,
  and stellar parameters;
- a compact epoch bundle for the strict screening candidates plus a matched
  stable-control sample.

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
export DESI_RV_AUDIT_PUBLIC_DIR=/path/to/desi-rv-audit-public
```

If these variables are not set, `scripts/build_local_bundles.sh` assumes the
`desi-rv-audit` and `desi-rv-audit-public` checkouts are siblings of this
repository.

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
artifacts/build_manifest.json
```

`source_summary_oof.parquet` contains source-level before/after constant-RV
metrics for all sources with at least three good OOF-correctable epochs.

`candidate_epoch_bundle.parquet` contains all epochs for the frozen strict
screening candidates plus a deterministic matched stable-control sample. It is
for analysis and inspection, not for public catalog claims.

## Method Boundary

The `PROGRAM:NIGHT` offsets are applied out-of-fold:

1. A source's fold is computed from its stable `GROUP_ID`.
2. The offset for `PROGRAM:NIGHT` is taken from the audit fold trained on the
   other sources.
3. The epoch-level corrected velocity is `VRAD_ADOPTED - OFFSET_OOF`.
4. Candidate scoring never uses a final all-source fit.

The split is source-disjoint, not night-disjoint. This tests transfer across
different stars observed on the same nights. It does not test extrapolation to
unseen nights.

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
