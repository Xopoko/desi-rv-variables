from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _program_summary(high_amplitude: pd.DataFrame) -> pd.DataFrame:
    return (
        high_amplitude.groupby("PROGRAM", sort=True)
        .agg(
            N_DETECTED=("GROUP_ID", "nunique"),
            MEDIAN_MIN_SUPPORT_DELTA_RV_KMS=("MIN_SUPPORT_DELTA_RV_KMS", "median"),
            MAX_SUPPORT_DELTA_RV_KMS=("MAX_SUPPORT_DELTA_RV_KMS", "max"),
            MEDIAN_MIN_SUPPORT_PAIR_SIGMA=("MIN_SUPPORT_PAIR_SIGMA", "median"),
        )
        .reset_index()
    )


def _acceleration_gate_summary(sequences: pd.DataFrame) -> pd.DataFrame:
    gates = [
        ("slope_sigma", "SLOPE_SIGMA", lambda values: values >= 5.0),
        ("delta_chi2", "DELTA_CHI2", lambda values: values >= 25.0),
        ("end_to_end", "END_TO_END_KMS", lambda values: values >= 20.0),
        (
            "linear_reduced_chi2",
            "LINEAR_REDUCED_CHI2",
            lambda values: values <= 3.0,
        ),
        (
            "leave_one_night_out",
            "MIN_LOO_SLOPE_SIGMA",
            lambda values: values >= 3.0,
        ),
    ]
    rows: list[dict[str, object]] = []
    for gate, column, predicate in gates:
        values = pd.to_numeric(sequences[column], errors="coerce")
        rows.append(
            {
                "GATE": gate,
                "METRIC": column,
                "N_PASS": int(predicate(values).fillna(False).sum()),
                "MEDIAN": float(values.median()),
                "MAX": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def _external_context(eligible_crossmatch: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, mask in [
        ("DETECTED", eligible_crossmatch["IN_HIGH_AMPLITUDE"]),
        ("ELIGIBLE_NOT_DETECTED", ~eligible_crossmatch["IN_HIGH_AMPLITUDE"]),
    ]:
        cohort = eligible_crossmatch[mask].copy()
        matched = ~cohort["NO_DECLARED_CATALOGUE_MATCH"]
        rows.append(
            {
                "COHORT": label,
                "N_SOURCES": int(len(cohort)),
                "N_DECLARED_GAIA_OR_SPECDIS_MATCH": int(matched.sum()),
                "DECLARED_MATCH_FRACTION": float(matched.mean()),
            }
        )
    return pd.DataFrame(rows)


def _spectral_aggregate(
    source_results: pd.DataFrame, epoch_results: pd.DataFrame
) -> pd.DataFrame:
    metrics = [
        "CATALOG_SPECTRAL_RV_CORRELATION",
        "SPECTRAL_ON_CATALOG_SLOPE",
        "MEDIAN_ABS_RV_RESIDUAL_KMS",
        "MAX_ABS_RV_RESIDUAL_KMS",
        "CATALOG_RV_RANGE_KMS",
        "SPECTRAL_RV_RANGE_KMS",
    ]
    rows: list[dict[str, object]] = []
    for metric in metrics:
        values = pd.to_numeric(source_results[metric], errors="coerce")
        rows.append(
            {
                "METRIC": metric,
                "MIN": float(values.min()),
                "MEDIAN": float(values.median()),
                "MAX": float(values.max()),
            }
        )
    self_shift = pd.to_numeric(
        epoch_results["SELF_MODEL_SHIFT_KMS"], errors="coerce"
    ).abs()
    rows.append(
        {
            "METRIC": "ABS_SELF_MODEL_SHIFT_KMS",
            "MIN": float(self_shift.min()),
            "MEDIAN": float(self_shift.median()),
            "MAX": float(self_shift.max()),
        }
    )
    return pd.DataFrame(rows)


def _write_private_followup_dossier(
    path: Path,
    metal_external: pd.DataFrame,
    spectral_sources: pd.DataFrame,
    spectral_epochs: pd.DataFrame,
) -> None:
    selected = metal_external[
        metal_external["NO_EXTENDED_CATALOGUE_MATCH"].fillna(False)
    ].merge(
        spectral_sources,
        on=["GROUP_ID", "SOURCE_ID"],
        how="inner",
        validate="one_to_one",
    )
    selected = selected.sort_values(
        ["CATALOG_SPECTRAL_RV_CORRELATION", "MEDIAN_FEH_EPOCH"],
        ascending=[False, True],
        kind="mergesort",
    )
    lines = [
        "# Private Metal-poor RV Follow-up Dossiers",
        "",
        "These identifiers are exploratory follow-up targets, not claimed discoveries.",
        "External non-matches apply only to the versioned catalogues and rules in the protocol.",
        "",
    ]
    for rank, source in enumerate(selected.itertuples(index=False), start=1):
        epochs = spectral_epochs[
            spectral_epochs["GROUP_ID"] == int(source.GROUP_ID)
        ].sort_values(["MJD", "EXPID"], kind="mergesort")
        targetids = sorted(set(epochs["TARGETID"].astype("int64")))
        lines.extend(
            [
                f"## Follow-up {rank}: Gaia DR3 {int(source.SOURCE_ID)}",
                "",
                f"- Coordinates: RA {float(source.TARGET_RA):.8f}, Dec {float(source.TARGET_DEC):.8f} deg.",
                f"- Median epoch [Fe/H]: {float(source.MEDIAN_FEH_EPOCH):.3f}; robust width {float(source.ROBUST_FEH_WIDTH):.3f} dex.",
                f"- Epochs: {int(source.N_SPECTRAL_EPOCHS)}; catalogue RV range {float(source.CATALOG_RV_RANGE_KMS):.3f} km/s.",
                f"- Flux-level RV correlation: {float(source.CATALOG_SPECTRAL_RV_CORRELATION):.6f}; slope {float(source.SPECTRAL_ON_CATALOG_SLOPE):.4f}.",
                f"- Median/max absolute flux-level residual: {float(source.MEDIAN_ABS_RV_RESIDUAL_KMS):.3f}/{float(source.MAX_ABS_RV_RESIDUAL_KMS):.3f} km/s.",
                f"- SpecDis binary probability: {float(source.SPECDIS_BINARY_POSSIBILITY_MAX):.6f}; binary flag: {bool(source.SPECDIS_BINARY_CANDIDATE)}.",
                "- DESI spectrum viewer: "
                + ", ".join(
                    f"https://www.legacysurvey.org/viewer/desi-spectrum/dr1/targetid{targetid}"
                    for targetid in targetids
                ),
                "",
                "| Night | EXPID | Catalogue relative RV | Flux-fit relative RV | Residual |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for epoch in epochs.itertuples(index=False):
            lines.append(
                f"| {int(epoch.NIGHT)} | {int(epoch.EXPID)} | "
                f"{float(epoch.CATALOG_RELATIVE_RV_KMS):.3f} | "
                f"{float(epoch.SPECTRAL_RELATIVE_RV_KMS):.3f} | "
                f"{float(epoch.CATALOG_MINUS_SPECTRAL_KMS):.3f} |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def publish_experiment_report(
    experiment_dir: str | Path,
    report_dir: str | Path,
) -> dict[str, object]:
    experiment_dir = Path(experiment_dir)
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    experiment_manifest_path = experiment_dir / "experiment_manifest.json"
    catalogue_manifest_path = experiment_dir / "catalogue_crossmatch_manifest.json"
    spectral_manifest_path = experiment_dir / "spectral_validation_manifest.json"
    experiment_manifest = json.loads(
        experiment_manifest_path.read_text(encoding="utf-8")
    )
    catalogue_manifest = json.loads(catalogue_manifest_path.read_text(encoding="utf-8"))
    spectral_manifest = json.loads(spectral_manifest_path.read_text(encoding="utf-8"))

    high_amplitude = pd.read_parquet(
        experiment_dir / "high_amplitude_candidates.parquet"
    )
    sequences = pd.read_parquet(experiment_dir / "acceleration_sequences.parquet")
    acceleration_null = pd.read_csv(
        experiment_dir / "acceleration_time_permutation_null.csv"
    )
    eligible_crossmatch = pd.read_parquet(
        experiment_dir / "high_amplitude_eligible_external_crossmatch.parquet"
    )
    metal_external = pd.read_parquet(
        experiment_dir / "metal_poor_external_screen.parquet"
    )
    spectral_sources = pd.read_parquet(
        experiment_dir / "spectral_source_validation.parquet"
    )
    spectral_epochs = pd.read_parquet(
        experiment_dir / "spectral_epoch_validation.parquet"
    )
    private_dossier_path = experiment_dir / "followup_dossiers.md"
    _write_private_followup_dossier(
        private_dossier_path,
        metal_external,
        spectral_sources,
        spectral_epochs,
    )

    program_summary = _program_summary(high_amplitude)
    acceleration_gates = _acceleration_gate_summary(sequences)
    external_context = _external_context(eligible_crossmatch)
    spectral_aggregate = _spectral_aggregate(spectral_sources, spectral_epochs)
    output_tables = {
        "program_summary": report_dir / "exploratory_high_amplitude_by_program.csv",
        "acceleration_gates": report_dir / "exploratory_acceleration_gate_summary.csv",
        "external_context": report_dir / "exploratory_external_match_context.csv",
        "spectral_aggregate": report_dir
        / "exploratory_spectral_validation_summary.csv",
    }
    program_summary.to_csv(output_tables["program_summary"], index=False)
    acceleration_gates.to_csv(output_tables["acceleration_gates"], index=False)
    external_context.to_csv(output_tables["external_context"], index=False)
    spectral_aggregate.to_csv(output_tables["spectral_aggregate"], index=False)

    counts = experiment_manifest["counts"]
    crossmatch_counts = catalogue_manifest["counts"]
    external_validation = catalogue_manifest["high_amplitude_external_validation"]
    n_eligible = int(counts["high_amplitude_eligible_sources"])
    n_detected = int(counts["high_amplitude_detected_sources"])
    detected_fraction = n_detected / n_eligible
    detected_match = float(
        crossmatch_counts["high_amplitude_detected_known_catalogue_match_fraction"]
    )
    nondetected_match = float(
        crossmatch_counts["high_amplitude_nondetected_known_catalogue_match_fraction"]
    )
    metal_unmatched = metal_external[
        metal_external["NO_EXTENDED_CATALOGUE_MATCH"].fillna(False)
    ]
    high_probability_unflagged = int(
        (
            metal_unmatched["SPECDIS_MATCHED"].fillna(False)
            & ~metal_unmatched["SPECDIS_BINARY_CANDIDATE"].fillna(False)
            & (
                pd.to_numeric(
                    metal_unmatched["SPECDIS_BINARY_POSSIBILITY_MAX"], errors="coerce"
                )
                >= 0.8
            )
        ).sum()
    )
    n_spectral_consistent = int(spectral_sources["FLUX_LEVEL_CONSISTENT"].sum())
    median_spectral_correlation = float(
        spectral_sources["CATALOG_SPECTRAL_RV_CORRELATION"].median()
    )
    median_spectral_residual = float(
        spectral_sources["MEDIAN_ABS_RV_RESIDUAL_KMS"].median()
    )
    absolute_self_shift = pd.to_numeric(
        spectral_epochs["SELF_MODEL_SHIFT_KMS"], errors="coerce"
    ).abs()

    report = f"""# Exploratory DESI DR1 RV Follow-up Experiments

This report records three threshold-frozen exploratory tests on the public DESI
DR1 MAIN single-epoch radial-velocity sample. It is an independent analysis,
not an official DESI data product or a variable-star catalogue. Source-level
tables remain private pending independent spectroscopy and expert review.

## Result 1: repeated high-amplitude variability

The frozen same-program, inter-night, two-disjoint-pair rule detected
**{n_detected:,} of {n_eligible:,} eligible sources ({detected_fraction:.1%})**.
The support threshold requires two disjoint epoch pairs, each with at least
30 km/s absolute change and 8-sigma uncertainty-aware significance.

| Program | Detected | Median minimum support delta RV | Maximum support delta RV |
| --- | ---: | ---: | ---: |
"""
    for row in program_summary.itertuples(index=False):
        report += (
            f"| `{row.PROGRAM}` | {int(row.N_DETECTED):,} | "
            f"{row.MEDIAN_MIN_SUPPORT_DELTA_RV_KMS:.3f} km/s | "
            f"{row.MAX_SUPPORT_DELTA_RV_KMS:.3f} km/s |\n"
        )
    report += f"""

As a post-selection positive control, a declared Gaia DR3 NSS/variability or
SpecDis binary match occurs for **{detected_match:.1%}** of detections versus
**{nondetected_match:.1%}** of eligible non-detections. The descriptive Fisher
exact odds ratio is **{external_validation['descriptive_fisher_exact_odds_ratio']:.3f}**
(`p={external_validation['descriptive_fisher_exact_pvalue']:.3g}`). This supports
catalogue enrichment but is not a discovery significance or purity estimate.

## Result 2: secular acceleration

**No sequence passed all frozen acceleration gates** among
{int(counts['acceleration_eligible_sequences']):,} eligible source-program
sequences. None of the {len(acceleration_null):,} within-source time
permutations produced a detection either; because the observed count is zero,
that control adds no positive evidence. Large raw slope significances existed, but the
candidate sequences failed the linear reduced-chi-square or leave-one-night-out
requirements; the null result was retained without relaxing thresholds.

## Result 3: metal-poor external-novelty screen

The high-amplitude detections contained **{int(counts['metal_poor_candidates']):,}**
sources satisfying the frozen epoch-level metallicity-consistency rule. Two are
matched to known variable-star classifications. Four have no match under the
declared Gaia DR3, SpecDis flag, exact Gaia-ID SIMBAD, and 2-arcsec VSX rules.
One of those four nevertheless has a high but unflagged SpecDis binary
probability (`>=0.8`; count={high_probability_unflagged}), so absence of a flag
is not evidence of novelty.

The post-selection flux-level check downloaded all three DESI cframe arms for
every selected same-program epoch and fit their relative line shifts against a
common RVSpecFit model shape. **{n_spectral_consistent} of {len(spectral_sources)}** externally
unmatched metal-poor targets passed the pre-recorded consistency checks. Across
the four targets, the median catalogue-versus-flux relative-RV correlation is
**{median_spectral_correlation:.3f}** and the median per-source median absolute
residual is **{median_spectral_residual:.3f} km/s**.
Across the {len(spectral_epochs)} checked epochs, the median and maximum
absolute shift recovered against each epoch's own RVMOD model are
**{absolute_self_shift.median():.3f}** and **{absolute_self_shift.max():.3f} km/s**,
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
  `{catalogue_manifest['specdis']['sha256']}`.

## Primary references

- DESI DR1 MWS stellar catalogue: https://doi.org/10.33232/001c.155260
- Official DESI DR1 MWS VAC: https://data.desi.lbl.gov/doc/releases/dr1/vac/mws/
- Gaia DR3 archive data model: https://gea.esac.esa.int/archive/documentation/GDR3/
- DESI SpecDis v2.1 data model: https://data.desi.lbl.gov/doc/releases/dr1/vac/mws-specdis/
- Official DESI data access: https://data.desi.lbl.gov/doc/access/
"""
    report_path = report_dir / "exploratory_experiments_summary.md"
    report_path.write_text(report, encoding="utf-8")

    project_root = Path(__file__).resolve().parents[2]
    source_files = [
        project_root / "research" / "exploratory_experiments_protocol.md",
        project_root / "research" / "amendments.md",
        project_root / "src" / "desi_rv_variables" / "experiments.py",
        project_root / "src" / "desi_rv_variables" / "catalogues.py",
        project_root / "src" / "desi_rv_variables" / "spectral_validation.py",
        project_root / "src" / "desi_rv_variables" / "exploratory_reporting.py",
        project_root / "src" / "desi_rv_variables" / "provenance.py",
    ]
    public_manifest: dict[str, object] = {
        "status": "exploratory; no object-level discovery claim",
        "protocol": "research/exploratory_experiments_protocol.md",
        "aggregate_results": {
            "high_amplitude_eligible_sources": n_eligible,
            "high_amplitude_detected_sources": n_detected,
            "high_amplitude_detected_fraction": detected_fraction,
            "acceleration_eligible_sequences": int(
                counts["acceleration_eligible_sequences"]
            ),
            "acceleration_detected_sources": int(
                counts["acceleration_detected_sources"]
            ),
            "metal_poor_screen_sources": int(counts["metal_poor_candidates"]),
            "metal_poor_no_extended_catalogue_match": int(
                crossmatch_counts["metal_poor_no_extended_catalogue_match"]
            ),
            "flux_level_checked_sources": int(len(spectral_sources)),
            "flux_level_checked_epochs": int(len(spectral_epochs)),
            "flux_level_consistent_sources": n_spectral_consistent,
        },
        "frozen_experiment_inputs": experiment_manifest["inputs"],
        "frozen_experiment_thresholds": experiment_manifest["thresholds"],
        "frozen_experiment_parameters": experiment_manifest["parameters"],
        "runtime_environments": {
            "experiments": experiment_manifest["runtime_environment"],
            "catalogue_crossmatch": catalogue_manifest["runtime_environment"],
            "spectral_validation": spectral_manifest["runtime_environment"],
        },
        "external_catalogue_provenance": {
            "query_timestamp_utc": catalogue_manifest["query_timestamp_utc"],
            "specdis": catalogue_manifest["specdis"],
            "gaia": catalogue_manifest["gaia"],
            "secondary_catalogues": catalogue_manifest["secondary_catalogues"],
        },
        "private_manifest_hashes": {
            "experiment_manifest": _sha256(experiment_manifest_path),
            "catalogue_crossmatch_manifest": _sha256(catalogue_manifest_path),
            "spectral_validation_manifest": _sha256(spectral_manifest_path),
        },
        "analysis_source_hashes": {
            str(path.relative_to(project_root)): _sha256(path) for path in source_files
        },
        "aggregate_outputs": {
            report_path.name: _sha256(report_path),
            **{path.name: _sha256(path) for path in output_tables.values()},
        },
        "source_level_outputs_published": False,
        "private_followup_dossier": private_dossier_path.name,
        "spectral_validation": spectral_manifest["counts"],
        "spectral_validation_settings": spectral_manifest["settings"],
        "spectral_input_digests": {
            "cframe_set_sha256": spectral_manifest["cframe_set_sha256"],
            "rvspec_model_subset_sha256": spectral_manifest[
                "rvspec_model_subset_sha256"
            ],
        },
    }
    manifest_path = report_dir / "exploratory_experiments_manifest.json"
    manifest_path.write_text(
        json.dumps(public_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return public_manifest
