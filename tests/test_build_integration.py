from pathlib import Path

import pandas as pd

from desi_rv_variables.oof import build_bundles


def test_build_bundles_writes_uncertainty_null_and_selection_outputs(tmp_path: Path):
    rows = []
    nights = [20210101, 20210104, 20210108, 20210115]
    for group_id, values in ((1, [0.0, 20.0, 0.0, 20.0]), (2, [0.0, 0.0, 0.0, 0.0])):
        for index, (night, value) in enumerate(zip(nights, values)):
            rows.append(
                {
                    "TARGETID": group_id,
                    "SOURCE_ID": group_id,
                    "VRAD": value,
                    "VRAD_ERR": 1.0,
                    "SN_R": 20.0,
                    "RVS_WARN": 0,
                    "SUCCESS": True,
                    "EXPID": group_id * 100 + index,
                    "FIBER": index,
                    "MJD": float(index * 4 + 1),
                    "NIGHT": night,
                    "FIBERSTATUS": 0,
                    "TILEID": 10,
                    "VSINI": 1.0,
                    "RR_SPECTYPE": "STAR",
                    "SURVEY": "MAIN",
                    "PROGRAM": "BRIGHT",
                    "TEFF": 5500.0,
                    "LOGG": 4.3,
                    "FEH": -1.0,
                }
            )
    epochs_path = tmp_path / "epochs.csv"
    pd.DataFrame(rows).to_csv(epochs_path, index=False)
    correction_path = tmp_path / "correction.csv"
    pd.DataFrame({"TARGETID": [999], "VRAD_OFFSET": [0.0]}).to_csv(
        correction_path, index=False
    )
    candidate_path = tmp_path / "candidates.csv"
    pd.DataFrame({"GROUP_ID": [1]}).to_csv(candidate_path, index=False)

    labels = [f"BRIGHT:{night}" for night in nights]
    offsets = pd.DataFrame(
        [
            {"FOLD": fold, "LABEL": label, "OFFSET_KMS": 0.0, "COMPONENT": 0}
            for fold in range(5)
            for label in labels
        ]
    )
    offsets_path = tmp_path / "offsets.csv"
    offsets.to_csv(offsets_path, index=False)

    permutation_offsets = offsets.assign(PERMUTATION=0)
    permutation_offsets["LABEL"] = permutation_offsets.groupby("FOLD").cumcount().map(
        lambda index: f"BRIGHT:FAKE{index}"
    )
    permutation_offsets_path = tmp_path / "permutation_offsets.csv"
    permutation_offsets.to_csv(permutation_offsets_path, index=False)
    exposure_rows = []
    for row in rows:
        exposure_rows.append(
            {
                "PERMUTATION": 0,
                "EXPOSURE_KEY": f"MAIN|BRIGHT|{row['EXPID']}",
                "SHUFFLED_NIGHT": f"FAKE{nights.index(row['NIGHT'])}",
            }
        )
    exposure_map_path = tmp_path / "exposure_map.csv"
    pd.DataFrame(exposure_rows).to_csv(exposure_map_path, index=False)

    bootstrap_offsets = pd.concat(
        [offsets.assign(BOOTSTRAP=bootstrap) for bootstrap in (0, 1)],
        ignore_index=True,
    )
    bootstrap_offsets_path = tmp_path / "bootstrap_offsets.csv"
    bootstrap_offsets.to_csv(bootstrap_offsets_path, index=False)

    output_dir = tmp_path / "artifacts"
    public_dir = tmp_path / "reports"
    result = build_bundles(
        fits_paths=[epochs_path],
        backup_correction_path=correction_path,
        offsets_path=offsets_path,
        permutation_offsets_path=permutation_offsets_path,
        permutation_exposure_map_path=exposure_map_path,
        bootstrap_offsets_path=bootstrap_offsets_path,
        strict_candidates_path=candidate_path,
        output_dir=output_dir,
        public_report_dir=public_dir,
        control_ratio=1.0,
        injection_base_ratio=1.0,
        injection_trials_per_cell=10,
        backup_correction_md5="",
        strict_candidates_sha256=None,
        check_frozen_input_hashes=False,
        check_offsets_git_commit=False,
    )

    assert len(result.source_summary) == 2
    assert (output_dir / "full_pipeline_permutation_null.csv").exists()
    assert (output_dir / "candidate_bootstrap_stability.parquet").exists()
    assert (output_dir / "candidate_robustness.parquet").exists()
    assert (output_dir / "injection_recovery.csv").exists()
    assert result.manifest["full_pipeline_permutation_null_summary"]["n_permutations"] == 1
    assert "n_robust_diagnostic_subset" in result.manifest
    assert (public_dir / "build_manifest_public.json").exists()
    report = (public_dir / "bundle_build_summary.md").read_text(encoding="utf-8")
    assert "Full-Pipeline Null Control" in report
    assert "Automated robust diagnostic subset" in report
    assert str(tmp_path) not in report
    assert str(tmp_path) not in (public_dir / "build_manifest_public.json").read_text(
        encoding="utf-8"
    )
