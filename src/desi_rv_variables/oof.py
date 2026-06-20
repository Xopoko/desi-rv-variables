from __future__ import annotations

import json
import hashlib
import importlib.metadata
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from desi_rv_audit.corrections import apply_velocity_calibration
from desi_rv_audit.io import load_many
from desi_rv_audit.quality import QualityRules, quality_mask


DEFAULT_BACKUP_CORRECTION_MD5 = "f48a4b21b541e94d61f4372f4c555f12"
STRICT_CANDIDATES_SHA256 = "5c96d5cc823725f9c80f133c11f0aad3ca09c7eaa678a5d694b095eb46944b47"
STRICT_CANDIDATES_GZ_SHA256 = "7958ac85c59e5228069710f44420483373e7fddef58f2fb0aa4b5b8b06aed2e3"


@dataclass(frozen=True)
class BundleBuildResult:
    source_summary: pd.DataFrame
    epoch_bundle: pd.DataFrame
    manifest: dict[str, object]


def validate_parameters(
    min_sn_r: float,
    n_folds: int,
    control_ratio: float,
    injection_base_ratio: float,
) -> None:
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")
    if min_sn_r <= 0:
        raise ValueError("min_sn_r must be positive")
    if control_ratio < 0:
        raise ValueError("control_ratio must be non-negative")
    if injection_base_ratio < 0:
        raise ValueError("injection_base_ratio must be non-negative")


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: str | Path) -> dict[str, object]:
    path = Path(path)
    return {"path": str(path), "size": path.stat().st_size, "sha256": _sha256(path)}


