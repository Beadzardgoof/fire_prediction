"""
Google Earth Engine API - Distance to Nearest Body of Water

This module provides functions to fetch distance to nearest body of water data
using Google Earth Engine (GEE) for use in fire prediction models. It uses:
- HydroSHEDS: Global hydrological datasets for drainage networks
- OpenStreetMap: Rivers and lakes data

The script calculates the distance from a given centroid (latitude, longitude)
to the nearest body of water in meters.

Example usage in Jupyter notebook:
    from data.google_gee.get_water_distance import get_distance_to_water
    
    # Get distance to nearest water for a location
    distance = get_distance_to_water(
        latitude=40.7128,
        longitude=-74.0060,
        max_search_radius_km=50.0
    )
    print(f"Distance to nearest water: {distance:.2f} meters")
"""

import os
import json
import warnings
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

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
    
    Uses SERVICE_ACCOUNT (email) and GEE_KEY (path to JSON key file or JSON string)
    environment variables for authentication.
    
    Returns:
    --------
    bool
        True if initialization successful, False otherwise
    """
    if not HAS_EARTHENGINE:
        raise ImportError("earthengine-api is not installed. Please install it: pip install earthengine-api")
    
    try:
        # Check if already initialized
        ee.Number(1).getInfo()
        return True
    except:
        pass
    
    # Get credentials from environment variables
    service_account = os.getenv('SERVICE_ACCOUNT')
    gee_key = os.getenv('GEE_KEY')
    
    if not service_account:
        raise ValueError(
            "SERVICE_ACCOUNT environment variable not found. "
            "Please set it to your service account email."
        )
    
    if not gee_key:
        raise ValueError(
            "GEE_KEY environment variable not found. "
            "Please set it to either:\n"
            "  1. Path to your service account JSON key file, or\n"
            "  2. JSON string containing the service account credentials"
        )
    
    try:
        # Check if GEE_KEY is a file path
        if os.path.isfile(gee_key):
            # Load from file
            credentials = ee.ServiceAccountCredentials(service_account, gee_key)
        else:
            # Try to parse as JSON string
            try:
                key_dict = json.loads(gee_key)
                # Create temporary credentials object
                credentials = ee.ServiceAccountCredentials(
                    service_account, 
                    key_data=key_dict
                )
            except json.JSONDecodeError:
                # If it's not valid JSON, try treating it as a file path that might not exist yet
                # or check if it's actually a file that exists
                if os.path.exists(gee_key):
                    credentials = ee.ServiceAccountCredentials(service_account, gee_key)
                else:
                    raise ValueError(
                        f"GEE_KEY must be either a valid file path or JSON string. "
                        f"Could not find file: {gee_key}"
                    )
        
        # Initialize Earth Engine with credentials
        ee.Initialize(credentials)
        return True
        
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize Google Earth Engine: {str(e)}\n"
            "Please check your SERVICE_ACCOUNT and GEE_KEY environment variables."
        ) from e


def _get_water_datasets(date: Optional[str] = None):
    """
    Get combined water body datasets from JRC Global Surface Water with temporal awareness.
    
    Parameters:
    -----------
    date : str, optional
        Date in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'. If provided, uses temporal
        water data for that time period. If None, uses permanent water bodies.
        
    Returns:
    --------
    ee.Image
        Binary image where 1 = water, 0 = land
    """
    # Primary dataset: JRC Global Surface Water
    jrc_water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    
    if date:
        # For temporal water data, filter by the year of the fire
        # This gives us water bodies that existed during that time period
        try:
            from datetime import datetime
            fire_date = datetime.strptime(date.split('T')[0], '%Y-%m-%d')
            fire_year = fire_date.year
            # JRC dataset covers 1984-2021, convert fire year to relative year
            fire_year_index = fire_year - 1984
            
            # The 'occurrence' band shows percentage of time water was detected (1984-2021)
            # For temporal awareness, use lower threshold to include seasonal/permanent water
            # The 'change' band indicates the year (since 1984) when water disappeared
            #   - 0 means water never disappeared (permanent)
            #   - >0 means water disappeared in that year
            
            # Water exists at fire time if:
            #   1. occurrence > 30% (water was present frequently), AND
            #   2. change == 0 (permanent water) OR change > fire_year_index (disappeared after fire)
            occurrence = jrc_water.select('occurrence')
            change = jrc_water.select('change')
            
            # Water that existed at fire time
            temporal_water = occurrence.gt(30)
            water_existed = change.eq(0).Or(change.gt(fire_year_index))
            
            # Combine conditions: water if frequently present AND existed at fire time
            combined_water = temporal_water.And(water_existed).rename('water')
            
        except Exception as e:
            warnings.warn(f"Error processing date {date}: {e}. Using permanent water instead.")
            # Fallback to permanent water
            combined_water = jrc_water.select('occurrence').gt(99).rename('water')
    else:
        # No date provided: use permanent water (occurrence > 99%)
        combined_water = jrc_water.select('occurrence').gt(99).rename('water')
    
    return combined_water


def _calculate_distance_to_water(
    point: ee.Geometry,
    water_image: ee.Image,
    max_distance_meters: float = 50000.0,
    scale: float = 30.0
) -> float:
    """
    Calculate distance from a point to the nearest water body.
    
    Parameters:
    -----------
    point : ee.Geometry
        Point geometry (longitude, latitude)
    water_image : ee.Image
        Binary water image (1 = water, 0 = land)
    max_distance_meters : float
        Maximum distance to search in meters (default: 50km)
    scale : float
        Scale/resolution in meters for distance calculation (default: 30m)
        
    Returns:
    --------
    float
        Distance to nearest water in meters, or max_distance_meters if no water found
    """
    # Create a buffer around the point for searching
    search_region = point.buffer(max_distance_meters)
    
    # Clip water image to search region and ensure it's binary (0 or 1)
    water_clipped = water_image.clip(search_region).unmask(0)
    
    # Compute distance transform: calculates Euclidean distance to nearest water pixel
    # The distance() method calculates distance to nearest non-zero (water) pixel
    # We invert the water image (1->0, 0->1) so distance is from land to water
    distance_image = water_clipped.Not().distance(
        kernel=None,  # Use default Euclidean distance
        maxDistance=max_distance_meters
    ).rename('distance')
    
    # Clip to search region
    distance_image = distance_image.clip(search_region)
    
    # Get distance at the point location using reduceRegion for more reliable results
    try:
        # Use a small buffer around the point to ensure we get a value
        small_buffer = point.buffer(scale)
        distance_result = distance_image.reduceRegion(
            reducer=ee.Reducer.min(),
            geometry=small_buffer,
            scale=scale,
            maxPixels=1e9
        )
        
        distance_info = distance_result.getInfo()
        distance_value = distance_info.get('distance')
        
        if distance_value is None:
            # If still no value, try sampling method
            distance_sample = distance_image.sample(
                region=point,
                scale=scale,
                numPixels=1,
                geometries=False
            )
            distance_info_sample = distance_sample.first().getInfo()
            distance_value = distance_info_sample.get('properties', {}).get('distance', max_distance_meters)
        
        # Ensure distance is within bounds and valid
        if distance_value is None:
            distance_value = max_distance_meters
        else:
            distance_value = min(float(distance_value), max_distance_meters)
            # Ensure non-negative
            distance_value = max(0.0, distance_value)
            
    except Exception as e:
        warnings.warn(f"Error calculating distance: {e}. Returning max distance.")
        distance_value = max_distance_meters
    
    return float(distance_value) if distance_value is not None else max_distance_meters


def get_distance_to_water(
    latitude: float,
    longitude: float,
    max_search_radius_km: float,
    scale_meters: float = 30.0,
    fire_date: Optional[str] = None
) -> float:
    """
    Get distance to nearest body of water for a given location at a specific time.
    
    Parameters:
    -----------
    latitude : float
        Latitude of the location (-90 to 90)
    longitude : float
        Longitude of the location (-180 to 180)
    max_search_radius_km : float
        Maximum radius to search for water in kilometers
        If no water is found within this radius, returns this value in meters
    scale_meters : float, optional
        Scale/resolution in meters for distance calculation (default: 30.0)
        Lower values are more accurate but slower
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
        If provided, calculates distance to water bodies that existed at that time.
        If None, uses permanent water bodies.
        
    Returns:
    --------
    float
        Distance to nearest body of water in meters
        
    Examples:
    --------
    >>> # Get distance to nearest water at fire time
    >>> distance = get_distance_to_water(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     max_search_radius_km=50.0,
    ...     fire_date='2023-07-15'
    ... )
    >>> print(f"Distance: {distance:.2f} meters")
    >>> 
    >>> # Without specific date (uses permanent water)
    >>> distance = get_distance_to_water(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     max_search_radius_km=100.0
    ... )
    """
    # Validate inputs
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    
    # Initialize Google Earth Engine
    _initialize_gee()
    
    # Create point geometry (note: GEE uses [longitude, latitude] order)
    point = ee.Geometry.Point([longitude, latitude])
    
    # Get water datasets (with temporal awareness if fire_date provided)
    water_image = _get_water_datasets(date=fire_date)
    
    # Calculate distance to nearest water
    max_distance_meters = max_search_radius_km * 1000.0
    distance = _calculate_distance_to_water(
        point=point,
        water_image=water_image,
        max_distance_meters=max_distance_meters,
        scale=scale_meters
    )
    
    return distance


def get_distance_to_water_batch(
    coordinates: list,
    max_search_radius_km: float,
    scale_meters: float = 30.0,
    fire_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Get distance to nearest water for multiple locations.
    
    Parameters:
    -----------
    coordinates : list
        List of (latitude, longitude) tuples
    max_search_radius_km : float
        Maximum radius to search for water in kilometers
    scale_meters : float, optional
        Scale/resolution in meters for distance calculation (default: 30.0)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
        If provided, calculates distance to water bodies that existed at that time.
        
    Returns:
    --------
    pandas.DataFrame
        DataFrame with columns: latitude, longitude, distance_to_water_meters
        
    Examples:
    --------
    >>> # Get distances for multiple locations at fire time
    >>> coords = [(40.7128, -74.0060), (34.0522, -118.2437)]
    >>> df = get_distance_to_water_batch(
    ...     coordinates=coords,
    ...     max_search_radius_km=50.0,
    ...     fire_date='2023-07-15'
    ... )
    >>> print(df)
    """
    results = []
    
    for lat, lon in coordinates:
        try:
            distance = get_distance_to_water(
                latitude=lat,
                longitude=lon,
                max_search_radius_km=max_search_radius_km,
                scale_meters=scale_meters,
                fire_date=fire_date
            )
            results.append({
                'latitude': lat,
                'longitude': lon,
                'distance_to_water_meters': distance
            })
        except Exception as e:
            warnings.warn(f"Error processing ({lat}, {lon}): {e}")
            results.append({
                'latitude': lat,
                'longitude': lon,
                'distance_to_water_meters': np.nan
            })
    
    return pd.DataFrame(results)


