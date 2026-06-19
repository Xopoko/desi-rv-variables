from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from desi_rv_audit.corrections import apply_velocity_calibration
from desi_rv_audit.io import load_many
from desi_rv_audit.quality import QualityRules, quality_mask
from desi_rv_audit.stats import _max_pair_sigma_by_target


DEFAULT_BACKUP_CORRECTION_MD5 = "f48a4b21b541e94d61f4372f4c555f12"


@dataclass(frozen=True)
class BundleBuildResult:
    source_summary: pd.DataFrame
    epoch_bundle: pd.DataFrame
    manifest: dict[str, object]


def source_fold_ids(group_ids: pd.Series, n_folds: int = 5) -> pd.Series:
    hashed = pd.util.hash_pandas_object(group_ids.astype("string"), index=False).to_numpy(
        dtype=np.uint64
    )
    return pd.Series((hashed % np.uint64(n_folds)).astype(np.int64), index=group_ids.index)


def program_night_labels(program: pd.Series, night: pd.Series) -> pd.Series:
    return (
        program.astype("string").str.strip().str.upper().fillna("UNKNOWN")
        + ":"
        + night.astype("string").str.strip().fillna("UNKNOWN")
    )


def load_program_night_offsets(path: str | Path) -> pd.DataFrame:
    offsets = pd.read_csv(path)
    required = {"FOLD", "LABEL", "OFFSET_KMS"}
    missing = required - set(offsets.columns)
    if missing:
        raise ValueError(f"Offset table is missing columns: {', '.join(sorted(missing))}")
    result = offsets[["FOLD", "LABEL", "OFFSET_KMS"]].copy()
    result["FOLD"] = pd.to_numeric(result["FOLD"], errors="coerce").astype("Int64")
    result["LABEL"] = result["LABEL"].astype("string")
    result["OFFSET_KMS"] = pd.to_numeric(result["OFFSET_KMS"], errors="coerce")
    result = result.dropna(subset=["FOLD", "LABEL", "OFFSET_KMS"])
    if result.duplicated(["FOLD", "LABEL"]).any():
        examples = result.loc[result.duplicated(["FOLD", "LABEL"], keep=False), ["FOLD", "LABEL"]]
        raise ValueError(f"Duplicate fold/label offsets: {examples.head().to_dict('records')}")
    return result.reset_index(drop=True)


def apply_oof_program_night_offsets(
    frame: pd.DataFrame,
    offsets: pd.DataFrame,
    n_folds: int = 5,
) -> pd.DataFrame:
    result = frame.copy()
    result["PROGRAM_NIGHT_FOLD"] = source_fold_ids(result["GROUP_ID"], n_folds=n_folds).astype(int)
    result["PROGRAM_NIGHT_LABEL"] = program_night_labels(result["PROGRAM"], result["NIGHT"])
    offset_map = offsets.set_index(["FOLD", "LABEL"])["OFFSET_KMS"]
    lookup = pd.MultiIndex.from_frame(
        result[["PROGRAM_NIGHT_FOLD", "PROGRAM_NIGHT_LABEL"]].rename(
            columns={"PROGRAM_NIGHT_FOLD": "FOLD", "PROGRAM_NIGHT_LABEL": "LABEL"}
        )
    )
    result["PROGRAM_NIGHT_OFFSET_OOF"] = offset_map.reindex(lookup).to_numpy(dtype=float)
    result["OOF_OFFSET_AVAILABLE"] = np.isfinite(result["PROGRAM_NIGHT_OFFSET_OOF"])
    result["VRAD_CORRECTED_OOF"] = np.where(
        result["OOF_OFFSET_AVAILABLE"],
        pd.to_numeric(result["VRAD_ADOPTED"], errors="coerce")
        - result["PROGRAM_NIGHT_OFFSET_OOF"],
        np.nan,
    )
    result["VRAD_ERROR_CALIBRATED"] = pd.to_numeric(
        result["VRAD_ERR_ADOPTED"], errors="coerce"
    )
    return result


