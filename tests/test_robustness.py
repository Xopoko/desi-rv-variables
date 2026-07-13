import pandas as pd

from desi_rv_variables.robustness import candidate_robustness_table


def _epochs(group_id: int, values: list[float]) -> pd.DataFrame:
    count = len(values)
    return pd.DataFrame(
        {
            "GROUP_ID": [group_id] * count,
            "MJD": [1.0, 4.0, 8.0, 15.0][:count],
            "NIGHT": [20210101, 20210104, 20210108, 20210115][:count],
            "EXPID": list(range(100, 100 + count)),
            "PROGRAM": ["BRIGHT"] * count,
            "GOOD_EPOCH": [True] * count,
            "OOF_OFFSET_AVAILABLE": [True] * count,
            "VRAD_CORRECTED_OOF": values,
            "VRAD_ERROR_CALIBRATED": [1.0] * count,
        }
    )


def test_candidate_robustness_separates_persistent_and_single_epoch_signals():
    frame = pd.concat(
        [
            _epochs(1, [0.0, 20.0, 0.0, 20.0]),
            _epochs(2, [0.0, 0.0, 0.0, 20.0]),
        ],
        ignore_index=True,
    )

    result = candidate_robustness_table(frame, {1, 2}).set_index("GROUP_ID")

    assert bool(result.loc[1, "LOO_ALL_OUTLIER"])
    assert result.loc[1, "N_DISJOINT_SIGNIFICANT_PAIRS"] >= 2
    assert not bool(result.loc[2, "LOO_ALL_OUTLIER"])
    assert result.loc[2, "N_DISJOINT_SIGNIFICANT_PAIRS"] == 1
