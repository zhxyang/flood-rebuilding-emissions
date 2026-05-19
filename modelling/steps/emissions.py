# -*- coding: utf-8 -*-
"""
steps/emissions.py

Converts material quantities (tonnes) to GHG emissions (kgCO2e) by
multiplying with material-specific emission factors.

Also averages across ensemble members so that e.g. rcp4p5_2050_1 … _5
collapse into a single rcp4p5_2050 group_identifier.

Public API
----------
run(material_df, config) -> pd.DataFrame
    material_df : output of exposure_damage.run()
                  columns: COUNTRY, material_type, tonne,
                           flood_type, scenario, threat
    config      : must contain 'EMISSION_FACTOR_XLS'
    returns     : same rows + columns emission_factor, ghg_tonne,
                  group_identifier  (scenario averaged)
"""

import time
import pandas as pd
from datetime import timedelta


def run(material_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    t0 = time.time()
    def _e(): return str(timedelta(seconds=int(time.time() - t0)))

    # ── load emission factors ─────────────────────────────────────────────────
    ef = pd.read_excel(config['EMISSION_FACTOR_XLS'], sheet_name='Sheet2')
    # expected columns: type, emission_factor  (unit: kgCO2e/kg)
    print(f"  [emissions] Loaded {len(ef)} emission factors  [{_e()}]")

    # ── merge ─────────────────────────────────────────────────────────────────
    df = material_df.merge(ef, left_on='material_type', right_on='type', how='left')
    df['ghg_tonne'] = df['tonne'] * df['emission_factor']
    df = df.drop(columns=['type'])

    # ── collapse ensemble members into scenario groups ────────────────────────
    # e.g. rcp4p5_2050_1 … rcp4p5_2050_5  →  rcp4p5_2050
    df['group_identifier'] = df['scenario'].str.extract(r'(rcp[^_]+_[^_]+)')
    df.loc[df['scenario'] == 'historical', 'group_identifier'] = 'historical'

    name1_cols = ['NAME_1'] if 'NAME_1' in df.columns else []
    group_cols = ['COUNTRY'] + name1_cols + ['material_type', 'flood_type', 'threat', 'group_identifier']
    # average tonne and ghg_tonne across ensemble members; keep emission_factor as-is
    df_avg = (df.groupby(group_cols, as_index=False)
                .agg(tonne=('tonne', 'mean'),
                     ghg_tonne=('ghg_tonne', 'mean'),
                     emission_factor=('emission_factor', 'first')))

    # ── add Total row across all material types ───────────────────────────────
    totals = (df_avg.groupby(['COUNTRY'] + name1_cols + ['flood_type', 'threat', 'group_identifier'],
                             as_index=False)
                    .agg(tonne=('tonne', 'sum'),
                         ghg_tonne=('ghg_tonne', 'sum')))
    totals['material_type']  = 'Total'
    totals['emission_factor'] = None   # not meaningful for aggregate row

    result = pd.concat([df_avg, totals], ignore_index=True)
    result.sort_values(['COUNTRY'] + name1_cols + ['flood_type', 'threat',
                        'group_identifier', 'material_type'], inplace=True)
    result['unit_tonne']    = 'tonne'
    result['unit_ghg']      = 'kgCO2e'
    result['unit_ef']       = 'kgCO2e/kg'

    result['unit_tonne']    = 'tonne'
    result['unit_ghg']      = 'kgCO2e'
    result['unit_ef']       = 'kgCO2e/kg'

    print(f"  [emissions] Done. {len(result):,} rows  [{_e()}]")
    return result