def _robust_scale(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def _weighted_metrics(group: pd.DataFrame, value_column: str, error_column: str, prefix: str) -> dict[str, float]:
    values = pd.to_numeric(group[value_column], errors="coerce").to_numpy(dtype=float)
    errors = pd.to_numeric(group[error_column], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0)
    values = values[valid]
    errors = errors[valid]
    if len(values) < 2:
        return {
            f"CHI2_CONST_{prefix}": np.nan,
            f"P_CONST_{prefix}": np.nan,
            f"LOG_P_CONST_{prefix}": np.nan,
            f"MAX_PAIR_SIGMA_{prefix}": np.nan,
            f"MAX_DELTA_VRAD_{prefix}": np.nan,
            f"ROBUST_SCATTER_{prefix}": np.nan,
        }
    weights = 1.0 / np.square(errors)
    mean = float(np.sum(weights * values) / np.sum(weights))
    chi2_value = float(np.sum(np.square((values - mean) / errors)))
    dof = len(values) - 1
    p_const = float(chi2.sf(chi2_value, dof))
    log_p_const = float(chi2.logsf(chi2_value, dof))

    max_sigma = 0.0
    max_delta = 0.0
    for index in range(len(values) - 1):
        delta = np.abs(values[index] - values[index + 1 :])
        denom = np.hypot(errors[index], errors[index + 1 :])
        sigma = np.divide(delta, denom, out=np.zeros_like(delta), where=denom > 0)
        if len(delta):
            max_delta = max(max_delta, float(np.max(delta)))
            max_sigma = max(max_sigma, float(np.max(sigma)))
    return {
        f"CHI2_CONST_{prefix}": chi2_value,
        f"P_CONST_{prefix}": p_const,
        f"LOG_P_CONST_{prefix}": log_p_const,
        f"MAX_PAIR_SIGMA_{prefix}": max_sigma,
        f"MAX_DELTA_VRAD_{prefix}": max_delta,
        f"ROBUST_SCATTER_{prefix}": _robust_scale(values),
    }


def summarize_oof_sources(epoch_table: pd.DataFrame, good_mask_column: str = "GOOD_EPOCH") -> pd.DataFrame:
    good = epoch_table.loc[
        epoch_table[good_mask_column].astype(bool) & epoch_table["OOF_OFFSET_AVAILABLE"].astype(bool)
    ].copy()
    if good.empty:
        return pd.DataFrame()

    for column in (
        "GROUP_ID",
        "SOURCE_ID",
        "TARGETID",
        "MJD",
        "VRAD_ADOPTED",
        "VRAD_ERR_ADOPTED",
        "VRAD_CORRECTED_OOF",
        "VRAD_ERROR_CALIBRATED",
        "SN_R",
        "TEFF",
        "LOGG",
        "FEH",
    ):
        if column in good.columns:
            good[column] = pd.to_numeric(good[column], errors="coerce")
    good["PROGRAM"] = good["PROGRAM"].astype("string").str.strip().str.upper()
    good["NIGHT"] = good["NIGHT"].astype("string").str.strip()
    good = good[np.isfinite(good["GROUP_ID"])].copy()
    good["GROUP_ID"] = good["GROUP_ID"].astype("int64")

    grouped = good.groupby("GROUP_ID", sort=False)
    summary = grouped.agg(
        GROUP_KIND=("GROUP_KIND", "first"),
        SOURCE_ID=("SOURCE_ID", "first"),
        TARGETID=("TARGETID", "first"),
        N_EPOCHS_GOOD_OOF=("VRAD_CORRECTED_OOF", "size"),
        N_NIGHTS_GOOD_OOF=("NIGHT", "nunique"),
        N_PROGRAMS_GOOD_OOF=("PROGRAM", "nunique"),
        MJD_MIN=("MJD", "min"),
        MJD_MAX=("MJD", "max"),
        MEDIAN_SN_R=("SN_R", "median"),
        MEDIAN_TEFF=("TEFF", "median"),
        MEDIAN_LOGG=("LOGG", "median"),
        MEDIAN_FEH=("FEH", "median"),
        VRAD_BEFORE_MIN=("VRAD_ADOPTED", "min"),
        VRAD_BEFORE_MAX=("VRAD_ADOPTED", "max"),
        VRAD_OOF_MIN=("VRAD_CORRECTED_OOF", "min"),
        VRAD_OOF_MAX=("VRAD_CORRECTED_OOF", "max"),
    )
    summary = summary[summary["N_EPOCHS_GOOD_OOF"] >= 3].copy()
    if summary.empty:
        return pd.DataFrame()
    summary["TIME_BASELINE_DAYS_OOF"] = summary["MJD_MAX"] - summary["MJD_MIN"]

    program_counts = (
        good.groupby(["GROUP_ID", "PROGRAM"], sort=False)
        .size()
        .rename("N")
        .reset_index()
        .sort_values(["GROUP_ID", "N", "PROGRAM"], ascending=[True, False, True])
        .drop_duplicates("GROUP_ID", keep="first")
        .set_index("GROUP_ID")["PROGRAM"]
    )
    summary["DOMINANT_PROGRAM"] = summary.index.map(program_counts).astype("string")

    for prefix, value_column, error_column in (
        ("BEFORE", "VRAD_ADOPTED", "VRAD_ERR_ADOPTED"),
        ("OOF", "VRAD_CORRECTED_OOF", "VRAD_ERROR_CALIBRATED"),
    ):
        values = pd.to_numeric(good[value_column], errors="coerce")
        errors = pd.to_numeric(good[error_column], errors="coerce")
        valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0)
        weights = pd.Series(np.where(valid, 1.0 / np.square(errors), 0.0), index=good.index)
        weighted_values = weights * values.fillna(0.0)
        weighted_values2 = weights * np.square(values.fillna(0.0))
        sums = pd.DataFrame(
            {
                "GROUP_ID": good["GROUP_ID"],
                "_W": weights,
                "_WV": weighted_values,
                "_WV2": weighted_values2,
            }
        ).groupby("GROUP_ID", sort=False).sum()
        sums = sums.reindex(summary.index)
        mean = sums["_WV"] / sums["_W"]
        chi2_values = sums["_WV2"] - np.square(mean) * sums["_W"]
        chi2_values = chi2_values.clip(lower=0.0)
        dof = summary["N_EPOCHS_GOOD_OOF"] - 1
        has_dof = dof > 0
        p_values = np.full(len(summary), np.nan, dtype=float)
        log_p_values = np.full(len(summary), np.nan, dtype=float)
        p_values[has_dof.to_numpy()] = chi2.sf(
            chi2_values.loc[has_dof].to_numpy(dtype=float),
            dof.loc[has_dof].to_numpy(dtype=float),
        )
        log_p_values[has_dof.to_numpy()] = chi2.logsf(
            chi2_values.loc[has_dof].to_numpy(dtype=float),
            dof.loc[has_dof].to_numpy(dtype=float),
        )
        summary[f"CHI2_CONST_{prefix}"] = chi2_values
        summary[f"P_CONST_{prefix}"] = p_values
        summary[f"LOG_P_CONST_{prefix}"] = log_p_values

        med = good.groupby("GROUP_ID", sort=False)[value_column].transform("median")
        abs_dev = (good[value_column] - med).abs()
        robust_scatter = 1.4826 * abs_dev.groupby(good["GROUP_ID"], sort=False).median()
        summary[f"ROBUST_SCATTER_{prefix}"] = robust_scatter.reindex(summary.index)
        summary[f"MAX_PAIR_SIGMA_{prefix}"] = _max_pair_sigma_by_target(
            good,
            summary["N_EPOCHS_GOOD_OOF"],
            value_column,
            error_column,
        ).reindex(summary.index)

    summary["MAX_DELTA_VRAD_BEFORE"] = summary["VRAD_BEFORE_MAX"] - summary["VRAD_BEFORE_MIN"]
    summary["MAX_DELTA_VRAD_OOF"] = summary["VRAD_OOF_MAX"] - summary["VRAD_OOF_MIN"]
    summary["CLASSIFICATION_BEFORE"] = _classification_series(
        summary["N_EPOCHS_GOOD_OOF"],
        summary["TIME_BASELINE_DAYS_OOF"],
        summary["N_NIGHTS_GOOD_OOF"],
        summary["P_CONST_BEFORE"],
        summary["MAX_PAIR_SIGMA_BEFORE"],
    )
    summary["CLASSIFICATION_OOF"] = _classification_series(
        summary["N_EPOCHS_GOOD_OOF"],
        summary["TIME_BASELINE_DAYS_OOF"],
        summary["N_NIGHTS_GOOD_OOF"],
        summary["P_CONST_OOF"],
        summary["MAX_PAIR_SIGMA_OOF"],
    )
    summary = summary.drop(
        columns=[
            "MJD_MIN",
            "MJD_MAX",
            "VRAD_BEFORE_MIN",
            "VRAD_BEFORE_MAX",
            "VRAD_OOF_MIN",
            "VRAD_OOF_MAX",
        ]
    ).reset_index()
    for column in ("GROUP_ID", "SOURCE_ID", "TARGETID"):
        if column in summary.columns:
            summary[column] = pd.to_numeric(summary[column], errors="coerce").astype("Int64")
    return summary.sort_values(
        ["CLASSIFICATION_OOF", "LOG_P_CONST_OOF", "MAX_PAIR_SIGMA_OOF"],
        ascending=[True, True, False],
        na_position="last",
    ).reset_index(drop=True)


