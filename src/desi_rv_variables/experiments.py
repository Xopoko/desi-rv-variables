from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .provenance import runtime_environment


HIGH_AMPLITUDE_COLUMNS = [
    "GROUP_ID",
    "SOURCE_ID",
    "GROUP_KIND",
    "PROGRAM",
    "N_PROGRAM_EPOCHS",
    "N_PROGRAM_NIGHTS",
    "PROGRAM_BASELINE_DAYS",
    "N_THRESHOLD_PAIRS",
    "MIN_SUPPORT_DELTA_RV_KMS",
    "MAX_SUPPORT_DELTA_RV_KMS",
    "MIN_SUPPORT_PAIR_SIGMA",
    "MAX_SUPPORT_PAIR_SIGMA",
    "SUPPORT_NIGHTS",
    "MEDIAN_FEH",
    "MEDIAN_TEFF",
    "MEDIAN_LOGG",
    "OOF_OUTLIER_BOOTSTRAP_FRACTION",
    "LOO_OUTLIER_FRACTION",
]

METAL_POOR_COLUMNS = [
    "GROUP_ID",
    "SOURCE_ID",
    "IN_HIGH_AMPLITUDE",
    "IN_ACCELERATION",
    "N_FINITE_FEH_EPOCHS",
    "MEDIAN_FEH_EPOCH",
    "ROBUST_FEH_WIDTH",
    "MEDIAN_TEFF_EPOCH",
    "MEDIAN_LOGG",
    "TARGET_RA",
    "TARGET_DEC",
]

ACCELERATION_COLUMNS = [
    "GROUP_ID",
    "SOURCE_ID",
    "GROUP_KIND",
    "PROGRAM",
    "N_EPOCHS",
    "N_NIGHTS",
    "BASELINE_DAYS",
    "SLOPE_KMS_PER_YEAR",
    "SLOPE_ERROR_KMS_PER_YEAR",
    "SLOPE_SIGMA",
    "DELTA_CHI2",
    "LINEAR_REDUCED_CHI2",
    "END_TO_END_KMS",
    "LOO_SAME_SIGN",
    "MIN_LOO_SLOPE_SIGMA",
    "DETECTED",
    "MEDIAN_FEH",
    "MEDIAN_TEFF",
    "MEDIAN_LOGG",
]


@dataclass(frozen=True)
class ExperimentThresholds:
    high_amplitude_min_epochs: int = 4
    high_amplitude_min_nights: int = 3
    high_amplitude_min_baseline_days: float = 30.0
    high_amplitude_min_delta_kms: float = 30.0
    high_amplitude_min_pair_sigma: float = 8.0
    acceleration_min_epochs: int = 4
    acceleration_min_nights: int = 4
    acceleration_min_baseline_days: float = 180.0
    acceleration_min_slope_sigma: float = 5.0
    acceleration_min_delta_chi2: float = 25.0
    acceleration_min_end_to_end_kms: float = 20.0
    acceleration_max_reduced_chi2: float = 3.0
    acceleration_loo_min_slope_sigma: float = 3.0
    metal_poor_max_median_feh: float = -2.0
    metal_poor_max_robust_feh_width: float = 0.30
    metal_poor_min_finite_feh_epochs: int = 3
    metal_poor_min_teff: float = 4000.0
    metal_poor_max_teff: float = 7000.0


