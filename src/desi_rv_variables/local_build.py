from __future__ import annotations

import gzip
import os
import shutil
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .oof import (
    DEFAULT_BACKUP_CORRECTION_MD5,
    EXPECTED_AUDIT_MODEL_SHA256_BY_NAME,
    STRICT_CANDIDATES_GZ_SHA256,
    STRICT_CANDIDATES_SHA256,
    _sha256,
    build_bundles,
)


DEFAULT_STRICT_CANDIDATES_URL = (
    "https://github.com/Xopoko/desi-rv-variables/releases/download/"
    "v0.2.0/candidate_sources_strict.csv.gz"
)
DEFAULT_AUDIT_MODEL_ASSET_BASE_URL = (
    "https://github.com/Xopoko/desi-rv-audit/releases/download/v0.3.0"
)
EXPECTED_AUDIT_MODEL_GZIP_SHA256_BY_NAME = {
    "program_night_permutation_offsets.csv": "38bb2f2d3905482591b7638717a498da80a14c3408c4b15d23f0e36dd71db13d",
    "program_night_permutation_exposure_map.csv": "80bade3799731beaa82902a92efe35113d625613939a7bb067794b370c7c9663",
    "program_night_bootstrap_offsets.csv": "72544b6d11dbc9edd7cfa76173f61f5692199a669f4a7b3d437d64ce8874a12d",
}


@dataclass(frozen=True)
class LocalBuildPaths:
    project_root: Path
    audit_data_dir: Path
    audit_artifact_dir: Path
    strict_candidates: Path
    output_dir: Path
    public_report_dir: Path


def _path_from_value(value: str | Path | None, default: Path) -> Path:
    if value is None:
        return default
    return Path(value).expanduser()


def resolve_local_build_paths(
    project_root: str | Path | None = None,
    audit_data_dir: str | Path | None = None,
    audit_artifact_dir: str | Path | None = None,
    strict_candidates: str | Path | None = None,
    output_dir: str | Path | None = None,
    public_report_dir: str | Path | None = None,
) -> LocalBuildPaths:
    root = Path(project_root or os.environ.get("DESI_RV_VARIABLES_PROJECT_ROOT") or Path.cwd())
    root = root.expanduser().resolve()
    projects_root = root.parent
    return LocalBuildPaths(
        project_root=root,
        audit_data_dir=_path_from_value(
            audit_data_dir or os.environ.get("DESI_RV_AUDIT_DATA_DIR"),
            projects_root / "desi-rv-audit" / "data",
        ),
        audit_artifact_dir=_path_from_value(
            audit_artifact_dir or os.environ.get("DESI_RV_AUDIT_ARTIFACT_DIR"),
            projects_root / "desi-rv-audit" / "reports" / "program_night_artifacts",
        ),
        strict_candidates=_path_from_value(
            strict_candidates or os.environ.get("DESI_RV_STRICT_CANDIDATES"),
            root / "artifacts" / "inputs" / "candidate_sources_strict.csv",
        ),
        output_dir=_path_from_value(output_dir, root / "artifacts"),
        public_report_dir=_path_from_value(public_report_dir, root / "reports"),
    )


def _download(url: str, target: Path, attempts: int = 3) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "desi-rv-variables"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temp.open(
                "wb"
            ) as handle:
                shutil.copyfileobj(response, handle)
            temp.replace(target)
            return
        except Exception:
            temp.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            time.sleep(float(attempt))


def ensure_strict_candidates(
    path: str | Path,
    url: str | None = None,
    expected_sha256: str = STRICT_CANDIDATES_SHA256,
    expected_gz_sha256: str = STRICT_CANDIDATES_GZ_SHA256,
    force: bool = False,
) -> Path:
    target = Path(path).expanduser()
    if target.exists() and not force:
        actual = _sha256(target)
        if actual != expected_sha256:
            raise ValueError(
                f"strict candidates SHA-256 mismatch for {target}: "
                f"expected {expected_sha256}, got {actual}"
            )
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    gz_path = target.with_name(target.name + ".gz")
    _download(url or DEFAULT_STRICT_CANDIDATES_URL, gz_path)
    actual_gz = _sha256(gz_path)
    if actual_gz != expected_gz_sha256:
        raise ValueError(
            f"downloaded strict candidates gzip SHA-256 mismatch for {gz_path}: "
            f"expected {expected_gz_sha256}, got {actual_gz}"
        )

    temp = target.with_name(target.name + ".tmp")
    with gzip.open(gz_path, "rb") as source, temp.open("wb") as destination:
        shutil.copyfileobj(source, destination)
    temp.replace(target)

    actual = _sha256(target)
    if actual != expected_sha256:
        raise ValueError(
            f"strict candidates SHA-256 mismatch for {target}: "
            f"expected {expected_sha256}, got {actual}"
        )
    return target