def _classification_series(
    n_epochs: pd.Series,
    baseline_days: pd.Series,
    n_nights: pd.Series,
    p_const: pd.Series,
    max_pair_sigma: pd.Series,
) -> np.ndarray:
    classification = np.full(len(n_epochs), "STABLE_LIKE", dtype=object)
    classification[n_epochs.to_numpy(dtype=int) < 3] = "INSUFFICIENT_EPOCHS"
    insufficient_baseline = (baseline_days.to_numpy(dtype=float) <= 1.0) | (
        n_nights.to_numpy(dtype=int) < 2
    )
    classification[insufficient_baseline] = "INSUFFICIENT_BASELINE"
    outlier = (
        (n_epochs.to_numpy(dtype=int) >= 3)
        & ~insufficient_baseline
        & np.isfinite(p_const.to_numpy(dtype=float))
        & (p_const.to_numpy(dtype=float) < 1e-6)
        & np.isfinite(max_pair_sigma.to_numpy(dtype=float))
        & (max_pair_sigma.to_numpy(dtype=float) >= 5.0)
    )
    classification[outlier] = "CONSTANT_RV_OUTLIER"
    return classification


def _classification(
    n_epochs: int,
    baseline_days: float,
    n_nights: int,
    p_const: float,
    max_pair_sigma: float,
) -> str:
    if n_epochs < 3:
        return "INSUFFICIENT_EPOCHS"
    if baseline_days <= 1.0 or n_nights < 2:
        return "INSUFFICIENT_BASELINE"
    if (
        np.isfinite(p_const)
        and p_const < 1e-6
        and np.isfinite(max_pair_sigma)
        and max_pair_sigma >= 5.0
    ):
        return "CONSTANT_RV_OUTLIER"
    return "STABLE_LIKE"


