from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u

from .provenance import runtime_environment


SPEED_OF_LIGHT_KMS = 299_792.458
DESI_DR1_S3_ROOT = "https://desidata.s3.amazonaws.com/dr1"
DESI_DR1_MWS_ROOT = "https://data.desi.lbl.gov/public/dr1/vac/dr1/mws/iron/v1.0"
ARMS = ("B", "R", "Z")
TELLURIC_RANGES = (
    (6860.0, 6960.0),
    (7160.0, 7350.0),
    (7580.0, 7700.0),
    (8100.0, 8400.0),
    (8900.0, 9900.0),
)

SPECTRAL_EPOCH_COLUMNS = [
    "GROUP_ID",
    "SOURCE_ID",
    "TARGETID",
    "PROGRAM",
    "NIGHT",
    "EXPID",
    "MJD",
    "VRAD_CORRECTED_OOF",
    "REFERENCE_EXPID",
    "REFERENCE_TEMPLATE_SHIFT_KMS",
    "SELF_MODEL_SHIFT_KMS",
    "N_VALID_PIXELS",
    "SPECTRAL_RELATIVE_RV_KMS",
    "CATALOG_RELATIVE_RV_KMS",
    "CATALOG_MINUS_SPECTRAL_KMS",
]

SPECTRAL_SOURCE_COLUMNS = [
    "GROUP_ID",
    "SOURCE_ID",
    "N_SPECTRAL_EPOCHS",
    "CATALOG_SPECTRAL_RV_CORRELATION",
    "SPECTRAL_ON_CATALOG_SLOPE",
    "MEDIAN_ABS_RV_RESIDUAL_KMS",
    "MAX_ABS_RV_RESIDUAL_KMS",
    "CATALOG_RV_RANGE_KMS",
    "SPECTRAL_RV_RANGE_KMS",
    "FLUX_LEVEL_CONSISTENT",
]


@dataclass(frozen=True)
class SpectralValidationSettings:
    velocity_min_kms: float = -250.0
    velocity_max_kms: float = 250.0
    velocity_step_kms: float = 1.0
    continuum_polynomial_degree: int = 3
    min_valid_pixels_per_arm: int = 250
    min_source_epochs: int = 4
    confirmation_min_correlation: float = 0.8
    confirmation_max_median_abs_residual_kms: float = 10.0
    confirmation_min_spectral_range_kms: float = 20.0
    max_download_workers: int = 8


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _healpix64_nested(ra: float, dec: float) -> int:
    try:
        from astropy_healpix import HEALPix
    except ImportError as error:
        raise RuntimeError(
            "spectral validation requires the optional 'spectra' dependencies"
        ) from error
    healpix = HEALPix(nside=64, order="nested", frame="icrs")
    coordinate = SkyCoord(ra=float(ra) * u.deg, dec=float(dec) * u.deg, frame="icrs")
    return int(healpix.skycoord_to_healpix(coordinate))


def cframe_path(
    cache_dir: str | Path, night: int, expid: int, fiber: int, arm: str
) -> Path:
    arm = arm.lower()
    if arm not in {item.lower() for item in ARMS}:
        raise ValueError(f"unsupported DESI arm: {arm}")
    padded_expid = f"{int(expid):08d}"
    spectrograph = int(fiber) // 500
    return (
        Path(cache_dir)
        / str(int(night))
        / padded_expid
        / f"cframe-{arm}{spectrograph}-{padded_expid}.fits.gz"
    )


def cframe_url(night: int, expid: int, fiber: int, arm: str) -> str:
    path = cframe_path("", night, expid, fiber, arm)
    return (
        f"{DESI_DR1_S3_ROOT}/spectro/redux/iron/exposures/"
        f"{int(night)}/{int(expid):08d}/{path.name}"
    )