def _git_commit_for_path(path: str | Path) -> str:
    current = Path(path).resolve()
    if current.is_file():
        current = current.parent
    try:
        return subprocess.check_output(
            ["git", "-C", str(current), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _git_dirty_for_path(path: str | Path) -> bool | str:
    current = Path(path).resolve()
    if current.is_file():
        current = current.parent
    try:
        status = subprocess.check_output(
            ["git", "-C", str(current), "status", "--short"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return bool(status.strip())
    except Exception:
        return ""


def _package_versions() -> dict[str, str]:
    names = [
        "desi-rv-variables",
        "desi-rv-audit",
        "numpy",
        "pandas",
        "scipy",
        "astropy",
        "pyarrow",
    ]
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = ""
    return versions


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


def load_program_night_offsets(path: str | Path, n_folds: int | None = None) -> pd.DataFrame:
    offsets = pd.read_csv(path)
    required = {"FOLD", "LABEL", "OFFSET_KMS", "COMPONENT"}
    missing = required - set(offsets.columns)
    if missing:
        raise ValueError(f"Offset table is missing columns: {', '.join(sorted(missing))}")
    result = offsets[["FOLD", "LABEL", "OFFSET_KMS", "COMPONENT"]].copy()
    result["FOLD"] = pd.to_numeric(result["FOLD"], errors="coerce").astype("Int64")
    result["LABEL"] = result["LABEL"].astype("string")
    result["OFFSET_KMS"] = pd.to_numeric(result["OFFSET_KMS"], errors="coerce")
    result["COMPONENT"] = pd.to_numeric(result["COMPONENT"], errors="coerce").astype("Int64")
    result = result.dropna(subset=["FOLD", "LABEL", "OFFSET_KMS", "COMPONENT"])
    if result.duplicated(["FOLD", "LABEL"]).any():
        examples = result.loc[result.duplicated(["FOLD", "LABEL"], keep=False), ["FOLD", "LABEL"]]
        raise ValueError(f"Duplicate fold/label offsets: {examples.head().to_dict('records')}")
    if n_folds is not None:
        folds = sorted(result["FOLD"].astype(int).unique().tolist())
        expected = list(range(n_folds))
        if folds != expected:
            raise ValueError(f"Offset table folds {folds} do not match expected {expected}")
    return result.reset_index(drop=True)


def apply_oof_program_night_offsets(
    frame: pd.DataFrame,
    offsets: pd.DataFrame,
    n_folds: int = 5,
) -> pd.DataFrame:
    result = frame.copy()
    result["PROGRAM_NIGHT_FOLD"] = source_fold_ids(result["GROUP_ID"], n_folds=n_folds).astype(int)
    result["PROGRAM_NIGHT_LABEL"] = program_night_labels(result["PROGRAM"], result["NIGHT"])
    indexed = offsets.set_index(["FOLD", "LABEL"])
    offset_map = indexed["OFFSET_KMS"]
    component_map = indexed["COMPONENT"]
    lookup = pd.MultiIndex.from_frame(
        result[["PROGRAM_NIGHT_FOLD", "PROGRAM_NIGHT_LABEL"]].rename(
            columns={"PROGRAM_NIGHT_FOLD": "FOLD", "PROGRAM_NIGHT_LABEL": "LABEL"}
        )
    )
    result["PROGRAM_NIGHT_OFFSET_OOF"] = offset_map.reindex(lookup).to_numpy(dtype=float)
    result["PROGRAM_NIGHT_COMPONENT_OOF"] = component_map.reindex(lookup).to_numpy(dtype=float)
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


def _max_pair_sigma_by_group(
    good: pd.DataFrame,
    n_epochs_good: pd.Series,
    value_column: str,
    error_column: str,
) -> pd.Series:
    result = pd.Series(np.nan, index=n_epochs_good.index, dtype=float)
    if good.empty:
        return result

    counts_by_row = good["GROUP_ID"].map(n_epochs_good)
    two_epoch = good.loc[counts_by_row == 2, ["GROUP_ID", value_column, error_column]]
    if not two_epoch.empty:
        two_summary = two_epoch.groupby("GROUP_ID", sort=False).agg(
            first_vrad=(value_column, "first"),
            last_vrad=(value_column, "last"),
            e1=(error_column, "first"),
            e2=(error_column, "last"),
        )
        denom = np.hypot(
            two_summary["e1"].to_numpy(dtype=float),
            two_summary["e2"].to_numpy(dtype=float),
        )
        sigma = np.divide(
            np.abs(
                two_summary["first_vrad"].to_numpy(dtype=float)
                - two_summary["last_vrad"].to_numpy(dtype=float)
            ),
            denom,
            out=np.full(len(two_summary), np.nan, dtype=float),
            where=denom > 0,
        )
        result.loc[two_summary.index] = sigma

    many_epoch = good.loc[counts_by_row > 2, ["GROUP_ID", value_column, error_column]]
    for group_id, group in many_epoch.groupby("GROUP_ID", sort=False):
        values = group[value_column].to_numpy(dtype=float)
        errors = group[error_column].to_numpy(dtype=float)
        best = 0.0
        for index in range(values.size - 1):
            denom = np.hypot(errors[index], errors[index + 1 :])
            sigma = np.divide(
                np.abs(values[index] - values[index + 1 :]),
                denom,
                out=np.zeros_like(denom, dtype=float),
                where=denom > 0,
            )
            if sigma.size:
                best = max(best, float(np.max(sigma)))
        result.loc[group_id] = best
    return result


def summarize_oof_sources(epoch_table: pd.DataFrame, good_mask_column: str = "GOOD_EPOCH") -> pd.DataFrame:
    good_all = epoch_table.loc[epoch_table[good_mask_column].astype(bool)].copy()
    if good_all.empty:
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
        "PROGRAM_NIGHT_COMPONENT_OOF",
    ):
        if column in good_all.columns:
            good_all[column] = pd.to_numeric(good_all[column], errors="coerce")
    good_all["PROGRAM"] = good_all["PROGRAM"].astype("string").str.strip().str.upper()
    good_all["NIGHT"] = good_all["NIGHT"].astype("string").str.strip()
    good_all = good_all[np.isfinite(good_all["GROUP_ID"])].copy()
    good_all["GROUP_ID"] = good_all["GROUP_ID"].astype("int64")

    total_grouped = good_all.groupby("GROUP_ID", sort=False)
    summary = total_grouped.agg(
        GROUP_KIND=("GROUP_KIND", "first"),
        SOURCE_ID=("SOURCE_ID", "first"),
        TARGETID=("TARGETID", "first"),
        N_EPOCHS_GOOD_TOTAL=("VRAD_ADOPTED", "size"),
        N_NIGHTS_GOOD_TOTAL=("NIGHT", "nunique"),
        N_PROGRAMS_GOOD_TOTAL=("PROGRAM", "nunique"),
        MJD_MIN_TOTAL=("MJD", "min"),
        MJD_MAX_TOTAL=("MJD", "max"),
    )
    summary = summary[summary["N_EPOCHS_GOOD_TOTAL"] >= 3].copy()
    if summary.empty:
        return pd.DataFrame()

    oof_good = good_all.loc[good_all["OOF_OFFSET_AVAILABLE"].astype(bool)].copy()
    if not oof_good.empty:
        oof_grouped = oof_good.groupby("GROUP_ID", sort=False)
        oof_summary = oof_grouped.agg(
            N_EPOCHS_GOOD_OOF=("VRAD_CORRECTED_OOF", "size"),
            N_NIGHTS_GOOD_OOF=("NIGHT", "nunique"),
            N_PROGRAMS_GOOD_OOF=("PROGRAM", "nunique"),
            N_OOF_COMPONENTS=("PROGRAM_NIGHT_COMPONENT_OOF", "nunique"),
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
        summary = summary.join(oof_summary, how="left")
    else:
        for column in (
            "N_EPOCHS_GOOD_OOF",
            "N_NIGHTS_GOOD_OOF",
            "N_PROGRAMS_GOOD_OOF",
            "N_OOF_COMPONENTS",
            "MJD_MIN",
            "MJD_MAX",
            "MEDIAN_SN_R",
            "MEDIAN_TEFF",
            "MEDIAN_LOGG",
            "MEDIAN_FEH",
            "VRAD_BEFORE_MIN",
            "VRAD_BEFORE_MAX",
            "VRAD_OOF_MIN",
            "VRAD_OOF_MAX",
        ):
            summary[column] = np.nan

    count_columns = [
        "N_EPOCHS_GOOD_OOF",
        "N_NIGHTS_GOOD_OOF",
        "N_PROGRAMS_GOOD_OOF",
        "N_OOF_COMPONENTS",
    ]
    for column in count_columns:
        summary[column] = summary[column].fillna(0).astype(int)
    summary["OOF_EPOCH_COVERAGE_FRACTION"] = (
        summary["N_EPOCHS_GOOD_OOF"] / summary["N_EPOCHS_GOOD_TOTAL"].clip(lower=1)
    )
    summary["TIME_BASELINE_DAYS_TOTAL"] = summary["MJD_MAX_TOTAL"] - summary["MJD_MIN_TOTAL"]
    summary["TIME_BASELINE_DAYS_OOF"] = summary["MJD_MAX"] - summary["MJD_MIN"]

    status = np.full(len(summary), "COMPLETE_SINGLE_COMPONENT", dtype=object)
    insufficient = summary["N_EPOCHS_GOOD_OOF"].to_numpy(dtype=int) < 3
    cross_component = summary["N_OOF_COMPONENTS"].to_numpy(dtype=int) > 1
    partial = summary["OOF_EPOCH_COVERAGE_FRACTION"].to_numpy(dtype=float) < 1.0
    status[partial] = "PARTIAL_COVERAGE"
    status[cross_component] = "CROSS_COMPONENT_UNSCORABLE"
    status[insufficient] = "INSUFFICIENT_OOF_EPOCHS"
    summary["OOF_SCORING_STATUS"] = status
    summary["PRIMARY_COHORT"] = summary["OOF_SCORING_STATUS"].eq("COMPLETE_SINGLE_COMPONENT")

    program_counts = (
        oof_good.groupby(["GROUP_ID", "PROGRAM"], sort=False)
        .size()
        .rename("N")
        .reset_index()
        .sort_values(["GROUP_ID", "N", "PROGRAM"], ascending=[True, False, True])
        .drop_duplicates("GROUP_ID", keep="first")
        .set_index("GROUP_ID")["PROGRAM"]
        if not oof_good.empty
        else pd.Series(dtype="string")
    )
    summary["DOMINANT_PROGRAM"] = summary.index.map(program_counts).astype("string")

    scorable_index = summary.index[
        (summary["N_EPOCHS_GOOD_OOF"] >= 3) & (summary["N_OOF_COMPONENTS"] == 1)
    ]
    scored_good = oof_good[oof_good["GROUP_ID"].isin(scorable_index)].copy()

    for column in (
        "CHI2_CONST_BEFORE",
        "P_CONST_BEFORE",
        "LOG_P_CONST_BEFORE",
        "ROBUST_SCATTER_BEFORE",
        "MAX_PAIR_SIGMA_BEFORE",
        "CHI2_CONST_OOF",
        "P_CONST_OOF",
        "LOG_P_CONST_OOF",
        "ROBUST_SCATTER_OOF",
        "MAX_PAIR_SIGMA_OOF",
    ):
        summary[column] = np.nan

    for prefix, value_column, error_column in (
        ("BEFORE", "VRAD_ADOPTED", "VRAD_ERR_ADOPTED"),
        ("OOF", "VRAD_CORRECTED_OOF", "VRAD_ERROR_CALIBRATED"),
    ):
        values = pd.to_numeric(scored_good[value_column], errors="coerce")
        errors = pd.to_numeric(scored_good[error_column], errors="coerce")
        valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0)
        weights = pd.Series(np.where(valid, 1.0 / np.square(errors), 0.0), index=scored_good.index)
        weighted_values = weights * values.fillna(0.0)
        weighted_values2 = weights * np.square(values.fillna(0.0))
        sums = pd.DataFrame(
            {
                "GROUP_ID": scored_good["GROUP_ID"],
                "_W": weights,
                "_WV": weighted_values,
                "_WV2": weighted_values2,
            }
        ).groupby("GROUP_ID", sort=False).sum()
        sums = sums.reindex(scorable_index)
        mean = sums["_WV"] / sums["_W"]
        chi2_values = sums["_WV2"] - np.square(mean) * sums["_W"]
        chi2_values = chi2_values.clip(lower=0.0)
        dof = summary.loc[scorable_index, "N_EPOCHS_GOOD_OOF"] - 1
        has_dof = dof > 0
        p_values = pd.Series(np.nan, index=scorable_index, dtype=float)
        log_p_values = pd.Series(np.nan, index=scorable_index, dtype=float)
        p_values.loc[has_dof] = chi2.sf(
            chi2_values.loc[has_dof].to_numpy(dtype=float),
            dof.loc[has_dof].to_numpy(dtype=float),
        )
        log_p_values.loc[has_dof] = chi2.logsf(
            chi2_values.loc[has_dof].to_numpy(dtype=float),
            dof.loc[has_dof].to_numpy(dtype=float),
        )
        summary.loc[scorable_index, f"CHI2_CONST_{prefix}"] = chi2_values
        summary.loc[scorable_index, f"P_CONST_{prefix}"] = p_values
        summary.loc[scorable_index, f"LOG_P_CONST_{prefix}"] = log_p_values

        med = scored_good.groupby("GROUP_ID", sort=False)[value_column].transform("median")
        abs_dev = (scored_good[value_column] - med).abs()
        robust_scatter = 1.4826 * abs_dev.groupby(scored_good["GROUP_ID"], sort=False).median()
        summary.loc[scorable_index, f"ROBUST_SCATTER_{prefix}"] = robust_scatter.reindex(
            scorable_index
        )
        summary.loc[scorable_index, f"MAX_PAIR_SIGMA_{prefix}"] = _max_pair_sigma_by_group(
            scored_good,
            summary.loc[scorable_index, "N_EPOCHS_GOOD_OOF"],
            value_column,
            error_column,
        ).reindex(scorable_index)

    summary["MAX_DELTA_VRAD_BEFORE"] = summary["VRAD_BEFORE_MAX"] - summary["VRAD_BEFORE_MIN"]
    summary["MAX_DELTA_VRAD_OOF"] = summary["VRAD_OOF_MAX"] - summary["VRAD_OOF_MIN"]
    summary["CLASSIFICATION_BEFORE"] = "UNSCORABLE"
    summary["CLASSIFICATION_OOF"] = "UNSCORABLE"
    if len(scorable_index):
        summary.loc[scorable_index, "CLASSIFICATION_BEFORE"] = _classification_series(
            summary.loc[scorable_index, "N_EPOCHS_GOOD_OOF"],
            summary.loc[scorable_index, "TIME_BASELINE_DAYS_OOF"],
            summary.loc[scorable_index, "N_NIGHTS_GOOD_OOF"],
            summary.loc[scorable_index, "P_CONST_BEFORE"],
            summary.loc[scorable_index, "MAX_PAIR_SIGMA_BEFORE"],
        )
        summary.loc[scorable_index, "CLASSIFICATION_OOF"] = _classification_series(
            summary.loc[scorable_index, "N_EPOCHS_GOOD_OOF"],
            summary.loc[scorable_index, "TIME_BASELINE_DAYS_OOF"],
            summary.loc[scorable_index, "N_NIGHTS_GOOD_OOF"],
            summary.loc[scorable_index, "P_CONST_OOF"],
            summary.loc[scorable_index, "MAX_PAIR_SIGMA_OOF"],
        )
    summary.loc[
        summary["OOF_SCORING_STATUS"].eq("CROSS_COMPONENT_UNSCORABLE"),
        "CLASSIFICATION_OOF",
    ] = "CROSS_COMPONENT_UNSCORABLE"
    summary.loc[
        summary["OOF_SCORING_STATUS"].eq("INSUFFICIENT_OOF_EPOCHS"),
        "CLASSIFICATION_OOF",
    ] = "INSUFFICIENT_OOF_EPOCHS"
    summary = summary.drop(
        columns=[
            "MJD_MIN_TOTAL",
            "MJD_MAX_TOTAL",
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
        ["PRIMARY_COHORT", "CLASSIFICATION_OOF", "LOG_P_CONST_OOF", "MAX_PAIR_SIGMA_OOF"],
        ascending=[False, True, True, False],
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


def _transition_class(label: object) -> str:
    value = str(label)
    if value == "CONSTANT_RV_OUTLIER":
        return "OUTLIER"
    if value == "STABLE_LIKE":
        return "STABLE"
    if value == "INSUFFICIENT_BASELINE":
        return "INSUFFICIENT_BASELINE"
    if value == "INSUFFICIENT_EPOCHS":
        return "INSUFFICIENT_EPOCHS"
    if value == "INSUFFICIENT_OOF_EPOCHS":
        return "INSUFFICIENT_OOF_EPOCHS"
    if value == "CROSS_COMPONENT_UNSCORABLE":
        return "CROSS_COMPONENT_UNSCORABLE"
    if value == "PARTIAL_COVERAGE":
        return "PARTIAL_COVERAGE"
    return "UNSCORABLE"


def strict_candidate_transition_table(
    summary: pd.DataFrame,
    candidate_ids: set[int],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if candidate_ids:
        work = summary[summary["GROUP_ID"].astype("int64").isin(candidate_ids)].copy()
    else:
        work = summary.iloc[0:0].copy()

    missing = len(candidate_ids) - len(work)
    for _, row in work.iterrows():
        if bool(row.get("PRIMARY_COHORT", False)):
            before = _transition_class(row["CLASSIFICATION_BEFORE"])
            after = _transition_class(row["CLASSIFICATION_OOF"])
        else:
            before = "UNSCORABLE"
            after = _transition_class(row.get("OOF_SCORING_STATUS", "UNSCORABLE"))
        rows.append({"BEFORE_CLASS": before, "OOF_CLASS": after, "N": 1})
    if missing > 0:
        rows.append({"BEFORE_CLASS": "UNSCORABLE", "OOF_CLASS": "MISSING_FROM_SUMMARY", "N": missing})
    if not rows:
        return pd.DataFrame(columns=["BEFORE_CLASS", "OOF_CLASS", "N"])
    return (
        pd.DataFrame(rows)
        .groupby(["BEFORE_CLASS", "OOF_CLASS"], as_index=False, sort=True)["N"]
        .sum()
    )


def _candidate_group_ids(
    path: str | Path | None,
    expected_sha256: str | None = STRICT_CANDIDATES_SHA256,
) -> set[int]:
    if path is None:
        return set()
    if expected_sha256:
        actual = _sha256(path)
        if actual != expected_sha256:
            raise ValueError(
                f"{path} SHA-256 mismatch: expected {expected_sha256}, got {actual}"
            )
    candidates = pd.read_csv(path)
    column = "group_id" if "group_id" in candidates.columns else "GROUP_ID"
    if column not in candidates.columns:
        raise ValueError(f"{path} does not contain group_id/GROUP_ID")
    return set(pd.to_numeric(candidates[column], errors="coerce").dropna().astype("int64"))


def _add_cadence_bins(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["_EPOCH_BIN"] = result["N_EPOCHS_GOOD_OOF"].clip(upper=8)
    result["_NIGHT_BIN"] = result["N_NIGHTS_GOOD_OOF"].clip(upper=8)
    result["_BASELINE_BIN"] = pd.cut(
        result["TIME_BASELINE_DAYS_OOF"],
        bins=[-np.inf, 7, 30, 180, np.inf],
        labels=["lt7", "lt30", "lt180", "ge180"],
    ).astype(str)
    return result


def _select_by_candidate_strata(
    candidates: pd.DataFrame,
    pool: pd.DataFrame,
    ratio: float,
) -> set[int]:
    if ratio == 0 or candidates.empty or pool.empty:
        return set()
    candidates = _add_cadence_bins(candidates)
    pool = _add_cadence_bins(pool)
    strata = ["DOMINANT_PROGRAM", "_EPOCH_BIN", "_NIGHT_BIN", "_BASELINE_BIN"]
    selected: list[pd.DataFrame] = []
    for key, group in candidates.groupby(strata, dropna=False, sort=True):
        subset = pool
        values = key if isinstance(key, tuple) else (key,)
        for column, value in zip(strata, values):
            subset = subset[subset[column].eq(value)]
        if subset.empty:
            continue
        n_take = min(len(subset), int(np.ceil(len(group) * ratio)))
        if n_take <= 0:
            continue
        subset = subset.assign(
            _HASH=pd.util.hash_pandas_object(subset["GROUP_ID"].astype("string"), index=False)
        ).sort_values("_HASH", kind="mergesort")
        selected.append(subset.head(n_take))
    if not selected:
        return set()
    return set(pd.concat(selected)["GROUP_ID"].astype("int64"))


def _cadence_matched_inspection_control_ids(
    summary: pd.DataFrame,
    candidate_ids: set[int],
    ratio: float = 1.0,
) -> set[int]:
    if not candidate_ids or ratio == 0:
        return set()
    work = summary.copy()
    work["WAS_STRICT_SCREENING_CANDIDATE"] = work["GROUP_ID"].astype("int64").isin(candidate_ids)
    candidates = work[work["WAS_STRICT_SCREENING_CANDIDATE"]]
    inspection_pool = work[
        (~work["WAS_STRICT_SCREENING_CANDIDATE"])
        & work["PRIMARY_COHORT"].astype(bool)
        & work["CLASSIFICATION_BEFORE"].eq("STABLE_LIKE")
        & work["CLASSIFICATION_OOF"].eq("STABLE_LIKE")
    ]
    return _select_by_candidate_strata(candidates, inspection_pool, ratio)


def _injection_base_population_ids(
    summary: pd.DataFrame,
    candidate_ids: set[int],
    ratio: float = 1.0,
) -> set[int]:
    if not candidate_ids or ratio == 0:
        return set()
    work = summary.copy()
    work["WAS_STRICT_SCREENING_CANDIDATE"] = work["GROUP_ID"].astype("int64").isin(candidate_ids)
    candidates = work[work["WAS_STRICT_SCREENING_CANDIDATE"]]
    base_pool = work[
        (~work["WAS_STRICT_SCREENING_CANDIDATE"])
        & work["PRIMARY_COHORT"].astype(bool)
    ]
    return _select_by_candidate_strata(candidates, base_pool, ratio)


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def build_bundles(
    fits_paths: list[str | Path],
    backup_correction_path: str | Path,
    offsets_path: str | Path,
    output_dir: str | Path,
    strict_candidates_path: str | Path | None = None,
    min_sn_r: float = 5.0,
    n_folds: int = 5,
    control_ratio: float = 1.0,
    injection_base_ratio: float = 1.0,
    backup_correction_md5: str = DEFAULT_BACKUP_CORRECTION_MD5,
    strict_candidates_sha256: str | None = STRICT_CANDIDATES_SHA256,
) -> BundleBuildResult:
    validate_parameters(
        min_sn_r=min_sn_r,
        n_folds=n_folds,
        control_ratio=control_ratio,
        injection_base_ratio=injection_base_ratio,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fits_paths = [Path(path) for path in fits_paths]
    backup_correction_path = Path(backup_correction_path)
    offsets_path = Path(offsets_path)
    strict_candidates_path_obj = Path(strict_candidates_path) if strict_candidates_path else None

    frame = load_many(fits_paths, strict_desi_main=True)
    frame = apply_velocity_calibration(
        frame,
        backup_correction_path=backup_correction_path,
        expected_backup_correction_md5=backup_correction_md5,
    )
    good_mask = quality_mask(frame, QualityRules(min_sn_r=min_sn_r))
    frame["GOOD_EPOCH"] = good_mask.to_numpy(dtype=bool)

    offsets = load_program_night_offsets(offsets_path, n_folds=n_folds)
    frame = apply_oof_program_night_offsets(frame, offsets, n_folds=n_folds)
    summary = summarize_oof_sources(frame)
    candidate_ids = _candidate_group_ids(
        strict_candidates_path_obj,
        expected_sha256=strict_candidates_sha256,
    )
    summary["WAS_STRICT_SCREENING_CANDIDATE"] = summary["GROUP_ID"].astype("int64").isin(candidate_ids)
    summary["REMAINS_OOF_OUTLIER"] = (
        summary["PRIMARY_COHORT"].astype(bool)
        & summary["CLASSIFICATION_OOF"].eq("CONSTANT_RV_OUTLIER")
    )
    strict_summary = summary[summary["WAS_STRICT_SCREENING_CANDIDATE"]]
    primary_strict = strict_summary[strict_summary["PRIMARY_COHORT"].astype(bool)]
    before_outlier_primary_strict = primary_strict[
        primary_strict["CLASSIFICATION_BEFORE"].eq("CONSTANT_RV_OUTLIER")
    ]
    reclassified_primary_strict = before_outlier_primary_strict[
        ~before_outlier_primary_strict["CLASSIFICATION_OOF"].eq("CONSTANT_RV_OUTLIER")
    ]
    primary_non_strict = summary[
        (~summary["WAS_STRICT_SCREENING_CANDIDATE"]) & summary["PRIMARY_COHORT"].astype(bool)
    ]
    n_strict_input = int(len(candidate_ids))
    n_strict_in_summary = int(len(strict_summary))
    n_strict_primary = int(len(primary_strict))
    n_strict_before_outlier_primary = int(len(before_outlier_primary_strict))
    n_strict_reclassified_primary = int(len(reclassified_primary_strict))
    n_strict_oof_outlier_primary = int(primary_strict["REMAINS_OOF_OUTLIER"].sum())
    n_new_oof_outliers = int(primary_non_strict["REMAINS_OOF_OUTLIER"].sum())
    transition = strict_candidate_transition_table(summary, candidate_ids)

    inspection_control_ids = _cadence_matched_inspection_control_ids(
        summary,
        candidate_ids,
        ratio=control_ratio,
    )
    injection_base_ids = _injection_base_population_ids(
        summary,
        candidate_ids,
        ratio=injection_base_ratio,
    )

    summary["IS_CADENCE_MATCHED_INSPECTION_CONTROL"] = summary["GROUP_ID"].astype("int64").isin(
        inspection_control_ids
    )
    summary["IS_INJECTION_RECOVERY_BASE_POPULATION"] = summary["GROUP_ID"].astype("int64").isin(
        injection_base_ids
    )

    bundle_ids = candidate_ids | inspection_control_ids | injection_base_ids
    bundle = frame[frame["GROUP_ID"].astype("int64").isin(bundle_ids)].copy()
    bundle_group_ids = bundle["GROUP_ID"].astype("int64")
    bundle["IS_CADENCE_MATCHED_INSPECTION_CONTROL"] = bundle_group_ids.isin(
        inspection_control_ids
    )
    bundle["IS_INJECTION_RECOVERY_BASE_POPULATION"] = bundle_group_ids.isin(injection_base_ids)
    bundle["BUNDLE_ROLE"] = "INJECTION_RECOVERY_BASE_POPULATION"
    bundle.loc[
        bundle["IS_CADENCE_MATCHED_INSPECTION_CONTROL"],
        "BUNDLE_ROLE",
    ] = "CADENCE_MATCHED_INSPECTION_CONTROL"
    bundle.loc[
        bundle["IS_CADENCE_MATCHED_INSPECTION_CONTROL"]
        & bundle["IS_INJECTION_RECOVERY_BASE_POPULATION"],
        "BUNDLE_ROLE",
    ] = "CADENCE_MATCHED_INSPECTION_AND_INJECTION_BASE"
    bundle.loc[
        bundle_group_ids.isin(candidate_ids),
        "BUNDLE_ROLE",
    ] = "STRICT_SCREENING_CANDIDATE"

    source_path = output_dir / "source_summary_oof.parquet"
    bundle_path = output_dir / "candidate_epoch_bundle.parquet"
    transition_path = output_dir / "strict_candidate_transition_table.csv"
    manifest_path = output_dir / "build_manifest.json"
    summary.to_parquet(source_path, index=False)
    bundle[_bundle_columns(bundle)].to_parquet(bundle_path, index=False)
    transition.to_csv(transition_path, index=False)
    repo_root = Path(__file__).resolve().parents[2]
    fold_fixture_ids = pd.Series([1, 101, 202, 303, 123456789012345678, -55], dtype="int64")
    manifest = {
        "parameters": {
            "min_sn_r": min_sn_r,
            "n_folds": n_folds,
            "control_ratio": control_ratio,
            "injection_base_ratio": injection_base_ratio,
            "backup_correction_md5": backup_correction_md5,
            "strict_candidates_sha256": strict_candidates_sha256 or "",
        },
        "input_files": {
            "fits": [_file_record(path) for path in fits_paths],
            "backup_correction": _file_record(backup_correction_path),
            "program_night_offsets": _file_record(offsets_path),
            "strict_candidates": (
                _file_record(strict_candidates_path_obj)
                if strict_candidates_path_obj is not None
                else None
            ),
        },
        "repositories": {
            "desi_rv_variables_commit": _git_commit_for_path(repo_root),
            "desi_rv_variables_dirty": _git_dirty_for_path(repo_root),
            "desi_rv_audit_artifact_commit": _git_commit_for_path(offsets_path),
            "desi_rv_audit_artifact_dirty": _git_dirty_for_path(offsets_path),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": _package_versions(),
        },
        "fold_fixture": [
            {"group_id": int(group_id), "fold": int(fold)}
            for group_id, fold in zip(
                fold_fixture_ids,
                source_fold_ids(fold_fixture_ids, n_folds=n_folds),
            )
        ],
        "offset_table": {
            "n_rows": int(len(offsets)),
            "component_counts": {
                str(key): int(value)
                for key, value in offsets["COMPONENT"].astype(int).value_counts().sort_index().items()
            },
        },
        "oof_scoring_status_counts": {
            str(key): int(value)
            for key, value in summary["OOF_SCORING_STATUS"].value_counts().sort_index().items()
        },
        "n_sources_oof_summary": int(len(summary)),
        "n_strict_screening_candidates_input": n_strict_input,
        "n_strict_screening_candidates_in_summary": n_strict_in_summary,
        "n_strict_screening_candidates_primary_complete_case": n_strict_primary,
        "n_strict_screening_candidates_before_outlier_primary": n_strict_before_outlier_primary,
        "n_strict_screening_candidates_oof_outlier_primary": n_strict_oof_outlier_primary,
        "n_strict_screening_candidates_reclassified_primary": n_strict_reclassified_primary,
        "coverage_attrition_fraction": _safe_fraction(n_strict_input - n_strict_primary, n_strict_input),
        "before_rule_reconciliation_fraction": _safe_fraction(
            n_strict_primary - n_strict_before_outlier_primary,
            n_strict_primary,
        ),
        "oof_reclassification_fraction": _safe_fraction(
            n_strict_reclassified_primary,
            n_strict_before_outlier_primary,
        ),
        "new_oof_outlier_fraction": _safe_fraction(n_new_oof_outliers, int(len(primary_non_strict))),
        "strict_candidate_transition_table": transition.to_dict("records"),
        "n_oof_outliers": int(summary["REMAINS_OOF_OUTLIER"].sum()),
        "n_new_oof_outliers_not_in_strict_screening": n_new_oof_outliers,
        "n_candidate_epoch_bundle_rows": int(len(bundle)),
        "n_cadence_matched_inspection_control_sources": int(len(inspection_control_ids)),
        "n_injection_recovery_base_population_sources": int(len(injection_base_ids)),
        "source_summary_oof": str(source_path),
        "candidate_epoch_bundle": str(bundle_path),
        "strict_candidate_transition_table_csv": str(transition_path),
    }
    manifest["output_files"] = {
        "source_summary_oof": _file_record(source_path),
        "candidate_epoch_bundle": _file_record(bundle_path),
        "strict_candidate_transition_table": _file_record(transition_path),
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
        "PROGRAM_NIGHT_COMPONENT_OOF",
        "OOF_OFFSET_AVAILABLE",
        "VRAD_CORRECTED_OOF",
        "VRAD_ERROR_CALIBRATED",
        "IS_CADENCE_MATCHED_INSPECTION_CONTROL",
        "IS_INJECTION_RECOVERY_BASE_POPULATION",
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