@dataclass(frozen=True)
class ExperimentResult:
    high_amplitude_eligible: pd.DataFrame
    high_amplitude: pd.DataFrame
    acceleration_sequences: pd.DataFrame
    acceleration_candidates: pd.DataFrame
    acceleration_null: pd.DataFrame
    metal_poor_candidates: pd.DataFrame
    manifest: dict[str, object]


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_eligibility(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()
    result["GROUP_ID"] = pd.to_numeric(result["GROUP_ID"], errors="raise").astype(
        "int64"
    )
    result["PRIMARY_COHORT"] = result["PRIMARY_COHORT"].fillna(False).astype(bool)
    result["WAS_STRICT_SCREENING_CANDIDATE"] = (
        result["WAS_STRICT_SCREENING_CANDIDATE"].fillna(False).astype(bool)
    )
    return result


def attach_offset_uncertainty(
    epoch_table: pd.DataFrame,
    offset_uncertainty: pd.DataFrame,
) -> pd.DataFrame:
    required_epoch = {
        "GROUP_ID",
        "PROGRAM_NIGHT_FOLD",
        "PROGRAM_NIGHT_LABEL",
        "VRAD_ERROR_CALIBRATED",
    }
    required_offsets = {"FOLD", "LABEL", "OFFSET_STD_KMS", "N_BOOTSTRAPS"}
    missing_epoch = required_epoch.difference(epoch_table.columns)
    missing_offsets = required_offsets.difference(offset_uncertainty.columns)
    if missing_epoch:
        raise ValueError(f"epoch table missing columns: {sorted(missing_epoch)}")
    if missing_offsets:
        raise ValueError(
            f"offset uncertainty table missing columns: {sorted(missing_offsets)}"
        )

    offsets = offset_uncertainty[
        ["FOLD", "LABEL", "OFFSET_STD_KMS", "N_BOOTSTRAPS"]
    ].copy()
    offsets["FOLD"] = pd.to_numeric(offsets["FOLD"], errors="raise").astype("int64")
    offsets["LABEL"] = offsets["LABEL"].astype("string")
    if offsets.duplicated(["FOLD", "LABEL"]).any():
        raise ValueError("offset uncertainty table has duplicate FOLD/LABEL rows")
    offsets = offsets.rename(
        columns={
            "FOLD": "PROGRAM_NIGHT_FOLD",
            "LABEL": "PROGRAM_NIGHT_LABEL",
            "N_BOOTSTRAPS": "OFFSET_N_BOOTSTRAPS",
        }
    )

    result = epoch_table.copy()
    result["GROUP_ID"] = pd.to_numeric(result["GROUP_ID"], errors="raise").astype(
        "int64"
    )
    result["PROGRAM_NIGHT_FOLD"] = pd.to_numeric(
        result["PROGRAM_NIGHT_FOLD"], errors="coerce"
    ).astype("Int64")
    result["PROGRAM_NIGHT_LABEL"] = result["PROGRAM_NIGHT_LABEL"].astype("string")
    result = result.merge(
        offsets,
        on=["PROGRAM_NIGHT_FOLD", "PROGRAM_NIGHT_LABEL"],
        how="left",
        validate="many_to_one",
    )
    calibrated = pd.to_numeric(result["VRAD_ERROR_CALIBRATED"], errors="coerce")
    offset_std = pd.to_numeric(result["OFFSET_STD_KMS"], errors="coerce")
    result["TOTAL_EPOCH_ERROR_KMS"] = np.hypot(calibrated, offset_std)
    return result


def _eligible_epoch_rows(
    epoch_table: pd.DataFrame, source_ids: set[int]
) -> pd.DataFrame:
    if not source_ids:
        return epoch_table.iloc[0:0].copy()
    return epoch_table[
        epoch_table["GROUP_ID"].astype("int64").isin(source_ids)
        & epoch_table["GOOD_EPOCH"].fillna(False).astype(bool)
        & epoch_table["OOF_OFFSET_AVAILABLE"].fillna(False).astype(bool)
    ].copy()


def _pair_records(
    group: pd.DataFrame, thresholds: ExperimentThresholds
) -> list[dict[str, object]]:
    group = group.sort_values(["MJD", "EXPID", "FIBER"], kind="mergesort").reset_index(
        drop=True
    )
    values = pd.to_numeric(group["VRAD_CORRECTED_OOF"], errors="coerce").to_numpy(float)
    errors = pd.to_numeric(group["VRAD_ERROR_CALIBRATED"], errors="coerce").to_numpy(
        float
    )
    offset_std = pd.to_numeric(group["OFFSET_STD_KMS"], errors="coerce").to_numpy(float)
    labels = group["PROGRAM_NIGHT_LABEL"].astype("string").to_numpy()
    nights = group["NIGHT"].astype("string").to_numpy()
    mjd = pd.to_numeric(group["MJD"], errors="coerce").to_numpy(float)
    records: list[dict[str, object]] = []
    for first in range(len(group) - 1):
        for second in range(first + 1, len(group)):
            if nights[first] == nights[second]:
                continue
            if not (
                np.isfinite(values[first])
                and np.isfinite(values[second])
                and np.isfinite(errors[first])
                and np.isfinite(errors[second])
                and errors[first] > 0
                and errors[second] > 0
            ):
                continue
            offset_variance = 0.0
            if labels[first] != labels[second]:
                if not (
                    np.isfinite(offset_std[first]) and np.isfinite(offset_std[second])
                ):
                    continue
                offset_variance = offset_std[first] ** 2 + offset_std[second] ** 2
            denominator = float(
                np.sqrt(errors[first] ** 2 + errors[second] ** 2 + offset_variance)
            )
            delta = float(abs(values[first] - values[second]))
            sigma = delta / denominator
            if (
                delta >= thresholds.high_amplitude_min_delta_kms
                and sigma >= thresholds.high_amplitude_min_pair_sigma
            ):
                records.append(
                    {
                        "FIRST": first,
                        "SECOND": second,
                        "NIGHT_FIRST": str(nights[first]),
                        "NIGHT_SECOND": str(nights[second]),
                        "MJD_FIRST": float(mjd[first]),
                        "MJD_SECOND": float(mjd[second]),
                        "ABSMAX_DELTA_RV_KMS": delta,
                        "PAIR_SIGMA": sigma,
                    }
                )
    return records


def _best_disjoint_pair_support(
    edges: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]] | None:
    best: (
        tuple[tuple[float, float, float, float], dict[str, object], dict[str, object]]
        | None
    ) = None
    for first_edge, second_edge in itertools.combinations(edges, 2):
        indices = {
            int(first_edge["FIRST"]),
            int(first_edge["SECOND"]),
            int(second_edge["FIRST"]),
            int(second_edge["SECOND"]),
        }
        if len(indices) != 4:
            continue
        nights = {
            str(first_edge["NIGHT_FIRST"]),
            str(first_edge["NIGHT_SECOND"]),
            str(second_edge["NIGHT_FIRST"]),
            str(second_edge["NIGHT_SECOND"]),
        }
        if len(nights) < 3:
            continue
        score = (
            min(float(first_edge["PAIR_SIGMA"]), float(second_edge["PAIR_SIGMA"])),
            min(
                float(first_edge["ABSMAX_DELTA_RV_KMS"]),
                float(second_edge["ABSMAX_DELTA_RV_KMS"]),
            ),
            float(first_edge["PAIR_SIGMA"]) + float(second_edge["PAIR_SIGMA"]),
            float(first_edge["ABSMAX_DELTA_RV_KMS"])
            + float(second_edge["ABSMAX_DELTA_RV_KMS"]),
        )
        if best is None or score > best[0]:
            best = (score, first_edge, second_edge)
    if best is None:
        return None
    return best[1], best[2]