def _download_with_resume(url: str, output: Path, attempts: int = 5) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        try:
            with fits.open(output, memmap=False) as hdul:
                if "FIBERMAP" in hdul and "FLUX" in hdul:
                    return output
        except Exception:
            pass
    for attempt in range(1, attempts + 1):
        existing = output.stat().st_size if output.exists() else 0
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "desi-rv-variables-spectral-validation/0.3",
                **({"Range": f"bytes={existing}-"} if existing else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                append = existing > 0 and response.status == 206
                mode = "ab" if append else "wb"
                with output.open(mode) as handle:
                    while chunk := response.read(1024 * 1024):
                        handle.write(chunk)
            with fits.open(output, memmap=False) as hdul:
                if "FIBERMAP" not in hdul or "FLUX" not in hdul:
                    raise ValueError(f"invalid cframe: {output}")
            return output
        except urllib.error.HTTPError as error:
            if error.code == 416 and output.exists():
                output.unlink()
            if attempt == attempts:
                raise
            time.sleep(float(attempt))
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable download retry state")


def download_candidate_cframes(
    epochs: pd.DataFrame,
    cache_dir: str | Path,
    max_workers: int = 8,
) -> list[Path]:
    required = {"NIGHT", "EXPID", "FIBER"}
    missing = required.difference(epochs.columns)
    if missing:
        raise ValueError(f"epoch table missing cframe keys: {sorted(missing)}")
    jobs: list[tuple[str, Path]] = []
    unique_epochs = epochs[["NIGHT", "EXPID", "FIBER"]].drop_duplicates()
    for row in unique_epochs.itertuples(index=False):
        for arm in ARMS:
            path = cframe_path(cache_dir, row.NIGHT, row.EXPID, row.FIBER, arm)
            jobs.append((cframe_url(row.NIGHT, row.EXPID, row.FIBER, arm), path))
    results: list[Path] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_download_with_resume, url, path): path for url, path in jobs
        }
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results)


def _read_cframe_epoch(path: Path, targetid: int) -> dict[str, np.ndarray]:
    with fits.open(path, memmap=False) as hdul:
        fibermap = hdul["FIBERMAP"].data
        matches = np.flatnonzero(fibermap["TARGETID"] == int(targetid))
        if len(matches) != 1:
            raise ValueError(
                f"expected one TARGETID={targetid} row in {path}, found {len(matches)}"
            )
        row = int(matches[0])
        return {
            "wavelength": np.asarray(hdul["WAVELENGTH"].data, dtype=float),
            "flux": np.asarray(hdul["FLUX"].data[row], dtype=float),
            "ivar": np.asarray(hdul["IVAR"].data[row], dtype=float),
            "mask": np.asarray(hdul["MASK"].data[row]),
        }


def _rvspec_model_url(survey: str, program: str, healpix: int) -> str:
    survey = str(survey).lower()
    program = str(program).lower()
    return (
        f"{DESI_DR1_MWS_ROOT}/rv_output/240521/healpix/{survey}/{program}/"
        f"{healpix // 100}/{healpix}/rvmod_spectra-{survey}-{program}-{healpix}.fits"
    )


def _read_remote_models(
    targetids: set[int], survey: str, program: str, healpix: int
) -> tuple[dict[str, np.ndarray], dict[tuple[int, int], dict[str, np.ndarray]], str]:
    try:
        import httpio
        import urllib3
    except ImportError as error:
        raise RuntimeError(
            "spectral validation requires the optional 'spectra' dependencies"
        ) from error
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = _rvspec_model_url(survey, program, healpix)
    with httpio.open(url, verify=False, block_size=28_800) as handle:
        with fits.open(handle) as hdul:
            fibermap = hdul["FIBERMAP"].data
            selected = np.isin(
                np.asarray(fibermap["TARGETID"], dtype=np.int64),
                np.asarray(sorted(targetids), dtype=np.int64),
            )
            rows = np.flatnonzero(selected)
            wavelengths = {
                arm: np.asarray(hdul[f"{arm}_WAVELENGTH"].data, dtype=float)
                for arm in ARMS
            }
            models: dict[tuple[int, int], dict[str, np.ndarray]] = {}
            for row in rows:
                key = (int(fibermap["TARGETID"][row]), int(fibermap["EXPID"][row]))
                if key in models:
                    raise ValueError(f"duplicate RVMOD TARGETID/EXPID row: {key}")
                models[key] = {
                    arm: np.asarray(hdul[f"{arm}_MODEL"].section[row, :], dtype=float)
                    for arm in ARMS
                }
    return wavelengths, models, url


