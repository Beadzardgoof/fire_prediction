"""
Google Earth Engine API - Terrain Features

This module provides functions to fetch terrain features using Google Earth Engine (GEE)
for use in fire prediction models. It replaces the NASA DEM/OpenTopo dataset to avoid
rate limiting issues.

Features computed:
- Elevation (mean and standard deviation)
- Slope (mean and maximum)
- Ruggedness (Terrain Roughness Index)
- Curvature (profile curvature)
- Canyons (steep terrain detection)

Example usage:
    from data_ingest.google_gee.get_terrain_features import get_terrain_features
    
    # Get terrain features for a location
    terrain = get_terrain_features(
        latitude=40.7128,
        longitude=-74.0060,
        scale_meters=30.0,
        buffer_km=1.0
    )
    print(f"Elevation: {terrain['elevation']:.2f} m")
    print(f"Slope: {terrain['slope']:.2f} degrees")
"""

import ee
import os
import json
import warnings
from typing import Dict, Optional
import numpy as np

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use environment variables directly

# Try to import earthengine-api
try:
    import ee
    HAS_EARTHENGINE = True
except ImportError:
    HAS_EARTHENGINE = False
    warnings.warn("earthengine-api not installed. Please install it: pip install earthengine-api")


def _initialize_gee():
    """
    Initialize Google Earth Engine with service account credentials.
    
    Uses GEE_KEY (path to JSON key file) environment variable for authentication.
    Earth Engine should already be initialized in the calling code, but this
    ensures it's ready.
    
    Returns:
    --------
    bool
        True if initialization successful or already initialized
    """
    if not HAS_EARTHENGINE:
        raise ImportError("earthengine-api is not installed. Please install it: pip install earthengine-api")
    
    try:
        # Check if already initialized
        ee.Number(1).getInfo()
        return True
    except:
        # Should be initialized by caller (notebook), but if not, raise error
        raise RuntimeError(
            "Google Earth Engine not initialized. "
            "Please initialize GEE in your notebook before calling this function."
        )


def _compute_terrain_ruggedness_index(dem_image: ee.Image) -> ee.Image:
    """
    Compute Terrain Roughness Index (TRI) from DEM.
    
    TRI is the mean of absolute differences between a cell and its 8 neighbors.
    
    Parameters:
    -----------
    dem_image : ee.Image
        Digital Elevation Model image
        
    Returns:
    --------
    ee.Image
        Ruggedness index image
    """
    # Create a kernel for 8-neighbor window
    kernel = ee.Kernel.fixed(3, 3, [
        [1, 1, 1],
        [1, 0, 1],
        [1, 1, 1]
    ], -1, -1, False)
    
    # Compute mean of neighbors
    mean_neighbors = dem_image.convolve(kernel).divide(8)
    
    # TRI is absolute difference from center
    tri = dem_image.subtract(mean_neighbors).abs()
    
    return tri.rename('ruggedness')


def _compute_profile_curvature(dem_image: ee.Image) -> ee.Image:
    """
    Compute profile curvature from DEM.
    
    Profile curvature is the curvature in the direction of steepest slope.
    Positive values indicate convex (hills), negative indicate concave (valleys).
    
    Parameters:
    -----------
    dem_image : ee.Image
        Digital Elevation Model image
        
    Returns:
    --------
    ee.Image
        Profile curvature image
    """
    # Compute slope and aspect
    slope = ee.Terrain.slope(dem_image).multiply(np.pi / 180.0)  # Convert to radians
    aspect = ee.Terrain.aspect(dem_image).multiply(np.pi / 180.0)  # Convert to radians
    
    # Compute second derivatives using convolution kernels
    # Horizontal second derivative
    dx_kernel = ee.Kernel.fixed(3, 3, [
        [0, 0, 0],
        [1, -2, 1],
        [0, 0, 0]
    ], -1, -1, False)
    
    # Vertical second derivative
    dy_kernel = ee.Kernel.fixed(3, 3, [
        [0, 1, 0],
        [0, -2, 0],
        [0, 1, 0]
    ], -1, -1, False)
    
    # Cross derivative
    dxy_kernel = ee.Kernel.fixed(3, 3, [
        [1, 0, -1],
        [0, 0, 0],
        [-1, 0, 1]
    ], -1, -1, False)
    
    dxx = dem_image.convolve(dx_kernel)
    dyy = dem_image.convolve(dy_kernel)
    dxy = dem_image.convolve(dxy_kernel).divide(4)
    
    # Profile curvature formula: -(dxx * dx^2 + 2*dxy*dx*dy + dyy*dy^2) / (dx^2 + dy^2)
    # Where dx = sin(slope) * sin(aspect), dy = sin(slope) * cos(aspect)
    dx = slope.sin().multiply(aspect.sin())
    dy = slope.sin().multiply(aspect.cos())
    
    numerator = dxx.multiply(dx.pow(2)).add(
        dxy.multiply(2).multiply(dx).multiply(dy)
    ).add(dyy.multiply(dy.pow(2)))
    
    denominator = dx.pow(2).add(dy.pow(2)).add(1e-10)  # Add small value to avoid division by zero
    
    curvature = numerator.divide(denominator).multiply(-1).rename('curvature')
    
    return curvature


