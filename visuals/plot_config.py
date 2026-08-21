# -*- coding: utf-8 -*-
"""
plot_config.py  —  Shared configuration for all visualisation scripts.

Edit BASE and DATA_FILE to point to the latest pipeline output.
All plotting scripts import from here so only this file needs updating.
"""

import os
import glob as _glob
import pandas as pd
from datetime import datetime

# ── project root ──────────────────────────────────────────────────────────────
BASE    = r"C:/Users/xzhon/OneDrive/文档/SIGS/SIGS 科研/flood/flood_2026"
VISUALS = os.path.dirname(os.path.abspath(__file__))

# ── micro-states and dependent territories excluded from analysis ─────────────
# These entities are too small to be reliably represented at 1 km resolution
EXCLUDE_COUNTRIES = {
    'Andorra', 'Liechtenstein', 'San Marino', 'Monaco', 'Vatican City',  # micro-states
    'Gibraltar', 'Malta',                               # small territories (< 500 km²)
    'Akrotiri and Dhekelia',                            # UK sovereign base areas
    'Guernsey', 'Jersey', 'Isle of Man',                # Crown dependencies
    'Faroe Islands', 'Faroes',                          # Danish autonomous territory
    '\ufffdland',                                       # Åland Islands (encoding artifact)
}

# Also match by prefix to catch encoding variants of Åland
def _exclude(df):
    return df[~df['COUNTRY'].isin(EXCLUDE_COUNTRIES) &
              ~df['COUNTRY'].str.startswith('\xc5land', na=False)].reset_index(drop=True)

# ── pipeline output: set to the latest run_tag ───────────────────────────────
# e.g. "river+coastal_all_scenarios_2026-04-18"
# Set to None to auto-detect the most recent file
RUN_TAG = None

def _latest(pattern_prefix, folder):
    """Return path to the most recently modified CSV matching prefix."""
    files = _glob.glob(os.path.join(folder, f"{pattern_prefix}*.csv"))
    if not files:
        raise FileNotFoundError(f"No file matching {pattern_prefix}* in {folder}")
    return max(files, key=os.path.getmtime)


def _add_combined(df):
    """Add combined flood_type (river + coastal) in memory."""
    value_cols = [c for c in ['tonne', 'ghg_tonne'] if c in df.columns]
    group_cols = [c for c in df.columns
                  if c not in value_cols + ['flood_type', 'unit_tonne', 'unit_ghg', 'unit_ef']]

    river   = df[df['flood_type'] == 'river']
    coastal = df[df['flood_type'] == 'coastal']
    if river.empty or coastal.empty:
        return df  # nothing to combine

    merged = pd.merge(
        river.groupby(group_cols)[value_cols].sum(),
        coastal.groupby(group_cols)[value_cols].sum(),
        on=group_cols, how='outer', suffixes=('_r', '_c')
    ).fillna(0).reset_index()

    for col in value_cols:
        merged[col] = merged[f'{col}_r'] + merged[f'{col}_c']
        merged.drop(columns=[f'{col}_r', f'{col}_c'], inplace=True)

    merged['flood_type'] = 'combined'
    return pd.concat([df, merged], ignore_index=True)


def load_emissions_with_combined():
    """
    Load the visualisation-ready emissions DataFrame (with combined flood_type).
    Uses the with_combined file if available; otherwise builds it on the fly
    from the standard emissions output. Micro-states are excluded via EXCLUDE_COUNTRIES.
    """
    # prefer pre-built with_combined file
    try:
        path = _latest("Material_country_emissions_with_combined_", RESULTS_DIR)
        df = pd.read_csv(path)
    except FileNotFoundError:
        # fallback: load standard emissions and add combined in memory
        path = _latest("Material_country_emissions_", RESULTS_DIR)
        print(f"  [plot_config] with_combined not found; building from {os.path.basename(path)}")
        df = pd.read_csv(path)
        df = _add_combined(df)

    return _exclude(df)

RESULTS_DIR = os.path.join(
    BASE, "modelling", "output"
)

def get_emissions_with_combined():
    """Kept for backwards compatibility — prefer load_emissions_with_combined()."""
    try:
        return _latest("Material_country_emissions_with_combined_", RESULTS_DIR)
    except FileNotFoundError:
        return _latest("Material_country_emissions_", RESULTS_DIR)

def get_emissions():
    """Return path to Material_country_emissions_*.csv (without combined)"""
    if RUN_TAG:
        return os.path.join(RESULTS_DIR,
                            f"Material_country_emissions_{RUN_TAG}.csv")
    return _latest("Material_country_emissions_", RESULTS_DIR)

def get_uncertainty_material():
    if RUN_TAG:
        return os.path.join(RESULTS_DIR, f"Uncertainty_material_{RUN_TAG}.csv")
    return _latest("Uncertainty_material_", RESULTS_DIR)

def get_uncertainty_emissions():
    if RUN_TAG:
        return os.path.join(RESULTS_DIR, f"Uncertainty_emissions_{RUN_TAG}.csv")
    return _latest("Uncertainty_emissions_", RESULTS_DIR)

def load_sub_country_emissions():
    """Load sub-country emissions CSV, excluding micro-states."""
    path = _latest("Material_sub_country_emissions_with_combined_", RESULTS_DIR)
    df = pd.read_csv(path)
    return _exclude(df)

def load_uncertainty_emissions():
    """Load uncertainty emissions CSV, excluding micro-states."""
    df = pd.read_csv(get_uncertainty_emissions())
    return _exclude(df)

def load_uncertainty_material():
    """Load uncertainty material CSV, excluding micro-states."""
    df = pd.read_csv(get_uncertainty_material())
    return _exclude(df)

# ── geospatial data ───────────────────────────────────────────────────────────
GADM_SHP = os.path.join(
    BASE, "regional_boundaries", "gadm",
    "gadm410_level1_RE_selected_for_visualization_2.shp"
)


def load_gadm_europe():
    """
    Load the pre-selected GADM shapefile, reproject to EPSG:3035,
    and dissolve to country level for country-level choropleth maps.
    """
    import geopandas as gpd
    gadm = gpd.read_file(GADM_SHP)[['COUNTRY', 'geometry']]
    gadm = gadm.to_crs(epsg=3035)
    gadm = gadm.dissolve(by='COUNTRY').reset_index()
    return gadm

# ── output folder for figures ─────────────────────────────────────────────────
FIG_DIR = VISUALS

def fig_path(name):
    """Return full output path for a figure, appending today's date."""
    today = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(FIG_DIR, f"{name}_{today}.png")
