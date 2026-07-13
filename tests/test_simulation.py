import numpy as np
import pandas as pd

from desi_rv_variables.simulation import _keplerian_signal, run_injection_recovery


def test_keplerian_signal_is_finite_for_declared_eccentricity_grid():
    mjd = np.linspace(0.0, 100.0, 64)

    for eccentricity in (0.0, 0.5, 0.8):
        signal = _keplerian_signal(
            mjd,
            semi_amplitude_kms=20.0,
            period_days=17.0,
            eccentricity=eccentricity,
            phase=0.3,
            argument_of_periastron=1.2,
        )
        assert np.isfinite(signal).all()
        assert np.ptp(signal) > 10.0


def test_injection_recovery_detects_large_signals_more_often_than_null():
    rows = []
    for group_id in range(20):
        for index, mjd in enumerate((1.0, 4.0, 8.0, 15.0)):
            rows.append(
                {
                    "GROUP_ID": group_id,
                    "MJD": mjd,
                    "NIGHT": 20210101 + index,
                    "EXPID": 1000 + group_id * 10 + index,
                    "PROGRAM": "BRIGHT",
                    "GOOD_EPOCH": True,
                    "OOF_OFFSET_AVAILABLE": True,
                    "VRAD_ERROR_CALIBRATED": 0.3,
                    "PROGRAM_NIGHT_FOLD": group_id % 5,
                    "PROGRAM_NIGHT_LABEL": f"BRIGHT:{20210101 + index}",
                    "IS_INJECTION_RECOVERY_BASE_POPULATION": True,
                    "SN_R": 20.0,
                    "TEFF": 5500.0,
                    "LOGG": 4.2,
                    "FEH": -1.0,
                }
            )
    result = run_injection_recovery(
        pd.DataFrame(rows),
        amplitudes_kms=(20.0,),
        periods_days=(10.0,),
        n_trials_per_cell=200,
        seed=7,
    )
    overall = result[result["STRATUM"].eq("ALL")].sort_values("AMPLITUDE_KMS")

    assert overall.iloc[-1]["DETECTION_FRACTION"] > overall.iloc[0]["DETECTION_FRACTION"]
    assert set(overall["SIGNAL_MODEL"]) == {"NULL", "KEPLERIAN"}
    assert set(overall["NOISE_MODEL"]) == {
        "GAUSSIAN_PLUS_BOOTSTRAP_OFFSET",
        "STUDENT_T_DF_5_PLUS_BOOTSTRAP_OFFSET",
    }
