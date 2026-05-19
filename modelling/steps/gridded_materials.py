# -*- coding: utf-8 -*-
"""
steps/gridded_materials.py

Computes gridded building materials by intersecting NLC polygons with flood
raster pixels.  Replaces the ArcGIS Tabulate Intersection step.

Public API
----------
run(config) -> pd.DataFrame
    Returns a DataFrame with one row per (pointid_ri, pointid_co) pixel,
    columns: pointid_ri, pointid_co, category,
             gridded_R_*, gridded_NR_*, gridded_MS_sum
    Does NOT include COUNTRY or FLOPROS — those are joined in pipeline.py.
"""

import os, time, warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from datetime import timedelta

warnings.filterwarnings('ignore')

# ── column name constants ──────────────────────────────────────────────────────
NLC_KEEP    = ['ID', 'R_Concrete', 'R_Steel', 'R_Copper', 'R_Aluminum',
               'R_Wood', 'R_Glass', 'NR_Concret', 'NR_Steel', 'NR_Copper',
               'NR_Aluminu', 'NR_Wood', 'NR_Glass', 'MS_sum']
NLC_R_COLS  = ['R_Concrete', 'R_Steel', 'R_Copper', 'R_Aluminum', 'R_Wood', 'R_Glass']
NLC_NR_COLS = ['NR_Concret', 'NR_Steel', 'NR_Copper', 'NR_Aluminu', 'NR_Wood', 'NR_Glass']
OUT_R_COLS  = ['gridded_R_Concrete', 'gridded_R_Steel', 'gridded_R_Copper',
               'gridded_R_Aluminium', 'gridded_R_Wood', 'gridded_R_Glass']
OUT_NR_COLS = ['gridded_NR_Concrete', 'gridded_NR_Steel', 'gridded_NR_Copper',
               'gridded_NR_Aluminium', 'gridded_NR_Wood', 'gridded_NR_Glass']


