from __future__ import annotations

import numpy as np
import pandas as pd

from .robustness import _constant_rv_metrics


def bootstrap_offset_uncertainty(bootstrap_offsets: pd.DataFrame) -> pd.DataFrame:
    if bootstrap_offsets.empty:
        return pd.DataFrame(columns=["FOLD", "LABEL", "OFFSET_STD_KMS", "N_BOOTSTRAPS"])
    result = (
        bootstrap_offsets.groupby(["FOLD", "LABEL"], sort=True)["OFFSET_KMS"]
        .agg(OFFSET_STD_KMS="std", N_BOOTSTRAPS="count")
        .reset_index()
    )
    return result


def _template_records(epoch_bundle: pd.DataFrame) -> list[dict[str, object]]:
    work = epoch_bundle[
        epoch_bundle["IS_INJECTION_RECOVERY_BASE_POPULATION"].astype(bool)
        & epoch_bundle["GOOD_EPOCH"].astype(bool)
        & epoch_bundle["OOF_OFFSET_AVAILABLE"].astype(bool)
    ].copy()
    records: list[dict[str, object]] = []
    for group_id, group in work.groupby("GROUP_ID", sort=False):
        group = group.sort_values(["MJD", "EXPID"], kind="mergesort")
        if len(group) < 3:
            continue
        records.append(
            {
                "GROUP_ID": int(group_id),
                "MJD": pd.to_numeric(group["MJD"], errors="coerce").to_numpy(float),
                "NIGHT": group["NIGHT"].astype("string").to_numpy(),
                "ERROR": pd.to_numeric(
                    group["VRAD_ERROR_CALIBRATED"], errors="coerce"
                ).to_numpy(float),
                "FOLD": pd.to_numeric(group["PROGRAM_NIGHT_FOLD"], errors="coerce").to_numpy(int),
                "LABEL": group["PROGRAM_NIGHT_LABEL"].astype("string").to_numpy(),
                "PROGRAM": str(group["PROGRAM"].astype("string").str.upper().mode().iloc[0]),
                "MEDIAN_SN_R": float(
                    pd.to_numeric(group["SN_R"], errors="coerce").median()
                ),
                "MEDIAN_TEFF": float(
                    pd.to_numeric(group["TEFF"], errors="coerce").median()
                ),
                "MEDIAN_LOGG": float(
                    pd.to_numeric(group["LOGG"], errors="coerce").median()
                ),
                "MEDIAN_FEH": float(
                    pd.to_numeric(group["FEH"], errors="coerce").median()
                ),
            }
        )
    return records


def _numeric_bin(value: float, edges: tuple[float, ...], labels: tuple[str, ...]) -> str:
    if not np.isfinite(value):
        return "MISSING"
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1]


def _template_strata(template: dict[str, object]) -> dict[str, str]:
    mjd = np.asarray(template["MJD"], dtype=float)
    n_epochs = len(mjd)
    return {
        "PROGRAM": str(template["PROGRAM"]),
        "N_EPOCHS": "3" if n_epochs == 3 else "4" if n_epochs == 4 else "5+",
        "BASELINE_DAYS": _numeric_bin(
            float(np.ptp(mjd)), (30.0, 180.0, np.inf), ("LT30", "30_TO_180", "GE180")
        ),
        "MEDIAN_SN_R": _numeric_bin(
            float(template["MEDIAN_SN_R"]),
            (10.0, 30.0, np.inf),
            ("LT10", "10_TO_30", "GE30"),
        ),
        "MEDIAN_TEFF": _numeric_bin(
            float(template["MEDIAN_TEFF"]),
            (4500.0, 6500.0, np.inf),
            ("LT4500", "4500_TO_6500", "GE6500"),
        ),
        "MEDIAN_LOGG": _numeric_bin(
            float(template["MEDIAN_LOGG"]),
            (3.5, np.inf),
            ("LT3_5", "GE3_5"),
        ),
        "MEDIAN_FEH": _numeric_bin(
            float(template["MEDIAN_FEH"]),
            (-1.5, -0.5, np.inf),
            ("LT_MINUS1_5", "MINUS1_5_TO_MINUS0_5", "GE_MINUS0_5"),
        ),
    }


def _keplerian_signal(
    mjd: np.ndarray,
    semi_amplitude_kms: float,
    period_days: float,
    eccentricity: float,
    phase: float,
    argument_of_periastron: float,
) -> np.ndarray:
    mean_anomaly = (
        2.0 * np.pi * (mjd - np.min(mjd)) / period_days + phase
    ) % (2.0 * np.pi)
    eccentric_anomaly = mean_anomaly.copy()
    for _ in range(20):
        delta = (
            eccentric_anomaly
            - eccentricity * np.sin(eccentric_anomaly)
            - mean_anomaly
        ) / (1.0 - eccentricity * np.cos(eccentric_anomaly))
        eccentric_anomaly -= delta
        if np.max(np.abs(delta)) < 1e-12:
            break
    true_anomaly = 2.0 * np.arctan2(
        np.sqrt(1.0 + eccentricity) * np.sin(eccentric_anomaly / 2.0),
        np.sqrt(1.0 - eccentricity) * np.cos(eccentric_anomaly / 2.0),
    )
    return semi_amplitude_kms * (
        np.cos(true_anomaly + argument_of_periastron)
        + eccentricity * np.cos(argument_of_periastron)
    )


