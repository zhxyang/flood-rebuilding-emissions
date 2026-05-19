# -*- coding: utf-8 -*-
"""
steps/depth_tables.py

Extracts per-pixel flood depth values from Aqueduct GeoTIFF rasters.
Each output CSV has one row per flood pixel with all return-period depths.

The existing depth tables in Flood_depth_tables/ already have the wide format
(d_0002 ... d_1000) used by exposure_damage.py.  This step is idempotent:
files that already exist are skipped unless force=True.

Public API
----------
run(config, force=False)
    Writes CSVs to config['DEPTH_DIR'].
    River files:   <scenario_name>.csv  (pointid_ri, d_0002 ... d_1000)
    Coastal files: <scenario_name>.csv  (pointid_co, d_0002 ... d_1000)
"""

import os, glob, time
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from datetime import timedelta

# Return periods and their column names (must match exposure_damage.py)
RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 250, 500, 1000]
DEPTH_COLS     = [f'd_{rp:04d}' for rp in RETURN_PERIODS]

# Aqueduct filename patterns: rp token differs between river and coastal
RIVER_RP_TOKENS   = {2: 'rp00002', 5: 'rp00005', 10: 'rp00010', 25: 'rp00025',
                     50: 'rp00050', 100: 'rp00100', 250: 'rp00250',
                     500: 'rp00500', 1000: 'rp01000'}
COASTAL_RP_TOKENS = {2: 'rp0002', 5: 'rp0005', 10: 'rp0010', 25: 'rp0025',
                     50: 'rp0050', 100: 'rp0100', 250: 'rp0250',
                     500: 'rp0500', 1000: 'rp1000'}


def _sample_raster(tif_path, coords):
    """Sample raster at (x, y) coordinate list. Returns float32 array."""
    with rasterio.open(tif_path) as src:
        nd = src.nodata
        vals = np.array([v[0] for v in src.sample(coords)], dtype=np.float32)
    if nd is not None:
        vals[vals == nd] = np.nan
    return vals


def _build_wide_table(base_stem, rtp_gdf, pid_col, rp_tokens, aqueduct_dir):
    """
    For one scenario (base_stem), find all return-period TIFs and stack into
    a wide DataFrame: [pid_col, d_0002, d_0005, ..., d_1000].
    Returns None if no TIFs found.
    """
    coords = list(zip(rtp_gdf.geometry.x.values, rtp_gdf.geometry.y.values))
    pids   = rtp_gdf['pointid'].values

    cols = {}
    for rp, token in rp_tokens.items():
        pattern = os.path.join(aqueduct_dir, f"{base_stem}_{token}*.tif")
        matches = glob.glob(pattern)
        if not matches:
            return None   # missing TIF for this scenario
        tif = matches[0]
        cols[f'd_{rp:04d}'] = _sample_raster(tif, coords)

    df = pd.DataFrame({pid_col: pids, **cols})
    # keep only rows where at least one depth > 0
    depth_arr = df[DEPTH_COLS].values
    df = df[(~np.isnan(depth_arr)).any(axis=1) & (np.nanmax(depth_arr, axis=1) > 0)]
    df[DEPTH_COLS] = df[DEPTH_COLS].fillna(0)
    return df.reset_index(drop=True)


def run(config: dict, force: bool = False):
    """
    Parameters (from config dict)
    -----------------------------
    RTP_RIVER      : path to river RasterToPoint shapefile
    RTP_COASTAL    : path to coastal RasterToPoint shapefile
    AQUEDUCT_DIR   : directory containing Aqueduct TIF files
    DEPTH_DIR      : output directory for depth CSVs
    SCENARIO_TABLE : pd.DataFrame with columns scenario_name,
                     river_file_name, coastal_file_name
    """
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))

    os.makedirs(config['DEPTH_DIR'], exist_ok=True)
    scenario_table = config['SCENARIO_TABLE']

    print(f"  [depth_tables] Loading RTP shapefiles ...  [{_e()}]")
    rtp_ri = gpd.read_file(config['RTP_RIVER'],   include_fields=['pointid', 'geometry'])
    rtp_co = gpd.read_file(config['RTP_COASTAL'], include_fields=['pointid', 'geometry'])
    print(f"  [depth_tables] River: {len(rtp_ri):,}  Coastal: {len(rtp_co):,}  [{_e()}]")

    n = len(scenario_table)
    for i, row in scenario_table.iterrows():
        scenario = row['scenario_name']

        # ── river ─────────────────────────────────────────────────────────────
        river_stem = row['river_file_name']
        out_river  = os.path.join(config['DEPTH_DIR'], f"{river_stem}.csv")
        if os.path.exists(out_river) and not force:
            print(f"  [depth_tables] [{i+1}/{n}] skip (exists): {river_stem}.csv")
        else:
            print(f"  [depth_tables] [{i+1}/{n}] building {river_stem}.csv ...  [{_e()}]")
            df = _build_wide_table(river_stem, rtp_ri, 'pointid_ri',
                                   RIVER_RP_TOKENS, config['AQUEDUCT_DIR'])
            if df is not None:
                df.to_csv(out_river, index=False)
                print(f"    saved {len(df):,} rows  [{_e()}]")
            else:
                print(f"    WARNING: TIFs not found for {river_stem}, skipped")

        # ── coastal ───────────────────────────────────────────────────────────
        coastal_stem = row['coastal_file_name']
        out_coastal  = os.path.join(config['DEPTH_DIR'], f"{coastal_stem}.csv")
        if os.path.exists(out_coastal) and not force:
            print(f"  [depth_tables] [{i+1}/{n}] skip (exists): {coastal_stem}.csv")
        else:
            print(f"  [depth_tables] [{i+1}/{n}] building {coastal_stem}.csv ...  [{_e()}]")
            df = _build_wide_table(coastal_stem, rtp_co, 'pointid_co',
                                   COASTAL_RP_TOKENS, config['AQUEDUCT_DIR'])
            if df is not None:
                df.to_csv(out_coastal, index=False)
                print(f"    saved {len(df):,} rows  [{_e()}]")
            else:
                print(f"    WARNING: TIFs not found for {coastal_stem}, skipped")

    print(f"  [depth_tables] Done  total [{_e()}]")
