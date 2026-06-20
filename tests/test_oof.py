import numpy as np
import pandas as pd

from desi_rv_variables.oof import (
    _cadence_matched_inspection_control_ids,
    apply_oof_program_night_offsets,
    load_program_night_offsets,
    program_night_labels,
    source_fold_ids,
    strict_candidate_transition_table,
    summarize_oof_sources,
    validate_parameters,
)


def test_program_night_label_matches_audit_shape():
    labels = program_night_labels(
        pd.Series(["backup", " BRIGHT ", None]),
        pd.Series([20210101, "20210102", None]),
    )
    assert labels.tolist() == ["BACKUP:20210101", "BRIGHT:20210102", "UNKNOWN:UNKNOWN"]


def test_fold_fixture_matches_pinned_hashing():
    group_ids = pd.Series([1, 101, 202, 303, 123456789012345678, -55], dtype="int64")
    assert source_fold_ids(group_ids, n_folds=5).tolist() == [1, 4, 3, 0, 0, 4]


def test_offset_loader_requires_component_and_expected_folds(tmp_path):
    missing_component = tmp_path / "missing.csv"
    pd.DataFrame({"FOLD": [0], "LABEL": ["BRIGHT:1"], "OFFSET_KMS": [0.1]}).to_csv(
        missing_component,
        index=False,
    )
    try:
        load_program_night_offsets(missing_component, n_folds=1)
    except ValueError as error:
        assert "COMPONENT" in str(error)
    else:
        raise AssertionError("missing COMPONENT should fail")

    wrong_folds = tmp_path / "wrong.csv"
    pd.DataFrame(
        {"FOLD": [0, 1], "LABEL": ["BRIGHT:1", "BRIGHT:2"], "OFFSET_KMS": [0.1, 0.2], "COMPONENT": [0, 0]}
    ).to_csv(wrong_folds, index=False)
    try:
        load_program_night_offsets(wrong_folds, n_folds=3)
    except ValueError as error:
        assert "do not match expected" in str(error)
    else:
        raise AssertionError("wrong fold set should fail")


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
        {"FOLD": [fold], "LABEL": ["BACKUP:20210101"], "OFFSET_KMS": [1.25], "COMPONENT": [0]}
    )
    corrected = apply_oof_program_night_offsets(frame, offsets)
    assert corrected["OOF_OFFSET_AVAILABLE"].iloc[0]
    assert corrected["VRAD_CORRECTED_OOF"].iloc[0] == 98.75
    assert corrected["PROGRAM_NIGHT_COMPONENT_OOF"].iloc[0] == 0


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
            "PROGRAM_NIGHT_COMPONENT_OOF": [0, 0, 0],
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


def test_cross_component_source_is_unscorable():
    frame = pd.DataFrame(
        {
            "GROUP_ID": [2, 2, 2],
            "GROUP_KIND": ["GAIA_SOURCE_ID"] * 3,
            "SOURCE_ID": [20, 20, 20],
            "TARGETID": [200, 200, 200],
            "MJD": [1.0, 5.0, 10.0],
            "NIGHT": [20210101, 20210105, 20210110],
            "PROGRAM": ["BRIGHT", "BRIGHT", "BRIGHT"],
            "GOOD_EPOCH": [True, True, True],
            "OOF_OFFSET_AVAILABLE": [True, True, True],
            "VRAD_ADOPTED": [0.0, 20.0, 0.0],
            "VRAD_ERR_ADOPTED": [1.0, 1.0, 1.0],
            "VRAD_CORRECTED_OOF": [0.0, 20.0, 0.0],
            "VRAD_ERROR_CALIBRATED": [1.0, 1.0, 1.0],
            "PROGRAM_NIGHT_COMPONENT_OOF": [0, 1, 0],
            "SN_R": [20.0, 21.0, 19.0],
            "TEFF": [5500.0, 5500.0, 5500.0],
            "LOGG": [4.3, 4.3, 4.3],
            "FEH": [-1.0, -1.0, -1.0],
        }
    )
    summary = summarize_oof_sources(frame)
    assert summary["N_OOF_COMPONENTS"].iloc[0] == 2
    assert not bool(summary["PRIMARY_COHORT"].iloc[0])
    assert summary["CLASSIFICATION_OOF"].iloc[0] == "CROSS_COMPONENT_UNSCORABLE"


def test_strict_transition_table_uses_primary_complete_case_only():
    summary = pd.DataFrame(
        {
            "GROUP_ID": [1, 2, 3],
            "PRIMARY_COHORT": [True, True, False],
            "CLASSIFICATION_BEFORE": ["CONSTANT_RV_OUTLIER", "CONSTANT_RV_OUTLIER", "UNSCORABLE"],
            "CLASSIFICATION_OOF": ["STABLE_LIKE", "CONSTANT_RV_OUTLIER", "CROSS_COMPONENT_UNSCORABLE"],
            "OOF_SCORING_STATUS": [
                "COMPLETE_SINGLE_COMPONENT",
                "COMPLETE_SINGLE_COMPONENT",
                "CROSS_COMPONENT_UNSCORABLE",
            ],
        }
    )
    table = strict_candidate_transition_table(summary, {1, 2, 3, 4})
    counts = {
        (row.BEFORE_CLASS, row.OOF_CLASS): row.N
        for row in table.itertuples(index=False)
    }
    assert counts[("OUTLIER", "STABLE")] == 1
    assert counts[("OUTLIER", "OUTLIER")] == 1
    assert counts[("UNSCORABLE", "CROSS_COMPONENT_UNSCORABLE")] == 1
    assert counts[("UNSCORABLE", "MISSING_FROM_SUMMARY")] == 1


def test_control_ratio_zero_returns_no_controls():
    validate_parameters(min_sn_r=5.0, n_folds=5, control_ratio=0.0, injection_base_ratio=0.0)
    summary = pd.DataFrame(
        {
            "GROUP_ID": [1, 2],
            "PRIMARY_COHORT": [True, True],
            "CLASSIFICATION_BEFORE": ["CONSTANT_RV_OUTLIER", "STABLE_LIKE"],
            "CLASSIFICATION_OOF": ["CONSTANT_RV_OUTLIER", "STABLE_LIKE"],
            "DOMINANT_PROGRAM": ["BRIGHT", "BRIGHT"],
            "N_EPOCHS_GOOD_OOF": [3, 3],
            "N_NIGHTS_GOOD_OOF": [3, 3],
            "TIME_BASELINE_DAYS_OOF": [10.0, 10.0],
        }
    )
    assert _cadence_matched_inspection_control_ids(summary, {1}, ratio=0.0) == set()