def run_injection_recovery(
    epoch_bundle: pd.DataFrame,
    offset_uncertainty: pd.DataFrame | None = None,
    amplitudes_kms: tuple[float, ...] = (0.0, 2.0, 5.0, 10.0, 20.0, 50.0),
    periods_days: tuple[float, ...] = (2.0, 10.0, 100.0, 1000.0),
    eccentricities: tuple[float, ...] = (0.0, 0.5, 0.8),
    n_trials_per_cell: int = 1000,
    student_t_df: float = 5.0,
    noise_models: tuple[str, ...] = ("GAUSSIAN", "STUDENT_T"),
    seed: int = 20260713,
) -> pd.DataFrame:
    if n_trials_per_cell < 1:
        raise ValueError("n_trials_per_cell must be positive")
    if student_t_df <= 2:
        raise ValueError("student_t_df must be greater than 2")
    if not eccentricities or any(value < 0 or value >= 1 for value in eccentricities):
        raise ValueError("eccentricities must be in [0, 1)")
    supported_noise_models = {"GAUSSIAN", "STUDENT_T"}
    unknown_noise_models = set(noise_models) - supported_noise_models
    if unknown_noise_models:
        raise ValueError(f"Unsupported noise models: {sorted(unknown_noise_models)}")
    templates = _template_records(epoch_bundle)
    if not templates:
        return pd.DataFrame()
    sigma_map: dict[tuple[int, str], float] = {}
    if offset_uncertainty is not None and not offset_uncertainty.empty:
        sigma_map = {
            (int(row.FOLD), str(row.LABEL)): float(row.OFFSET_STD_KMS)
            for row in offset_uncertainty.itertuples(index=False)
            if np.isfinite(row.OFFSET_STD_KMS)
        }
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    t_scale = np.sqrt(student_t_df / (student_t_df - 2.0))
    cells = [(0.0, np.nan, 0.0)] + [
        (float(amplitude), float(period), float(eccentricity))
        for amplitude in amplitudes_kms
        if amplitude > 0
        for period in periods_days
        for eccentricity in eccentricities
    ]
    for noise_model in noise_models:
        noise_label = (
            "GAUSSIAN_PLUS_BOOTSTRAP_OFFSET"
            if noise_model == "GAUSSIAN"
            else f"STUDENT_T_DF_{student_t_df:g}_PLUS_BOOTSTRAP_OFFSET"
        )
        for amplitude, period, eccentricity in cells:
            detected = 0
            by_stratum: dict[str, dict[str, list[int]]] = {}
            for _ in range(n_trials_per_cell):
                template = templates[int(rng.integers(0, len(templates)))]
                mjd = template["MJD"]
                errors = template["ERROR"]
                nights = template["NIGHT"]
                if noise_model == "GAUSSIAN":
                    noise = rng.normal(0.0, errors)
                else:
                    noise = rng.standard_t(student_t_df, len(mjd)) / t_scale * errors
                calibration = np.zeros(len(mjd), dtype=float)
                label_draws: dict[tuple[int, str], float] = {}
                for index, key in enumerate(zip(template["FOLD"], template["LABEL"])):
                    normalized_key = (int(key[0]), str(key[1]))
                    if normalized_key not in label_draws:
                        label_draws[normalized_key] = rng.normal(
                            0.0, sigma_map.get(normalized_key, 0.0)
                        )
                    calibration[index] = label_draws[normalized_key]
                if amplitude > 0:
                    signal = _keplerian_signal(
                        mjd,
                        semi_amplitude_kms=amplitude,
                        period_days=period,
                        eccentricity=eccentricity,
                        phase=rng.uniform(0.0, 2.0 * np.pi),
                        argument_of_periastron=rng.uniform(0.0, 2.0 * np.pi),
                    )
                else:
                    signal = np.zeros(len(mjd), dtype=float)
                is_detected = int(
                    bool(
                        _constant_rv_metrics(
                            signal + noise + calibration,
                            errors,
                            mjd,
                            nights,
                        )["is_outlier"]
                    )
                )
                detected += is_detected
                for stratum, value in _template_strata(template).items():
                    by_stratum.setdefault(stratum, {}).setdefault(value, []).append(
                        is_detected
                    )
            common = {
                "AMPLITUDE_KMS": amplitude,
                "PERIOD_DAYS": period,
                "ECCENTRICITY": eccentricity,
                "SIGNAL_MODEL": "NULL" if amplitude == 0 else "KEPLERIAN",
                "NOISE_MODEL": noise_label,
                "SEED": seed,
            }
            rows.append(
                {
                    "STRATUM": "ALL",
                    "STRATUM_VALUE": "ALL",
                    **common,
                    "N_TRIALS": n_trials_per_cell,
                    "N_DETECTED": detected,
                    "DETECTION_FRACTION": detected / n_trials_per_cell,
                }
            )
            for stratum, groups in sorted(by_stratum.items()):
                for value, outcomes in sorted(groups.items()):
                    rows.append(
                        {
                            "STRATUM": stratum,
                            "STRATUM_VALUE": value,
                            **common,
                            "N_TRIALS": len(outcomes),
                            "N_DETECTED": int(sum(outcomes)),
                            "DETECTION_FRACTION": float(np.mean(outcomes)),
                        }
                    )
    return pd.DataFrame(rows)
