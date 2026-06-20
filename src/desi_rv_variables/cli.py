from __future__ import annotations

import argparse

from .oof import (
    DEFAULT_BACKUP_CORRECTION_MD5,
    STRICT_CANDIDATES_SHA256,
    build_bundles,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DESI RV variable candidate bundle tools")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-bundles", help="Build OOF source summary and candidate epoch bundle")
    build.add_argument("fits", nargs="+", help="DESI rvpix_exp FITS files")
    build.add_argument("--backup-correction", required=True)
    build.add_argument("--offsets", required=True)
    build.add_argument("--strict-candidates")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--public-report-dir")
    build.add_argument("--min-sn-r", type=float, default=5.0)
    build.add_argument("--n-folds", type=int, default=5)
    build.add_argument("--control-ratio", type=float, default=1.0)
    build.add_argument("--injection-base-ratio", type=float, default=1.0)
    build.add_argument("--n-candidate-shuffles", type=int, default=20)
    build.add_argument("--candidate-shuffle-seed", type=int, default=20260620)
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
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "build-bundles":
        result = build_bundles(
            fits_paths=args.fits,
            backup_correction_path=args.backup_correction,
            offsets_path=args.offsets,
            output_dir=args.output_dir,
            strict_candidates_path=args.strict_candidates,
            public_report_dir=args.public_report_dir,
            min_sn_r=args.min_sn_r,
            n_folds=args.n_folds,
            control_ratio=args.control_ratio,
            injection_base_ratio=args.injection_base_ratio,
            n_candidate_shuffles=args.n_candidate_shuffles,
            candidate_shuffle_seed=args.candidate_shuffle_seed,
            backup_correction_md5=args.backup_correction_md5,
            strict_candidates_sha256=args.strict_candidates_sha256,
            check_frozen_input_hashes=not args.skip_frozen_input_hash_checks,
            check_offsets_git_commit=not args.skip_offsets_git_commit_check,
            allow_empty_candidates=args.allow_empty_candidates,
        )
        print(f"source_summary_oof rows: {len(result.source_summary)}")
        print(f"candidate_epoch_bundle rows: {len(result.epoch_bundle)}")
        print(f"manifest: {result.manifest}")


if __name__ == "__main__":
    main()
