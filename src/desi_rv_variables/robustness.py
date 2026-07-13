from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import chi2


def _constant_rv_metrics(
    values: np.ndarray,
    errors: np.ndarray,
    mjd: np.ndarray,
    nights: np.ndarray,
) -> dict[str, float | bool]:
    valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0) & np.isfinite(mjd)
    values = values[valid]
    errors = errors[valid]
    mjd = mjd[valid]
    nights = nights[valid]
    if values.size < 3:
        return {"p_const": np.nan, "max_pair_sigma": np.nan, "is_outlier": False}
    weights = 1.0 / np.square(errors)
    mean = float(np.sum(weights * values) / np.sum(weights))
    chi2_value = float(np.sum(weights * np.square(values - mean)))
    p_const = float(chi2.sf(chi2_value, values.size - 1))
    pair_sigma = 0.0
    for index in range(values.size - 1):
        denom = np.hypot(errors[index], errors[index + 1 :])
        sigma = np.abs(values[index] - values[index + 1 :]) / denom
        if sigma.size:
            pair_sigma = max(pair_sigma, float(np.max(sigma)))
    baseline = float(np.max(mjd) - np.min(mjd))
    is_outlier = (
        baseline > 1.0
        and pd.Series(nights).astype("string").nunique(dropna=True) >= 2
        and p_const < 1e-6
        and pair_sigma >= 5.0
    )
    return {"p_const": p_const, "max_pair_sigma": pair_sigma, "is_outlier": is_outlier}


def _gaussian_log_likelihood(values: np.ndarray, errors: np.ndarray, jitter: float) -> float:
    variance = np.square(errors) + jitter * jitter
    weights = 1.0 / variance
    mean = float(np.sum(weights * values) / np.sum(weights))
    return float(
        -0.5
        * np.sum(np.square(values - mean) / variance + np.log(2.0 * np.pi * variance))
    )


def intrinsic_jitter_fit(values: np.ndarray, errors: np.ndarray) -> tuple[float, float]:
    valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0)
    values = np.asarray(values, dtype=float)[valid]
    errors = np.asarray(errors, dtype=float)[valid]
    if values.size < 3:
        return np.nan, np.nan
    null_loglike = _gaussian_log_likelihood(values, errors, 0.0)
    upper = max(10.0, float(np.ptp(values)) * 2.0, float(np.max(errors)) * 10.0)
    fit = minimize_scalar(
        lambda log_jitter: -_gaussian_log_likelihood(values, errors, float(np.exp(log_jitter))),
        bounds=(np.log(1e-4), np.log(upper)),
        method="bounded",
        options={"xatol": 1e-6},
    )
    jitter = float(np.exp(fit.x))
    improvement = max(0.0, -float(fit.fun) - null_loglike)
    if improvement <= 1e-8:
        jitter = 0.0
    return jitter, improvement


def _maximum_disjoint_pairs(n_epochs: int, edges: list[tuple[int, int]]) -> int:
    if not edges:
        return 0
    adjacency = [0] * n_epochs
    for first, second in edges:
        adjacency[first] |= 1 << second
        adjacency[second] |= 1 << first
    if n_epochs > 22:
        used: set[int] = set()
        count = 0
        for first, second in edges:
            if first not in used and second not in used:
                used.update((first, second))
                count += 1
        return count

    @lru_cache(maxsize=None)
    def solve(mask: int) -> int:
        if mask == 0:
            return 0
        first_bit = mask & -mask
        first = first_bit.bit_length() - 1
        best = solve(mask & ~first_bit)
        candidates = adjacency[first] & mask
        while candidates:
            second_bit = candidates & -candidates
            best = max(best, 1 + solve(mask & ~first_bit & ~second_bit))
            candidates &= ~second_bit
        return best

    return solve((1 << n_epochs) - 1)


def candidate_robustness_table(
    epoch_table: pd.DataFrame,
    candidate_ids: set[int],
) -> pd.DataFrame:
    columns = [
        "GROUP_ID",
        "N_EPOCHS_OOF",
        "N_SIGNIFICANT_PAIRS",
        "N_DISJOINT_SIGNIFICANT_PAIRS",
        "SIGNAL_ONLY_CROSS_PROGRAM",
        "LOO_EVALUABLE",
        "N_LOO_TRIALS",
        "N_LOO_OUTLIER",
        "LOO_OUTLIER_FRACTION",
        "LOO_ALL_OUTLIER",
        "JITTER_MLE_KMS",
        "DELTA_LOG_LIKELIHOOD_M1_M0",
    ]
    if not candidate_ids:
        return pd.DataFrame(columns=columns)
    work = epoch_table[
        epoch_table["GROUP_ID"].astype("int64").isin(candidate_ids)
        & epoch_table["GOOD_EPOCH"].astype(bool)
        & epoch_table["OOF_OFFSET_AVAILABLE"].astype(bool)
    ].copy()
    rows: list[dict[str, object]] = []
    for group_id, group in work.groupby("GROUP_ID", sort=False):
        group = group.sort_values(["MJD", "EXPID"], kind="mergesort")
        values = pd.to_numeric(group["VRAD_CORRECTED_OOF"], errors="coerce").to_numpy(float)
        errors = pd.to_numeric(group["VRAD_ERROR_CALIBRATED"], errors="coerce").to_numpy(float)
        mjd = pd.to_numeric(group["MJD"], errors="coerce").to_numpy(float)
        nights = group["NIGHT"].astype("string").to_numpy()
        programs = group["PROGRAM"].astype("string").str.upper().to_numpy()
        significant_edges: list[tuple[int, int]] = []
        cross_program_flags: list[bool] = []
        for first in range(len(group) - 1):
            denom = np.hypot(errors[first], errors[first + 1 :])
            sigma = np.abs(values[first] - values[first + 1 :]) / denom
            for relative_second in np.flatnonzero(sigma >= 5.0):
                second = first + 1 + int(relative_second)
                significant_edges.append((first, second))
                cross_program_flags.append(programs[first] != programs[second])
        loo_outlier = 0
        loo_trials = len(group) if len(group) >= 4 else 0
        for removed in range(loo_trials):
            keep = np.arange(len(group)) != removed
            metrics = _constant_rv_metrics(values[keep], errors[keep], mjd[keep], nights[keep])
            loo_outlier += int(bool(metrics["is_outlier"]))
        jitter, improvement = intrinsic_jitter_fit(values, errors)
        rows.append(
            {
                "GROUP_ID": int(group_id),
                "N_EPOCHS_OOF": int(len(group)),
                "N_SIGNIFICANT_PAIRS": int(len(significant_edges)),
                "N_DISJOINT_SIGNIFICANT_PAIRS": _maximum_disjoint_pairs(
                    len(group), significant_edges
                ),
                "SIGNAL_ONLY_CROSS_PROGRAM": bool(cross_program_flags)
                and all(cross_program_flags),
                "LOO_EVALUABLE": bool(loo_trials),
                "N_LOO_TRIALS": loo_trials,
                "N_LOO_OUTLIER": loo_outlier,
                "LOO_OUTLIER_FRACTION": loo_outlier / loo_trials if loo_trials else np.nan,
                "LOO_ALL_OUTLIER": bool(loo_trials and loo_outlier == loo_trials),
                "JITTER_MLE_KMS": jitter,
                "DELTA_LOG_LIKELIHOOD_M1_M0": improvement,
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values("GROUP_ID").reset_index(drop=True)