def _arm_loss(
    observed: dict[str, np.ndarray],
    model_wavelength: np.ndarray,
    model_flux: np.ndarray,
    velocity_kms: float,
    polynomial_degree: int,
    min_valid_pixels: int,
) -> tuple[float, int]:
    wavelength = observed["wavelength"]
    flux = observed["flux"]
    ivar = observed["ivar"]
    mask = observed["mask"]
    shifted_model = np.interp(
        wavelength / (1.0 + velocity_kms / SPEED_OF_LIGHT_KMS),
        model_wavelength,
        model_flux,
        left=np.nan,
        right=np.nan,
    )
    valid = (
        np.isfinite(wavelength)
        & np.isfinite(flux)
        & np.isfinite(ivar)
        & (ivar > 0)
        & (mask == 0)
        & np.isfinite(shifted_model)
    )
    for lower, upper in TELLURIC_RANGES:
        valid &= (wavelength < lower) | (wavelength > upper)
    if int(valid.sum()) < min_valid_pixels:
        return np.nan, int(valid.sum())
    x = 2.0 * (wavelength - wavelength.min()) / np.ptp(wavelength) - 1.0
    polynomial = np.polynomial.legendre.legvander(x, polynomial_degree)
    design = shifted_model[:, None] * polynomial
    selected_design = design[valid]
    selected_weight = ivar[valid]
    selected_flux = flux[valid]
    normal = selected_design.T @ (selected_weight[:, None] * selected_design)
    right_hand_side = selected_design.T @ (selected_weight * selected_flux)
    try:
        coefficients = np.linalg.solve(normal, right_hand_side)
    except np.linalg.LinAlgError:
        coefficients = np.linalg.lstsq(normal, right_hand_side, rcond=None)[0]
    chi2 = float(
        np.sum(selected_weight * np.square(selected_flux))
        - coefficients @ right_hand_side
    )
    return max(0.0, chi2), int(valid.sum())


def fit_velocity_shift(
    observed_by_arm: dict[str, dict[str, np.ndarray]],
    model_wavelengths: dict[str, np.ndarray],
    model_by_arm: dict[str, np.ndarray],
    settings: SpectralValidationSettings = SpectralValidationSettings(),
) -> dict[str, float | int]:
    velocity_grid = np.arange(
        settings.velocity_min_kms,
        settings.velocity_max_kms + 0.5 * settings.velocity_step_kms,
        settings.velocity_step_kms,
    )
    losses: list[float] = []
    valid_pixels: list[int] = []
    for velocity in velocity_grid:
        total_loss = 0.0
        total_pixels = 0
        for arm in ARMS:
            loss, pixels = _arm_loss(
                observed_by_arm[arm],
                model_wavelengths[arm],
                model_by_arm[arm],
                float(velocity),
                settings.continuum_polynomial_degree,
                settings.min_valid_pixels_per_arm,
            )
            if np.isfinite(loss):
                total_loss += loss
                total_pixels += pixels
        losses.append(total_loss if total_pixels else np.nan)
        valid_pixels.append(total_pixels)
    loss_array = np.asarray(losses, dtype=float)
    if not np.isfinite(loss_array).any():
        return {
            "BEST_SHIFT_KMS": np.nan,
            "MIN_CHI2": np.nan,
            "N_VALID_PIXELS": 0,
            "DELTA_CHI2_ZERO_TO_BEST": np.nan,
        }
    best_index = int(np.nanargmin(loss_array))
    subpixel = 0.0
    if 0 < best_index < len(loss_array) - 1:
        local = loss_array[best_index - 1 : best_index + 2]
        denominator = local[0] - 2.0 * local[1] + local[2]
        if np.isfinite(denominator) and denominator > 0:
            subpixel = 0.5 * (local[0] - local[2]) / denominator
            subpixel = float(np.clip(subpixel, -1.0, 1.0))
    best_shift = float(
        velocity_grid[best_index] + subpixel * settings.velocity_step_kms
    )
    zero_index = int(np.argmin(np.abs(velocity_grid)))
    return {
        "BEST_SHIFT_KMS": best_shift,
        "MIN_CHI2": float(loss_array[best_index]),
        "N_VALID_PIXELS": int(valid_pixels[best_index]),
        "DELTA_CHI2_ZERO_TO_BEST": float(
            max(0.0, loss_array[zero_index] - loss_array[best_index])
        ),
    }


