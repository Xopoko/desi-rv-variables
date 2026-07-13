# Exploratory Follow-up Experiments

Status: frozen before inspecting experiment-ranked source identifiers.

This document defines three bounded exploratory tests on the existing
source-disjoint OOF epoch bundle. They are searches for follow-up targets, not
catalogue claims. Thresholds are not changed after inspecting ranked source
identifiers; any later change must be recorded in `research/amendments.md` and
reported as a separate sensitivity analysis.

## Shared Inputs

- `artifacts/source_summary_oof.parquet`
- `artifacts/candidate_epoch_bundle.parquet`
- `artifacts/program_night_offset_uncertainty.csv`
- DESI RV Audit `v0.3.0` OOF `PROGRAM:NIGHT` models
- Gaia DR3 archive tables, queried by exact Gaia `SOURCE_ID`
- DESI SpecDis `v2.1`, file `iron-yr1-v2.1.fits`

Only epochs satisfying the frozen DESI quality rules and having an OOF offset
are scored. OOF-corrected velocities are used throughout. Pair uncertainties
include both epoch errors and the published source-bootstrap standard deviation
of each `PROGRAM:NIGHT` label; the label term cancels for two epochs sharing the
same label.

## Experiment 1: Repeated High-Amplitude Variability

Question:

> Which strict screening sources show high-amplitude RV changes supported by
> two vertex-disjoint, same-program, inter-night epoch pairs?

Eligibility:

- complete, single-component OOF source;
- frozen strict screening candidate;
- at least four OOF epochs and three OOF nights;
- OOF baseline of at least 30 days;
- outlier classification in at least 95% of scorable source-bootstrap models;
- leave-one-epoch-out outlier classification in every evaluable trial;
- signal is not confined to cross-program transitions.

Detection rule:

- two vertex-disjoint epoch pairs from the same DESI program;
- each pair spans different nights;
- each pair has `abs(delta RV) >= 30 km/s`;
- each pair has uncertainty-aware significance `>= 8`;
- all four supporting epochs are distinct and span at least three nights.

Primary outputs are the number of eligible and detected sources, the program
distribution, amplitudes, and a private source-level follow-up table.

## Experiment 2: Secular RV Acceleration

Question:

> Which sources show a same-program RV trend that is robust to removing any
> single epoch and is unlikely under a within-source time-permutation null?

Each source-program sequence is tested independently. Same-night epochs are
first combined into inverse-variance weighted nightly means so correlated
same-night measurements cannot dominate the fit. Eligibility:

- complete, single-component OOF source and frozen strict screening candidate;
- at least four OOF epochs on at least four nights in one program;
- same-program baseline of at least 180 days.

Weighted constant and linear models use OOF-corrected RVs and total epoch
uncertainties. A sequence is detected when:

- absolute slope significance is at least 5;
- fitted end-to-end change is at least 20 km/s;
- `delta chi-square >= 25` relative to a constant model;
- linear-model reduced chi-square is at most 3;
- every leave-one-night-out fit preserves the slope
  sign and has slope significance at least 3.

The primary null keeps each source's measured `(RV, uncertainty)` tuples intact
and permutes them across its actual observing times. Two hundred deterministic
global permutations produce the null distribution of the number of detected
source-program sequences. This preserves the frozen candidate selection and
the observed cadence while removing temporal ordering.

## Experiment 3: Metal-Poor External-Novelty Screen

Question:

> Are any detections from Experiments 1 or 2 consistently metal poor and absent
> from the declared external binary/variability catalogues?

Eligibility:

- detected by Experiment 1 or Experiment 2;
- Gaia-grouped source with a positive Gaia DR3 `SOURCE_ID`;
- at least three finite epoch-level `[Fe/H]` measurements;
- median `[Fe/H] <= -2.0`;
- robust `[Fe/H]` width (`1.4826 * MAD`) at most 0.30 dex;
- median `Teff` between 4000 K and 7000 K.

External exact-ID checks:

- Gaia DR3 `nss_two_body_orbit`;
- Gaia DR3 `nss_acceleration_astro`;
- Gaia DR3 `nss_non_linear_spectro`;
- Gaia DR3 `vari_summary`;
- DESI SpecDis `v2.1` `BINARY_FLAG` and `BINARY_POSSIBILITY`.

`NO_DECLARED_CATALOGUE_MATCH` means only that no row or binary/variability flag
was found in these versioned resources under the exact-ID rules. It does not
establish novelty. SIMBAD/VSX checks, spectrum/model inspection, source
association review, and independent spectroscopy remain mandatory before an
object-level claim.

## Reporting Boundaries

- Source-level tables stay under ignored `artifacts/exploratory/` until direct
  spectrum review is complete.
- Public reports contain aggregate counts and hashed provenance, not ranked
  source identifiers.
- No detection is called a binary, compact companion, or new variable star.
- A null result is retained and reported without changing thresholds.

## Primary References

- DESI DR1 Stellar Catalogue:
  https://doi.org/10.33232/001c.155260
- Gaia DR3 non-single-star table documentation:
  https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_non--single_stars_tables/ssec_dm_nss_two_body_orbit.html
- Gaia DR3 variability summary table:
  https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_variability_tables/ssec_dm_vari_summary.html
- DESI SpecDis `v2.1` data model:
  https://data.desi.lbl.gov/doc/releases/dr1/vac/mws-specdis/
- Moe, Kratter, and Badenes, close-binary metallicity dependence:
  https://arxiv.org/abs/1808.02116
