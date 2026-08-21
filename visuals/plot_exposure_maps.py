# -*- coding: utf-8 -*-
"""
plot_exposure_maps.py
Based on Exposure_rev_2024_12_07_3.py — updated to use 2026 pipeline output.

3-panel choropleth map of material exposure to 1-in-100yr floods:
  a) Riverine   b) Coastal   c) River & Coastal combined
"""

import glob, os
import sys
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.colorbar import ColorbarBase
from matplotlib import gridspec
from datetime import datetime

BASE        = r"C:/Users/xzhon/OneDrive/文档/SIGS/SIGS 科研/flood/flood_2026"
RESULTS_DIR = os.path.join(BASE, "modelling", "output")
GADM_SHP    = os.path.join(BASE, "regional_boundaries", "gadm",
                            "gadm410_level1_RE_selected_for_visualization_2.shp")
VISUALS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(VISUALS_DIR)
from plot_config import load_sub_country_emissions


def make_exposure_map():
    # ── load data ─────────────────────────────────────────────────────────────
    df = load_sub_country_emissions()
    df = df.loc[df['material_type'] == 'Total']
    df = df[['COUNTRY', 'NAME_1', 'flood_type', 'threat', 'group_identifier', 'tonne']].reset_index(drop=True)
    df = df.rename(columns={'group_identifier': 'scenario'})

    river_historical = df[
        (df['flood_type'] == 'river') &
        (df['threat'] == 'exposure_100yrs') &
        (df['scenario'] == 'historical')
    ]
    coastal_historical = df[
        (df['flood_type'] == 'coastal') &
        (df['threat'] == 'exposure_100yrs') &
        (df['scenario'] == 'historical')
    ]
    mixed_historical = df[
        (df['flood_type'] == 'mixed') &
        (df['threat'] == 'exposure_100yrs') &
        (df['scenario'] == 'historical')
    ]

    # ── load shapefile ────────────────────────────────────────────────────────
    gadm410_level1_RE = gpd.read_file(GADM_SHP)
    print(gadm410_level1_RE.crs)
    gadm410_level1_RE = gadm410_level1_RE.to_crs(epsg=3035)
    print(gadm410_level1_RE.crs)
    gadm410_level1_RE = gadm410_level1_RE[['COUNTRY', 'NAME_1', 'geometry']]

    # ── merge on NAME_1 (sub-national level, matching old scripts) ────────────
    shp_river = gpd.GeoDataFrame(
        pd.merge(gadm410_level1_RE, river_historical[['COUNTRY', 'NAME_1', 'tonne']],
                 on=['COUNTRY', 'NAME_1'], how='left'))
    shp_coastal = gpd.GeoDataFrame(
        pd.merge(gadm410_level1_RE, coastal_historical[['COUNTRY', 'NAME_1', 'tonne']],
                 on=['COUNTRY', 'NAME_1'], how='left'))
    shp_mixed = gpd.GeoDataFrame(
        pd.merge(gadm410_level1_RE, mixed_historical[['COUNTRY', 'NAME_1', 'tonne']],
                 on=['COUNTRY', 'NAME_1'], how='left'))

    shp_river['tonne']   = shp_river['tonne'].fillna(0)
    shp_coastal['tonne'] = shp_coastal['tonne'].fillna(0)
    shp_mixed['tonne']   = shp_mixed['tonne'].fillna(0)

    shp_river['tonne_million']   = shp_river['tonne']   / 1e6
    shp_coastal['tonne_million'] = shp_coastal['tonne'] / 1e6
    shp_mixed['tonne_million']   = shp_mixed['tonne']   / 1e6

    # ── colour scheme ─────────────────────────────────────────────────────────
    colors = ['#deebf7', '#91bfdb', '#fee090', '#fc8d59', '#d73027', '#67001f']
    bins   = [0, 5, 10, 50, 100, 300, 700]
    custom_cmap = ListedColormap(colors)
    norm = BoundaryNorm(bins, len(colors), clip=True)

    # ── plot ──────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(20, 6))
    spec = gridspec.GridSpec(ncols=3, nrows=1, width_ratios=[1, 1, 1], wspace=0.02)

    def _panel(ax, gdf, title):
        gdf.plot(ax=ax, column='tonne_million', cmap=custom_cmap, norm=norm,
                 legend=False, edgecolor='grey', linewidth=0.2)
        gdf.dissolve(by='COUNTRY').plot(ax=ax, edgecolor='black', facecolor='none', linewidth=0.3)
        ax.set_title(title, fontsize=20, weight='bold', loc='center')
        ax.axis('off')

    _panel(fig.add_subplot(spec[0]), shp_river,   'a   Riverine')
    _panel(fig.add_subplot(spec[1]), shp_coastal, 'b   Coastal')
    _panel(fig.add_subplot(spec[2]), shp_mixed,   'c   River & Coastal')

    # ── colorbar ──────────────────────────────────────────────────────────────
    cbar_ax = fig.add_axes([0.2, 0.02, 0.6, 0.02])
    cbar = ColorbarBase(cbar_ax, cmap=custom_cmap, norm=norm, orientation='horizontal')
    cbar.set_label('Material exposure (Million tons)', fontsize=20, fontweight='bold')
    midpoints = [(bins[i] + bins[i+1]) / 2 for i in range(len(bins)-1)]
    cbar.set_ticks(midpoints)
    cbar.set_ticklabels(['0-5', '5-10', '10-50', '50-100', '100-300', '>300'])
    cbar.ax.tick_params(length=0, labelsize=18, width=1.5)
    for lbl in cbar.ax.get_xticklabels():
        lbl.set_fontweight('bold')

    plt.subplots_adjust(wspace=0, hspace=0)
    current_date = datetime.now().strftime('%Y-%m-%d')
    out = os.path.join(VISUALS_DIR, f"Exposure_sub_country_rev_{current_date}.png")
    plt.savefig(out, dpi=200, bbox_inches='tight', transparent=True)
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    make_exposure_map()
