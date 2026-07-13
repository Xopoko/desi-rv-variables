from __future__ import annotations

import numpy as np
import pandas as pd

from desi_rv_variables.spectral_validation import (
    ARMS,
    SPEED_OF_LIGHT_KMS,
    SpectralValidationSettings,
    _source_validation_summary,
    cframe_path,
    cframe_url,
    fit_velocity_shift,
)


def _synthetic_spectrum(velocity_kms: float):
    observed = {}
    model_wavelengths = {}
    models = {}
    ranges = {"B": (4000.0, 5000.0), "R": (5800.0, 6800.0), "Z": (8450.0, 8850.0)}
    for arm in ARMS:
        wavelength = np.linspace(*ranges[arm], 800)
        centers = np.linspace(ranges[arm][0] + 100.0, ranges[arm][1] - 100.0, 6)
        model = np.ones_like(wavelength)
        for index, center in enumerate(centers):
            model -= (0.08 + 0.01 * index) * np.exp(
                -0.5 * np.square((wavelength - center) / (1.1 + 0.1 * index))
            )
        flux = np.interp(
            wavelength / (1.0 + velocity_kms / SPEED_OF_LIGHT_KMS),
            wavelength,
            model,
        )
        flux *= 1.0 + 0.02 * (wavelength - wavelength.mean()) / np.ptp(wavelength)
        observed[arm] = {
            "wavelength": wavelength,
            "flux": flux,
            "ivar": np.full_like(wavelength, 10_000.0),
            "mask": np.zeros_like(wavelength, dtype=np.int64),
        }
        model_wavelengths[arm] = wavelength
        models[arm] = model
    return observed, model_wavelengths, models


def test_flux_level_fit_recovers_injected_velocity_shift():
    observed, wavelengths, models = _synthetic_spectrum(42.0)
    settings = SpectralValidationSettings(
        velocity_min_kms=-80.0,
        velocity_max_kms=80.0,
        velocity_step_kms=1.0,
        min_valid_pixels_per_arm=100,
    )
    result = fit_velocity_shift(observed, wavelengths, models, settings)
    assert abs(float(result["BEST_SHIFT_KMS"]) - 42.0) < 1.0
    assert int(result["N_VALID_PIXELS"]) > 2_000


def test_source_validation_summary_applies_declared_continuous_checks():
    frame = pd.DataFrame(
        {
            "GROUP_ID": [1, 1, 1, 1],
            "SOURCE_ID": pd.Series([123456789012345678] * 4, dtype="int64"),
            "CATALOG_RELATIVE_RV_KMS": [0.0, 40.0, -20.0, 60.0],
            "SPECTRAL_RELATIVE_RV_KMS": [0.0, 41.0, -19.0, 59.0],
        }
    )
    result = _source_validation_summary(frame)
    assert len(result) == 1
    assert bool(result.iloc[0]["FLUX_LEVEL_CONSISTENT"])
    assert int(result.iloc[0]["SOURCE_ID"]) == 123456789012345678


def test_cframe_location_uses_padded_expid_and_spectrograph(tmp_path):
    path = cframe_path(tmp_path, 20210515, 88535, 1531, "R")
    assert path.name == "cframe-r3-00088535.fits.gz"
    assert "20210515/00088535" in path.as_posix()
    assert cframe_url(20210515, 88535, 1531, "R").endswith(
        "/20210515/00088535/cframe-r3-00088535.fits.gz"
    )
