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

Official v2.1 data model:
https://data.desi.lbl.gov/doc/releases/dr1/vac/mws-specdis/

Use:

- external context for DESI DR1 distance products and equal-mass
  binary-candidate flags;
- do not treat a SpecDis match as confirmation of known multi-epoch RV
  variability;
- avoid presenting generic RV variability search as novel without versioned
  crossmatches.
- interpret `BINARY_FLAG == 0` as the released binary-candidate flag and retain
  the continuous `BINARY_POSSIBILITY` value even when the flag is not set.

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

Exact archive tables used by the exploratory follow-up:

- `gaiadr3.nss_two_body_orbit`:
  https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_non--single_stars_tables/ssec_dm_nss_two_body_orbit.html
- `gaiadr3.nss_acceleration_astro`;
- `gaiadr3.nss_non_linear_spectro`;
- `gaiadr3.vari_summary`:
  https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_variability_tables/ssec_dm_vari_summary.html

An absent exact-ID row means only that the source is absent from these DR3
tables. It is not evidence that the source is new.

## Metallicity and Close Binaries

Moe, Kratter, and Badenes:
https://arxiv.org/abs/1808.02116

Use:

- motivate a bounded metal-poor follow-up screen;
- do not infer a companion class or formation channel from DESI metallicity
  and sparse RV epochs alone.

## Direct DESI Spectrum Access

Official access documentation:
https://data.desi.lbl.gov/doc/access/

Use:

- public DR1 cframe spectra are downloaded from the AWS DESI mirror;
- all three arms are used for the post-selection relative line-shift check;
- the check is not an independent survey because the common stellar model
  shape comes from the public RVSpecFit `RVMOD` product.

## Hypervelocity Stars

Example DESI DR1 context:
https://arxiv.org/abs/2601.19866

Use:

- exclusion boundary for the first project stage. This project does not start
  with black-hole or hypervelocity-star claims.
