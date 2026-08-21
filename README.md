# Building materials and GHG emissions from flood hazards in Europe

Code for the paper:
**"Building materials and emissions from rebuilding under increasing climate-driven flood hazards"**
Xiaoyang Zhong, Tomer Fishman, Timothy Tiggeloven, Yoav Peled, Yi Jin, Philip J. Ward, Paul Behrens

## Overview

This repository contains the modelling pipeline and visualisation scripts used to estimate expected annual damage (EAD) to building materials and associated embodied GHG emissions from riverine and coastal flooding across European countries, under historical and future climate scenarios (RCP4.5 / RCP8.5, 2050 / 2080).

## Repository structure

```
modelling/
  pipeline.py              # Main entry point — runs all stages in sequence
  steps/
    gridded_materials.py   # Stage 1: load/prepare gridded building material stocks
    depth_tables.py        # Stage 2: load flood depth tables
    exposure_damage.py     # Stage 3: compute exposure and EAD per scenario
    emissions.py           # Stage 4: apply emission factors, average GCM ensemble
    post_processing.py     # Stage 5: add combined flood type, national/sub-national outputs
    uncertainty.py         # Stage 6: GCM ensemble spread statistics

visuals/
  plot_all.py              # Run all figures in one go
  plot_exposure_maps.py    # Fig: material exposure (river / coastal / combined)
  plot_europe_bars.py      # Fig: Europe-level stacked bar chart
  plot_EAD_ghg_maps_river.py     # Fig: EAD + GHG maps, river
  plot_EAD_ghg_maps_coastal.py   # Fig: EAD + GHG maps, coastal
  plot_EAD_ghg_maps_combined.py  # Fig: EAD + GHG maps, combined  
  plot_uncertainty.py      # Fig: uncertainty bar chart + per-country CV map
```

## Running the pipeline

### Requirements

```
python >= 3.10
geopandas, pandas, numpy, matplotlib, openpyxl
```

Install with conda:
```bash
conda install geopandas pandas numpy matplotlib openpyxl
```

### Data

Input data (not included in this repository due to size and licensing):
- Gridded building material stocks (Peled & Fishman 2021)
- GLOFRIS flood depth tables (river: Aqueduct Floods; coastal: Tiggeloven et al. 2020)
- FLOPROS flood protection standards
- Sub-country name lookup: `Join_country_names/Flood_polygon_RE_sub_country_names.csv`
- Scenario table: `data/scenario_list.xlsx`
- Emission factors: `data/Emission_factor.xlsx`
- GADM level-1 shapefile: `regional_boundaries/gadm/gadm410_level1_RE_selected_for_visualization_2.shp`

### Running

```bash
cd modelling
python pipeline.py
```

Output CSVs are saved to `modelling/output/`.

### Generating figures

```bash
cd visuals
python plot_all.py
```

Figures are saved to `visuals/` with the current date in the filename.

## Scenarios

| Group identifier | Description |
|---|---|
| `historical` | Baseline (single member) |
| `rcp4p5_2050` | RCP4.5, 2050 (mean of 5 GCM members) |
| `rcp4p5_2080` | RCP4.5, 2080 (mean of 5 GCM members) |
| `rcp8p5_2050` | RCP8.5, 2050 (mean of 5 GCM members) |
| `rcp8p5_2080` | RCP8.5, 2080 (mean of 5 GCM members) |

## Citation

> Zhong et al. (2026). Building materials and emissions from rebuilding under increasing climate-driven flood hazards.
