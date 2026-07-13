from importlib.metadata import version
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

import yaml


def test_release_versions_are_synchronized():
    root = Path(__file__).resolve().parents[1]
    package_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    citation_version = yaml.safe_load(
        (root / "CITATION.cff").read_text(encoding="utf-8")
    )["version"]

    assert package_version == "0.2.0"
    assert citation_version == package_version
    assert version("desi-rv-variables") == package_version
