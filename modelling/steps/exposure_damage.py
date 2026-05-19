# -*- coding: utf-8 -*-
"""
steps/exposure_damage.py

Calculates material exposure and EAD (Expected Annual Damage) from flooding,
with and without flood protection (FLOPROS dikes).

Public API
----------
run(gridded_materials, config) -> pd.DataFrame
"""

import time
import numpy as np
import pandas as pd
from datetime import timedelta

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 250, 500, 1000]
DEPTH_COLS     = [f'd_{rp:04d}' for rp in RETURN_PERIODS]
MATERIAL_TYPES = ['Aluminium', 'Concrete', 'Copper', 'Glass', 'Steel', 'Wood']

# Coastal depth column rename map (raw file uses d_002_0 etc.)
COASTAL_RENAME = {
    'd_002_0': 'd_0002', 'd_005_0': 'd_0005', 'd_010_0': 'd_0010',
    'd_025_0': 'd_0025', 'd_050_0': 'd_0050', 'd_100_0': 'd_0100',
    'd_250_0': 'd_0250', 'd_500_0': 'd_0500', 'd_000_0': 'd_1000',
}

_PROBS = np.array([1/2, 1/5, 1/10, 1/25, 1/50, 1/100, 1/250, 1/500, 1/1000, 0],
                  dtype=np.float64)
_W     = (_PROBS[:-1] - _PROBS[1:]) / 2

TRAP      = np.empty(9, dtype=np.float64)
TRAP[0]   = _W[0]
TRAP[1:8] = _W[0:7] + _W[1:8]
# Last interval: assume flood depth stays at d_1000 beyond RP=1000
# i.e. (d_1000 + d_1000) * (1/1000 - 0) / 2 = d_1000 * 1/1000
# This gives TRAP[8] = (1/500-1/1000)/2 + 1/1000 = 0.0015, matching the original script.
TRAP[8]   = _W[8] + _PROBS[8]

PROT_COL_MAP = {
    'river': {
        'historical': 'r_flopros',
        **{f'rcp4p5_2050_{i}': 'r_45_50' for i in range(1, 6)},
        **{f'rcp8p5_2050_{i}': 'r_85_50' for i in range(1, 6)},
        **{f'rcp4p5_2080_{i}': 'r_45_80' for i in range(1, 6)},
        **{f'rcp8p5_2080_{i}': 'r_85_80' for i in range(1, 6)},
    },
    'coastal': {
        'historical': 'c_flopros',
        **{f'rcp4p5_2050_{i}': 'c_45_50' for i in range(1, 6)},
        **{f'rcp8p5_2050_{i}': 'c_85_50' for i in range(1, 6)},
        **{f'rcp4p5_2080_{i}': 'c_45_80' for i in range(1, 6)},
        **{f'rcp8p5_2080_{i}': 'c_85_80' for i in range(1, 6)},
    },
    # mixed uses the more conservative (higher) of river and coastal protection
    'mixed': {
        'historical': 'r_flopros',
        **{f'rcp4p5_2050_{i}': 'r_45_50' for i in range(1, 6)},
        **{f'rcp8p5_2050_{i}': 'r_85_50' for i in range(1, 6)},
        **{f'rcp4p5_2080_{i}': 'r_45_80' for i in range(1, 6)},
        **{f'rcp8p5_2080_{i}': 'r_85_80' for i in range(1, 6)},
    },
}


def _res_damage(d):
    d = np.asarray(d, dtype=np.float64)
    return np.select(
        [d > 6, d > 5, d > 4, d > 3, d > 2, d > 1.5, d > 1, d > 0.5],
        [1.00,  0.95,  0.85,  0.75,  0.60,  0.50,    0.40,  0.25],
        default=0.0)


def _comm_damage(d):
    d = np.asarray(d, dtype=np.float64)
    return np.select(
        [d > 6, d > 5, d > 4, d > 3, d > 2, d > 1.5, d > 1, d > 0.5],
        [1.00,  1.00,  0.90,  0.75,  0.55,  0.45,    0.30,  0.15],
        default=0.0)


def _load_depth(depth_dir, file_name, pid_col, is_coastal=False):
    """Load depth CSV, rename pointid → pid_col, normalise column names."""
    df = pd.read_csv(f"{depth_dir}/{file_name}.csv")
    # raw files have 'pointid' not 'pointid_ri'/'pointid_co'
    if 'pointid' in df.columns and pid_col not in df.columns:
        df = df.rename(columns={'pointid': pid_col})
    # coastal files use different depth column names
    if is_coastal:
        df = df.rename(columns=COASTAL_RENAME)
    # drop grid_code if present
    df = df.drop(columns=[c for c in ['grid_code'] if c in df.columns])
    return df


