# -*- coding: utf-8 -*-
"""
steps/uncertainty.py

Computes ensemble uncertainty statistics across GCM members.

For each climate scenario group (e.g. rcp4p5_2050), the 5 ensemble members
(_1 … _5) are used to derive:
    mean, std, cv (coefficient of variation), p05, p25, p75, p95

historical has only one member, so uncertainty stats are NaN for that group.

Public API
----------
run(material_df, emissions_df) -> (pd.DataFrame, pd.DataFrame)
    material_df  : output of exposure_damage.run()
    emissions_df : output of emissions.run()
    returns      : (uncertainty_material, uncertainty_emissions)
                   both in wide format with one row per
                   (COUNTRY, material_type, flood_type, threat, group_identifier)
"""

import numpy as np
import pandas as pd
import time
from datetime import timedelta


def _ensemble_stats(df, value_col):
    """
    Given a DataFrame with columns including 'scenario' (e.g. rcp4p5_2050_1)
    and value_col, compute per-group ensemble statistics.
    Returns wide DataFrame with mean/std/cv/p05/p25/p75/p95.
    """
    # derive group_identifier (strip trailing _N)
    df = df.copy()
    df['group_identifier'] = df['scenario'].str.extract(r'(rcp[^_]+_[^_]+)')
    df.loc[df['scenario'] == 'historical', 'group_identifier'] = 'historical'

    # If NAME_1 is present, aggregate to country level first so that
    # sub-national regions are not treated as extra ensemble members.
    if 'NAME_1' in df.columns:
        agg_cols = ['COUNTRY', 'material_type', 'flood_type', 'threat',
                    'scenario', 'group_identifier']
        df = df.groupby(agg_cols, as_index=False)[value_col].sum()

    group_cols = ['COUNTRY', 'material_type', 'flood_type', 'threat', 'group_identifier']

    stats = (df.groupby(group_cols)[value_col]
               .agg(
                   mean='mean',
                   std='std',
                   p05=lambda x: np.percentile(x, 5),
                   p25=lambda x: np.percentile(x, 25),
                   p75=lambda x: np.percentile(x, 75),
                   p95=lambda x: np.percentile(x, 95),
                   n_members='count',
               )
               .reset_index())

    # coefficient of variation (std / mean), NaN where mean == 0
    stats['cv'] = stats['std'] / stats['mean'].replace(0, np.nan)

    # historical has 1 member → std is NaN by definition, mark explicitly
    stats.loc[stats['group_identifier'] == 'historical',
              ['std', 'cv', 'p05', 'p25', 'p75', 'p95']] = np.nan

    return stats


def run(material_df: pd.DataFrame, emissions_df: pd.DataFrame):
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))

    print(f"  [uncertainty] Computing ensemble statistics ...  [{_e()}]")

    # drop aggregate rows — uncertainty is computed on individual material types only
    mat_core = material_df[~material_df['material_type'].isin(['Total', 'Sum'])].copy()

    # ── material uncertainty ──────────────────────────────────────────────────
    unc_mat = _ensemble_stats(mat_core, 'tonne')
    unc_mat['unit'] = 'tonne'
    print(f"  [uncertainty] Material: {len(unc_mat):,} rows  [{_e()}]")

    # ── emissions uncertainty ─────────────────────────────────────────────────
    # emissions_df from emissions.run() is already averaged (group_identifier),
    # so we need to re-derive from material_df × emission_factor
    # emissions_df has 'group_identifier' not 'scenario' — use material stats
    # and apply emission factors from emissions_df
    ef_map = (emissions_df[emissions_df['material_type'] != 'Total']
              [['material_type', 'emission_factor']]
              .drop_duplicates('material_type')
              .set_index('material_type')['emission_factor'])

    mat_with_ef = mat_core.copy()
    mat_with_ef['emission_factor'] = mat_with_ef['material_type'].map(ef_map)
    mat_with_ef['ghg_tonne'] = mat_with_ef['tonne'] * mat_with_ef['emission_factor']

    unc_em = _ensemble_stats(mat_with_ef, 'ghg_tonne')
    unc_em['unit'] = 'kgCO2e'
    print(f"  [uncertainty] Emissions: {len(unc_em):,} rows  [{_e()}]")

    print(f"  [uncertainty] Done  [{_e()}]")
    return unc_mat, unc_em
