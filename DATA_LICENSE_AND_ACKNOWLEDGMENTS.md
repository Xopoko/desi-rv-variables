# Data License and Acknowledgments

The source code in this repository is licensed under the MIT License.

DESI data products used by this project are not covered by the repository's MIT
code license. DESI data are distributed under the Creative Commons Attribution
4.0 International License, with release-paper citation, change-disclosure, and
acknowledgment requirements documented by DESI:

https://data.desi.lbl.gov/doc/acknowledgments/

The ignored Parquet files under `artifacts/`, the aggregate report under
`reports/`, and the release asset `candidate_sources_strict.csv.gz` are
transformed/derived artifacts from public DESI DR1 data and should be treated
as DESI-derived data products under those DESI terms.

Transformations applied by this repository include:

- applying the published DESI DR1 backup-program velocity correction to
  `MAIN/BACKUP` rows;
- applying published program-level uncertainty floors inherited from
  `desi-rv-audit`;
- applying source-disjoint diagnostic `PROGRAM:NIGHT` offsets from
  `desi-rv-audit`;
- rebuilding source-level constant-RV screening metrics;
- selecting deterministic cadence-matched inspection controls and an
  injection-recovery base-population epoch bundle.

Publications, reports, or derived works using these artifacts should cite the
DESI DR1 release paper, the DESI DR1 Stellar Catalogue paper, the Zenodo
backup-correction dataset, and this repository.

## Official DESI Acknowledgment

This research used data obtained with the Dark Energy Spectroscopic Instrument
(DESI). DESI construction and operations is managed by the Lawrence Berkeley
National Laboratory. This material is based upon work supported by the U.S.
Department of Energy, Office of Science, Office of High-Energy Physics, under
Contract No. DE–AC02–05CH11231, and by the National Energy Research Scientific
Computing Center, a DOE Office of Science User Facility under the same contract.

Additional support for DESI was provided by the U.S. National Science Foundation
(NSF), Division of Astronomical Sciences under Contract No. AST-0950945 to the
NSF’s National Optical-Infrared Astronomy Research Laboratory; the Science and
Technology Facilities Council of the United Kingdom; the Gordon and Betty Moore
Foundation; the Heising-Simons Foundation; the French Alternative Energies and
Atomic Energy Commission (CEA); the National Council of Humanities, Science and
Technology of Mexico (CONAHCYT); the Ministry of Science and Innovation of Spain
(MICINN), and by the DESI Member Institutions:
https://www.desi.lbl.gov/collaborating-institutions.

The DESI collaboration is honored to be permitted to conduct scientific research
on I’oligam Du’ag (Kitt Peak), a mountain with particular significance to the
Tohono O’odham Nation. Any opinions, findings, and conclusions or
recommendations expressed in this material are those of the author(s) and do not
necessarily reflect the views of the U.S. National Science Foundation, the U.S.
Department of Energy, or any of the listed funding agencies.
