import numpy as np
import pandas as pd

from desi_rv_variables.oof import (
    apply_oof_program_night_offsets,
    program_night_labels,
    source_fold_ids,
    summarize_oof_sources,
)


def test_program_night_label_matches_audit_shape():
    labels = program_night_labels(
        pd.Series(["backup", " BRIGHT ", None]),
        pd.Series([20210101, "20210102", None]),
    )
    assert labels.tolist() == ["BACKUP:20210101", "BRIGHT:20210102", "UNKNOWN:UNKNOWN"]


def test_oof_offset_is_subtracted_for_matching_fold_label():
    frame = pd.DataFrame(
        {
            "GROUP_ID": [101],
            "GROUP_KIND": ["GAIA_SOURCE_ID"],
            "SOURCE_ID": [123456789012345678],
            "TARGETID": [55],
            "PROGRAM": ["BACKUP"],
            "NIGHT": [20210101],
            "VRAD_ADOPTED": [100.0],
            "VRAD_ERR_ADOPTED": [2.1],
        }
    )
    fold = int(source_fold_ids(frame["GROUP_ID"], 5).iloc[0])
    offsets = pd.DataFrame(
        {"FOLD": [fold], "LABEL": ["BACKUP:20210101"], "OFFSET_KMS": [1.25]}
    )
    corrected = apply_oof_program_night_offsets(frame, offsets)
    assert corrected["OOF_OFFSET_AVAILABLE"].iloc[0]
    assert corrected["VRAD_CORRECTED_OOF"].iloc[0] == 98.75


def test_oof_source_summary_flags_persistent_outlier():
    frame = pd.DataFrame(
        {
            "GROUP_ID": [1, 1, 1],
            "GROUP_KIND": ["GAIA_SOURCE_ID"] * 3,
            "SOURCE_ID": [10, 10, 10],
            "TARGETID": [100, 100, 100],
            "MJD": [1.0, 5.0, 10.0],
            "NIGHT": [20210101, 20210105, 20210110],
            "PROGRAM": ["BRIGHT", "BRIGHT", "BRIGHT"],
            "GOOD_EPOCH": [True, True, True],
            "OOF_OFFSET_AVAILABLE": [True, True, True],
            "VRAD_ADOPTED": [0.0, 0.0, 0.0],
            "VRAD_ERR_ADOPTED": [1.0, 1.0, 1.0],
            "VRAD_CORRECTED_OOF": [0.0, 20.0, 0.0],
            "VRAD_ERROR_CALIBRATED": [1.0, 1.0, 1.0],
            "SN_R": [20.0, 21.0, 19.0],
            "TEFF": [5500.0, 5500.0, 5500.0],
            "LOGG": [4.3, 4.3, 4.3],
            "FEH": [-1.0, -1.0, -1.0],
        }
    )
    summary = summarize_oof_sources(frame)
    assert len(summary) == 1
    assert summary["N_EPOCHS_GOOD_OOF"].iloc[0] == 3
    assert summary["CLASSIFICATION_OOF"].iloc[0] == "CONSTANT_RV_OUTLIER"
    assert np.isfinite(summary["LOG_P_CONST_OOF"].iloc[0])

