# -*- coding: utf-8 -*-
"""
plot_EAD_ghg_maps_combined.py
Based on EAD&ghg_with_protection_scenarios_river&coastal_combined_2024_12_07.py
Updated to use 2026 pipeline output.

6-panel map: EAD (left) and GHG (right) for Historical / RCP4.5-2080 / RCP8.5-2080
flood_type = combined (river + coastal), threat = EAD_current_dike
"""

import glob, os
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
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


def make_ead_ghg_map_combined():
    FLOOD_TYPE = 'combined'

    # ── load data ─────────────────────────────────────────────────────────────
    df = pd.read_csv(_latest_csv("Material_sub_country_emissions_with_combined_"))
    df = df.loc[df['material_type'] == 'Total']
    df = df[['COUNTRY', 'NAME_1', 'flood_type', 'threat', 'group_identifier', 'tonne', 'ghg_tonne']].reset_index(drop=True)
    df = df.rename(columns={'group_identifier': 'scenario'})

    def _filter(scenario):
        sub = df[
            (df['flood_type'] == FLOOD_TYPE) &
            (df['threat'] == 'EAD_current_dike') &
            (df['scenario'] == scenario)
        ].copy()
        sub['tonne']     = sub['tonne']     * 0.000001
        sub['ghg_tonne'] = sub['ghg_tonne'] * 0.000001
        return sub

    hist      = _filter('historical')
    rcp45_80  = _filter('rcp4p5_2080')
    rcp85_80  = _filter('rcp8p5_2080')

    # ── load shapefile ────────────────────────────────────────────────────────
    gadm410_level1_RE = gpd.read_file(GADM_SHP)
    print(gadm410_level1_RE.crs)
    gadm410_level1_RE = gadm410_level1_RE.to_crs(epsg=3035)
    print(gadm410_level1_RE.crs)
    gadm410_level1_RE = gadm410_level1_RE[['COUNTRY', 'NAME_1', 'geometry']]

    def _merge(sub):
        return gpd.GeoDataFrame(pd.merge(gadm410_level1_RE,
                                         sub[['COUNTRY', 'NAME_1', 'tonne', 'ghg_tonne']],
                                         on=['COUNTRY', 'NAME_1'], how='left'))

    shp_hist_ead     = _merge(hist)
    shp_rcp45_80_ead = _merge(rcp45_80)
    shp_rcp85_80_ead = _merge(rcp85_80)
    shp_hist_ghg     = _merge(hist)
    shp_rcp45_80_ghg = _merge(rcp45_80)
    shp_rcp85_80_ghg = _merge(rcp85_80)

    # ── colour schemes ────────────────────────────────────────────────────────
    bins1   = [0, 0.1, 0.3, 0.8, 2.0, 8.0, 130]
    colors1 = ["#e3f2fd", "#90caf9", "#7986cb", "#5e35b1", "#e57373", "#c2185b"]
    cmap1   = ListedColormap(colors1)
    norm1   = BoundaryNorm(bins1, len(colors1), clip=True)

    bins2   = [0, 0.1, 0.2, 0.3, 0.6, 2.0, 50]
    colors2 = ["#e0f3db", "#b8e2c2", "#a8ddb5", "#43a2ca", "#f768a1", "#7a0177"]
    cmap2   = ListedColormap(colors2)
    norm2   = BoundaryNorm(bins2, len(colors2), clip=True)

    # ── plot ──────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(20, 25))
    spec = gridspec.GridSpec(ncols=2, nrows=3, hspace=0, wspace=0)

    def _panel(ax, gdf, col, cmap, norm, row_label=None, panel_label=None):
        gdf.plot(ax=ax, column=col, cmap=cmap, norm=norm, linewidth=0.2, edgecolor='grey')
        gdf.dissolve(by='COUNTRY').plot(ax=ax, edgecolor='black', facecolor='none', linewidth=0.3)
        if row_label:
            ax.set_ylabel(row_label, labelpad=20, fontsize=23, weight='bold')
        if panel_label:
            ax.text(0, 1, panel_label, fontsize=23, weight='bold', transform=ax.transAxes)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

    _panel(fig.add_subplot(spec[0]), shp_hist_ead,     'tonne',     cmap1, norm1, 'Historical',   'a')
    _panel(fig.add_subplot(spec[1]), shp_hist_ghg,     'ghg_tonne', cmap2, norm2, panel_label='d')
    _panel(fig.add_subplot(spec[2]), shp_rcp45_80_ead, 'tonne',     cmap1, norm1, 'RCP 4.5-2080', 'b')
    _panel(fig.add_subplot(spec[3]), shp_rcp45_80_ghg, 'ghg_tonne', cmap2, norm2, panel_label='e')
    _panel(fig.add_subplot(spec[4]), shp_rcp85_80_ead, 'tonne',     cmap1, norm1, 'RCP 8.5-2080', 'c')
    _panel(fig.add_subplot(spec[5]), shp_rcp85_80_ghg, 'ghg_tonne', cmap2, norm2, panel_label='f')

    # ── colorbars ─────────────────────────────────────────────────────────────
    cax1 = fig.add_axes([0.1, 0.08, 0.35, 0.02])
    sm1  = plt.cm.ScalarMappable(cmap=cmap1, norm=norm1); sm1._A = []
    cbar1 = fig.colorbar(sm1, cax=cax1, orientation='horizontal')
    cbar1.set_label('Expected annual damage (Mt)', fontsize=23, fontweight='bold', labelpad=15)
    midpoints1 = [(bins1[i] + bins1[i+1]) / 2 for i in range(len(bins1)-1)]
    cbar1.set_ticks(midpoints1)
    cbar1.set_ticklabels(['0-0.1', '0.1-0.3', '0.3-0.8', '0.8-2.0', '2.0-8.0', '>8.0'])
    cbar1.ax.tick_params(length=0, labelsize=18, width=1.5)
    for lbl in cbar1.ax.get_xticklabels():
        lbl.set_fontweight('bold')

    cax2 = fig.add_axes([0.5, 0.08, 0.35, 0.02])
    sm2  = plt.cm.ScalarMappable(cmap=cmap2, norm=norm2); sm2._A = []
    cbar2 = fig.colorbar(sm2, cax=cax2, orientation='horizontal')
    cbar2.set_label('Annual embodied emissions (Mt CO2-eq)', fontsize=23, fontweight='bold', labelpad=15)
    midpoints2 = [(bins2[i] + bins2[i+1]) / 2 for i in range(len(bins2)-1)]
    cbar2.set_ticks(midpoints2)
    cbar2.set_ticklabels(['0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.6', '0.6-2.0', '>2.0'])
    cbar2.ax.tick_params(length=0, labelsize=18, width=1.5)
    for lbl in cbar2.ax.get_xticklabels():
        lbl.set_fontweight('bold')

    plt.subplots_adjust(wspace=0, hspace=-0.4)
    current_date = datetime.now().strftime('%Y-%m-%d')
    out = os.path.join(VISUALS_DIR, f"EAD&ghg_current_dike_scenarios_combined_rev_{current_date}.png")
    plt.savefig(out, dpi=200, bbox_inches='tight', transparent=True)
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    make_ead_ghg_map_combined()
