# -*- coding: utf-8 -*-
"""
pipeline.py  —  Master entry point for the flood material damage pipeline.

Usage
-----
Run from the modelling/ directory with the geo conda environment:

    <geo_env>/python.exe pipeline.py

Configuration
-------------
Edit the CONFIG block below.  All other files (steps/) should not need
to be touched for routine runs.

Pipeline stages
---------------
1. Gridded materials
   USE_EXISTING_MATERIALS = True   -> load pre-computed CSV (fast, default)
   USE_EXISTING_MATERIALS = False  -> recompute from NLC + RTP shapefiles
                                      (needed when changing PIXEL_RES or NLC)

2. Depth tables
   REBUILD_DEPTH_TABLES = False    -> skip files that already exist (default)
   REBUILD_DEPTH_TABLES = True     -> force rebuild all depth CSVs

3. Exposure & damage
   Always runs for the selected SCENARIO_LIST and FLOOD_TYPE_LIST.

4. Emissions
   Multiplies material tonnes by emission factors (kgCO2e/kg) from
   Emission_factor.xlsx.  Ensemble members are averaged into scenario
   groups (e.g. rcp4p5_2050_1…5 → rcp4p5_2050).

5. Post-processing
   Adds 'combined' flood_type (river + coastal) for visualisation.
   Outputs the visualisation-ready CSV used by the plotting scripts.

6. Uncertainty
   Computes ensemble spread statistics (mean, std, CV, p05/p95) across
   the 5 GCM members per scenario group.  Requires SCENARIO_LIST to
   include multiple ensemble members (or None for all scenarios).
"""

import os, sys, time
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from steps import gridded_materials, depth_tables, exposure_damage, emissions, post_processing, uncertainty

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  —  edit here
# ══════════════════════════════════════════════════════════════════════════════

BASE = r"C:/Users/xzhon/OneDrive/文档/SIGS/SIGS 科研/flood/flood_2026"

# ── Stage 1: Gridded materials ────────────────────────────────────────────────
USE_EXISTING_MATERIALS  = True
EXISTING_MATERIALS_PATH = f"{BASE}/material_polygons/material_polygons_2024-05-17.csv"

# Only used when USE_EXISTING_MATERIALS = False
# 1/120 matches the Aqueduct raster grid; change e.g. to 1/60 for sensitivity test
PIXEL_RES = 1 / 120

# ── Country filter ────────────────────────────────────────────────────────────
# Set to None to include all countries in COUNTRY_CSV.
# Set to a list to restrict output to those countries only (reproduces 2024 scope).
COUNTRY_FILTER = [
    'Akrotiri and Dhekelia', 'Albania', 'Andorra', 'Austria', 'Belarus',
    'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus',
    'Czechia', 'Denmark', 'Estonia', 'Faroe Islands', 'Finland', 'France',
    'Germany', 'Greece', 'Guernsey', 'Hungary', 'Iceland', 'Ireland',
    'Isle of Man', 'Italy', 'Jersey', 'Kosovo', 'Latvia', 'Liechtenstein',
    'Lithuania', 'Luxembourg', 'Malta', 'Moldova', 'Montenegro', 'Netherlands',
    'North Macedonia', 'Norway', 'Poland', 'Portugal', 'Romania', 'San Marino',
    'Serbia', 'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Switzerland',
    'Turkey', 'Ukraine', 'United Kingdom', 'Åland',
]

# ── Stage 4: Emissions ───────────────────────────────────────────────────────
EMISSION_FACTOR_XLS = f"{BASE}/results_emissions/Emission_factor.xlsx"

# ── Stage 2: Depth tables ─────────────────────────────────────────────────────
REBUILD_DEPTH_TABLES = False

# ── Stage 3: Exposure & damage ────────────────────────────────────────────────
# FLOOD_TYPE_LIST = ['river']
# FLOOD_TYPE_LIST = ['river', 'coastal']
FLOOD_TYPE_LIST = ['river', 'coastal', 'mixed']

# SCENARIO_LIST = ['historical']
# SCENARIO_LIST = ['historical', 'rcp4p5_2050_1']
SCENARIO_LIST = None   # None = run all scenarios in scenario_list.xlsx

# ══════════════════════════════════════════════════════════════════════════════
# PATHS  —  only change if your directory layout differs
# ══════════════════════════════════════════════════════════════════════════════

