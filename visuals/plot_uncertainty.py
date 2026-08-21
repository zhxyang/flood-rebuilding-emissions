# -*- coding: utf-8 -*-
"""
plot_uncertainty.py
Two-panel uncertainty figure for the NC revision:
  Fig A: EU-total EAD (materials + GHG) across scenarios with p05/p95 bars
  Fig B: Per-country CV choropleth map (river, EAD_current_dike, rcp4p5_2080)
"""

import glob, os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.colors import BoundaryNorm, ListedColormap
from datetime import datetime

BASE        = r"C:/Users/xzhon/OneDrive/文档/SIGS/SIGS 科研/flood/flood_2026"
RESULTS_DIR = os.path.join(BASE, "modelling", "output")
GADM_SHP    = os.path.join(BASE, "regional_boundaries", "gadm",
                            "gadm410_level1_RE_selected_for_visualization_2.shp")
VISUALS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(VISUALS_DIR)
from plot_config import load_uncertainty_emissions, load_uncertainty_material


def _eu_agg(df, flood_type, scenario, threat):
    """Aggregate uncertainty stats to Europe total."""
    sub = df[(df['flood_type'] == flood_type) &
             (df['group_identifier'] == scenario) &
             (df['threat'] == threat)]
    m   = sub['mean'].sum()
    p05 = sub['p05'].fillna(sub['mean']).sum()
    p95 = sub['p95'].fillna(sub['mean']).sum()
    return m, p05, p95


