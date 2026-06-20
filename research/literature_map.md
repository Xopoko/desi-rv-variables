# Literature Map

This map is for scoping and crosschecks. It is not evidence for any candidate
object until source-level analysis and external crossmatches are complete.

## DESI DR1 Stellar Catalogue

Primary data source:
https://data.desi.lbl.gov/doc/releases/dr1/vac/mws/

Relevant facts:

- DESI DR1 MWS VAC includes single-epoch stellar radial velocities and stellar
  parameters.
- The VAC contains `RVTAB`, `FIBERMAP`, and Gaia crossmatch extensions.
- The release page reports 10,012,925 single-epoch spectra with stellar
  parameters and radial velocities.
- It reports 1,718,305 Gaia sources with more than one RV/stellar-parameter
  measurement.
- Known issues include backup-program radial-velocity systematics.

## DESI DR1 Stellar Catalogue Paper

Koposov et al., "DESI Data Release 1: Stellar Catalogue"

- Open Journal of Astrophysics DOI: https://doi.org/10.33232/001c.155260
- arXiv: https://arxiv.org/abs/2505.14787

Use:

- official quality-cut guidance;
- backup correction and uncertainty-floor context;
- known night/tile/program systematics;
- comparison target for calibration-aware candidate counts.

## SpecDis

Paper:
https://arxiv.org/abs/2503.02291

Use:

- external context for DESI DR1 distance products and equal-mass
  binary-candidate flags;
- do not treat a SpecDis match as confirmation of known multi-epoch RV
  variability;
- avoid presenting generic RV variability search as novel without versioned
  crossmatches.

## The Joker

Paper:
https://arxiv.org/abs/1610.07602

Use:

- sparse RV orbital posterior modelling for selected high-quality candidates;
- report multimodal posterior constraints rather than unique orbits.

## Gaia DR3 Multiplicity

Paper:
https://arxiv.org/abs/2206.05595

Use:

- external known-binary/non-single-star crossmatch;
- distinguish known multiplicity from DESI-only new candidates.

## Hypervelocity Stars

Example DESI DR1 context:
https://arxiv.org/abs/2601.19866

Use:

- exclusion boundary for the first project stage. This project does not start
  with black-hole or hypervelocity-star claims.