PATHS = {
    'NLC_SHP'     : f"{BASE}/materials/NLC_data_WGS_1984.shp",
    'RTP_RIVER'   : f"{BASE}/Flood_RasterToPoint/Flood_river_RasterToPoint_RE.shp",
    'RTP_COASTAL' : f"{BASE}/Flood_RasterToPoint/Flood_coastal_RasterToPoint_RE.shp",
    'AQUEDUCT_DIR': f"{BASE}/data/Aqueduct",
    'DEPTH_DIR'   : f"{BASE}/Flood_depth_tables",
    'COUNTRY_CSV' : f"{BASE}/Join_country_names/Flood_polygon_RE_country_names.csv",
    'FLOPROS_CSV' : f"{BASE}/data/Dike_height_csv/Flood_river_coastal_polygon_joining_Prot_scenarios_v2.csv",
    'SUB_COUNTRY_CSV': f"{BASE}/Join_country_names/Flood_polygon_RE_sub_country_names.csv",
    'SCENARIO_XLS': f"{BASE}/data/scenario_list.xlsx",
    'RESULTS_DIR' : os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output'),
}

FLOPROS_COLS = ['pointid_ri', 'pointid_co',
                'r_flopros', 'c_flopros',
                'r_45_50', 'r_85_50', 'r_45_80', 'r_85_80',
                'c_45_50', 'c_85_50', 'c_45_80', 'c_85_80']

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))
    print(f"Pipeline start: {datetime.now()}")

    os.makedirs(PATHS['RESULTS_DIR'], exist_ok=True)

    # ── load scenario table ───────────────────────────────────────────────────
    scenario_table = pd.read_excel(PATHS['SCENARIO_XLS'], sheet_name='full')
    scenario_list  = (SCENARIO_LIST if SCENARIO_LIST is not None
                      else scenario_table['scenario_name'].tolist())

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 1 — Gridded materials
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Stage 1: Gridded materials  [{_e()}]")
    print('='*60)

    if USE_EXISTING_MATERIALS:
        print(f"  Loading: {EXISTING_MATERIALS_PATH}")
        gm_raw = pd.read_csv(EXISTING_MATERIALS_PATH)
        # drop ArcGIS index column if present
        gm_raw = gm_raw.drop(columns=[c for c in gm_raw.columns
                                       if c.startswith('Unnamed')], errors='ignore')
        print(f"  {len(gm_raw):,} rows loaded")

        if 'COUNTRY' not in gm_raw.columns:
            print("  Joining country names ...")
            cn = pd.read_csv(PATHS['COUNTRY_CSV'],
                             usecols=['pointid_ri', 'pointid_co', 'COUNTRY'])
            gm_raw = gm_raw.merge(cn, on=['pointid_ri', 'pointid_co'], how='left')

        if 'r_flopros' not in gm_raw.columns:
            print("  Joining FLOPROS ...")
            fl = pd.read_csv(PATHS['FLOPROS_CSV'], usecols=FLOPROS_COLS)
            gm_raw = gm_raw.merge(fl, on=['pointid_ri', 'pointid_co'], how='left')

        if 'NAME_1' not in gm_raw.columns:
            print("  Joining sub-country names (NAME_1) ...")
            sc = pd.read_csv(PATHS['SUB_COUNTRY_CSV'],
                             usecols=['pointid_ri', 'pointid_co', 'NAME_1'])
            gm_raw = gm_raw.merge(sc, on=['pointid_ri', 'pointid_co'], how='left')

        gridded_mat = gm_raw

    else:
        print(f"  Recomputing (PIXEL_RES={PIXEL_RES:.6f}) ...")
        gm_config = {**PATHS, 'PIXEL_RES': PIXEL_RES}
        gm_core   = gridded_materials.run(gm_config)

        print("  Joining country names ...")
        cn = pd.read_csv(PATHS['COUNTRY_CSV'],
                         usecols=['pointid_ri', 'pointid_co', 'COUNTRY'])
        gm_core = gm_core.merge(cn, on=['pointid_ri', 'pointid_co'], how='left')

        print("  Joining FLOPROS ...")
        fl = pd.read_csv(PATHS['FLOPROS_CSV'], usecols=FLOPROS_COLS)
        gm_core = gm_core.merge(fl, on=['pointid_ri', 'pointid_co'], how='left')

        print("  Joining sub-country names (NAME_1) ...")
        sc = pd.read_csv(PATHS['SUB_COUNTRY_CSV'],
                         usecols=['pointid_ri', 'pointid_co', 'NAME_1'])
        gridded_mat = gm_core.merge(sc, on=['pointid_ri', 'pointid_co'], how='left')

        today   = datetime.now().strftime('%Y-%m-%d')
        res_str = f"res{int(round(1/PIXEL_RES))}" if PIXEL_RES != 1/120 else "default"
        out_mp  = os.path.join(PATHS['RESULTS_DIR'],
                               f"material_polygons_{today}_{res_str}.csv")
        gridded_mat.to_csv(out_mp, index=False)

    # ── apply country filter ──────────────────────────────────────────────────
    if COUNTRY_FILTER is not None:
        before = len(gridded_mat)
        gridded_mat = gridded_mat[gridded_mat['COUNTRY'].isin(COUNTRY_FILTER)]
        print(f"  Country filter: {before:,} → {len(gridded_mat):,} rows "
              f"({len(COUNTRY_FILTER)} countries)")

    print(f"Stage 1 complete  [{_e()}]")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 2 — Depth tables
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Stage 2: Depth tables  [{_e()}]")
    print('='*60)

    depth_tables.run({**PATHS, 'SCENARIO_TABLE': scenario_table},
                     force=REBUILD_DEPTH_TABLES)
    print(f"Stage 2 complete  [{_e()}]")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 3 — Exposure & damage
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Stage 3: Exposure & damage  [{_e()}]")
    print(f"  Scenarios:   {scenario_list}")
    print(f"  Flood types: {FLOOD_TYPE_LIST}")
    print('='*60)

    results = exposure_damage.run(gridded_mat, {
        **PATHS,
        'SCENARIO_TABLE' : scenario_table,
        'SCENARIO_LIST'  : scenario_list,
        'FLOOD_TYPE_LIST': FLOOD_TYPE_LIST,
    })

    today      = datetime.now().strftime('%Y-%m-%d')
    flood_tag  = '+'.join(FLOOD_TYPE_LIST)
    scen_tag   = ('+'.join(scenario_list)
                  if len(scenario_list) <= 3
                  else 'all_scenarios')
    run_tag    = f"{flood_tag}_{scen_tag}_{today}"

    out_path = f"{PATHS['RESULTS_DIR']}/Material_country_{run_tag}.csv"
    results.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}  ({len(results):,} rows)")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 4 — Emissions
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Stage 4: Emissions  [{_e()}]")
    print('='*60)

    emissions_result = emissions.run(results, {
        'EMISSION_FACTOR_XLS': EMISSION_FACTOR_XLS,
    })

    out_em = f"{PATHS['RESULTS_DIR']}/Material_country_emissions_{run_tag}.csv"
    emissions_result.to_csv(out_em, index=False)
    print(f"\nSaved: {out_em}  ({len(emissions_result):,} rows)")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 5 — Post-processing (visualisation-ready output)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Stage 5: Post-processing  [{_e()}]")
    print('='*60)

    pp = post_processing.run(emissions_result, {
        'SUB_COUNTRY_CSV': PATHS['SUB_COUNTRY_CSV'],
    })

    out_pp = f"{PATHS['RESULTS_DIR']}/Material_country_emissions_with_combined_{run_tag}.csv"
    pp['national'].to_csv(out_pp, index=False)
    print(f"\nSaved: {out_pp}  ({len(pp['national']):,} rows)")

    if pp['sub_country'] is not None:
        out_sub = f"{PATHS['RESULTS_DIR']}/Material_sub_country_emissions_with_combined_{run_tag}.csv"
        pp['sub_country'].to_csv(out_sub, index=False)
        print(f"Saved: {out_sub}  ({len(pp['sub_country']):,} rows)")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 6 — Uncertainty
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Stage 6: Uncertainty  [{_e()}]")
    print('='*60)

    unc_mat, unc_em = uncertainty.run(results, emissions_result)

    out_unc_mat = f"{PATHS['RESULTS_DIR']}/Uncertainty_material_{run_tag}.csv"
    out_unc_em  = f"{PATHS['RESULTS_DIR']}/Uncertainty_emissions_{run_tag}.csv"
    unc_mat.to_csv(out_unc_mat, index=False)
    unc_em.to_csv(out_unc_em,  index=False)
    print(f"\nSaved: {out_unc_mat}  ({len(unc_mat):,} rows)")
    print(f"Saved: {out_unc_em}  ({len(unc_em):,} rows)")
    print(f"Pipeline complete.  Total time: {timedelta(seconds=int(time.time()-t0))}")


if __name__ == '__main__':
    main()