def make_uncertainty():
    unc_em  = load_uncertainty_emissions()
    unc_mat = load_uncertainty_material()

    # ── aggregate to Europe total ─────────────────────────────────────────────
    scenarios  = ['historical', 'rcp4p5_2050', 'rcp4p5_2080', 'rcp8p5_2050', 'rcp8p5_2080']
    sc_labels  = ['Historical', 'RCP4.5\n2050', 'RCP4.5\n2080', 'RCP8.5\n2050', 'RCP8.5\n2080']
    flood_types = ['river', 'coastal', 'mixed']
    ft_labels   = ['River', 'Coastal', 'Combined']
    ft_colors   = ['#4575b4', '#d73027', '#74add1']

    threat = 'EAD_current_dike'

    # Build arrays: shape (n_ft, n_sc)
    mat_mean = np.zeros((3, 5)); mat_p05 = np.zeros((3, 5)); mat_p95 = np.zeros((3, 5))
    ghg_mean = np.zeros((3, 5)); ghg_p05 = np.zeros((3, 5)); ghg_p95 = np.zeros((3, 5))

    for i, ft in enumerate(flood_types):
        for j, sc in enumerate(scenarios):
            m, p05, p95 = _eu_agg(unc_mat, ft, sc, threat)
            mat_mean[i,j] = m / 1e6
            mat_p05[i,j]  = p05 / 1e6
            mat_p95[i,j]  = p95 / 1e6
            m, p05, p95 = _eu_agg(unc_em, ft, sc, threat)
            ghg_mean[i,j] = m / 1e6
            ghg_p05[i,j]  = p05 / 1e6
            ghg_p95[i,j]  = p95 / 1e6

    # ── per-country CV for choropleth ─────────────────────────────────────────
    # Use river rcp4p5_2080 EAD_current_dike; sum across materials per country
    unc_mat_r = unc_mat[(unc_mat['flood_type'] == 'river') &
                        (unc_mat['group_identifier'] == 'rcp4p5_2080') &
                        (unc_mat['threat'] == threat)]
    cv_country = (unc_mat_r.groupby('COUNTRY')
                            .apply(lambda g: np.sqrt((g['std'].fillna(0)**2).sum()) /
                                             g['mean'].sum() * 100
                                   if g['mean'].sum() > 0 else np.nan)
                            .reset_index(name='cv'))

    gadm = gpd.read_file(GADM_SHP).to_crs(epsg=3035)
    gadm_nat = gadm.dissolve(by='COUNTRY').reset_index()[['COUNTRY', 'geometry']]
    shp_cv = gadm_nat.merge(cv_country, on='COUNTRY', how='left')

    # ── figure layout ─────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(20, 18))
    spec = gridspec.GridSpec(2, 2, height_ratios=[1, 1.1],
                             hspace=0.35, wspace=0.3)

    # ── Panel a: Materials bar chart ──────────────────────────────────────────
    ax1 = fig.add_subplot(spec[0, 0])
    x = np.arange(len(scenarios))
    w = 0.25
    for i, (ft, lbl, col) in enumerate(zip(flood_types, ft_labels, ft_colors)):
        xpos = x + (i - 1) * w
        bars = ax1.bar(xpos, mat_mean[i], width=w, color=col, label=lbl,
                       alpha=0.85, edgecolor='white', linewidth=0.5)
        # error bars only where there is spread (future scenarios, river/mixed)
        for j in range(len(scenarios)):
            if mat_p95[i,j] > mat_mean[i,j]:
                ax1.errorbar(xpos[j], mat_mean[i,j],
                             yerr=[[mat_mean[i,j] - mat_p05[i,j]],
                                   [mat_p95[i,j] - mat_mean[i,j]]],
                             fmt='none', color='black', capsize=4, linewidth=1.2)

    ax1.set_xticks(x)
    ax1.set_xticklabels(sc_labels, fontsize=13)
    ax1.set_ylabel('Expected annual damage (Mt yr⁻¹)', fontsize=14)
    ax1.set_title('a   Building materials', fontsize=15, weight='bold', loc='left')
    ax1.legend(fontsize=12, framealpha=0.8)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.yaxis.grid(True, linestyle='--', alpha=0.5)
    ax1.set_axisbelow(True)

    # ── Panel b: GHG bar chart ────────────────────────────────────────────────
    ax2 = fig.add_subplot(spec[0, 1])
    for i, (ft, lbl, col) in enumerate(zip(flood_types, ft_labels, ft_colors)):
        xpos = x + (i - 1) * w
        ax2.bar(xpos, ghg_mean[i], width=w, color=col, label=lbl,
                alpha=0.85, edgecolor='white', linewidth=0.5)
        for j in range(len(scenarios)):
            if ghg_p95[i,j] > ghg_mean[i,j]:
                ax2.errorbar(xpos[j], ghg_mean[i,j],
                             yerr=[[ghg_mean[i,j] - ghg_p05[i,j]],
                                   [ghg_p95[i,j] - ghg_mean[i,j]]],
                             fmt='none', color='black', capsize=4, linewidth=1.2)

    ax2.set_xticks(x)
    ax2.set_xticklabels(sc_labels, fontsize=13)
    ax2.set_ylabel('Annual embodied emissions (MtCO₂eq yr⁻¹)', fontsize=14)
    ax2.set_title('b   GHG emissions', fontsize=15, weight='bold', loc='left')
    ax2.legend(fontsize=12, framealpha=0.8)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.yaxis.grid(True, linestyle='--', alpha=0.5)
    ax2.set_axisbelow(True)

    # ── Panel c: CV choropleth (spans both columns) ───────────────────────────
    ax3 = fig.add_subplot(spec[1, :])

    bins_cv   = [0, 2, 5, 10, 20, 50, 100]
    colors_cv = ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#2c7fb8', '#253494']
    cmap_cv   = ListedColormap(colors_cv)
    norm_cv   = BoundaryNorm(bins_cv, len(colors_cv), clip=True)

    shp_cv.plot(ax=ax3, column='cv', cmap=cmap_cv, norm=norm_cv,
                linewidth=0.3, edgecolor='grey', missing_kwds={'color': '#f0f0f0'})
    gadm_nat.plot(ax=ax3, edgecolor='black', facecolor='none', linewidth=0.5)

    ax3.set_title('c   Coefficient of variation (%) — river EAD, RCP4.5-2080, GCM ensemble',
                  fontsize=15, weight='bold', loc='left')
    ax3.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax3.spines.values():
        spine.set_visible(False)

    # colorbar
    cax = fig.add_axes([0.15, 0.04, 0.7, 0.018])
    sm  = plt.cm.ScalarMappable(cmap=cmap_cv, norm=norm_cv); sm._A = []
    cbar = fig.colorbar(sm, cax=cax, orientation='horizontal')
    cbar.set_label('Coefficient of variation (%)', fontsize=14, fontweight='bold', labelpad=10)
    mids = [(bins_cv[i] + bins_cv[i+1]) / 2 for i in range(len(bins_cv)-1)]
    cbar.set_ticks(mids)
    cbar.set_ticklabels(['0–2', '2–5', '5–10', '10–20', '20–50', '>50'])
    cbar.ax.tick_params(length=0, labelsize=12)
    for lbl in cbar.ax.get_xticklabels():
        lbl.set_fontweight('bold')

    current_date = datetime.now().strftime('%Y-%m-%d')
    out = os.path.join(VISUALS_DIR, f"Uncertainty_EAD_CV_{current_date}.png")
    plt.savefig(out, dpi=200, bbox_inches='tight', transparent=False)
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    make_uncertainty()