def run(config: dict) -> pd.DataFrame:
    """
    Parameters (from config dict)
    -----------------------------
    NLC_SHP     : path to NLC_data_WGS_1984.shp
    RTP_RIVER   : path to Flood_river_RasterToPoint_RE.shp
    RTP_COASTAL : path to Flood_coastal_RasterToPoint_RE.shp
    PIXEL_RES   : raster pixel size in degrees (default 1/120 ≈ 0.00833)

    Returns
    -------
    pd.DataFrame  with columns pointid_ri, pointid_co, category,
                  gridded_R_*, gridded_NR_*, gridded_MS_sum
    """
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))

    pixel_res = config.get('PIXEL_RES', 1 / 120)
    half      = pixel_res / 2

    # ── Step 1: Load NLC ──────────────────────────────────────────────────────
    print(f"  [gridded_materials] Loading NLC ...  [{_e()}]")
    nlc = gpd.read_file(config['NLC_SHP'], include_fields=NLC_KEEP)
    nlc = nlc.rename(columns={'ID': 'id_mat'})
    if nlc.crs is None or str(nlc.crs).upper() != 'EPSG:4326':
        nlc = nlc.to_crs('EPSG:4326')
    nlc['nlc_area'] = nlc.geometry.area
    nlc_bbox = nlc.total_bounds
    print(f"  [gridded_materials] {len(nlc):,} NLC polygons  [{_e()}]")

    # ── Step 2: Load RTP, clip to NLC bbox ───────────────────────────────────
    print(f"  [gridded_materials] Loading RTP shapefiles ...  [{_e()}]")
    rtp_ri = gpd.read_file(config['RTP_RIVER'],   include_fields=['pointid', 'geometry'],
                           bbox=tuple(nlc_bbox))
    rtp_co = gpd.read_file(config['RTP_COASTAL'], include_fields=['pointid', 'geometry'],
                           bbox=tuple(nlc_bbox))
    print(f"  [gridded_materials] River pixels: {len(rtp_ri):,}  Coastal: {len(rtp_co):,}  [{_e()}]")

    # ── Step 3: Build pixel polygons ─────────────────────────────────────────
    print(f"  [gridded_materials] Building pixel polygons (res={pixel_res:.6f}°) ...  [{_e()}]")

    def _to_pixels(rtp_gdf, pid_col):
        xs = rtp_gdf.geometry.x.values
        ys = rtp_gdf.geometry.y.values
        geoms = [box(x - half, y - half, x + half, y + half) for x, y in zip(xs, ys)]
        return gpd.GeoDataFrame({pid_col: rtp_gdf['pointid'].values},
                                geometry=geoms, crs='EPSG:4326')

    pixels_ri = _to_pixels(rtp_ri, 'pointid_ri')
    pixels_co = _to_pixels(rtp_co, 'pointid_co')

    # ── Step 4: Vector overlay (exact area intersection) ─────────────────────
    def _tabulate(nlc_gdf, pixel_gdf, pid_col):
        print(f"  [gridded_materials] Overlay NLC x {pid_col} ...  [{_e()}]")
        inter = gpd.overlay(nlc_gdf[['id_mat', 'nlc_area', 'geometry']],
                            pixel_gdf[[pid_col, 'geometry']],
                            how='intersection', keep_geom_type=False)
        if len(inter) == 0:
            return pd.DataFrame(columns=['id_mat', pid_col, 'PERCENTAGE'])
        inter['PERCENTAGE'] = (inter.geometry.area / inter['nlc_area']) * 100.0
        return (inter[['id_mat', pid_col, 'PERCENTAGE']]
                .groupby(['id_mat', pid_col], as_index=False)['PERCENTAGE'].sum())

    river_tab   = _tabulate(nlc, pixels_ri, 'pointid_ri')
    coastal_tab = _tabulate(nlc, pixels_co, 'pointid_co')
    print(f"  [gridded_materials] river_tab: {len(river_tab):,}  coastal_tab: {len(coastal_tab):,}  [{_e()}]")

    # ── Step 5: Classify c1/c2/c3 and combine ────────────────────────────────
    print(f"  [gridded_materials] Classifying categories ...  [{_e()}]")
    both_ids = set(river_tab['id_mat']).intersection(set(coastal_tab['id_mat']))

    river_tab['pointid_co']   = 0
    coastal_tab['pointid_ri'] = 0

    # c2: for each river row whose id_mat also has coastal coverage,
    # attach the dominant coastal pointid (highest PERCENTAGE for that id_mat)
    river_c2 = river_tab[river_tab['id_mat'].isin(both_ids)].copy()
    coastal_dominant = (coastal_tab[coastal_tab['id_mat'].isin(both_ids)]
                        .sort_values('PERCENTAGE', ascending=False)
                        .drop_duplicates('id_mat')[['id_mat', 'pointid_co']])
    river_c2 = river_c2.merge(coastal_dominant, on='id_mat', how='left')
    river_c2['pointid_co'] = river_c2['pointid_co_y'].fillna(0).astype(np.int64)
    river_c2 = river_c2.drop(columns=['pointid_co_x', 'pointid_co_y'])

    river_c1   = river_tab[~river_tab['id_mat'].isin(both_ids)].copy()
    coastal_c3 = coastal_tab[~coastal_tab['id_mat'].isin(both_ids)].copy()

    tab = pd.concat([river_c1, river_c2, coastal_c3], ignore_index=True)
    tab = tab[~((tab['pointid_ri'] == 0) & (tab['pointid_co'] == 0))]
    tab['category'] = np.select(
        [(tab['pointid_ri'] != 0) & (tab['pointid_co'] == 0),
         (tab['pointid_ri'] != 0) & (tab['pointid_co'] != 0),
         (tab['pointid_ri'] == 0) & (tab['pointid_co'] != 0)],
        ['c1', 'c2', 'c3'], default='unknown')
    print(f"  [gridded_materials] {tab['category'].value_counts().to_dict()}  [{_e()}]")

    # ── Step 6: Calculate gridded materials ───────────────────────────────────
    print(f"  [gridded_materials] Calculating material quantities ...  [{_e()}]")
    mat_cols = NLC_R_COLS + NLC_NR_COLS + ['MS_sum']
    tab = tab.merge(nlc[['id_mat'] + mat_cols], on='id_mat', how='left')
    pct = tab['PERCENTAGE'] * 0.01
    for src, dst in zip(NLC_R_COLS,  OUT_R_COLS):  tab[dst] = tab[src] * pct
    for src, dst in zip(NLC_NR_COLS, OUT_NR_COLS): tab[dst] = tab[src] * pct
    tab['gridded_MS_sum'] = tab['MS_sum'] * pct

    out_cols = OUT_R_COLS + OUT_NR_COLS + ['gridded_MS_sum']
    gm = (tab[['pointid_ri', 'pointid_co', 'category'] + out_cols]
          .groupby(['pointid_ri', 'pointid_co', 'category'], as_index=False).sum())

    print(f"  [gridded_materials] Done. {len(gm):,} rows  total [{_e()}]")
    return gm