def run(gridded_materials: pd.DataFrame, config: dict) -> pd.DataFrame:
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))

    scenario_table  = config['SCENARIO_TABLE']
    scenario_list   = config['SCENARIO_LIST']
    flood_type_list = config['FLOOD_TYPE_LIST']
    depth_dir       = config['DEPTH_DIR']

    exposure_rows = []
    ead_rows      = []
    ead_fps_rows  = []

    for scenario_name in scenario_list:
        print(f"\n  [exposure_damage] Scenario: {scenario_name}  [{_e()}]")
        s_row = scenario_table.loc[scenario_table['scenario_name'] == scenario_name]

        for flood_type in flood_type_list:
            print(f"  [exposure_damage]   flood_type: {flood_type}")

            # ── load and merge depth table ────────────────────────────────────
            if flood_type == 'river':
                file_name = s_row['river_file_name'].iloc[0]
                depth_csv = _load_depth(depth_dir, file_name, 'pointid_ri')
                full = gridded_materials.merge(depth_csv, on='pointid_ri', how='left')

            elif flood_type == 'coastal':
                file_name = s_row['coastal_file_name'].iloc[0]
                depth_csv = _load_depth(depth_dir, file_name, 'pointid_co',
                                        is_coastal=True)
                full = gridded_materials.merge(depth_csv, on='pointid_co', how='left')

            elif flood_type == 'mixed':
                r_file = s_row['river_file_name'].iloc[0]
                c_file = s_row['coastal_file_name'].iloc[0]
                r_csv  = _load_depth(depth_dir, r_file, 'pointid_ri')
                c_csv  = _load_depth(depth_dir, c_file, 'pointid_co', is_coastal=True)
                full   = (gridded_materials
                          .merge(r_csv, on='pointid_ri', how='left')
                          .merge(c_csv, on='pointid_co', how='left',
                                 suffixes=['', '_c']))
                for col in DEPTH_COLS:
                    col_c = col + '_c'
                    if col_c in full.columns:
                        full[col] = np.maximum(full[col].fillna(0),
                                               full[col_c].fillna(0))
                        full.drop(columns=[col_c], inplace=True)

            # ── fill missing depth cols with 0 ────────────────────────────────
            for col in DEPTH_COLS:
                if col not in full.columns:
                    full[col] = 0.0
                full[col] = full[col].fillna(0).astype(np.float32)

            # ── pre-compute damage arrays (N × 9) ────────────────────────────
            depth_arr = full[DEPTH_COLS].values.astype(np.float64)
            R_dmg  = _res_damage(depth_arr)
            NR_dmg = _comm_damage(depth_arr)

            # ── protection factors (N × 9) ────────────────────────────────────
            thresholds = np.array(RETURN_PERIODS, dtype=np.float64)
            prot_col   = PROT_COL_MAP[flood_type][scenario_name]
            dike       = full[prot_col].fillna(0).values[:, None]
            pf         = (dike < thresholds).astype(np.float64)

            # ── 1. Exposure to 1-in-100yr flood ──────────────────────────────
            mask_100 = full['d_0100'].values > 0
            exp_df   = full.loc[mask_100, ['COUNTRY', 'NAME_1']].copy().reset_index(drop=True)
            for mt in MATERIAL_TYPES:
                exp_df[mt] = (
                    full.loc[mask_100, f'gridded_R_{mt}'].values +
                    full.loc[mask_100, f'gridded_NR_{mt}'].values)
            exp_country = (exp_df.groupby(['COUNTRY', 'NAME_1'])[MATERIAL_TYPES]
                           .sum().reset_index())
            exp_long = exp_country.melt(id_vars=['COUNTRY', 'NAME_1'],
                                        var_name='material_type', value_name='tonne')
            exp_long['flood_type'] = flood_type
            exp_long['scenario']   = scenario_name
            exposure_rows.append(exp_long)

            # ── 2. EAD without protection ─────────────────────────────────────
            R_contrib  = (R_dmg  * TRAP).sum(axis=1)
            NR_contrib = (NR_dmg * TRAP).sum(axis=1)

            ead_df = full[['COUNTRY', 'NAME_1']].copy().reset_index(drop=True)
            for mt in MATERIAL_TYPES:
                ead_df[mt] = (full[f'gridded_R_{mt}'].values  * R_contrib +
                              full[f'gridded_NR_{mt}'].values * NR_contrib)
            ead_country = ead_df.groupby(['COUNTRY', 'NAME_1'])[MATERIAL_TYPES].sum().reset_index()
            ead_long = ead_country.melt(id_vars=['COUNTRY', 'NAME_1'],
                                        var_name='material_type', value_name='tonne')
            ead_long['flood_type'] = flood_type
            ead_long['scenario']   = scenario_name
            ead_rows.append(ead_long)

            # ── 3. EAD with FLOPROS protection ───────────────────────────────
            R_fps  = (R_dmg  * pf * TRAP).sum(axis=1)
            NR_fps = (NR_dmg * pf * TRAP).sum(axis=1)

            fps_df = full[['COUNTRY', 'NAME_1']].copy().reset_index(drop=True)
            for mt in MATERIAL_TYPES:
                fps_df[mt] = (full[f'gridded_R_{mt}'].values  * R_fps +
                              full[f'gridded_NR_{mt}'].values * NR_fps)
            fps_country = fps_df.groupby(['COUNTRY', 'NAME_1'])[MATERIAL_TYPES].sum().reset_index()
            fps_long = fps_country.melt(id_vars=['COUNTRY', 'NAME_1'],
                                        var_name='material_type', value_name='tonne')
            fps_long['flood_type'] = flood_type
            fps_long['scenario']   = scenario_name
            ead_fps_rows.append(fps_long)

            print(f"  [exposure_damage]   done {scenario_name}/{flood_type}  [{_e()}]")

    exposure_combined = pd.concat(exposure_rows, ignore_index=True)
    ead_combined      = pd.concat(ead_rows,      ignore_index=True)
    ead_fps_combined  = pd.concat(ead_fps_rows,  ignore_index=True)

    exposure_combined['threat'] = 'exposure_100yrs'
    ead_combined['threat']      = 'EAD_no_protection'
    ead_fps_combined['threat']  = 'EAD_current_dike'

    result = pd.concat([exposure_combined, ead_combined, ead_fps_combined],
                       ignore_index=True)
    result['unit'] = 'tonne'
    print(f"  [exposure_damage] Done. {len(result):,} rows  total [{_e()}]")
    return result
