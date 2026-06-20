from __future__ import annotations

import argparse

from .oof import DEFAULT_BACKUP_CORRECTION_MD5, STRICT_CANDIDATES_SHA256, build_bundles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DESI RV variable candidate bundle tools")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-bundles", help="Build OOF source summary and candidate epoch bundle")
    build.add_argument("fits", nargs="+", help="DESI rvpix_exp FITS files")
    build.add_argument("--backup-correction", required=True)
    build.add_argument("--offsets", required=True)
    build.add_argument("--strict-candidates")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--min-sn-r", type=float, default=5.0)
    build.add_argument("--n-folds", type=int, default=5)
    build.add_argument("--control-ratio", type=float, default=1.0)
    build.add_argument("--injection-base-ratio", type=float, default=1.0)
    build.add_argument(
        "--backup-correction-md5",
        default=DEFAULT_BACKUP_CORRECTION_MD5,
    )
    build.add_argument(
        "--strict-candidates-sha256",
        default=STRICT_CANDIDATES_SHA256,
    )
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
            min_sn_r=args.min_sn_r,
            n_folds=args.n_folds,
            control_ratio=args.control_ratio,
            injection_base_ratio=args.injection_base_ratio,
            backup_correction_md5=args.backup_correction_md5,
            strict_candidates_sha256=args.strict_candidates_sha256,
        )
        print(f"source_summary_oof rows: {len(result.source_summary)}")
        print(f"candidate_epoch_bundle rows: {len(result.epoch_bundle)}")
        print(f"manifest: {result.manifest}")


if __name__ == "__main__":
    main()
