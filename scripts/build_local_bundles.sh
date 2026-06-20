#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
projects_root="$(cd "$repo_root/.." && pwd)"
if [[ -x "$repo_root/.venv/bin/desi-rv-variables" ]]; then
  runner="$repo_root/.venv/bin/desi-rv-variables"
else
  runner="desi-rv-variables"
fi

audit_data_dir="${DESI_RV_AUDIT_DATA_DIR:-$projects_root/desi-rv-audit/data}"
audit_artifact_dir="${DESI_RV_AUDIT_ARTIFACT_DIR:-$projects_root/desi-rv-audit/reports/program_night_artifacts}"
strict_candidates="${DESI_RV_STRICT_CANDIDATES:-$repo_root/artifacts/inputs/candidate_sources_strict.csv}"
strict_candidates_url="${DESI_RV_STRICT_CANDIDATES_URL:-https://github.com/Xopoko/desi-rv-variables/releases/download/v0.1.3/candidate_sources_strict.csv.gz}"
strict_candidates_sha256="5c96d5cc823725f9c80f133c11f0aad3ca09c7eaa678a5d694b095eb46944b47"
strict_candidates_gz_sha256="7958ac85c59e5228069710f44420483373e7fddef58f2fb0aa4b5b8b06aed2e3"

if [[ ! -f "$strict_candidates" ]]; then
  mkdir -p "$(dirname "$strict_candidates")"
  gz_path="$strict_candidates.gz"
  curl --fail --location --retry 3 "$strict_candidates_url" -o "$gz_path"
  echo "$strict_candidates_gz_sha256  $gz_path" | shasum -a 256 -c -
  gzip -dc "$gz_path" > "$strict_candidates"
fi

echo "$strict_candidates_sha256  $strict_candidates" | shasum -a 256 -c -

"$runner" build-bundles \
  "$audit_data_dir/desi_main/rvpix_exp-main-backup.fits" \
  "$audit_data_dir/desi_main/rvpix_exp-main-bright.fits" \
  "$audit_data_dir/desi_main/rvpix_exp-main-dark.fits" \
  --backup-correction "$audit_data_dir/desi_corrections/backup_correction.fits" \
  --offsets "$audit_artifact_dir/diagnostic_offsets_program_night.csv" \
  --strict-candidates "$strict_candidates" \
  --strict-candidates-sha256 "$strict_candidates_sha256" \
  --output-dir artifacts \
  --public-report-dir reports \
  --min-sn-r 5 \
  --n-folds 5 \
  --control-ratio 1.0 \
  --injection-base-ratio 1.0 \
  --n-candidate-shuffles 20
