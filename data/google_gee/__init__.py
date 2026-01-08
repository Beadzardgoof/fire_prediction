"""
Google Earth Engine data fetching module for fire prediction.

This module provides functions to fetch geospatial data using Google Earth Engine:
- Distance to nearest body of water using HydroSHEDS and JRC Global Surface Water
- Forest types and vegetation classifications using MODIS and ESA CCI Land Cover
- Fuel layers and load using LANDFIRE (US) and land cover proxies (global)
"""

from .get_water_distance import (
    get_distance_to_water,
    get_distance_to_water_batch,
    get_distance_to_water_for_block_centroid
)

from .get_vegetation_features import (
    get_forest_types,
    get_fuel_layers,
    get_vegetation_features_for_block_centroid
)

__all__ = [
    'get_distance_to_water',
    'get_distance_to_water_batch',
    'get_distance_to_water_for_block_centroid',
    'get_forest_types',
    'get_fuel_layers',
    'get_vegetation_features_for_block_centroid',
]

