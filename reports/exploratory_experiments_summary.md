# Exploratory DESI DR1 RV Follow-up Experiments

This report records three threshold-frozen exploratory tests on the public DESI
DR1 MAIN single-epoch radial-velocity sample. It is an independent analysis,
not an official DESI data product or a variable-star catalogue. Source-level
tables remain private pending independent spectroscopy and expert review.

## Result 1: repeated high-amplitude variability

The frozen same-program, inter-night, two-disjoint-pair rule detected
**197 of 953 eligible sources (20.7%)**.
The support threshold requires two disjoint epoch pairs, each with at least
30 km/s absolute change and 8-sigma uncertainty-aware significance.

| Program | Detected | Median minimum support delta RV | Maximum support delta RV |
| --- | ---: | ---: | ---: |
| `BACKUP` | 161 | 42.872 km/s | 185.269 km/s |
| `BRIGHT` | 8 | 36.900 km/s | 112.775 km/s |
| `DARK` | 28 | 41.696 km/s | 115.154 km/s |


As a post-selection positive control, a declared Gaia DR3 NSS/variability or
SpecDis binary match occurs for **47.7%** of detections versus
**32.5%** of eligible non-detections. The descriptive Fisher
exact odds ratio is **1.892**
(`p=0.000115`). This supports
catalogue enrichment but is not a discovery significance or purity estimate.

## Result 2: secular acceleration

**No sequence passed all frozen acceleration gates** among
56 eligible source-program
sequences. None of the 200 within-source time
permutations produced a detection either; because the observed count is zero,
that control adds no positive evidence. Large raw slope significances existed, but the
candidate sequences failed the linear reduced-chi-square or leave-one-night-out
requirements; the null result was retained without relaxing thresholds.

## Result 3: metal-poor external-novelty screen

The high-amplitude detections contained **6**
sources satisfying the frozen epoch-level metallicity-consistency rule. Two are
matched to known variable-star classifications. Four have no match under the
declared Gaia DR3, SpecDis flag, exact Gaia-ID SIMBAD, and 2-arcsec VSX rules.
One of those four nevertheless has a high but unflagged SpecDis binary
probability (`>=0.8`; count=1), so absence of a flag
is not evidence of novelty.

The post-selection flux-level check downloaded all three DESI cframe arms for
every selected same-program epoch and fit their relative line shifts against a
common RVSpecFit model shape. **4 of 4** externally
unmatched metal-poor targets passed the pre-recorded consistency checks. Across
the four targets, the median catalogue-versus-flux relative-RV correlation is
**0.999** and the median per-source median absolute
residual is **1.782 km/s**.
Across the 19 checked epochs, the median and maximum
absolute shift recovered against each epoch's own RVMOD model are
**1.325** and **6.749 km/s**,
respectively.

These four objects are follow-up targets, not claimed discoveries. The flux
check reuses an RVSpecFit model shape, although it independently fits shifts to
the public cframe fluxes; source association review and new spectroscopy remain
required before an object-level claim.

## Reproduction boundaries

- Frozen questions and thresholds: `research/exploratory_experiments_protocol.md`.
- Post-selection additions: `research/amendments.md`.
- Aggregate CSVs and a checksummed public manifest are stored beside this file.
- Private source-level Parquet products are intentionally ignored by Git.
- The SpecDis v2.1 input SHA-256 is
  `25075043f066c27af6ac25edd381cdff20930ed87f9d337b2d9c2df1403ddf1b`.

## Primary references

- DESI DR1 MWS stellar catalogue: https://doi.org/10.33232/001c.155260
- Official DESI DR1 MWS VAC: https://data.desi.lbl.gov/doc/releases/dr1/vac/mws/
- Gaia DR3 archive data model: https://gea.esac.esa.int/archive/documentation/GDR3/
- DESI SpecDis v2.1 data model: https://data.desi.lbl.gov/doc/releases/dr1/vac/mws-specdis/
- Official DESI data access: https://data.desi.lbl.gov/doc/access/
