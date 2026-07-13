from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits
from scipy.stats import fisher_exact

from .provenance import runtime_environment


GAIA_DR3_TAP_SYNC = "https://gea.esac.esa.int/tap-server/tap/sync"
SIMBAD_TAP_SYNC = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
VIZIER_TAP_SYNC = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync"
SPECDIS_V21_SHA256 = "25075043f066c27af6ac25edd381cdff20930ed87f9d337b2d9c2df1403ddf1b"
GAIA_TABLES = {
    "GAIA_NSS_TWO_BODY": ("gaiadr3.nss_two_body_orbit", "nss_solution_type"),
    "GAIA_NSS_ACCELERATION": ("gaiadr3.nss_acceleration_astro", None),
    "GAIA_NSS_NON_LINEAR_SPECTRO": ("gaiadr3.nss_non_linear_spectro", None),
    "GAIA_VARI_SUMMARY": ("gaiadr3.vari_summary", None),
}


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tap_csv(
    adql: str, endpoint: str = GAIA_DR3_TAP_SYNC, attempts: int = 3
) -> pd.DataFrame:
    payload = urllib.parse.urlencode(
        {
            "REQUEST": "doQuery",
            "LANG": "ADQL",
            "FORMAT": "csv",
            "QUERY": adql,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"User-Agent": "desi-rv-variables/0.3.0"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
            return pd.read_csv(io.StringIO(body), dtype={"source_id": "string"})
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable TAP retry state")


def gaia_dr3_exact_id_crossmatch(
    source_ids: list[int] | set[int] | np.ndarray,
    chunk_size: int = 100,
) -> pd.DataFrame:
    ids = sorted({int(item) for item in source_ids if pd.notna(item) and int(item) > 0})
    result = pd.DataFrame({"SOURCE_ID": pd.Series(ids, dtype="int64")})
    if not ids:
        for output_column in GAIA_TABLES:
            result[output_column] = pd.Series(dtype="bool")
        result["GAIA_NSS_SOLUTION_TYPES"] = pd.Series(dtype="string")
        return result

    matches: dict[str, set[int]] = {column: set() for column in GAIA_TABLES}
    solution_types: dict[int, set[str]] = {}
    for start in range(0, len(ids), chunk_size):
        chunk = ids[start : start + chunk_size]
        in_clause = ",".join(str(item) for item in chunk)
        for output_column, (table, detail_column) in GAIA_TABLES.items():
            selected = (
                "source_id" if detail_column is None else f"source_id,{detail_column}"
            )
            frame = _tap_csv(
                f"SELECT {selected} FROM {table} WHERE source_id IN ({in_clause})"
            )
            if frame.empty:
                continue
            matched_ids = frame["source_id"].dropna().astype("int64")
            matches[output_column].update(int(item) for item in matched_ids)
            if detail_column is not None and detail_column in frame.columns:
                for record in (
                    frame[["source_id", detail_column]].dropna().itertuples(index=False)
                ):
                    solution_types.setdefault(int(record[0]), set()).add(str(record[1]))

    for output_column in GAIA_TABLES:
        result[output_column] = result["SOURCE_ID"].isin(matches[output_column])
    result["GAIA_NSS_SOLUTION_TYPES"] = (
        result["SOURCE_ID"]
        .map(
            lambda source_id: ";".join(
                sorted(solution_types.get(int(source_id), set()))
            )
        )
        .astype("string")
    )
    return result


def simbad_exact_gaia_id_crossmatch(
    source_ids: list[int] | set[int] | np.ndarray,
    chunk_size: int = 100,
) -> pd.DataFrame:
    ids = sorted({int(item) for item in source_ids if pd.notna(item) and int(item) > 0})
    matches: dict[int, list[tuple[str, str]]] = {source_id: [] for source_id in ids}
    for start in range(0, len(ids), chunk_size):
        chunk = ids[start : start + chunk_size]
        identifiers = ",".join(f"'Gaia DR3 {source_id}'" for source_id in chunk)
        query = (
            "SELECT i.id,b.main_id,b.otype FROM ident AS i "
            "JOIN basic AS b ON i.oidref=b.oid "
            f"WHERE i.id IN ({identifiers})"
        )
        frame = _tap_csv(query, endpoint=SIMBAD_TAP_SYNC)
        for record in frame.itertuples(index=False):
            identifier = str(record[0]).strip()
            try:
                source_id = int(identifier.rsplit(" ", 1)[-1])
            except ValueError:
                continue
            if source_id in matches:
                matches[source_id].append(
                    (str(record[1]).strip(), str(record[2]).strip())
                )
    return pd.DataFrame(
        {
            "SOURCE_ID": pd.Series(ids, dtype="int64"),
            "SIMBAD_MATCHED": [bool(matches[source_id]) for source_id in ids],
            "SIMBAD_MAIN_IDS": [
                ";".join(sorted({item[0] for item in matches[source_id]}))
                for source_id in ids
            ],
            "SIMBAD_OBJECT_TYPES": [
                ";".join(sorted({item[1] for item in matches[source_id]}))
                for source_id in ids
            ],
        }
    )


def vsx_coordinate_crossmatch(
    candidates: pd.DataFrame,
    radius_arcsec: float = 2.0,
) -> pd.DataFrame:
    required_columns = ["SOURCE_ID", "TARGET_RA", "TARGET_DEC"]
    missing = set(required_columns).difference(candidates.columns)
    if missing:
        raise ValueError(f"VSX candidate table missing columns: {sorted(missing)}")
    if radius_arcsec <= 0:
        raise ValueError("radius_arcsec must be positive")
    output_columns = [
        "SOURCE_ID",
        "VSX_MATCHED_2ARCSEC",
        "VSX_N_MATCHES_2ARCSEC",
        "VSX_NAMES",
        "VSX_TYPES",
    ]
    if candidates.empty:
        return pd.DataFrame(columns=output_columns)
    radius_degrees = radius_arcsec / 3600.0
    rows: list[dict[str, object]] = []
    for record in (
        candidates[required_columns]
        .drop_duplicates("SOURCE_ID")
        .itertuples(index=False)
    ):
        values = dict(zip(required_columns, record, strict=True))
        source_id = int(values["SOURCE_ID"])
        ra = float(values["TARGET_RA"])
        dec = float(values["TARGET_DEC"])
        query = (
            'SELECT Name,Type,RAJ2000,DEJ2000 FROM "B/vsx/vsx" WHERE '
            "1=CONTAINS(POINT('ICRS',RAJ2000,DEJ2000),"
            f"CIRCLE('ICRS',{ra:.10f},{dec:.10f},{radius_degrees:.12f}))"
        )
        frame = _tap_csv(query, endpoint=VIZIER_TAP_SYNC)
        rows.append(
            {
                "SOURCE_ID": source_id,
                "VSX_MATCHED_2ARCSEC": bool(len(frame)),
                "VSX_N_MATCHES_2ARCSEC": int(len(frame)),
                "VSX_NAMES": ";".join(
                    sorted(
                        frame.get("Name", pd.Series(dtype="string"))
                        .dropna()
                        .astype(str)
                    )
                ),
                "VSX_TYPES": ";".join(
                    sorted(
                        frame.get("Type", pd.Series(dtype="string"))
                        .dropna()
                        .astype(str)
                    )
                ),
            }
        )
    return pd.DataFrame(rows, columns=output_columns)


def specdis_exact_id_crossmatch(
    path: str | Path,
    source_ids: list[int] | set[int] | np.ndarray,
) -> pd.DataFrame:
    ids = sorted({int(item) for item in source_ids if pd.notna(item) and int(item) > 0})
    columns = [
        "SOURCE_ID",
        "SPECDIS_MATCHED",
        "SPECDIS_N_ROWS",
        "SPECDIS_BINARY_CANDIDATE",
        "SPECDIS_BINARY_POSSIBILITY_MAX",
    ]
    if not ids:
        return pd.DataFrame(columns=columns)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    with fits.open(path, memmap=True) as hdul:
        table_hdu = next(
            (hdu for hdu in hdul[1:] if isinstance(hdu, fits.BinTableHDU)),
            None,
        )
        if table_hdu is None or table_hdu.data is None:
            raise ValueError(f"no binary table found in {path}")
        names = set(table_hdu.columns.names)
        required = {"SOURCE_ID", "BINARY_FLAG", "BINARY_POSSIBILITY"}
        missing = required.difference(names)
        if missing:
            raise ValueError(f"SpecDis table missing columns: {sorted(missing)}")
        source = np.asarray(table_hdu.data["SOURCE_ID"], dtype=np.int64)
        mask = np.isin(source, np.asarray(ids, dtype=np.int64))
        matched_source = source[mask]
        binary_flag = np.asarray(table_hdu.data["BINARY_FLAG"], dtype=np.int64)[mask]
        binary_probability = np.asarray(
            table_hdu.data["BINARY_POSSIBILITY"], dtype=float
        )[mask]

    matched = pd.DataFrame(
        {
            "SOURCE_ID": matched_source,
            "BINARY_FLAG": binary_flag,
            "BINARY_POSSIBILITY": binary_probability,
        }
    )
    if matched.empty:
        aggregate = pd.DataFrame(columns=columns)
    else:
        aggregate = (
            matched.groupby("SOURCE_ID", sort=True)
            .agg(
                SPECDIS_N_ROWS=("SOURCE_ID", "size"),
                SPECDIS_BINARY_CANDIDATE=(
                    "BINARY_FLAG",
                    lambda values: bool((values == 0).any()),
                ),
                SPECDIS_BINARY_POSSIBILITY_MAX=("BINARY_POSSIBILITY", "max"),
            )
            .reset_index()
        )
        aggregate["SPECDIS_MATCHED"] = True
    result = pd.DataFrame({"SOURCE_ID": pd.Series(ids, dtype="int64")})
    result = result.merge(aggregate, on="SOURCE_ID", how="left", validate="one_to_one")
    result["SPECDIS_MATCHED"] = (
        result["SPECDIS_MATCHED"].astype("boolean").fillna(False)
    )
    result["SPECDIS_N_ROWS"] = (
        pd.to_numeric(result["SPECDIS_N_ROWS"], errors="coerce")
        .fillna(0)
        .astype("int64")
    )
    result["SPECDIS_BINARY_CANDIDATE"] = (
        result["SPECDIS_BINARY_CANDIDATE"].astype("boolean").fillna(False)
    )
    return result[columns]


def declared_catalogue_crossmatch(
    candidates: pd.DataFrame,
    specdis_path: str | Path,
) -> pd.DataFrame:
    if "SOURCE_ID" not in candidates:
        raise ValueError("candidate table must contain SOURCE_ID")
    source_ids = candidates["SOURCE_ID"].dropna().astype("int64").tolist()
    gaia = gaia_dr3_exact_id_crossmatch(source_ids)
    specdis = specdis_exact_id_crossmatch(specdis_path, source_ids)
    result = candidates.merge(gaia, on="SOURCE_ID", how="left", validate="many_to_one")
    result = result.merge(specdis, on="SOURCE_ID", how="left", validate="many_to_one")
    match_columns = [
        "GAIA_NSS_TWO_BODY",
        "GAIA_NSS_ACCELERATION",
        "GAIA_NSS_NON_LINEAR_SPECTRO",
        "GAIA_VARI_SUMMARY",
        "SPECDIS_BINARY_CANDIDATE",
    ]
    for column in match_columns:
        result[column] = result[column].astype("boolean").fillna(False)
    result["NO_DECLARED_CATALOGUE_MATCH"] = ~result[match_columns].any(axis=1)
    return result


def crossmatch_experiment_outputs(
    experiment_dir: str | Path,
    specdis_path: str | Path,
    expected_specdis_sha256: str = SPECDIS_V21_SHA256,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    experiment_dir = Path(experiment_dir)
    specdis_path = Path(specdis_path)
    actual_specdis_sha256 = _sha256(specdis_path)
    if actual_specdis_sha256 != expected_specdis_sha256:
        raise ValueError(
            f"SpecDis SHA-256 mismatch: expected {expected_specdis_sha256}, "
            f"got {actual_specdis_sha256}"
        )
    high_eligible = pd.read_parquet(
        experiment_dir / "high_amplitude_eligible_sources.parquet"
    )
    high = pd.read_parquet(experiment_dir / "high_amplitude_candidates.parquet")
    acceleration = pd.read_parquet(experiment_dir / "acceleration_candidates.parquet")
    metal = pd.read_parquet(experiment_dir / "metal_poor_candidates.parquet")

    population = high_eligible[["GROUP_ID", "SOURCE_ID"]].copy()
    population["HIGH_AMPLITUDE_ELIGIBLE"] = True
    high_base = high[["GROUP_ID", "SOURCE_ID"]].copy()
    high_base["IN_HIGH_AMPLITUDE"] = True
    acceleration_base = acceleration[["GROUP_ID", "SOURCE_ID"]].copy()
    acceleration_base["IN_ACCELERATION"] = True
    population = population.merge(
        high_base,
        on=["GROUP_ID", "SOURCE_ID"],
        how="outer",
        validate="one_to_one",
    )
    population = population.merge(
        acceleration_base,
        on=["GROUP_ID", "SOURCE_ID"],
        how="outer",
        validate="one_to_one",
    )
    for column in [
        "HIGH_AMPLITUDE_ELIGIBLE",
        "IN_HIGH_AMPLITUDE",
        "IN_ACCELERATION",
    ]:
        population[column] = population[column].astype("boolean").fillna(False)

    population_crossmatch = declared_catalogue_crossmatch(population, specdis_path)
    eligible_crossmatch = population_crossmatch[
        population_crossmatch["HIGH_AMPLITUDE_ELIGIBLE"]
    ].copy()
    crossmatch = population_crossmatch[
        population_crossmatch["IN_HIGH_AMPLITUDE"]
        | population_crossmatch["IN_ACCELERATION"]
    ].copy()
    simbad = simbad_exact_gaia_id_crossmatch(crossmatch["SOURCE_ID"].tolist())
    crossmatch = crossmatch.merge(
        simbad, on="SOURCE_ID", how="left", validate="many_to_one"
    )
    metal_external = metal.merge(
        crossmatch,
        on=["GROUP_ID", "SOURCE_ID", "IN_HIGH_AMPLITUDE", "IN_ACCELERATION"],
        how="left",
        validate="one_to_one",
    )
    vsx = vsx_coordinate_crossmatch(metal_external)
    metal_external = metal_external.merge(
        vsx, on="SOURCE_ID", how="left", validate="one_to_one"
    )
    metal_external["NO_EXTENDED_CATALOGUE_MATCH"] = (
        metal_external["NO_DECLARED_CATALOGUE_MATCH"].fillna(False)
        & ~metal_external["SIMBAD_MATCHED"].fillna(False)
        & ~metal_external["VSX_MATCHED_2ARCSEC"].fillna(False)
    )
    crossmatch_path = experiment_dir / "external_catalogue_crossmatch.parquet"
    eligible_crossmatch_path = (
        experiment_dir / "high_amplitude_eligible_external_crossmatch.parquet"
    )
    metal_path = experiment_dir / "metal_poor_external_screen.parquet"
    eligible_crossmatch.to_parquet(eligible_crossmatch_path, index=False)
    crossmatch.to_parquet(crossmatch_path, index=False)
    metal_external.to_parquet(metal_path, index=False)
    gaia_match_columns = [
        "GAIA_NSS_TWO_BODY",
        "GAIA_NSS_ACCELERATION",
        "GAIA_NSS_NON_LINEAR_SPECTRO",
        "GAIA_VARI_SUMMARY",
    ]
    known_external = ~eligible_crossmatch["NO_DECLARED_CATALOGUE_MATCH"]
    detected_high_amplitude = eligible_crossmatch["IN_HIGH_AMPLITUDE"]
    n_detected_high_amplitude = int(detected_high_amplitude.sum())
    n_nondetected_high_amplitude = int((~detected_high_amplitude).sum())
    n_detected_known = int((detected_high_amplitude & known_external).sum())
    n_nondetected_known = int(((~detected_high_amplitude) & known_external).sum())
    known_match_contingency = [
        [n_detected_known, n_detected_high_amplitude - n_detected_known],
        [n_nondetected_known, n_nondetected_high_amplitude - n_nondetected_known],
    ]
    if n_detected_high_amplitude and n_nondetected_high_amplitude:
        known_match_odds_ratio, known_match_pvalue = fisher_exact(
            known_match_contingency, alternative="two-sided"
        )
    else:
        known_match_odds_ratio, known_match_pvalue = np.nan, np.nan
    manifest = {
        "query_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_environment": runtime_environment(),
        "specdis": {
            "name": specdis_path.name,
            "sha256": actual_specdis_sha256,
            "expected_sha256": expected_specdis_sha256,
        },
        "gaia": {
            "release": "DR3",
            "tap_endpoint": GAIA_DR3_TAP_SYNC,
            "tables": [table for table, _detail in GAIA_TABLES.values()],
        },
        "secondary_catalogues": {
            "simbad_tap_endpoint": SIMBAD_TAP_SYNC,
            "simbad_rule": "exact Gaia DR3 identifier",
            "vsx_tap_endpoint": VIZIER_TAP_SYNC,
            "vsx_table": "B/vsx/vsx",
            "vsx_radius_arcsec": 2.0,
        },
        "high_amplitude_external_validation": {
            "contingency_rows": ["detected", "eligible_not_detected"],
            "contingency_columns": ["declared_match", "no_declared_match"],
            "contingency_table": known_match_contingency,
            "descriptive_fisher_exact_odds_ratio": float(known_match_odds_ratio),
            "descriptive_fisher_exact_pvalue": float(known_match_pvalue),
            "interpretation": (
                "post-selection external positive control; not a discovery significance"
            ),
        },
        "counts": {
            "high_amplitude_eligible_crossmatched": int(len(eligible_crossmatch)),
            "high_amplitude_detected_known_catalogue_match": n_detected_known,
            "high_amplitude_detected_known_catalogue_match_fraction": (
                n_detected_known / n_detected_high_amplitude
                if n_detected_high_amplitude
                else None
            ),
            "high_amplitude_nondetected_known_catalogue_match": n_nondetected_known,
            "high_amplitude_nondetected_known_catalogue_match_fraction": (
                n_nondetected_known / n_nondetected_high_amplitude
                if n_nondetected_high_amplitude
                else None
            ),
            "detected_sources_crossmatched": int(len(crossmatch)),
            "gaia_nss_or_variability_match": int(
                crossmatch[gaia_match_columns].any(axis=1).sum()
            ),
            "specdis_binary_candidate": int(
                crossmatch["SPECDIS_BINARY_CANDIDATE"].sum()
            ),
            "no_declared_catalogue_match": int(
                crossmatch["NO_DECLARED_CATALOGUE_MATCH"].sum()
            ),
            "metal_poor_screen_sources": int(len(metal_external)),
            "metal_poor_no_declared_catalogue_match": int(
                metal_external["NO_DECLARED_CATALOGUE_MATCH"].fillna(False).sum()
            ),
            "simbad_exact_id_match": int(
                crossmatch["SIMBAD_MATCHED"].fillna(False).sum()
            ),
            "metal_poor_vsx_match_2arcsec": int(
                metal_external["VSX_MATCHED_2ARCSEC"].fillna(False).sum()
            ),
            "metal_poor_no_extended_catalogue_match": int(
                metal_external["NO_EXTENDED_CATALOGUE_MATCH"].fillna(False).sum()
            ),
        },
        "outputs": {
            "high_amplitude_eligible_external_crossmatch": {
                "name": eligible_crossmatch_path.name,
                "sha256": _sha256(eligible_crossmatch_path),
            },
            "external_catalogue_crossmatch": {
                "name": crossmatch_path.name,
                "sha256": _sha256(crossmatch_path),
            },
            "metal_poor_external_screen": {
                "name": metal_path.name,
                "sha256": _sha256(metal_path),
            },
        },
    }
    manifest_path = experiment_dir / "catalogue_crossmatch_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return crossmatch, metal_external, manifest