def repeated_high_amplitude_experiment(
    source_summary: pd.DataFrame,
    epoch_table: pd.DataFrame,
    thresholds: ExperimentThresholds = ExperimentThresholds(),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = _source_eligibility(source_summary)
    eligible = summary[
        summary["PRIMARY_COHORT"]
        & summary["WAS_STRICT_SCREENING_CANDIDATE"]
        & (
            pd.to_numeric(summary["N_EPOCHS_GOOD_OOF"], errors="coerce")
            >= thresholds.high_amplitude_min_epochs
        )
        & (
            pd.to_numeric(summary["N_NIGHTS_GOOD_OOF"], errors="coerce")
            >= thresholds.high_amplitude_min_nights
        )
        & (
            pd.to_numeric(summary["TIME_BASELINE_DAYS_OOF"], errors="coerce")
            >= thresholds.high_amplitude_min_baseline_days
        )
        & summary["BOOTSTRAP_ROBUST_95"].astype("boolean").fillna(False)
        & summary["LOO_ALL_OUTLIER"].astype("boolean").fillna(False)
        & ~summary["SIGNAL_ONLY_CROSS_PROGRAM"].astype("boolean").fillna(True)
    ].copy()
    eligible_ids = set(eligible["GROUP_ID"].astype("int64"))
    epochs = _eligible_epoch_rows(epoch_table, eligible_ids)
    metadata = eligible.set_index("GROUP_ID", drop=False)
    detections: list[dict[str, object]] = []
    for group_id, source_group in epochs.groupby("GROUP_ID", sort=True):
        source_best: dict[str, object] | None = None
        for program, program_group in source_group.groupby(
            source_group["PROGRAM"].astype("string").str.upper(), sort=True
        ):
            if len(program_group) < thresholds.high_amplitude_min_epochs:
                continue
            if (
                program_group["NIGHT"].astype("string").nunique()
                < thresholds.high_amplitude_min_nights
            ):
                continue
            edges = _pair_records(program_group, thresholds)
            support = _best_disjoint_pair_support(edges)
            if support is None:
                continue
            first_edge, second_edge = support
            row = {
                "GROUP_ID": int(group_id),
                "SOURCE_ID": metadata.at[int(group_id), "SOURCE_ID"],
                "GROUP_KIND": metadata.at[int(group_id), "GROUP_KIND"],
                "PROGRAM": str(program),
                "N_PROGRAM_EPOCHS": int(len(program_group)),
                "N_PROGRAM_NIGHTS": int(
                    program_group["NIGHT"].astype("string").nunique()
                ),
                "PROGRAM_BASELINE_DAYS": float(
                    pd.to_numeric(program_group["MJD"], errors="coerce").max()
                    - pd.to_numeric(program_group["MJD"], errors="coerce").min()
                ),
                "N_THRESHOLD_PAIRS": int(len(edges)),
                "MIN_SUPPORT_DELTA_RV_KMS": min(
                    float(first_edge["ABSMAX_DELTA_RV_KMS"]),
                    float(second_edge["ABSMAX_DELTA_RV_KMS"]),
                ),
                "MAX_SUPPORT_DELTA_RV_KMS": max(
                    float(first_edge["ABSMAX_DELTA_RV_KMS"]),
                    float(second_edge["ABSMAX_DELTA_RV_KMS"]),
                ),
                "MIN_SUPPORT_PAIR_SIGMA": min(
                    float(first_edge["PAIR_SIGMA"]), float(second_edge["PAIR_SIGMA"])
                ),
                "MAX_SUPPORT_PAIR_SIGMA": max(
                    float(first_edge["PAIR_SIGMA"]), float(second_edge["PAIR_SIGMA"])
                ),
                "SUPPORT_NIGHTS": ";".join(
                    sorted(
                        {
                            str(first_edge["NIGHT_FIRST"]),
                            str(first_edge["NIGHT_SECOND"]),
                            str(second_edge["NIGHT_FIRST"]),
                            str(second_edge["NIGHT_SECOND"]),
                        }
                    )
                ),
                "MEDIAN_FEH": metadata.at[int(group_id), "MEDIAN_FEH"],
                "MEDIAN_TEFF": metadata.at[int(group_id), "MEDIAN_TEFF"],
                "MEDIAN_LOGG": metadata.at[int(group_id), "MEDIAN_LOGG"],
                "OOF_OUTLIER_BOOTSTRAP_FRACTION": metadata.at[
                    int(group_id), "OOF_OUTLIER_BOOTSTRAP_FRACTION"
                ],
                "LOO_OUTLIER_FRACTION": metadata.at[
                    int(group_id), "LOO_OUTLIER_FRACTION"
                ],
            }
            if source_best is None or (
                float(row["MIN_SUPPORT_PAIR_SIGMA"]),
                float(row["MIN_SUPPORT_DELTA_RV_KMS"]),
            ) > (
                float(source_best["MIN_SUPPORT_PAIR_SIGMA"]),
                float(source_best["MIN_SUPPORT_DELTA_RV_KMS"]),
            ):
                source_best = row
        if source_best is not None:
            detections.append(source_best)
    result = pd.DataFrame(detections, columns=HIGH_AMPLITUDE_COLUMNS)
    if not result.empty:
        result = result.sort_values(
            ["MIN_SUPPORT_PAIR_SIGMA", "MIN_SUPPORT_DELTA_RV_KMS", "GROUP_ID"],
            ascending=[False, False, True],
            kind="mergesort",
        ).reset_index(drop=True)
    eligible_result = eligible[["GROUP_ID", "SOURCE_ID", "GROUP_KIND"]].copy()
    detected_ids = set(result.get("GROUP_ID", pd.Series(dtype="int64")).astype("int64"))
    eligible_result["DETECTED_HIGH_AMPLITUDE"] = eligible_result["GROUP_ID"].isin(
        detected_ids
    )
    eligible_result = eligible_result.sort_values(
        "GROUP_ID", kind="mergesort"
    ).reset_index(drop=True)
    return result, eligible_result


def _nightly_means(program_group: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for night, group in program_group.groupby(
        program_group["NIGHT"].astype("string"), sort=True
    ):
        values = pd.to_numeric(group["VRAD_CORRECTED_OOF"], errors="coerce").to_numpy(
            float
        )
        errors = pd.to_numeric(
            group["VRAD_ERROR_CALIBRATED"], errors="coerce"
        ).to_numpy(float)
        mjd = pd.to_numeric(group["MJD"], errors="coerce").to_numpy(float)
        offset_std = pd.to_numeric(group["OFFSET_STD_KMS"], errors="coerce").to_numpy(
            float
        )
        valid = (
            np.isfinite(values)
            & np.isfinite(errors)
            & (errors > 0)
            & np.isfinite(mjd)
            & np.isfinite(offset_std)
        )
        if not np.any(valid):
            continue
        values = values[valid]
        errors = errors[valid]
        mjd = mjd[valid]
        offset_std = offset_std[valid]
        weights = 1.0 / np.square(errors)
        rows.append(
            {
                "NIGHT": str(night),
                "MJD": float(np.sum(weights * mjd) / np.sum(weights)),
                "VRAD": float(np.sum(weights * values) / np.sum(weights)),
                "ERROR": float(
                    np.hypot(np.sqrt(1.0 / np.sum(weights)), np.max(offset_std))
                ),
                "N_EPOCHS": int(valid.sum()),
            }
        )
    return (
        pd.DataFrame(rows).sort_values("MJD", kind="mergesort").reset_index(drop=True)
    )


def _linear_fit_metrics(
    times: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
) -> dict[str, float]:
    valid = (
        np.isfinite(times) & np.isfinite(values) & np.isfinite(errors) & (errors > 0)
    )
    times = np.asarray(times, dtype=float)[valid]
    values = np.asarray(values, dtype=float)[valid]
    errors = np.asarray(errors, dtype=float)[valid]
    if times.size < 3 or np.ptp(times) <= 0:
        return {
            "SLOPE_KMS_PER_DAY": np.nan,
            "SLOPE_ERROR_KMS_PER_DAY": np.nan,
            "SLOPE_SIGMA": np.nan,
            "DELTA_CHI2": np.nan,
            "LINEAR_REDUCED_CHI2": np.nan,
            "END_TO_END_KMS": np.nan,
        }
    weights = 1.0 / np.square(errors)
    center = float(np.sum(weights * times) / np.sum(weights))
    x = times - center
    design = np.column_stack([np.ones_like(x), x])
    normal = design.T @ (weights[:, None] * design)
    try:
        covariance = np.linalg.inv(normal)
    except np.linalg.LinAlgError:
        return {
            "SLOPE_KMS_PER_DAY": np.nan,
            "SLOPE_ERROR_KMS_PER_DAY": np.nan,
            "SLOPE_SIGMA": np.nan,
            "DELTA_CHI2": np.nan,
            "LINEAR_REDUCED_CHI2": np.nan,
            "END_TO_END_KMS": np.nan,
        }
    beta = covariance @ (design.T @ (weights * values))
    prediction = design @ beta
    linear_chi2 = float(np.sum(weights * np.square(values - prediction)))
    constant = float(np.sum(weights * values) / np.sum(weights))
    constant_chi2 = float(np.sum(weights * np.square(values - constant)))
    slope = float(beta[1])
    slope_error = float(np.sqrt(max(covariance[1, 1], 0.0)))
    slope_sigma = abs(slope) / slope_error if slope_error > 0 else np.nan
    return {
        "SLOPE_KMS_PER_DAY": slope,
        "SLOPE_ERROR_KMS_PER_DAY": slope_error,
        "SLOPE_SIGMA": float(slope_sigma),
        "DELTA_CHI2": max(0.0, constant_chi2 - linear_chi2),
        "LINEAR_REDUCED_CHI2": linear_chi2 / max(times.size - 2, 1),
        "END_TO_END_KMS": abs(slope) * float(np.ptp(times)),
    }


def _acceleration_detection(
    times: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    thresholds: ExperimentThresholds,
) -> tuple[dict[str, float | bool], bool]:
    metrics: dict[str, float | bool] = _linear_fit_metrics(times, values, errors)
    slope = float(metrics["SLOPE_KMS_PER_DAY"])
    loo_sigmas: list[float] = []
    loo_slopes: list[float] = []
    for removed in range(len(times)):
        keep = np.arange(len(times)) != removed
        loo = _linear_fit_metrics(times[keep], values[keep], errors[keep])
        loo_slopes.append(float(loo["SLOPE_KMS_PER_DAY"]))
        loo_sigmas.append(float(loo["SLOPE_SIGMA"]))
    same_sign = bool(
        np.isfinite(slope)
        and slope != 0
        and loo_slopes
        and all(
            np.isfinite(item) and np.sign(item) == np.sign(slope) for item in loo_slopes
        )
    )
    min_loo_sigma = float(np.min(loo_sigmas)) if loo_sigmas else np.nan
    metrics["LOO_SAME_SIGN"] = same_sign
    metrics["MIN_LOO_SLOPE_SIGMA"] = min_loo_sigma
    detected = bool(
        float(metrics["SLOPE_SIGMA"]) >= thresholds.acceleration_min_slope_sigma
        and float(metrics["DELTA_CHI2"]) >= thresholds.acceleration_min_delta_chi2
        and float(metrics["END_TO_END_KMS"])
        >= thresholds.acceleration_min_end_to_end_kms
        and float(metrics["LINEAR_REDUCED_CHI2"])
        <= thresholds.acceleration_max_reduced_chi2
        and same_sign
        and min_loo_sigma >= thresholds.acceleration_loo_min_slope_sigma
    )
    metrics["DETECTED"] = detected
    return metrics, detected


def acceleration_experiment(
    source_summary: pd.DataFrame,
    epoch_table: pd.DataFrame,
    thresholds: ExperimentThresholds = ExperimentThresholds(),
    n_permutations: int = 200,
    seed: int = 20260714,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    summary = _source_eligibility(source_summary)
    eligible_sources = summary[
        summary["PRIMARY_COHORT"] & summary["WAS_STRICT_SCREENING_CANDIDATE"]
    ].copy()
    eligible_ids = set(eligible_sources["GROUP_ID"].astype("int64"))
    epochs = _eligible_epoch_rows(epoch_table, eligible_ids)
    metadata = eligible_sources.set_index("GROUP_ID", drop=False)
    sequence_rows: list[dict[str, object]] = []
    sequence_arrays: list[tuple[int, str, np.ndarray, np.ndarray, np.ndarray]] = []
    for (group_id, program), program_group in epochs.groupby(
        ["GROUP_ID", epochs["PROGRAM"].astype("string").str.upper()], sort=True
    ):
        if len(program_group) < thresholds.acceleration_min_epochs:
            continue
        nightly = _nightly_means(program_group)
        if len(nightly) < thresholds.acceleration_min_nights:
            continue
        times = nightly["MJD"].to_numpy(float)
        if np.ptp(times) < thresholds.acceleration_min_baseline_days:
            continue
        values = nightly["VRAD"].to_numpy(float)
        errors = nightly["ERROR"].to_numpy(float)
        metrics, detected = _acceleration_detection(times, values, errors, thresholds)
        row = {
            "GROUP_ID": int(group_id),
            "SOURCE_ID": metadata.at[int(group_id), "SOURCE_ID"],
            "GROUP_KIND": metadata.at[int(group_id), "GROUP_KIND"],
            "PROGRAM": str(program),
            "N_EPOCHS": int(len(program_group)),
            "N_NIGHTS": int(len(nightly)),
            "BASELINE_DAYS": float(np.ptp(times)),
            "SLOPE_KMS_PER_YEAR": float(metrics["SLOPE_KMS_PER_DAY"]) * 365.25,
            "SLOPE_ERROR_KMS_PER_YEAR": float(metrics["SLOPE_ERROR_KMS_PER_DAY"])
            * 365.25,
            "SLOPE_SIGMA": metrics["SLOPE_SIGMA"],
            "DELTA_CHI2": metrics["DELTA_CHI2"],
            "LINEAR_REDUCED_CHI2": metrics["LINEAR_REDUCED_CHI2"],
            "END_TO_END_KMS": metrics["END_TO_END_KMS"],
            "LOO_SAME_SIGN": metrics["LOO_SAME_SIGN"],
            "MIN_LOO_SLOPE_SIGMA": metrics["MIN_LOO_SLOPE_SIGMA"],
            "DETECTED": detected,
            "MEDIAN_FEH": metadata.at[int(group_id), "MEDIAN_FEH"],
            "MEDIAN_TEFF": metadata.at[int(group_id), "MEDIAN_TEFF"],
            "MEDIAN_LOGG": metadata.at[int(group_id), "MEDIAN_LOGG"],
        }
        sequence_rows.append(row)
        sequence_arrays.append((int(group_id), str(program), times, values, errors))

    sequences = pd.DataFrame(sequence_rows, columns=ACCELERATION_COLUMNS)
    candidates = (
        sequences[sequences["DETECTED"]].copy()
        if not sequences.empty
        else sequences.copy()
    )
    if not candidates.empty:
        candidates = candidates.sort_values(
            ["SLOPE_SIGMA", "END_TO_END_KMS", "GROUP_ID"],
            ascending=[False, False, True],
            kind="mergesort",
        ).reset_index(drop=True)

    rng = np.random.default_rng(seed)
    null_rows: list[dict[str, object]] = []
    observed_sources = (
        int(candidates["GROUP_ID"].nunique()) if not candidates.empty else 0
    )
    for permutation in range(n_permutations):
        detected_sequences = 0
        detected_sources: set[int] = set()
        for group_id, _program, times, values, errors in sequence_arrays:
            order = rng.permutation(len(values))
            _metrics, detected = _acceleration_detection(
                times, values[order], errors[order], thresholds
            )
            if detected:
                detected_sequences += 1
                detected_sources.add(group_id)
        null_rows.append(
            {
                "PERMUTATION": permutation,
                "N_DETECTED_SEQUENCES": detected_sequences,
                "N_DETECTED_SOURCES": len(detected_sources),
                "N_GE_OBSERVED_SOURCES": int(len(detected_sources) >= observed_sources),
            }
        )
    null = pd.DataFrame(null_rows)
    return sequences, candidates, null


def metal_poor_screen(
    source_summary: pd.DataFrame,
    epoch_table: pd.DataFrame,
    high_amplitude: pd.DataFrame,
    acceleration_candidates: pd.DataFrame,
    thresholds: ExperimentThresholds = ExperimentThresholds(),
) -> pd.DataFrame:
    high_ids = set(
        high_amplitude.get("GROUP_ID", pd.Series(dtype="int64")).astype("int64")
    )
    acceleration_ids = set(
        acceleration_candidates.get("GROUP_ID", pd.Series(dtype="int64")).astype(
            "int64"
        )
    )
    candidate_ids = high_ids | acceleration_ids
    if not candidate_ids:
        return pd.DataFrame(columns=METAL_POOR_COLUMNS)
    epochs = _eligible_epoch_rows(epoch_table, candidate_ids)
    summary = _source_eligibility(source_summary).set_index("GROUP_ID", drop=False)
    rows: list[dict[str, object]] = []
    for group_id, group in epochs.groupby("GROUP_ID", sort=True):
        feh = pd.to_numeric(group["FEH"], errors="coerce").dropna().to_numpy(float)
        teff = pd.to_numeric(group["TEFF"], errors="coerce").dropna().to_numpy(float)
        if len(feh) < thresholds.metal_poor_min_finite_feh_epochs or not len(teff):
            continue
        median_feh = float(np.median(feh))
        robust_width = float(1.4826 * np.median(np.abs(feh - median_feh)))
        median_teff = float(np.median(teff))
        source_id = summary.at[int(group_id), "SOURCE_ID"]
        if pd.isna(source_id) or int(source_id) <= 0:
            continue
        if not (
            median_feh <= thresholds.metal_poor_max_median_feh
            and robust_width <= thresholds.metal_poor_max_robust_feh_width
            and thresholds.metal_poor_min_teff
            <= median_teff
            <= thresholds.metal_poor_max_teff
        ):
            continue
        rows.append(
            {
                "GROUP_ID": int(group_id),
                "SOURCE_ID": int(source_id),
                "IN_HIGH_AMPLITUDE": int(group_id) in high_ids,
                "IN_ACCELERATION": int(group_id) in acceleration_ids,
                "N_FINITE_FEH_EPOCHS": int(len(feh)),
                "MEDIAN_FEH_EPOCH": median_feh,
                "ROBUST_FEH_WIDTH": robust_width,
                "MEDIAN_TEFF_EPOCH": median_teff,
                "MEDIAN_LOGG": summary.at[int(group_id), "MEDIAN_LOGG"],
                "TARGET_RA": pd.to_numeric(
                    group["TARGET_RA"], errors="coerce"
                ).median(),
                "TARGET_DEC": pd.to_numeric(
                    group["TARGET_DEC"], errors="coerce"
                ).median(),
            }
        )
    return (
        pd.DataFrame(rows, columns=METAL_POOR_COLUMNS)
        .sort_values(["MEDIAN_FEH_EPOCH", "GROUP_ID"], kind="mergesort")
        .reset_index(drop=True)
    )


def run_experiments(
    source_summary_path: str | Path,
    epoch_bundle_path: str | Path,
    offset_uncertainty_path: str | Path,
    output_dir: str | Path,
    thresholds: ExperimentThresholds = ExperimentThresholds(),
    acceleration_permutations: int = 200,
    seed: int = 20260714,
) -> ExperimentResult:
    source_summary_path = Path(source_summary_path)
    epoch_bundle_path = Path(epoch_bundle_path)
    offset_uncertainty_path = Path(offset_uncertainty_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_summary = pd.read_parquet(source_summary_path)
    epoch_bundle = pd.read_parquet(epoch_bundle_path)
    offset_uncertainty = pd.read_csv(offset_uncertainty_path)
    epochs = attach_offset_uncertainty(epoch_bundle, offset_uncertainty)

    high_amplitude, high_amplitude_eligible = repeated_high_amplitude_experiment(
        source_summary, epochs, thresholds
    )
    acceleration_sequences, acceleration_candidates, acceleration_null = (
        acceleration_experiment(
            source_summary,
            epochs,
            thresholds,
            n_permutations=acceleration_permutations,
            seed=seed,
        )
    )
    metal_poor = metal_poor_screen(
        source_summary, epochs, high_amplitude, acceleration_candidates, thresholds
    )

    paths = {
        "high_amplitude_eligible": output_dir
        / "high_amplitude_eligible_sources.parquet",
        "high_amplitude": output_dir / "high_amplitude_candidates.parquet",
        "acceleration_sequences": output_dir / "acceleration_sequences.parquet",
        "acceleration_candidates": output_dir / "acceleration_candidates.parquet",
        "acceleration_null": output_dir / "acceleration_time_permutation_null.csv",
        "metal_poor": output_dir / "metal_poor_candidates.parquet",
    }
    high_amplitude_eligible.to_parquet(paths["high_amplitude_eligible"], index=False)
    high_amplitude.to_parquet(paths["high_amplitude"], index=False)
    acceleration_sequences.to_parquet(paths["acceleration_sequences"], index=False)
    acceleration_candidates.to_parquet(paths["acceleration_candidates"], index=False)
    acceleration_null.to_csv(paths["acceleration_null"], index=False)
    metal_poor.to_parquet(paths["metal_poor"], index=False)

    observed_acceleration_sources = int(acceleration_candidates["GROUP_ID"].nunique())
    n_null_ge = int(
        (acceleration_null["N_DETECTED_SOURCES"] >= observed_acceleration_sources).sum()
    )
    manifest: dict[str, object] = {
        "protocol": "research/exploratory_experiments_protocol.md",
        "runtime_environment": runtime_environment(),
        "thresholds": asdict(thresholds),
        "parameters": {
            "acceleration_permutations": acceleration_permutations,
            "seed": seed,
        },
        "inputs": {
            "source_summary_oof": {
                "name": source_summary_path.name,
                "sha256": _sha256(source_summary_path),
                "size": source_summary_path.stat().st_size,
            },
            "candidate_epoch_bundle": {
                "name": epoch_bundle_path.name,
                "sha256": _sha256(epoch_bundle_path),
                "size": epoch_bundle_path.stat().st_size,
            },
            "program_night_offset_uncertainty": {
                "name": offset_uncertainty_path.name,
                "sha256": _sha256(offset_uncertainty_path),
                "size": offset_uncertainty_path.stat().st_size,
            },
        },
        "counts": {
            "high_amplitude_eligible_sources": int(len(high_amplitude_eligible)),
            "high_amplitude_detected_sources": int(len(high_amplitude)),
            "acceleration_eligible_sequences": int(len(acceleration_sequences)),
            "acceleration_detected_sequences": int(len(acceleration_candidates)),
            "acceleration_detected_sources": observed_acceleration_sources,
            "metal_poor_candidates": int(len(metal_poor)),
        },
        "acceleration_null": {
            "n_permutations": int(len(acceleration_null)),
            "median_detected_sources": float(
                acceleration_null["N_DETECTED_SOURCES"].median()
            ),
            "max_detected_sources": int(acceleration_null["N_DETECTED_SOURCES"].max()),
            "n_ge_observed": n_null_ge,
            "corrected_empirical_exceedance_probability": (n_null_ge + 1)
            / (len(acceleration_null) + 1),
        },
        "outputs": {
            key: {
                "name": path.name,
                "sha256": _sha256(path),
                "size": path.stat().st_size,
            }
            for key, path in paths.items()
        },
    }
    manifest_path = output_dir / "experiment_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return ExperimentResult(
        high_amplitude_eligible=high_amplitude_eligible,
        high_amplitude=high_amplitude,
        acceleration_sequences=acceleration_sequences,
        acceleration_candidates=acceleration_candidates,
        acceleration_null=acceleration_null,
        metal_poor_candidates=metal_poor,
        manifest=manifest,
    )
