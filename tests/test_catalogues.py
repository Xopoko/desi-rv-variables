from __future__ import annotations

import re

import numpy as np
import pandas as pd
from astropy.io import fits

from desi_rv_variables import catalogues


def test_gaia_exact_id_crossmatch_preserves_ids_and_table_meaning(monkeypatch):
    first = 123456789012345678
    second = 223456789012345678

    def fake_tap(adql: str, endpoint: str = "", attempts: int = 3) -> pd.DataFrame:
        assert str(first) in adql and str(second) in adql
        if "nss_two_body_orbit" in adql:
            return pd.DataFrame(
                {
                    "source_id": pd.Series([str(first)], dtype="string"),
                    "nss_solution_type": ["SB1"],
                }
            )
        if "vari_summary" in adql:
            return pd.DataFrame({"source_id": pd.Series([str(second)], dtype="string")})
        return pd.DataFrame({"source_id": pd.Series(dtype="string")})

    monkeypatch.setattr(catalogues, "_tap_csv", fake_tap)
    result = catalogues.gaia_dr3_exact_id_crossmatch([first, second])
    assert result["SOURCE_ID"].tolist() == [first, second]
    assert bool(result.loc[result["SOURCE_ID"] == first, "GAIA_NSS_TWO_BODY"].iloc[0])
    assert (
        result.loc[result["SOURCE_ID"] == first, "GAIA_NSS_SOLUTION_TYPES"].iloc[0]
        == "SB1"
    )
    assert bool(result.loc[result["SOURCE_ID"] == second, "GAIA_VARI_SUMMARY"].iloc[0])


def test_specdis_binary_flag_zero_means_candidate(tmp_path):
    first = 123456789012345678
    second = 223456789012345678
    columns = [
        fits.Column(
            name="SOURCE_ID",
            format="K",
            array=np.array([first, first, second], dtype=np.int64),
        ),
        fits.Column(
            name="BINARY_FLAG", format="K", array=np.array([1, 0, 1], dtype=np.int64)
        ),
        fits.Column(
            name="BINARY_POSSIBILITY",
            format="D",
            array=np.array([0.1, 0.9, 0.2], dtype=float),
        ),
    ]
    path = tmp_path / "specdis.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU.from_columns(columns)]).writeto(
        path
    )
    result = catalogues.specdis_exact_id_crossmatch(path, [first, second])
    first_row = result[result["SOURCE_ID"] == first].iloc[0]
    second_row = result[result["SOURCE_ID"] == second].iloc[0]
    assert bool(first_row["SPECDIS_BINARY_CANDIDATE"])
    assert first_row["SPECDIS_N_ROWS"] == 2
    assert first_row["SPECDIS_BINARY_POSSIBILITY_MAX"] == 0.9
    assert not bool(second_row["SPECDIS_BINARY_CANDIDATE"])


def test_gaia_queries_use_only_numeric_exact_ids(monkeypatch):
    observed: list[str] = []

    def fake_tap(adql: str, endpoint: str = "", attempts: int = 3) -> pd.DataFrame:
        observed.append(adql)
        return pd.DataFrame({"source_id": pd.Series(dtype="string")})

    monkeypatch.setattr(catalogues, "_tap_csv", fake_tap)
    catalogues.gaia_dr3_exact_id_crossmatch([42, 84], chunk_size=1)
    assert observed
    assert all(re.search(r"source_id IN \((42|84)\)", query) for query in observed)


def test_simbad_and_vsx_secondary_matches_use_declared_rules(monkeypatch):
    source_id = 123456789012345678

    def fake_tap(adql: str, endpoint: str = "", attempts: int = 3) -> pd.DataFrame:
        if endpoint == catalogues.SIMBAD_TAP_SYNC:
            assert f"Gaia DR3 {source_id}" in adql
            return pd.DataFrame(
                {
                    "id": [f"Gaia DR3 {source_id}"],
                    "main_id": ["Synthetic object"],
                    "otype": ["Star"],
                }
            )
        if endpoint == catalogues.VIZIER_TAP_SYNC:
            assert '"B/vsx/vsx"' in adql
            assert "0.000555555556" in adql
            return pd.DataFrame(
                {
                    "Name": ["Synthetic variable"],
                    "Type": ["EA"],
                    "RAJ2000": [123.4],
                    "DEJ2000": [-12.3],
                }
            )
        raise AssertionError(endpoint)

    monkeypatch.setattr(catalogues, "_tap_csv", fake_tap)
    simbad = catalogues.simbad_exact_gaia_id_crossmatch([source_id])
    assert bool(simbad.iloc[0]["SIMBAD_MATCHED"])
    assert simbad.iloc[0]["SIMBAD_MAIN_IDS"] == "Synthetic object"
    vsx = catalogues.vsx_coordinate_crossmatch(
        pd.DataFrame(
            {"SOURCE_ID": [source_id], "TARGET_RA": [123.4], "TARGET_DEC": [-12.3]}
        )
    )
    assert bool(vsx.iloc[0]["VSX_MATCHED_2ARCSEC"])
    assert vsx.iloc[0]["VSX_TYPES"] == "EA"


def test_empty_vsx_input_preserves_merge_contract():
    result = catalogues.vsx_coordinate_crossmatch(
        pd.DataFrame(columns=["SOURCE_ID", "TARGET_RA", "TARGET_DEC"])
    )
    assert result.empty
    assert "SOURCE_ID" in result.columns
    assert "VSX_MATCHED_2ARCSEC" in result.columns