def _source_validation_summary(
    epoch_results: pd.DataFrame,
    settings: SpectralValidationSettings = SpectralValidationSettings(),
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group_id, group in epoch_results.groupby("GROUP_ID", sort=True):
        valid = group.dropna(
            subset=["CATALOG_RELATIVE_RV_KMS", "SPECTRAL_RELATIVE_RV_KMS"]
        )
        if valid.empty:
            rows.append(
                {
                    "GROUP_ID": int(group_id),
                    "SOURCE_ID": group["SOURCE_ID"].iloc[0],
                    "N_SPECTRAL_EPOCHS": 0,
                    "CATALOG_SPECTRAL_RV_CORRELATION": np.nan,
                    "SPECTRAL_ON_CATALOG_SLOPE": np.nan,
                    "MEDIAN_ABS_RV_RESIDUAL_KMS": np.nan,
                    "MAX_ABS_RV_RESIDUAL_KMS": np.nan,
                    "CATALOG_RV_RANGE_KMS": np.nan,
                    "SPECTRAL_RV_RANGE_KMS": np.nan,
                    "FLUX_LEVEL_CONSISTENT": False,
                }
            )
            continue
        if len(valid) < 2:
            correlation = np.nan
            slope = np.nan
        else:
            catalog = valid["CATALOG_RELATIVE_RV_KMS"].to_numpy(float)
            spectral = valid["SPECTRAL_RELATIVE_RV_KMS"].to_numpy(float)
            correlation = float(np.corrcoef(catalog, spectral)[0, 1])
            slope = (
                float(np.polyfit(catalog, spectral, 1)[0])
                if np.ptp(catalog) > 0
                else np.nan
            )
        residual = (
            valid["SPECTRAL_RELATIVE_RV_KMS"] - valid["CATALOG_RELATIVE_RV_KMS"]
        ).abs()
        spectral_range = float(np.ptp(valid["SPECTRAL_RELATIVE_RV_KMS"]))
        median_abs_residual = float(residual.median())
        confirmed = bool(
            len(valid) >= settings.min_source_epochs
            and np.isfinite(correlation)
            and correlation >= settings.confirmation_min_correlation
            and median_abs_residual <= settings.confirmation_max_median_abs_residual_kms
            and spectral_range >= settings.confirmation_min_spectral_range_kms
        )
        rows.append(
            {
                "GROUP_ID": int(group_id),
                "SOURCE_ID": valid["SOURCE_ID"].iloc[0],
                "N_SPECTRAL_EPOCHS": int(len(valid)),
                "CATALOG_SPECTRAL_RV_CORRELATION": correlation,
                "SPECTRAL_ON_CATALOG_SLOPE": slope,
                "MEDIAN_ABS_RV_RESIDUAL_KMS": median_abs_residual,
                "MAX_ABS_RV_RESIDUAL_KMS": float(residual.max()),
                "CATALOG_RV_RANGE_KMS": float(np.ptp(valid["CATALOG_RELATIVE_RV_KMS"])),
                "SPECTRAL_RV_RANGE_KMS": spectral_range,
                "FLUX_LEVEL_CONSISTENT": confirmed,
            }
        )
    return pd.DataFrame(rows, columns=SPECTRAL_SOURCE_COLUMNS)


def validate_followup_spectra(
    epoch_bundle_path: str | Path,
    high_amplitude_path: str | Path,
    metal_external_path: str | Path,
    output_dir: str | Path,
    cache_dir: str | Path,
    settings: SpectralValidationSettings = SpectralValidationSettings(),
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    epoch_bundle_path = Path(epoch_bundle_path)
    high_amplitude_path = Path(high_amplitude_path)
    metal_external_path = Path(metal_external_path)
    output_dir = Path(output_dir)
    cache_dir = Path(cache_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    epochs = pd.read_parquet(epoch_bundle_path)
    high_amplitude = pd.read_parquet(high_amplitude_path)
    metal = pd.read_parquet(metal_external_path)
    targets = metal[metal["NO_EXTENDED_CATALOGUE_MATCH"].fillna(False)].merge(
        high_amplitude[["GROUP_ID", "PROGRAM"]],
        on="GROUP_ID",
        how="inner",
        validate="one_to_one",
    )
    selected = epochs.merge(
        targets[["GROUP_ID", "PROGRAM"]],
        on=["GROUP_ID", "PROGRAM"],
        how="inner",
        validate="many_to_one",
    )
    selected = selected[
        selected["GOOD_EPOCH"].fillna(False)
        & selected["OOF_OFFSET_AVAILABLE"].fillna(False)
    ].copy()
    downloaded = download_candidate_cframes(
        selected,
        cache_dir,
        max_workers=settings.max_download_workers,
    )
    cframe_inputs = [
        {
            "path": str(path.relative_to(cache_dir)),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in downloaded
    ]
    cframe_set_sha256 = hashlib.sha256(
        json.dumps(cframe_inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    epoch_rows: list[dict[str, object]] = []
    model_urls: set[str] = set()
    model_subset_digest = hashlib.sha256()
    for group_id, group in selected.groupby("GROUP_ID", sort=True):
        group = group.sort_values(["MJD", "EXPID"], kind="mergesort").reset_index(
            drop=True
        )
        survey = str(group["SURVEY"].iloc[0]).lower()
        program = str(group["PROGRAM"].iloc[0]).lower()
        healpix = _healpix64_nested(
            float(pd.to_numeric(group["TARGET_RA"], errors="raise").median()),
            float(pd.to_numeric(group["TARGET_DEC"], errors="raise").median()),
        )
        targetids = set(group["TARGETID"].astype("int64"))
        model_wavelengths, models, model_url = _read_remote_models(
            targetids, survey, program, healpix
        )
        model_urls.add(model_url)
        for arm in ARMS:
            model_subset_digest.update(arm.encode("ascii"))
            model_subset_digest.update(
                np.asarray(model_wavelengths[arm], dtype="<f8").tobytes()
            )
        for key in sorted(models):
            model_subset_digest.update(f"{key[0]}:{key[1]}".encode("ascii"))
            for arm in ARMS:
                model_subset_digest.update(arm.encode("ascii"))
                model_subset_digest.update(
                    np.asarray(models[key][arm], dtype="<f8").tobytes()
                )
        reference_row = group.loc[
            pd.to_numeric(group["SN_R"], errors="coerce").idxmax()
        ]
        reference_key = (int(reference_row["TARGETID"]), int(reference_row["EXPID"]))
        if reference_key not in models:
            raise ValueError(f"reference epoch missing from RVMOD: {reference_key}")
        reference_model = models[reference_key]
        fitted_rows: list[dict[str, object]] = []
        for row in group.itertuples(index=False):
            observed_by_arm = {
                arm: _read_cframe_epoch(
                    cframe_path(cache_dir, row.NIGHT, row.EXPID, row.FIBER, arm),
                    int(row.TARGETID),
                )
                for arm in ARMS
            }
            reference_fit = fit_velocity_shift(
                observed_by_arm, model_wavelengths, reference_model, settings
            )
            self_key = (int(row.TARGETID), int(row.EXPID))
            self_fit = (
                fit_velocity_shift(
                    observed_by_arm, model_wavelengths, models[self_key], settings
                )
                if self_key in models
                else {"BEST_SHIFT_KMS": np.nan}
            )
            fitted_rows.append(
                {
                    "GROUP_ID": int(group_id),
                    "SOURCE_ID": int(row.SOURCE_ID),
                    "TARGETID": int(row.TARGETID),
                    "PROGRAM": str(row.PROGRAM),
                    "NIGHT": int(row.NIGHT),
                    "EXPID": int(row.EXPID),
                    "MJD": float(row.MJD),
                    "VRAD_CORRECTED_OOF": float(row.VRAD_CORRECTED_OOF),
                    "REFERENCE_EXPID": int(reference_row["EXPID"]),
                    "REFERENCE_TEMPLATE_SHIFT_KMS": reference_fit["BEST_SHIFT_KMS"],
                    "SELF_MODEL_SHIFT_KMS": self_fit["BEST_SHIFT_KMS"],
                    "N_VALID_PIXELS": reference_fit["N_VALID_PIXELS"],
                }
            )
        frame = pd.DataFrame(fitted_rows)
        reference_shift = float(
            frame.loc[
                frame["EXPID"] == int(reference_row["EXPID"]),
                "REFERENCE_TEMPLATE_SHIFT_KMS",
            ].iloc[0]
        )
        reference_catalog_rv = float(reference_row["VRAD_CORRECTED_OOF"])
        frame["SPECTRAL_RELATIVE_RV_KMS"] = (
            frame["REFERENCE_TEMPLATE_SHIFT_KMS"] - reference_shift
        )
        frame["CATALOG_RELATIVE_RV_KMS"] = (
            frame["VRAD_CORRECTED_OOF"] - reference_catalog_rv
        )
        frame["CATALOG_MINUS_SPECTRAL_KMS"] = (
            frame["CATALOG_RELATIVE_RV_KMS"] - frame["SPECTRAL_RELATIVE_RV_KMS"]
        )
        epoch_rows.extend(frame.to_dict(orient="records"))

    epoch_results = pd.DataFrame(epoch_rows, columns=SPECTRAL_EPOCH_COLUMNS)
    source_results = _source_validation_summary(epoch_results, settings)
    epoch_path = output_dir / "spectral_epoch_validation.parquet"
    source_path = output_dir / "spectral_source_validation.parquet"
    epoch_results.to_parquet(epoch_path, index=False)
    source_results.to_parquet(source_path, index=False)
    manifest = {
        "settings": asdict(settings),
        "runtime_environment": runtime_environment(),
        "inputs": {
            "epoch_bundle": {
                "name": epoch_bundle_path.name,
                "sha256": _sha256(epoch_bundle_path),
            },
            "high_amplitude": {
                "name": high_amplitude_path.name,
                "sha256": _sha256(high_amplitude_path),
            },
            "metal_external": {
                "name": metal_external_path.name,
                "sha256": _sha256(metal_external_path),
            },
        },
        "remote_model_urls": sorted(model_urls),
        "cframe_set_sha256": cframe_set_sha256,
        "cframe_inputs": cframe_inputs,
        "rvspec_model_subset_sha256": model_subset_digest.hexdigest(),
        "counts": {
            "sources": int(len(source_results)),
            "epochs": int(len(epoch_results)),
            "flux_level_consistent_sources": int(
                source_results["FLUX_LEVEL_CONSISTENT"].sum()
            ),
            "validated_cframes": int(len(downloaded)),
        },
        "outputs": {
            "spectral_epoch_validation": {
                "name": epoch_path.name,
                "sha256": _sha256(epoch_path),
            },
            "spectral_source_validation": {
                "name": source_path.name,
                "sha256": _sha256(source_path),
            },
        },
    }
    manifest_path = output_dir / "spectral_validation_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return epoch_results, source_results, manifest