def _detect_canyons(dem_image: ee.Image, slope_image: ee.Image, 
                    min_slope_degrees: float = 15.0, min_depth_meters: float = 50.0) -> ee.Image:
    """
    Detect canyons based on steep slopes and elevation differences.
    
    Parameters:
    -----------
    dem_image : ee.Image
        Digital Elevation Model image
    slope_image : ee.Image
        Slope image in degrees
    min_slope_degrees : float
        Minimum slope threshold for canyon detection (default: 15 degrees)
    min_depth_meters : float
        Minimum depth difference for canyon detection (default: 50 meters)
        
    Returns:
    --------
    ee.Image
        Binary image (1 = canyon, 0 = not canyon)
    """
    # Find areas with steep slopes
    steep_slopes = slope_image.gt(min_slope_degrees)
    
    # Compute local elevation range using focal statistics
    max_elev = dem_image.focalMax(radius=1, units='pixels')
    min_elev = dem_image.focalMin(radius=1, units='pixels')
    depth = max_elev.subtract(min_elev)
    
    # Canyons are steep areas with significant depth
    canyons = steep_slopes.And(depth.gt(min_depth_meters)).rename('canyons').multiply(1.0)
    
    return canyons


def get_terrain_features(
    latitude: float,
    longitude: float,
    scale_meters: float = 30.0,
    buffer_km: float = 1.0,
    fire_date: Optional[str] = None
) -> Dict[str, float]:
    """
    Get terrain features for a location using Google Earth Engine.
    
    This function replaces the NASA DEM/OpenTopo API to avoid rate limiting.
    It uses GEE's SRTM DEM dataset to compute terrain statistics.
    
    Parameters:
    -----------
    latitude : float
        Latitude of the location (-90 to 90)
    longitude : float
        Longitude of the location (-180 to 180)
    scale_meters : float, optional
        Scale/resolution in meters for sampling (default: 30.0)
        Lower values are more accurate but slower
    buffer_km : float, optional
        Buffer radius around point in kilometers for statistics (default: 1.0 km)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' (not used for terrain,
        but kept for API consistency)
        
    Returns:
    --------
    dict
        Dictionary containing terrain features:
        - latitude: Input latitude
        - longitude: Input longitude
        - elevation: Mean elevation in meters
        - elevation_std: Standard deviation of elevation in meters
        - slope: Mean slope in degrees
        - slope_max: Maximum slope in degrees
        - ruggedness: Mean terrain roughness index
        - curvature: Mean profile curvature
        - canyons: Binary indicator (1 if canyons detected, 0 otherwise)
        
    Examples:
    --------
    >>> # Get terrain features for a location
    >>> terrain = get_terrain_features(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     scale_meters=30.0,
    ...     buffer_km=1.0
    ... )
    >>> print(f"Elevation: {terrain['elevation']:.2f} m")
    >>> print(f"Slope: {terrain['slope']:.2f} degrees")
    """
    # Validate inputs
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    
    # Initialize Google Earth Engine (should already be initialized, but check)
    _initialize_gee()
    
    # Create point geometry and buffer region
    point = ee.Geometry.Point([longitude, latitude])
    buffer_meters = buffer_km * 1000.0
    region = point.buffer(buffer_meters)
    
    # Load SRTM DEM (30m resolution, global coverage)
    # Using USGS/SRTMGL1_003 which is the standard SRTM dataset
    dem = ee.Image('USGS/SRTMGL1_003').select('elevation')
    
    # Clip DEM to region
    dem_clipped = dem.clip(region)
    
    # Compute slope using GEE's built-in function
    slope = ee.Terrain.slope(dem_clipped)
    
    # Compute ruggedness (Terrain Roughness Index)
    ruggedness = _compute_terrain_ruggedness_index(dem_clipped)
    
    # Compute profile curvature
    curvature = _compute_profile_curvature(dem_clipped)
    
    # Detect canyons
    canyons = _detect_canyons(dem_clipped, slope)
    
    # Combine all layers into a single image
    terrain_image = dem_clipped.addBands([
        slope.rename('slope'),
        ruggedness.rename('ruggedness'),
        curvature.rename('curvature'),
        canyons.rename('canyons')
    ])
    
    # Compute statistics over the region
    try:
        # Compute mean and stdDev for all bands
        mean_stats = terrain_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=scale_meters,
            maxPixels=1e9
        )
        
        std_stats = terrain_image.select(['elevation']).reduceRegion(
            reducer=ee.Reducer.stdDev(),
            geometry=region,
            scale=scale_meters,
            maxPixels=1e9
        )
        
        # Compute max for slope and canyons
        max_stats = terrain_image.select(['slope', 'canyons']).reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=region,
            scale=scale_meters,
            maxPixels=1e9
        )
        
        # Get results
        mean_dict = mean_stats.getInfo()
        std_dict = std_stats.getInfo()
        max_dict = max_stats.getInfo()
        
        # Extract values with defaults
        elevation = mean_dict.get('elevation', 0.0)
        elevation_std = std_dict.get('elevation', 0.0)
        slope_mean = mean_dict.get('slope', 0.0)
        slope_max = max_dict.get('slope', 0.0)
        ruggedness_mean = mean_dict.get('ruggedness', 0.0)
        curvature_mean = mean_dict.get('curvature', 0.0)
        canyons_max = max_dict.get('canyons', 0.0)
        
        # Canyons indicator: 1 if any canyons detected, 0 otherwise
        canyons_indicator = 1.0 if canyons_max > 0.5 else 0.0
        
    except Exception as e:
        warnings.warn(f"Error computing terrain statistics: {e}. Using default values.")
        elevation = 0.0
        elevation_std = 0.0
        slope_mean = 0.0
        slope_max = 0.0
        ruggedness_mean = 0.0
        curvature_mean = 0.0
        canyons_indicator = 0.0
    
    result = {
        'latitude': latitude,
        'longitude': longitude,
        'elevation': float(elevation),
        'elevation_std': float(elevation_std),
        'slope': float(slope_mean),
        'slope_max': float(slope_max),
        'ruggedness': float(ruggedness_mean),
        'curvature': float(curvature_mean),
        'canyons': float(canyons_indicator)
    }
    
    if fire_date:
        result['fire_date'] = fire_date
    
    return result