def _candidate_group_ids(path: str | Path | None) -> set[int]:
    if path is None:
        return set()
    candidates = pd.read_csv(path)
    column = "group_id" if "group_id" in candidates.columns else "GROUP_ID"
    if column not in candidates.columns:
        raise ValueError(f"{path} does not contain group_id/GROUP_ID")
    return set(pd.to_numeric(candidates[column], errors="coerce").dropna().astype("int64"))


def _stable_control_ids(summary: pd.DataFrame, candidate_ids: set[int], ratio: float = 1.0) -> set[int]:
    if not candidate_ids:
        return set()
    work = summary.copy()
    work["WAS_STRICT_SCREENING_CANDIDATE"] = work["GROUP_ID"].astype("int64").isin(candidate_ids)
    candidates = work[work["WAS_STRICT_SCREENING_CANDIDATE"]]
    stable = work[
        (~work["WAS_STRICT_SCREENING_CANDIDATE"])
        & work["CLASSIFICATION_BEFORE"].eq("STABLE_LIKE")
        & work["CLASSIFICATION_OOF"].eq("STABLE_LIKE")
    ].copy()
    if candidates.empty or stable.empty:
        return set()

    for frame in (candidates, stable):
        frame["_EPOCH_BIN"] = frame["N_EPOCHS_GOOD_OOF"].clip(upper=8)
        frame["_NIGHT_BIN"] = frame["N_NIGHTS_GOOD_OOF"].clip(upper=8)
        frame["_BASELINE_BIN"] = pd.cut(
            frame["TIME_BASELINE_DAYS_OOF"],
            bins=[-np.inf, 7, 30, 180, np.inf],
            labels=["lt7", "lt30", "lt180", "ge180"],
        ).astype(str)

    strata = ["DOMINANT_PROGRAM", "_EPOCH_BIN", "_NIGHT_BIN", "_BASELINE_BIN"]
    selected: list[pd.DataFrame] = []
    for key, group in candidates.groupby(strata, dropna=False, sort=True):
        pool = stable
        for column, value in zip(strata, key if isinstance(key, tuple) else (key,)):
            pool = pool[pool[column].eq(value)]
        if pool.empty:
            continue
        n_take = min(len(pool), max(1, int(np.ceil(len(group) * ratio))))
        pool = pool.assign(
            _HASH=pd.util.hash_pandas_object(pool["GROUP_ID"].astype("string"), index=False)
        ).sort_values("_HASH", kind="mergesort")
        selected.append(pool.head(n_take))
    if not selected:
        return set()
    return set(pd.concat(selected)["GROUP_ID"].astype("int64"))


