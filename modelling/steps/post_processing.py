# -*- coding: utf-8 -*-
"""
steps/post_processing.py

Prepares visualisation-ready datasets from pipeline outputs.

Two operations:
1. Add 'combined' flood_type = river + coastal (summed per region/country)
2. Aggregate to national level (drop NAME_1) for country-level maps

Public API
----------
run(emissions_df, config) -> dict with keys:
    'sub_country'  : sub-national level with combined flood_type added
    'national'     : national level with combined flood_type added

Both DataFrames have columns:
    COUNTRY, NAME_1 (sub_country only), material_type,
    flood_type, threat, group_identifier,
    tonne, ghg_tonne, emission_factor, unit_tonne, unit_ghg, unit_ef
"""

import time
import pandas as pd
from datetime import timedelta


def _add_combined(df, group_cols, value_cols):
    """Sum river + coastal into a new 'combined' flood_type row."""
    river   = df[df['flood_type'] == 'river']
    coastal = df[df['flood_type'] == 'coastal']

    merged = pd.merge(
        river.groupby(group_cols)[value_cols].sum(),
        coastal.groupby(group_cols)[value_cols].sum(),
        on=group_cols, how='outer', suffixes=('_r', '_c')
    ).fillna(0)

    for col in value_cols:
        merged[col] = merged[f'{col}_r'] + merged[f'{col}_c']
        merged.drop(columns=[f'{col}_r', f'{col}_c'], inplace=True)

    merged = merged.reset_index()
    merged['flood_type'] = 'combined'
    return pd.concat([df, merged], ignore_index=True)


def run(emissions_df: pd.DataFrame, config: dict) -> dict:
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))

    sub_country_csv = config.get('SUB_COUNTRY_CSV')
    value_cols = ['tonne', 'ghg_tonne']

    # ── sub-national level: add combined flood_type ───────────────────────────
    if 'NAME_1' in emissions_df.columns:
        print(f"  [post_processing] Building sub-national output ...  [{_e()}]")
        sub_group_cols = ['COUNTRY', 'NAME_1', 'material_type', 'threat', 'group_identifier']
        sub_df = _add_combined(emissions_df, sub_group_cols, value_cols)
        for col in ['unit_tonne', 'unit_ghg', 'unit_ef']:
            if col in emissions_df.columns:
                sub_df[col] = sub_df[col].fillna(emissions_df[col].iloc[0])
        print(f"  [post_processing] Sub-national: {len(sub_df):,} rows  [{_e()}]")
    else:
        sub_df = None

    # ── national level: add combined flood_type ───────────────────────────────
    print(f"  [post_processing] Adding 'combined' flood_type ...  [{_e()}]")
    nat_group_cols = ['COUNTRY', 'material_type', 'threat', 'group_identifier']
    nat_df = _add_combined(emissions_df, nat_group_cols, value_cols)

    # carry forward unit columns
    for col in ['unit_tonne', 'unit_ghg', 'unit_ef']:
        if col in emissions_df.columns:
            nat_df[col] = nat_df[col].fillna(emissions_df[col].iloc[0])

    print(f"  [post_processing] National: {len(nat_df):,} rows  [{_e()}]")
    print(f"  [post_processing] Done  [{_e()}]")

    return {'national': nat_df, 'sub_country': sub_df}
