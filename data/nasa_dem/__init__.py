"""
NASA SRTM DEM API - Terrain Data Fetching Module

This package provides functions to fetch elevation data from NASA SRTM DEM
and compute terrain features for fire prediction.
"""

from .get_terrain import (
    fetch_terrain_features,
    fetch_terrain_features_batch,
    compute_terrain_from_elevation_array
)

__all__ = [
    'fetch_terrain_features',
    'fetch_terrain_features_batch',
    'compute_terrain_from_elevation_array'
]




