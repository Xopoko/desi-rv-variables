from __future__ import annotations

import numpy as np
import pandas as pd

from desi_rv_variables.experiments import (
    ExperimentThresholds,
    acceleration_experiment,
    attach_offset_uncertainty,
    metal_poor_screen,
    repeated_high_amplitude_experiment,
)


def _summary(group_id: int = 101) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "GROUP_ID": [group_id],
            "SOURCE_ID": pd.Series([123456789012345678], dtype="Int64"),
            "GROUP_KIND": ["GAIA"],
            "PRIMARY_COHORT": [True],
            "WAS_STRICT_SCREENING_CANDIDATE": [True],
            "N_EPOCHS_GOOD_OOF": [4],
            "N_NIGHTS_GOOD_OOF": [4],
            "TIME_BASELINE_DAYS_OOF": [600.0],
            "BOOTSTRAP_ROBUST_95": [True],
            "LOO_ALL_OUTLIER": [True],
            "SIGNAL_ONLY_CROSS_PROGRAM": [False],
            "MEDIAN_FEH": [-2.3],
            "MEDIAN_TEFF": [5200.0],
            "MEDIAN_LOGG": [4.1],
            "OOF_OUTLIER_BOOTSTRAP_FRACTION": [1.0],
            "LOO_OUTLIER_FRACTION": [1.0],
        }
    )


def _epochs(
    values: list[float],
    nights: list[int],
    mjd: list[float],
    group_id: int = 101,
) -> pd.DataFrame:
    count = len(values)
    return pd.DataFrame(
        {
            "GROUP_ID": [group_id] * count,
            "PROGRAM": ["BRIGHT"] * count,
            "GOOD_EPOCH": [True] * count,
            "OOF_OFFSET_AVAILABLE": [True] * count,
            "VRAD_CORRECTED_OOF": values,
            "VRAD_ERROR_CALIBRATED": [1.0] * count,
            "OFFSET_STD_KMS": [0.1] * count,
            "PROGRAM_NIGHT_LABEL": [f"BRIGHT:{night}" for night in nights],
            "PROGRAM_NIGHT_FOLD": [0] * count,
            "NIGHT": nights,
            "MJD": mjd,
            "EXPID": np.arange(count, dtype=int),
            "FIBER": np.arange(count, dtype=int),
            "FEH": [-2.30, -2.25, -2.35, -2.30][:count],
            "TEFF": [5200.0, 5220.0, 5180.0, 5210.0][:count],
            "TARGET_RA": [123.4] * count,
            "TARGET_DEC": [-12.3] * count,
        }
    )


def test_attach_offset_uncertainty_preserves_large_gaia_id():
    epochs = _epochs([0.0, 1.0, 2.0, 3.0], [1, 2, 3, 4], [0.0, 1.0, 2.0, 3.0])
    epochs["SOURCE_ID"] = pd.Series([123456789012345678] * 4, dtype="Int64")
    uncertainty = pd.DataFrame(
        {
            "FOLD": [0, 0, 0, 0],
            "LABEL": ["BRIGHT:1", "BRIGHT:2", "BRIGHT:3", "BRIGHT:4"],
            "OFFSET_STD_KMS": [0.1] * 4,
            "N_BOOTSTRAPS": [50] * 4,
        }
    )
    result = attach_offset_uncertainty(
        epochs.drop(columns="OFFSET_STD_KMS"), uncertainty
    )
    assert result["SOURCE_ID"].astype("int64").nunique() == 1
    assert int(result["SOURCE_ID"].iloc[0]) == 123456789012345678
    assert np.allclose(result["TOTAL_EPOCH_ERROR_KMS"], np.hypot(1.0, 0.1))


def test_high_amplitude_requires_two_disjoint_pairs_spanning_three_nights():
    summary = _summary()
    detected, eligible = repeated_high_amplitude_experiment(
        summary,
        _epochs([0.0, 40.0, 0.0, 40.0], [1, 2, 1, 3], [0.0, 10.0, 20.0, 40.0]),
    )
    assert len(eligible) == 1
    assert bool(eligible.iloc[0]["DETECTED_HIGH_AMPLITUDE"])
    assert len(detected) == 1
    assert detected.iloc[0]["MIN_SUPPORT_DELTA_RV_KMS"] == 40.0

    rejected, _ = repeated_high_amplitude_experiment(
        summary,
        _epochs([0.0, 40.0, 0.0, 40.0], [1, 2, 1, 2], [0.0, 10.0, 20.0, 40.0]),
    )
    assert rejected.empty


def test_acceleration_recovers_leave_one_night_out_linear_signal():
    summary = _summary()
    epochs = _epochs([0.0, 20.0, 40.0, 60.0], [1, 2, 3, 4], [0.0, 200.0, 400.0, 600.0])
    sequences, candidates, null = acceleration_experiment(
        summary,
        epochs,
        n_permutations=8,
        seed=12,
    )
    assert len(sequences) == 1
    assert len(candidates) == 1
    assert candidates.iloc[0]["LOO_SAME_SIGN"]
    assert candidates.iloc[0]["SLOPE_KMS_PER_YEAR"] > 30.0
    assert len(null) == 8


def test_acceleration_empty_cohort_keeps_output_schema():
    summary = _summary()
    summary["PRIMARY_COHORT"] = False
    sequences, candidates, null = acceleration_experiment(
        summary,
        _epochs([0.0, 20.0, 40.0, 60.0], [1, 2, 3, 4], [0.0, 200.0, 400.0, 600.0]),
        n_permutations=2,
    )
    assert sequences.empty
    assert candidates.empty
    assert "GROUP_ID" in candidates.columns
    assert null["N_DETECTED_SOURCES"].eq(0).all()


def test_metal_poor_screen_requires_consistent_epoch_metallicity():
    summary = _summary()
    epochs = _epochs([0.0, 40.0, 0.0, 40.0], [1, 2, 3, 4], [0.0, 10.0, 20.0, 40.0])
    high_amplitude = pd.DataFrame({"GROUP_ID": [101]})
    acceleration = pd.DataFrame(columns=["GROUP_ID"])
    result = metal_poor_screen(summary, epochs, high_amplitude, acceleration)
    assert len(result) == 1
    assert int(result.iloc[0]["SOURCE_ID"]) == 123456789012345678

    inconsistent = epochs.copy()
    inconsistent["FEH"] = [-3.0, -2.0, -1.0, 0.0]
    rejected = metal_poor_screen(summary, inconsistent, high_amplitude, acceleration)
    assert rejected.empty


def test_custom_thresholds_can_disable_a_detection():
    thresholds = ExperimentThresholds(high_amplitude_min_delta_kms=100.0)
    detected, _ = repeated_high_amplitude_experiment(
        _summary(),
        _epochs([0.0, 40.0, 0.0, 40.0], [1, 2, 1, 3], [0.0, 10.0, 20.0, 40.0]),
        thresholds,
    )
    assert detected.empty
