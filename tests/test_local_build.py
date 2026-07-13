import gzip
import hashlib
from pathlib import Path

from desi_rv_variables.local_build import (
    build_local_bundles,
    ensure_audit_model_artifacts,
    ensure_strict_candidates,
    resolve_local_build_paths,
)


def _write_gzip(path: Path, payload: bytes) -> None:
    with gzip.open(path, "wb") as handle:
        handle.write(payload)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_ensure_strict_candidates_downloads_decompresses_and_validates(tmp_path):
    csv_payload = b"GROUP_ID\n101\n202\n"
    gz_path = tmp_path / "candidate_sources_strict.csv.gz"
    _write_gzip(gz_path, csv_payload)
    target = tmp_path / "inputs" / "candidate_sources_strict.csv"

    result = ensure_strict_candidates(
        target,
        url=gz_path.as_uri(),
        expected_sha256=_sha256_bytes(csv_payload),
        expected_gz_sha256=_sha256_file(gz_path),
    )

    assert result == target
    assert target.read_bytes() == csv_payload


def test_ensure_audit_model_artifacts_downloads_and_validates(tmp_path):
    source_dir = tmp_path / "release"
    source_dir.mkdir()
    payload = b"FOLD,LABEL,OFFSET_KMS,COMPONENT\n0,BRIGHT:A,0.1,0\n"
    name = "program_night_bootstrap_offsets.csv"
    gzip_path = source_dir / f"{name}.gz"
    _write_gzip(gzip_path, payload)

    results = ensure_audit_model_artifacts(
        tmp_path / "artifacts",
        base_url=source_dir.as_uri(),
        expected_sha256_by_name={name: _sha256_bytes(payload)},
        expected_gzip_sha256_by_name={name: _sha256_file(gzip_path)},
    )

    assert len(results) == 1
    assert results[0].read_bytes() == payload


def test_resolve_local_build_paths_uses_env_defaults(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    audit_data_dir = tmp_path / "audit-data"
    audit_artifacts = tmp_path / "audit-artifacts"
    strict_candidates = tmp_path / "strict.csv"
    monkeypatch.setenv("DESI_RV_AUDIT_DATA_DIR", str(audit_data_dir))
    monkeypatch.setenv("DESI_RV_AUDIT_ARTIFACT_DIR", str(audit_artifacts))
    monkeypatch.setenv("DESI_RV_STRICT_CANDIDATES", str(strict_candidates))

    paths = resolve_local_build_paths(project_root=project_root)

    assert paths.project_root == project_root.resolve()
    assert paths.audit_data_dir == audit_data_dir
    assert paths.audit_artifact_dir == audit_artifacts
    assert paths.strict_candidates == strict_candidates
    assert paths.output_dir == project_root / "artifacts"
    assert paths.public_report_dir == project_root / "reports"


def test_build_local_bundles_ensures_candidates_and_calls_core_builder(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    audit_data_dir = tmp_path / "audit" / "data"
    audit_artifact_dir = tmp_path / "audit" / "reports" / "program_night_artifacts"
    (audit_data_dir / "desi_main").mkdir(parents=True)
    (audit_data_dir / "desi_corrections").mkdir(parents=True)
    audit_artifact_dir.mkdir(parents=True)
    for name in (
        "rvpix_exp-main-backup.fits",
        "rvpix_exp-main-bright.fits",
        "rvpix_exp-main-dark.fits",
    ):
        (audit_data_dir / "desi_main" / name).write_text("placeholder", encoding="utf-8")
    (audit_data_dir / "desi_corrections" / "backup_correction.fits").write_text(
        "placeholder",
        encoding="utf-8",
    )
    (audit_artifact_dir / "diagnostic_offsets_program_night.csv").write_text(
        "placeholder",
        encoding="utf-8",
    )
    for name in (
        "program_night_permutation_offsets.csv",
        "program_night_permutation_exposure_map.csv",
        "program_night_bootstrap_offsets.csv",
    ):
        (audit_artifact_dir / name).write_text("placeholder", encoding="utf-8")

    csv_payload = b"GROUP_ID\n101\n"
    gz_path = tmp_path / "candidate_sources_strict.csv.gz"
    _write_gzip(gz_path, csv_payload)
    captured = {}

    def fake_build_bundles(**kwargs):
        captured.update(kwargs)
        return "sentinel-result"

    monkeypatch.setattr("desi_rv_variables.local_build.build_bundles", fake_build_bundles)

    result = build_local_bundles(
        project_root=project_root,
        audit_data_dir=audit_data_dir,
        audit_artifact_dir=audit_artifact_dir,
        strict_candidates_url=gz_path.as_uri(),
        strict_candidates_sha256=_sha256_bytes(csv_payload),
        strict_candidates_gz_sha256=_sha256_file(gz_path),
        n_candidate_shuffles=2,
        check_frozen_input_hashes=False,
    )

    strict_candidates = project_root / "artifacts" / "inputs" / "candidate_sources_strict.csv"
    assert result == "sentinel-result"
    assert strict_candidates.read_bytes() == csv_payload
    assert captured["fits_paths"] == [
        audit_data_dir / "desi_main" / "rvpix_exp-main-backup.fits",
        audit_data_dir / "desi_main" / "rvpix_exp-main-bright.fits",
        audit_data_dir / "desi_main" / "rvpix_exp-main-dark.fits",
    ]
    assert captured["backup_correction_path"] == (
        audit_data_dir / "desi_corrections" / "backup_correction.fits"
    )
    assert captured["offsets_path"] == audit_artifact_dir / "diagnostic_offsets_program_night.csv"
    assert captured["permutation_offsets_path"] == (
        audit_artifact_dir / "program_night_permutation_offsets.csv"
    )
    assert captured["permutation_exposure_map_path"] == (
        audit_artifact_dir / "program_night_permutation_exposure_map.csv"
    )
    assert captured["bootstrap_offsets_path"] == (
        audit_artifact_dir / "program_night_bootstrap_offsets.csv"
    )
    assert captured["strict_candidates_path"] == strict_candidates
    assert captured["output_dir"] == project_root / "artifacts"
    assert captured["public_report_dir"] == project_root / "reports"
    assert captured["n_candidate_shuffles"] == 2