def get_terrain_features_batch(
    coordinates: list,
    scale_meters: float = 30.0,
    buffer_km: float = 1.0,
    fire_date: Optional[str] = None
) -> list:
    """
    Get terrain features for multiple locations.
    
    Parameters:
    -----------
    coordinates : list
        List of (latitude, longitude) tuples
    scale_meters : float, optional
        Scale/resolution in meters (default: 30.0)
    buffer_km : float, optional
        Buffer radius in kilometers (default: 1.0)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD'
        
    Returns:
    --------
    list
        List of dictionaries containing terrain features for each location
        
    Examples:
    --------
    >>> # Get terrain for multiple locations
    >>> coords = [(40.7128, -74.0060), (34.0522, -118.2437)]
    >>> results = get_terrain_features_batch(coords)
    """
    results = []
    
    for lat, lon in coordinates:
        try:
            terrain = get_terrain_features(
                latitude=lat,
                longitude=lon,
                scale_meters=scale_meters,
                buffer_km=buffer_km,
                fire_date=fire_date
            )
            results.append(terrain)
        except Exception as e:
            warnings.warn(f"Error processing ({lat}, {lon}): {e}")
            # Add placeholder with NaN values
            results.append({
                'latitude': lat,
                'longitude': lon,
                'elevation': np.nan,
                'elevation_std': np.nan,
                'slope': np.nan,
                'slope_max': np.nan,
                'ruggedness': np.nan,
                'curvature': np.nan,
                'canyons': np.nan
            })
    
    return results

