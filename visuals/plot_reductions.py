# -*- coding: utf-8 -*-
"""
plot_reductions.py
Based on EAD&ghg_reductions_historical_river_2024_10_16.py
Updated to use 2026 pipeline output.

Layout: 2 maps (EAD reduction, GHG reduction) + 1 horizontal bar chart (reduction %)
flood_type = river, scenario = historical
"""

import glob, os
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib import gridspec
from datetime import datetime

BASE        = r"C:/Users/xzhon/OneDrive/文档/SIGS/SIGS 科研/flood/flood_2026"
RESULTS_DIR = os.path.join(BASE, "modelling", "output")
GADM_SHP    = os.path.join(BASE, "regional_boundaries", "gadm",
                            "gadm410_level1_RE_selected_for_visualization_2.shp")
VISUALS_DIR = os.path.dirname(os.path.abspath(__file__))


def _latest_csv(prefix):
    files = glob.glob(os.path.join(RESULTS_DIR, f"{prefix}*.csv"))
    return max(files, key=os.path.getmtime)


def make_reductions():
    # ── load data ─────────────────────────────────────────────────────────────
    df = pd.read_csv(_latest_csv("Material_sub_country_emissions_with_combined_"))
    df = df.loc[df['material_type'] == 'Total']
    df = df[['COUNTRY', 'NAME_1', 'flood_type', 'threat', 'group_identifier', 'tonne', 'ghg_tonne']].reset_index(drop=True)
    df = df.rename(columns={'group_identifier': 'scenario'})

    ead_cur = df[
        (df['flood_type'] == 'river') &
        (df['threat'] == 'EAD_current_dike') &
        (df['scenario'] == 'historical')
    ][['COUNTRY', 'NAME_1', 'tonne', 'ghg_tonne']].rename(
        columns={'tonne': 'tonne_EAD_current_dike', 'ghg_tonne': 'ghg_tonne_EAD_current_dike'})

    ead_nop = df[
        (df['flood_type'] == 'river') &
        (df['threat'] == 'EAD_no_protection') &
        (df['scenario'] == 'historical')
    ][['COUNTRY', 'NAME_1', 'tonne', 'ghg_tonne']].rename(
        columns={'tonne': 'tonne_EAD_no_protection', 'ghg_tonne': 'ghg_tonne_EAD_no_protection'})

    reduction = pd.merge(ead_nop, ead_cur, on=['COUNTRY', 'NAME_1'], how='left')
    reduction['tonne_reduction']     = reduction['tonne_EAD_no_protection']     - reduction['tonne_EAD_current_dike']
    reduction['ghg_tonne_reduction'] = reduction['ghg_tonne_EAD_no_protection'] - reduction['ghg_tonne_EAD_current_dike']
    reduction['tonne_reduction_perc'] = (
        reduction['tonne_reduction'] / reduction['tonne_EAD_no_protection'].replace(0, pd.NA)) * 100
    reduction['ghg_tonne_reduction_perc'] = (
        reduction['ghg_tonne_reduction'] / reduction['ghg_tonne_EAD_no_protection'].replace(0, pd.NA)) * 100

    # tonne → million tonne
    reduction['tonne_reduction']     = reduction['tonne_reduction']     * 0.000001
    reduction['ghg_tonne_reduction'] = reduction['ghg_tonne_reduction'] * 0.000001

    # ── load shapefile ────────────────────────────────────────────────────────
    gadm410_level1_RE = gpd.read_file(GADM_SHP)
    gadm410_level1_RE = gadm410_level1_RE.to_crs(epsg=3035)
    gadm410_level1_RE = gadm410_level1_RE[['COUNTRY', 'NAME_1', 'geometry']]

    shp_reduction = gpd.GeoDataFrame(
        pd.merge(gadm410_level1_RE, reduction, on=['COUNTRY', 'NAME_1'], how='left'))

    # ── colour maps ───────────────────────────────────────────────────────────
    mymap2 = mpl.colors.ListedColormap(["cyan", "royalblue", "blueviolet", 'fuchsia', "red", "darkred"])
    colors1 = plt.cm.summer(np.linspace(1, 0, 128))
    mymap   = mcolors.LinearSegmentedColormap.from_list('my_colormap', colors1)

    # ── national bar chart: aggregate sub-national → country ─────────────────
    nat = reduction.groupby('COUNTRY')[
        ['tonne_EAD_no_protection', 'tonne_reduction']].sum().reset_index()
    nat['tonne_reduction_perc'] = (
        nat['tonne_reduction'] / nat['tonne_EAD_no_protection'].replace(0, pd.NA)) * 100
    national_sorted = nat.sort_values(by='tonne_reduction_perc', ascending=True)
    national_sorted = national_sorted[national_sorted['tonne_reduction_perc'] != 0]
    national_sorted = national_sorted.dropna(subset=['tonne_reduction_perc'])

    # ── plot ──────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(20, 20))
    plt.rcParams["legend.fontsize"] = 16
    spec = gridspec.GridSpec(ncols=2, nrows=2, width_ratios=[4, 1])

    # panel a: EAD reduction map
    ax1 = fig.add_subplot(spec[0, 0])
    shp_reduction.plot(ax=ax1, column='tonne_reduction', cmap=mymap2,
                       scheme="User_Defined",
                       legend=True,
                       legend_kwds={
                           'loc': 'upper left',
                           'bbox_to_anchor': (0, 0.55),
                           'prop': {'size': 12},
                           'borderpad': 0,
                           'labelspacing': 1.2,
                           'fmt': '{:.1f}'
                       },
                       classification_kwds=dict(bins=[0.2, 0.5, 1, 2, 6]),
                       linewidth=0.75, edgecolor=None)
    plt.rcParams["legend.fontsize"] = 16
    plt.rcParams["legend.handletextpad"] = 0
    ax1.text(0.01, 0.97, 'a', fontsize=20, weight='bold', transform=ax1.transAxes, va='top')
    ax1.text(0.06, 0.97, 'EAD reduction (Mt)', fontsize=22, weight='bold', transform=ax1.transAxes, va='top')

    # panel b: GHG reduction map
    ax2 = fig.add_subplot(spec[1, 0])
    shp_reduction.plot(ax=ax2, column='ghg_tonne_reduction', cmap='winter_r',
                       scheme="User_Defined",
                       legend=True,
                       legend_kwds={
                           'loc': 'upper left',
                           'bbox_to_anchor': (0, 0.55),
                           'prop': {'size': 12},
                           'borderpad': 0,
                           'labelspacing': 1.2,
                           'fmt': '{:.1f}'
                       },
                       classification_kwds=dict(bins=[0.2, 0.5, 1, 2, 6]),
                       k=6, linewidth=0.75, edgecolor=None)
    plt.rcParams["legend.fontsize"] = 16
    plt.rcParams["legend.handletextpad"] = 0
    ax2.text(0.01, 0.97, 'b', fontsize=20, weight='bold', transform=ax2.transAxes, va='top')
    ax2.text(0.06, 0.97, 'GHG reduction (Mt CO2-eq)', fontsize=22, weight='bold', transform=ax2.transAxes, va='top')

    # panel c: bar chart
    ax3 = fig.add_subplot(spec[:, 1])
    ax3.barh(national_sorted['COUNTRY'], national_sorted['tonne_reduction_perc'],
             color='orange', height=0.6)
    ax3.grid(axis='x', linestyle='--', alpha=0.7)
    ax3.tick_params(axis='y', labelsize=18)
    ax3.tick_params(axis='x', labelsize=18)
    ax3.yaxis.tick_left()
    ax3.yaxis.set_label_position("left")
    ax3.xaxis.tick_top()
    ax3.xaxis.set_label_position("top")
    ax3.set_ylabel('')
    ax3.grid(visible=False)
    ax3.set_ylim(-3, len(national_sorted) - 0.5)
    ax3.text(-0.12, 1.0, 'c', fontsize=20, weight='bold', transform=ax3.transAxes, va='top')
    ax3.text(-0.08, 0.97, 'EAD reduction percentage (%)', fontsize=22, weight='bold', transform=ax3.transAxes, va='top')

    # ── remove frames ─────────────────────────────────────────────────────────
    for ax in [ax1, ax2]:
        ax.axes.xaxis.set_ticks([])
        ax.axes.yaxis.set_ticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    ax3.spines['bottom'].set_visible(False)
    ax3.spines['left'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    ax3.spines['top'].set_linewidth(1)

    plt.subplots_adjust(wspace=0, hspace=0)
    current_date = datetime.now().strftime('%Y-%m-%d')
    out = os.path.join(VISUALS_DIR, f"EAD&ghg_historical_reduction_river_{current_date}.png")
    plt.savefig(out, dpi=200, bbox_inches='tight', transparent=False)
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    make_reductions()
