from __future__ import annotations

import argparse

from .oof import (
    DEFAULT_BACKUP_CORRECTION_MD5,
    STRICT_CANDIDATES_GZ_SHA256,
    STRICT_CANDIDATES_SHA256,
    build_bundles,
)
from .local_build import build_local_bundles, ensure_strict_candidates, resolve_local_build_paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DESI RV variable candidate bundle tools")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-bundles", help="Build OOF source summary and candidate epoch bundle")
    build.add_argument("fits", nargs="+", help="DESI rvpix_exp FITS files")
    build.add_argument("--backup-correction", required=True)
    build.add_argument("--offsets", required=True)
    build.add_argument("--permutation-offsets")
    build.add_argument("--permutation-exposure-map")
    build.add_argument("--bootstrap-offsets")
    build.add_argument("--strict-candidates")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--public-report-dir")
    build.add_argument("--min-sn-r", type=float, default=5.0)
    build.add_argument("--n-folds", type=int, default=5)
    build.add_argument("--control-ratio", type=float, default=1.0)
    build.add_argument("--injection-base-ratio", type=float, default=1.0)
    build.add_argument("--n-candidate-shuffles", type=int, default=0)
    build.add_argument("--candidate-shuffle-seed", type=int, default=20260620)
    build.add_argument("--injection-trials-per-cell", type=int, default=1000)
    build.add_argument("--injection-seed", type=int, default=20260713)
    build.add_argument(
        "--backup-correction-md5",
        default=DEFAULT_BACKUP_CORRECTION_MD5,
    )
    build.add_argument(
        "--strict-candidates-sha256",
        default=STRICT_CANDIDATES_SHA256,
    )
    build.add_argument("--skip-frozen-input-hash-checks", action="store_true")
    build.add_argument("--skip-offsets-git-commit-check", action="store_true")
    build.add_argument("--allow-empty-candidates", action="store_true")

    download = sub.add_parser(
        "download-strict-candidates",
        help="Download and verify the frozen strict candidate input",
    )
    download.add_argument("--project-root")
    download.add_argument("--output")
    download.add_argument("--url")
    download.add_argument("--sha256", default=STRICT_CANDIDATES_SHA256)
    download.add_argument("--gz-sha256", default=STRICT_CANDIDATES_GZ_SHA256)
    download.add_argument("--force", action="store_true")

    local = sub.add_parser(
        "build-local-bundles",
        help="Build local bundles using portable defaults for this checkout",
    )
    local.add_argument("--project-root")
    local.add_argument("--audit-data-dir")
    local.add_argument("--audit-artifact-dir")
    local.add_argument("--strict-candidates")
    local.add_argument("--strict-candidates-url")
    local.add_argument("--output-dir")
    local.add_argument("--public-report-dir")
    local.add_argument("--min-sn-r", type=float, default=5.0)
    local.add_argument("--n-folds", type=int, default=5)
    local.add_argument("--control-ratio", type=float, default=1.0)
    local.add_argument("--injection-base-ratio", type=float, default=1.0)
    local.add_argument("--n-candidate-shuffles", type=int, default=0)
    local.add_argument("--candidate-shuffle-seed", type=int, default=20260620)
    local.add_argument("--injection-trials-per-cell", type=int, default=1000)
    local.add_argument("--injection-seed", type=int, default=20260713)
    local.add_argument("--backup-correction-md5", default=DEFAULT_BACKUP_CORRECTION_MD5)
    local.add_argument("--strict-candidates-sha256", default=STRICT_CANDIDATES_SHA256)
    local.add_argument("--strict-candidates-gz-sha256", default=STRICT_CANDIDATES_GZ_SHA256)
    local.add_argument("--force-strict-candidates-download", action="store_true")
    local.add_argument("--force-audit-model-download", action="store_true")
    local.add_argument("--skip-frozen-input-hash-checks", action="store_true")
    local.add_argument("--skip-offsets-git-commit-check", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "build-bundles":
        result = build_bundles(
            fits_paths=args.fits,
            backup_correction_path=args.backup_correction,
            offsets_path=args.offsets,
            permutation_offsets_path=args.permutation_offsets,
            permutation_exposure_map_path=args.permutation_exposure_map,
            bootstrap_offsets_path=args.bootstrap_offsets,
            output_dir=args.output_dir,
            strict_candidates_path=args.strict_candidates,
            public_report_dir=args.public_report_dir,
            min_sn_r=args.min_sn_r,
            n_folds=args.n_folds,
            control_ratio=args.control_ratio,
            injection_base_ratio=args.injection_base_ratio,
            n_candidate_shuffles=args.n_candidate_shuffles,
            candidate_shuffle_seed=args.candidate_shuffle_seed,
            injection_trials_per_cell=args.injection_trials_per_cell,
            injection_seed=args.injection_seed,
            backup_correction_md5=args.backup_correction_md5,
            strict_candidates_sha256=args.strict_candidates_sha256,
            check_frozen_input_hashes=not args.skip_frozen_input_hash_checks,
            check_offsets_git_commit=not args.skip_offsets_git_commit_check,
            allow_empty_candidates=args.allow_empty_candidates,
        )
        print(f"source_summary_oof rows: {len(result.source_summary)}")
        print(f"candidate_epoch_bundle rows: {len(result.epoch_bundle)}")
        print(f"manifest: {result.manifest}")
    elif args.command == "download-strict-candidates":
        paths = resolve_local_build_paths(project_root=args.project_root)
        output = args.output or paths.strict_candidates
        path = ensure_strict_candidates(
            output,
            url=args.url,
            expected_sha256=args.sha256,
            expected_gz_sha256=args.gz_sha256,
            force=args.force,
        )
        print(f"strict candidates: {path}")
    elif args.command == "build-local-bundles":
        result = build_local_bundles(
            project_root=args.project_root,
            audit_data_dir=args.audit_data_dir,
            audit_artifact_dir=args.audit_artifact_dir,
            strict_candidates=args.strict_candidates,
            strict_candidates_url=args.strict_candidates_url,
            output_dir=args.output_dir,
            public_report_dir=args.public_report_dir,
            min_sn_r=args.min_sn_r,
            n_folds=args.n_folds,
            control_ratio=args.control_ratio,
            injection_base_ratio=args.injection_base_ratio,
            n_candidate_shuffles=args.n_candidate_shuffles,
            candidate_shuffle_seed=args.candidate_shuffle_seed,
            injection_trials_per_cell=args.injection_trials_per_cell,
            injection_seed=args.injection_seed,
            backup_correction_md5=args.backup_correction_md5,
            strict_candidates_sha256=args.strict_candidates_sha256,
            strict_candidates_gz_sha256=args.strict_candidates_gz_sha256,
            check_frozen_input_hashes=not args.skip_frozen_input_hash_checks,
            check_offsets_git_commit=not args.skip_offsets_git_commit_check,
            force_strict_candidates_download=args.force_strict_candidates_download,
            force_audit_model_download=args.force_audit_model_download,
        )
        print(f"source_summary_oof rows: {len(result.source_summary)}")
        print(f"candidate_epoch_bundle rows: {len(result.epoch_bundle)}")
        print(f"manifest: {result.manifest}")


if __name__ == "__main__":
    main()
