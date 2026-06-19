#!/usr/bin/env bash
set -euo pipefail

if [[ -x ".venv/bin/desi-rv-variables" ]]; then
  runner=".venv/bin/desi-rv-variables"
else
  runner="desi-rv-variables"
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
projects_root="$(cd "$repo_root/.." && pwd)"
audit_data_dir="${DESI_RV_AUDIT_DATA_DIR:-$projects_root/desi-rv-audit/data}"
audit_public_dir="${DESI_RV_AUDIT_PUBLIC_DIR:-$projects_root/desi-rv-audit-public}"

"$runner" build-bundles \
  "$audit_data_dir/desi_main/rvpix_exp-main-backup.fits" \
  "$audit_data_dir/desi_main/rvpix_exp-main-bright.fits" \
  "$audit_data_dir/desi_main/rvpix_exp-main-dark.fits" \
  --backup-correction "$audit_data_dir/desi_corrections/backup_correction.fits" \
  --offsets "$audit_public_dir/reports/program_night_artifacts/diagnostic_offsets_program_night.csv" \
  --strict-candidates "$audit_public_dir/outputs/desi_main_audit/candidate_sources_strict.csv" \
  --output-dir artifacts \
  --min-sn-r 5 \
  --n-folds 5 \
  --control-ratio 1.0
