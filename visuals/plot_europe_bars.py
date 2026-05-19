# -*- coding: utf-8 -*-
"""
plot_europe_bars.py
Based on europe_bars.py — updated to use 2026 pipeline output directly.

2-panel stacked bar chart: European total EAD and GHG by scenario.
"""

import glob, os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

BASE        = r"C:/Users/xzhon/OneDrive/文档/SIGS/SIGS 科研/flood/flood_2026"
RESULTS_DIR = os.path.join(BASE, "modelling", "output")
VISUALS_DIR = os.path.dirname(os.path.abspath(__file__))

SCENARIO_ORDER  = ['historical', 'rcp4p5_2050', 'rcp8p5_2050', 'rcp4p5_2080', 'rcp8p5_2080']
SCENARIO_LABELS = ['Historical', 'RCP4.5 2050', 'RCP8.5 2050', 'RCP4.5 2080', 'RCP8.5 2080']


def _latest_csv(prefix):
    files = glob.glob(os.path.join(RESULTS_DIR, f"{prefix}*.csv"))
    return max(files, key=os.path.getmtime)


def make_europe_bars():
    # ── load data ─────────────────────────────────────────────────────────────
    df = pd.read_csv(_latest_csv("Material_country_emissions_with_combined_"))
    df = df[
        (df['material_type'] == 'Total') &
        (df['threat'] == 'EAD_current_dike') &
        (df['flood_type'].isin(['river', 'coastal']))
    ].copy()
    df = df.rename(columns={'group_identifier': 'scenario'})

    # sum across all countries → Europe total
    europe = df.groupby(['flood_type', 'scenario'])[['tonne', 'ghg_tonne']].sum().reset_index()
    europe['tonne_M']     = europe['tonne']     / 1000000
    europe['ghg_tonne_M'] = europe['ghg_tonne'] / 1000000

    def _pivot(col):
        piv = europe.pivot(index='scenario', columns='flood_type', values=col)
        piv = piv.reindex(SCENARIO_ORDER).fillna(0)
        return piv

    ead_piv = _pivot('tonne_M')
    ghg_piv = _pivot('ghg_tonne_M')

    # ── plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(16, 6))

    ead_piv.plot(kind='bar', stacked=True, ax=axes[0], color=['#1f77b4', '#ff7f0e'])
    axes[0].set_ylabel('Expected annual damage (Mt)', fontsize=16)
    axes[0].legend(labels=['Riverine EAD', 'Coastal EAD'], fontsize=18)
    axes[0].tick_params(axis='x', labelsize=16)
    axes[0].tick_params(axis='y', labelsize=16)

    ghg_piv.plot(kind='bar', stacked=True, ax=axes[1], color=['#2ca02c', '#d62728'])
    axes[1].set_ylabel('Annual embodied emissions (Mt CO2eq)', fontsize=16)
    axes[1].legend(labels=['Riverine GHG', 'Coastal GHG'], fontsize=18)
    axes[1].tick_params(axis='x', labelsize=16)
    axes[1].tick_params(axis='y', labelsize=16)

    axes[0].set_xticklabels(SCENARIO_LABELS, rotation=45)
    axes[1].set_xticklabels(SCENARIO_LABELS, rotation=45)

    plt.tight_layout()

    fig.text(0.064, 0.95, 'a', fontsize=20, weight='bold', ha='center', va='center')
    fig.text(0.56,  0.95, 'b', fontsize=20, weight='bold', ha='center', va='center')

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    current_date = datetime.now().strftime('%Y-%m-%d')
    out = os.path.join(VISUALS_DIR, f"europe_risks_{current_date}.png")
    plt.savefig(out, dpi=200, bbox_inches='tight', transparent=False)
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    make_europe_bars()