def build_bundles(
    fits_paths: list[str | Path],
    backup_correction_path: str | Path,
    offsets_path: str | Path,
    output_dir: str | Path,
    strict_candidates_path: str | Path | None = None,
    min_sn_r: float = 5.0,
    n_folds: int = 5,
    control_ratio: float = 1.0,
    backup_correction_md5: str = DEFAULT_BACKUP_CORRECTION_MD5,
) -> BundleBuildResult:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = load_many(fits_paths, strict_desi_main=True)
    frame = apply_velocity_calibration(
        frame,
        backup_correction_path=backup_correction_path,
        expected_backup_correction_md5=backup_correction_md5,
    )
    good_mask = quality_mask(frame, QualityRules(min_sn_r=min_sn_r))
    frame["GOOD_EPOCH"] = good_mask.to_numpy(dtype=bool)

    offsets = load_program_night_offsets(offsets_path)
    frame = apply_oof_program_night_offsets(frame, offsets, n_folds=n_folds)
    summary = summarize_oof_sources(frame)
    candidate_ids = _candidate_group_ids(strict_candidates_path)
    summary["WAS_STRICT_SCREENING_CANDIDATE"] = summary["GROUP_ID"].astype("int64").isin(candidate_ids)
    summary["REMAINS_OOF_OUTLIER"] = summary["CLASSIFICATION_OOF"].eq("CONSTANT_RV_OUTLIER")
    strict_summary = summary[summary["WAS_STRICT_SCREENING_CANDIDATE"]]
    n_strict_input = int(len(candidate_ids))
    n_strict_in_summary = int(len(strict_summary))
    n_strict_remaining = int(strict_summary["REMAINS_OOF_OUTLIER"].sum())
    n_strict_removed_or_unscorable = n_strict_input - n_strict_remaining
    n_new_oof_outliers = int(
        ((~summary["WAS_STRICT_SCREENING_CANDIDATE"]) & summary["REMAINS_OOF_OUTLIER"]).sum()
    )

    control_ids = _stable_control_ids(summary, candidate_ids, ratio=control_ratio)
    bundle_ids = candidate_ids | control_ids
    bundle = frame[frame["GROUP_ID"].astype("int64").isin(bundle_ids)].copy()
    bundle["BUNDLE_ROLE"] = np.where(
        bundle["GROUP_ID"].astype("int64").isin(candidate_ids),
        "STRICT_SCREENING_CANDIDATE",
        "MATCHED_STABLE_CONTROL",
    )

    source_path = output_dir / "source_summary_oof.parquet"
    bundle_path = output_dir / "candidate_epoch_bundle.parquet"
    manifest_path = output_dir / "build_manifest.json"
    summary.to_parquet(source_path, index=False)
    bundle[_bundle_columns(bundle)].to_parquet(bundle_path, index=False)
    manifest = {
        "fits_paths": [str(path) for path in fits_paths],
        "backup_correction_path": str(backup_correction_path),
        "offsets_path": str(offsets_path),
        "strict_candidates_path": str(strict_candidates_path) if strict_candidates_path else "",
        "min_sn_r": min_sn_r,
        "n_folds": n_folds,
        "control_ratio": control_ratio,
        "n_sources_oof_summary": int(len(summary)),
        "n_strict_screening_candidates_input": n_strict_input,
        "n_strict_screening_candidates_in_summary": n_strict_in_summary,
        "n_strict_screening_candidates_oof_outlier": n_strict_remaining,
        "n_strict_screening_candidates_removed_or_unscorable": n_strict_removed_or_unscorable,
        "strict_screening_candidate_oof_survival_fraction": (
            n_strict_remaining / n_strict_input if n_strict_input else None
        ),
        "strict_screening_candidate_oof_removed_or_unscorable_fraction": (
            n_strict_removed_or_unscorable / n_strict_input if n_strict_input else None
        ),
        "n_oof_outliers": int(summary["REMAINS_OOF_OUTLIER"].sum()),
        "n_new_oof_outliers_not_in_strict_screening": n_new_oof_outliers,
        "n_candidate_epoch_bundle_rows": int(len(bundle)),
        "n_control_sources": int(len(control_ids)),
        "source_summary_oof": str(source_path),
        "candidate_epoch_bundle": str(bundle_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return BundleBuildResult(summary, bundle, manifest)


def _bundle_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [
        "BUNDLE_ROLE",
        "GROUP_ID",
        "GROUP_KIND",
        "SOURCE_ID",
        "TARGETID",
        "MJD",
        "NIGHT",
        "EXPID",
        "SURVEY",
        "PROGRAM",
        "VRAD",
        "VRAD_ERR",
        "VRAD_OFFSET",
        "VRAD_ADOPTED",
        "VRAD_FLOOR",
        "VRAD_ERR_ADOPTED",
        "PROGRAM_NIGHT_LABEL",
        "PROGRAM_NIGHT_FOLD",
        "PROGRAM_NIGHT_OFFSET_OOF",
        "OOF_OFFSET_AVAILABLE",
        "VRAD_CORRECTED_OOF",
        "VRAD_ERROR_CALIBRATED",
        "GOOD_EPOCH",
        "SN_B",
        "SN_R",
        "SN_Z",
        "TEFF",
        "LOGG",
        "FEH",
        "VSINI",
        "RVS_WARN",
        "SUCCESS",
        "FIBERSTATUS",
        "TILEID",
        "FIBER",
        "RR_SPECTYPE",
        "VRAD_SKEW",
        "VRAD_KURT",
        "CHISQ_TOT",
        "CHISQ_C_TOT",
        "CHISQ_B",
        "CHISQ_C_B",
        "CHISQ_R",
        "CHISQ_C_R",
        "CHISQ_Z",
        "CHISQ_C_Z",
        "_INPUT_FILE",
    ]
    return [column for column in preferred if column in frame.columns]
