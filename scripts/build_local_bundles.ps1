$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    & $VenvPython -m desi_rv_variables.cli build-local-bundles --project-root $RepoRoot @args
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m desi_rv_variables.cli build-local-bundles --project-root $RepoRoot @args
} else {
    & python -m desi_rv_variables.cli build-local-bundles --project-root $RepoRoot @args
}
exit $LASTEXITCODE