def get_distance_to_water_for_block_centroid(
    block_centroid: Tuple[float, float],
    block_size_km: float,
    max_search_radius_km: float,
    scale_meters: float = 30.0,
    fire_date: Optional[str] = None
) -> Dict[str, float]:
    """
    Get distance to nearest water for a block centroid at fire time.
    
    This function is designed for use with training data where locations
    are represented as blocks with centroids in a globally specified area.
    
    Parameters:
    -----------
    block_centroid : tuple
        (latitude, longitude) of the block centroid
    block_size_km : float
        Size of the block in kilometers (used for documentation/reference)
    max_search_radius_km : float
        Maximum radius to search for water in kilometers
    scale_meters : float, optional
        Scale/resolution in meters for distance calculation (default: 30.0)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
        If provided, calculates distance to water bodies that existed at that time.
        If None, uses permanent water bodies.
        
    Returns:
    --------
    dict
        Dictionary containing:
        - latitude: Block centroid latitude
        - longitude: Block centroid longitude
        - distance_to_water_meters: Distance to nearest water in meters
        - block_size_km: Block size (for reference)
        - fire_date: Fire date if provided (for reference)
        
    Examples:
    --------
    >>> # Get distance for a block centroid at fire time
    >>> result = get_distance_to_water_for_block_centroid(
    ...     block_centroid=(40.7128, -74.0060),
    ...     block_size_km=1.0,
    ...     max_search_radius_km=50.0,
    ...     fire_date='2023-07-15'
    ... )
    >>> print(f"Distance: {result['distance_to_water_meters']:.2f} meters")
    """
    lat, lon = block_centroid
    
    distance = get_distance_to_water(
        latitude=lat,
        longitude=lon,
        max_search_radius_km=max_search_radius_km,
        scale_meters=scale_meters,
        fire_date=fire_date
    )
    
    result = {
        'latitude': lat,
        'longitude': lon,
        'distance_to_water_meters': distance,
        'block_size_km': block_size_km
    }
    
    if fire_date:
        result['fire_date'] = fire_date
    