def ensure_audit_model_artifacts(
    artifact_dir: str | Path,
    base_url: str = DEFAULT_AUDIT_MODEL_ASSET_BASE_URL,
    expected_sha256_by_name: dict[str, str] = EXPECTED_AUDIT_MODEL_SHA256_BY_NAME,
    expected_gzip_sha256_by_name: dict[str, str] = EXPECTED_AUDIT_MODEL_GZIP_SHA256_BY_NAME,
    force: bool = False,
) -> list[Path]:
    artifact_dir = Path(artifact_dir).expanduser()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    for name, expected_gzip_sha256 in expected_gzip_sha256_by_name.items():
        expected_sha256 = expected_sha256_by_name[name]
        target = artifact_dir / name
        if target.exists() and not force:
            actual = _sha256(target)
            if actual != expected_sha256:
                raise ValueError(
                    f"audit model SHA-256 mismatch for {target}: "
                    f"expected {expected_sha256}, got {actual}"
                )
            results.append(target)
            continue

        gzip_path = artifact_dir / f"{name}.gz"
        _download(f"{base_url.rstrip('/')}/{name}.gz", gzip_path)
        actual_gzip = _sha256(gzip_path)
        if actual_gzip != expected_gzip_sha256:
            raise ValueError(
                f"audit model gzip SHA-256 mismatch for {gzip_path}: "
                f"expected {expected_gzip_sha256}, got {actual_gzip}"
            )
        temp = target.with_name(target.name + ".tmp")
        with gzip.open(gzip_path, "rb") as source, temp.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        temp.replace(target)
        actual = _sha256(target)
        if actual != expected_sha256:
            raise ValueError(
                f"audit model SHA-256 mismatch for {target}: "
                f"expected {expected_sha256}, got {actual}"
            )
        results.append(target)
    return results


def build_local_bundles(
    project_root: str | Path | None = None,
    audit_data_dir: str | Path | None = None,
    audit_artifact_dir: str | Path | None = None,
    strict_candidates: str | Path | None = None,
    strict_candidates_url: str | None = None,
    output_dir: str | Path | None = None,
    public_report_dir: str | Path | None = None,
    min_sn_r: float = 5.0,
    n_folds: int = 5,
    control_ratio: float = 1.0,
    injection_base_ratio: float = 1.0,
    n_candidate_shuffles: int = 0,
    candidate_shuffle_seed: int = 20260620,
    injection_trials_per_cell: int = 1000,
    injection_seed: int = 20260713,
    backup_correction_md5: str = DEFAULT_BACKUP_CORRECTION_MD5,
    strict_candidates_sha256: str = STRICT_CANDIDATES_SHA256,
    strict_candidates_gz_sha256: str = STRICT_CANDIDATES_GZ_SHA256,
    check_frozen_input_hashes: bool = True,
    check_offsets_git_commit: bool = True,
    force_strict_candidates_download: bool = False,
    force_audit_model_download: bool = False,
):
    paths = resolve_local_build_paths(
        project_root=project_root,
        audit_data_dir=audit_data_dir,
        audit_artifact_dir=audit_artifact_dir,
        strict_candidates=strict_candidates,
        output_dir=output_dir,
        public_report_dir=public_report_dir,
    )
    strict_path = ensure_strict_candidates(
        paths.strict_candidates,
        url=(
            strict_candidates_url
            or os.environ.get("DESI_RV_STRICT_CANDIDATES_URL")
            or DEFAULT_STRICT_CANDIDATES_URL
        ),
        expected_sha256=strict_candidates_sha256,
        expected_gz_sha256=strict_candidates_gz_sha256,
        force=force_strict_candidates_download,
    )
    if check_frozen_input_hashes:
        ensure_audit_model_artifacts(
            paths.audit_artifact_dir,
            force=force_audit_model_download,
        )
    fits_paths = [
        paths.audit_data_dir / "desi_main" / "rvpix_exp-main-backup.fits",
        paths.audit_data_dir / "desi_main" / "rvpix_exp-main-bright.fits",
        paths.audit_data_dir / "desi_main" / "rvpix_exp-main-dark.fits",
    ]
    return build_bundles(
        fits_paths=fits_paths,
        backup_correction_path=paths.audit_data_dir
        / "desi_corrections"
        / "backup_correction.fits",
        offsets_path=paths.audit_artifact_dir / "diagnostic_offsets_program_night.csv",
        permutation_offsets_path=paths.audit_artifact_dir
        / "program_night_permutation_offsets.csv",
        permutation_exposure_map_path=paths.audit_artifact_dir
        / "program_night_permutation_exposure_map.csv",
        bootstrap_offsets_path=paths.audit_artifact_dir
        / "program_night_bootstrap_offsets.csv",
        strict_candidates_path=strict_path,
        output_dir=paths.output_dir,
        public_report_dir=paths.public_report_dir,
        min_sn_r=min_sn_r,
        n_folds=n_folds,
        control_ratio=control_ratio,
        injection_base_ratio=injection_base_ratio,
        n_candidate_shuffles=n_candidate_shuffles,
        candidate_shuffle_seed=candidate_shuffle_seed,
        injection_trials_per_cell=injection_trials_per_cell,
        injection_seed=injection_seed,
        backup_correction_md5=backup_correction_md5,
        strict_candidates_sha256=strict_candidates_sha256,
        check_frozen_input_hashes=check_frozen_input_hashes,
        check_offsets_git_commit=check_offsets_git_commit,
        allow_empty_candidates=False,
    )
