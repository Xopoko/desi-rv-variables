from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError, version


DEFAULT_PACKAGES = (
    "desi-rv-variables",
    "desi-rv-audit",
    "numpy",
    "pandas",
    "scipy",
    "pyarrow",
    "astropy",
    "astropy-healpix",
    "httpio",
)


def runtime_environment(
    packages: tuple[str, ...] = DEFAULT_PACKAGES,
) -> dict[str, object]:
    package_versions: dict[str, str | None] = {}
    for package in packages:
        try:
            package_versions[package] = version(package)
        except PackageNotFoundError:
            package_versions[package] = None
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": package_versions,
    }
