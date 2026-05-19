# -*- coding: utf-8 -*-
"""
plot_all.py  —  Generate all manuscript figures in one run.

Usage
-----
    python plot_all.py

Figures produced (saved to visuals/ with today's date):
    Exposure_sub_country_rev_YYYY-MM-DD.png
    EAD&ghg_current_dike_scenarios_river_rev_YYYY-MM-DD.png
    EAD&ghg_current_dike_scenarios_coastal_rev_YYYY-MM-DD.png
    EAD&ghg_current_dike_scenarios_combined_rev_YYYY-MM-DD.png
    EAD&ghg_historical_reduction_river_YYYY-MM-DD.png
    europe_risks_YYYY-MM-DD.png
    Uncertainty_EAD_CV_YYYY-MM-DD.png
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plot_exposure_maps         import make_exposure_map
from plot_EAD_ghg_maps_river    import make_ead_ghg_map_river
from plot_EAD_ghg_maps_coastal  import make_ead_ghg_map_coastal
from plot_EAD_ghg_maps_combined import make_ead_ghg_map_combined
from plot_reductions            import make_reductions
from plot_europe_bars           import make_europe_bars
from plot_uncertainty           import make_uncertainty

if __name__ == '__main__':
    print("=== Generating all figures ===\n")

    print("[1/7] Exposure map (river / coastal / combined)")
    make_exposure_map()

    print("[2/7] EAD + GHG maps — river")
    make_ead_ghg_map_river()

    print("[3/7] EAD + GHG maps — coastal")
    make_ead_ghg_map_coastal()

    print("[4/7] EAD + GHG maps — combined")
    make_ead_ghg_map_combined()

    print("[5/7] Dike reduction maps + bar chart")
    make_reductions()

    print("[6/7] Europe stacked bar chart")
    make_europe_bars()

    print("[7/7] Uncertainty (bar chart + CV map)")
    make_uncertainty()

    print("\n=== All figures saved. ===")
