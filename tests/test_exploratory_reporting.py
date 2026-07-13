from __future__ import annotations

import pandas as pd

from desi_rv_variables.exploratory_reporting import (
    _acceleration_gate_summary,
    _external_context,
)


def test_external_context_keeps_detected_and_nondetected_denominators_separate():
    frame = pd.DataFrame(
        {
            "IN_HIGH_AMPLITUDE": pd.Series(
                [True, True, False, False, False], dtype="boolean"
            ),
            "NO_DECLARED_CATALOGUE_MATCH": pd.Series(
                [False, True, False, True, True], dtype="boolean"
            ),
        }
    )
    result = _external_context(frame).set_index("COHORT")
    assert result.at["DETECTED", "N_SOURCES"] == 2
    assert result.at["DETECTED", "DECLARED_MATCH_FRACTION"] == 0.5
    assert result.at["ELIGIBLE_NOT_DETECTED", "N_SOURCES"] == 3
    assert result.at["ELIGIBLE_NOT_DETECTED", "DECLARED_MATCH_FRACTION"] == 1 / 3


def test_acceleration_gate_summary_does_not_turn_partial_gates_into_detection():
    sequences = pd.DataFrame(
        {
            "SLOPE_SIGMA": [8.0, 2.0],
            "DELTA_CHI2": [64.0, 4.0],
            "END_TO_END_KMS": [25.0, 10.0],
            "LINEAR_REDUCED_CHI2": [20.0, 1.0],
            "MIN_LOO_SLOPE_SIGMA": [1.0, 4.0],
        }
    )
    result = _acceleration_gate_summary(sequences).set_index("GATE")
    assert result.at["slope_sigma", "N_PASS"] == 1
    assert result.at["linear_reduced_chi2", "N_PASS"] == 1
    assert result.at["leave_one_night_out", "N_PASS"] == 1
