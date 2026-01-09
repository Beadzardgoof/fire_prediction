"""
Google Earth Engine API - Vegetation and Fuel Features

This module provides functions to fetch forest type and fuel layer data
using Google Earth Engine (GEE) for use in fire prediction models. It uses:
- MODIS Land Cover (MCD12Q1): Global land cover classification
- ESA CCI Land Cover: European Space Agency Climate Change Initiative land cover
- LANDFIRE (US only): Fuel models and layers for United States

Example usage in Jupyter notebook:
    from data.google_gee.get_vegetation_features import get_forest_types, get_fuel_layers
    
    # Get forest types for a location
    forest_types = get_forest_types(
        latitude=40.7128,
        longitude=-74.0060,
        fire_date='2023-07-15'
    )
    
    # Get fuel layers (US locations)
    fuel_layers = get_fuel_layers(
        latitude=40.7128,
        longitude=-74.0060,
        fire_date='2023-07-15'
    )
"""

import os
import json
import warnings
from typing import Dict, Optional, Tuple, List
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
    
    # Clean up the path - strip quotes, whitespace, and control characters
    gee_key = gee_key.strip('"\'')  # Remove quotes
    # Remove control characters (form feeds, newlines, etc.)
    gee_key = ''.join(c for c in gee_key if ord(c) >= 32 or c in '\n\r\t')
    gee_key = gee_key.replace('\n', '').replace('\r', '').replace('\t', '')
    gee_key = gee_key.strip()
    
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


# MODIS IGBP classification scheme (most commonly used)
MODIS_IGBP_CLASSES = {
    0: "Water",
    1: "Evergreen Needleleaf Forest",
    2: "Evergreen Broadleaf Forest",
    3: "Deciduous Needleleaf Forest",
    4: "Deciduous Broadleaf Forest",
    5: "Mixed Forests",
    6: "Closed Shrublands",
    7: "Open Shrublands",
    8: "Woody Savannas",
    9: "Savannas",
    10: "Grasslands",
    11: "Permanent Wetlands",
    12: "Croplands",
    13: "Urban and Built-up Lands",
    14: "Cropland/Natural Vegetation Mosaics",
    15: "Snow and Ice",
    16: "Barren",
    255: "Unclassified"
}


def _get_modis_landcover(date: Optional[str] = None, classification_scheme: str = 'IGBP'):
    """
    Get MODIS Land Cover (MCD12Q1) dataset for a specific date.
    
    Parameters:
    -----------
    date : str, optional
        Date in format 'YYYY-MM-DD'. If provided, gets land cover for that year.
        MODIS MCD12Q1 is annual (yearly composites).
    classification_scheme : str
        Classification scheme: 'IGBP', 'UMD', 'LCCS1', 'LCCS2', 'PFT', or 'LAI'
        Default: 'IGBP' (International Geosphere-Biosphere Programme)
        
    Returns:
    --------
    ee.Image
        Land cover classification image
    """
    modis_lc = ee.ImageCollection("MODIS/006/MCD12Q1")
    
    if date:
        from datetime import datetime
        fire_date = datetime.strptime(date.split('T')[0], '%Y-%m-%d')
        fire_year = fire_date.year
        
        # MODIS MCD12Q1 is annual, filter by year
        # Year starts from 2001
        if 2001 <= fire_year <= 2023:  # MODIS MCD12Q1 available years
            modis_filtered = modis_lc.filterDate(
                f'{fire_year}-01-01',
                f'{fire_year + 1}-01-01'
            )
            # Get the first (and likely only) image for that year
            modis_image = modis_filtered.first()
        else:
            # Fallback to most recent available year
            warnings.warn(
                f"Date {fire_year} out of MODIS MCD12Q1 range (2001-2023). "
                "Using most recent available year."
            )
            modis_image = modis_lc.sort('system:time_start', False).first()
    else:
        # Use most recent available year
        modis_image = modis_lc.sort('system:time_start', False).first()
    
    # Select the appropriate classification scheme band
    band_map = {
        'IGBP': 'LC_Type1',
        'UMD': 'LC_Type2',
        'LCCS1': 'LC_Type3',
        'LCCS2': 'LC_Type4',
        'PFT': 'LC_Type5',
        'LAI': 'LC_Prop1'
    }
    
    band_name = band_map.get(classification_scheme, 'LC_Type1')
    lc_band = modis_image.select(band_name)
    
    return lc_band


def _get_esa_cci_landcover(date: Optional[str] = None):
    """
    Get ESA CCI Land Cover dataset for a specific date.
    
    Parameters:
    -----------
    date : str, optional
        Date in format 'YYYY-MM-DD'. If provided, gets land cover for that year.
        ESA CCI is annual (yearly composites), available 1992-2020.
        
    Returns:
    --------
    ee.Image
        Land cover classification image
    """
    esa_cci = ee.ImageCollection("ESA/WorldCover/v100")
    
    # ESA WorldCover is available for 2020-2021, with annual updates
    # For temporal data, we'd need the full CCI collection which may not be directly available
    # Using WorldCover as it's the most recent ESA product
    
    if date:
        from datetime import datetime
        fire_date = datetime.strptime(date.split('T')[0], '%Y-%m-%d')
        fire_year = fire_date.year
        
        # ESA WorldCover available from 2020
        if fire_year >= 2020:
            esa_filtered = esa_cci.filterDate(
                f'{fire_year}-01-01',
                f'{fire_year + 1}-01-01'
            )
            esa_image = esa_filtered.first()
        else:
            # For years before 2020, use 2020 data (most recent)
            warnings.warn(
                f"Date {fire_year} before ESA WorldCover range (2020+). "
                "Using 2020 data."
            )
            esa_image = esa_cci.first()
    else:
        # Use most recent available
        esa_image = esa_cci.first()
    
    # ESA WorldCover uses a simplified classification
    # Select the 'Map' band which contains the land cover classes
    lc_band = esa_image.select('Map')
    
    return lc_band


def _extract_forest_types_one_hot(
    point: ee.Geometry,
    landcover_image: ee.Image,
    scale: float = 250.0,  # MODIS resolution is 500m, using 250m for sampling
    classification_scheme: str = 'IGBP'
) -> Dict[str, float]:
    """
    Extract forest type classification at a point and return as one-hot encoded features.
    
    Parameters:
    -----------
    point : ee.Geometry
        Point geometry (longitude, latitude)
    landcover_image : ee.Image
        Land cover classification image
    scale : float
        Scale/resolution in meters for sampling (default: 250m for MODIS)
    classification_scheme : str
        Classification scheme used (for interpreting values)
        
    Returns:
    --------
    dict
        Dictionary with one-hot encoded forest type features
    """
    # Sample land cover value at the point
    try:
        sample = landcover_image.sample(
            region=point,
            scale=scale,
            numPixels=1,
            geometries=False
        )
        sample_info = sample.first().getInfo()
        
        # Get the land cover class value
        # The property name depends on the band selected
        prop_name = list(sample_info.get('properties', {}).keys())[0] if sample_info.get('properties') else None
        if prop_name:
            lc_value = sample_info['properties'][prop_name]
        else:
            # Fallback: try common band names
            lc_value = sample_info.get('properties', {}).get('LC_Type1') or \
                      sample_info.get('properties', {}).get('Map') or \
                      sample_info.get('properties', {}).get('classification')
        
        if lc_value is None:
            lc_value = 255  # Unclassified
        
    except Exception as e:
        warnings.warn(f"Error sampling land cover: {e}. Using unclassified.")
        lc_value = 255
    
    # Create one-hot encoding for forest types
    # Based on MODIS IGBP classification, forest types are: 1, 2, 3, 4, 5
    # But we'll create one-hot for all major classes that are relevant for fire prediction
    
    one_hot_features = {}
    
    if classification_scheme == 'IGBP':
        # MODIS IGBP classes - create one-hot for forest and vegetation types
        forest_types = {
            1: 'evergreen_needleleaf_forest',
            2: 'evergreen_broadleaf_forest',
            3: 'deciduous_needleleaf_forest',
            4: 'deciduous_broadleaf_forest',
            5: 'mixed_forests',
            6: 'closed_shrublands',
            7: 'open_shrublands',
            8: 'woody_savannas',
            9: 'savannas',
            10: 'grasslands',
            11: 'permanent_wetlands',
            12: 'croplands',
            13: 'urban_built_up',
            14: 'cropland_natural_mosaic',
            15: 'snow_ice',
            16: 'barren',
            0: 'water'
        }
        
        # Initialize all to 0
        for key, name in forest_types.items():
            one_hot_features[f'forest_type_{name}'] = 0.0
        
        # Set the detected class to 1
        if lc_value in forest_types:
            one_hot_features[f'forest_type_{forest_types[lc_value]}'] = 1.0
        else:
            # Unclassified or unknown
            one_hot_features['forest_type_unclassified'] = 1.0
    
    else:
        # For other schemes, create a generic one-hot based on value
        one_hot_features['landcover_class'] = float(lc_value)
        # Create binary indicators for forest-like classes (heuristic)
        one_hot_features['is_forest'] = 1.0 if 1 <= lc_value <= 5 else 0.0
        one_hot_features['is_vegetation'] = 1.0 if 1 <= lc_value <= 10 else 0.0
    
    # Add the raw class value for reference
    one_hot_features['landcover_class_raw'] = float(lc_value)
    
    return one_hot_features


def get_forest_types(
    latitude: float,
    longitude: float,
    fire_date: Optional[str] = None,
    data_source: str = 'MODIS',
    classification_scheme: str = 'IGBP',
    scale_meters: float = 250.0
) -> Dict[str, float]:
    """
    Get forest types for a location as one-hot encoded categorical features.
    
    Parameters:
    -----------
    latitude : float
        Latitude of the location (-90 to 90)
    longitude : float
        Longitude of the location (-180 to 180)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
        If provided, gets land cover for that year. If None, uses most recent.
    data_source : str, optional
        Data source: 'MODIS' or 'ESA' (default: 'MODIS')
        - MODIS: MODIS MCD12Q1 (global, 500m resolution, 2001-2023)
        - ESA: ESA WorldCover/CCI (global, 10m resolution, 2020+)
    classification_scheme : str, optional
        For MODIS only: 'IGBP', 'UMD', 'LCCS1', 'LCCS2', 'PFT', or 'LAI' (default: 'IGBP')
    scale_meters : float, optional
        Scale/resolution in meters for sampling (default: 250m)
        MODIS native resolution: 500m, ESA: 10m
        
    Returns:
    --------
    dict
        Dictionary with one-hot encoded forest type features:
        - forest_type_evergreen_needleleaf_forest: binary (0 or 1)
        - forest_type_evergreen_broadleaf_forest: binary (0 or 1)
        - forest_type_deciduous_needleleaf_forest: binary (0 or 1)
        - forest_type_deciduous_broadleaf_forest: binary (0 or 1)
        - forest_type_mixed_forests: binary (0 or 1)
        - forest_type_closed_shrublands: binary (0 or 1)
        - forest_type_open_shrublands: binary (0 or 1)
        - forest_type_woody_savannas: binary (0 or 1)
        - forest_type_savannas: binary (0 or 1)
        - forest_type_grasslands: binary (0 or 1)
        - forest_type_permanent_wetlands: binary (0 or 1)
        - forest_type_croplands: binary (0 or 1)
        - forest_type_urban_built_up: binary (0 or 1)
        - forest_type_cropland_natural_mosaic: binary (0 or 1)
        - forest_type_snow_ice: binary (0 or 1)
        - forest_type_barren: binary (0 or 1)
        - forest_type_water: binary (0 or 1)
        - landcover_class_raw: numeric class value
        
    Examples:
    --------
    >>> # Get forest types using MODIS
    >>> forest_types = get_forest_types(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     fire_date='2023-07-15',
    ...     data_source='MODIS'
    ... )
    >>> print(forest_types)
    """
    # Validate inputs
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    
    # Initialize Google Earth Engine
    _initialize_gee()
    
    # Create point geometry
    point = ee.Geometry.Point([longitude, latitude])
    
    # Get land cover dataset based on data source
    if data_source.upper() == 'MODIS':
        landcover_image = _get_modis_landcover(date=fire_date, classification_scheme=classification_scheme)
    elif data_source.upper() == 'ESA':
        landcover_image = _get_esa_cci_landcover(date=fire_date)
    else:
        raise ValueError(f"Unknown data_source: {data_source}. Must be 'MODIS' or 'ESA'")
    
    # Extract forest types as one-hot features
    features = _extract_forest_types_one_hot(
        point=point,
        landcover_image=landcover_image,
        scale=scale_meters,
        classification_scheme=classification_scheme if data_source.upper() == 'MODIS' else 'ESA'
    )
    
    # Add metadata
    features['latitude'] = latitude
    features['longitude'] = longitude
    if fire_date:
        features['fire_date'] = fire_date
    features['data_source'] = data_source
    
    return features


# Note: LANDFIRE pre-computed layers are no longer used to avoid location-based data leakage.
# All fuel characteristics are now derived globally using consistent methodology.
# LANDFIRE data could be used for validation/reference, but not as training features.


def _derive_fuel_characteristics_globally(
    date: Optional[str] = None,
    location: Optional[ee.Geometry] = None
) -> Dict[str, ee.Image]:
    """
    Derive fuel characteristics from vegetation indices and biomass (globally consistent).
    
    Always derives fuel characteristics using the same methodology globally to avoid
    location-based data leakage. Derived from:
    - MODIS NDVI/EVI: Vegetation indices for fuel load and canopy cover
    - MODIS NPP: Net Primary Productivity for biomass accumulation
    - MODIS Land Cover: For fuel model classification and canopy height estimation
    
    Parameters:
    -----------
    date : str, optional
        Date in format 'YYYY-MM-DD'. If provided, gets vegetation data for that time.
    location : ee.Geometry, optional
        Location geometry for spatial filtering
        
    Returns:
    --------
    dict
        Dictionary with derived fuel layer images:
        - fuel_load: Relative fuel load (0-1, derived from NDVI + NPP)
        - fuel_model: Categorical fuel model (1-13, based on land cover + NDVI)
        - canopy_height: Estimated canopy height (meters)
        - canopy_cover: Canopy cover fraction (0-1, from NDVI)
        - surface_fuel_load: Surface layer fuel load (0-1)
        - crown_fuel_load: Crown layer fuel load (0-1)
    """
    if date:
        from datetime import datetime
        fire_date = datetime.strptime(date.split('T')[0], '%Y-%m-%d')
        fire_year = fire_date.year
        start_date = f'{fire_year}-01-01'
        end_date = f'{fire_year + 1}-01-01'
    else:
        # Use most recent available year
        fire_year = 2023
        start_date = '2023-01-01'
        end_date = '2024-01-01'
    
    # Get MODIS vegetation indices
    modis_ndvi = ee.ImageCollection("MODIS/006/MOD13Q1")  # 16-day NDVI/EVI
    modis_npp = ee.ImageCollection("MODIS/006/MOD17A3HGF")  # Annual NPP
    modis_lc = ee.ImageCollection("MODIS/006/MCD12Q1")  # Land Cover
    
    # Filter by date
    ndvi_collection = modis_ndvi.filterDate(start_date, end_date)
    npp_collection = modis_npp.filterDate(start_date, end_date)
    lc_collection = modis_lc.filterDate(start_date, end_date)
    
    if location:
        ndvi_collection = ndvi_collection.filterBounds(location)
        npp_collection = npp_collection.filterBounds(location)
        lc_collection = lc_collection.filterBounds(location)
    
    # Calculate mean NDVI for the year (scale factor: 0.0001)
    ndvi_mean = ndvi_collection.select('NDVI').mean().multiply(0.0001)
    
    # Get annual NPP for biomass (scale factor: 0.0001)
    npp_image = npp_collection.select('Npp').mean().multiply(0.0001)
    
    # Get land cover classification
    landcover = lc_collection.select('LC_Type1').first()
    
    # Derive fuel load: combine NDVI and NPP
    # Higher NDVI and NPP = more vegetation biomass = higher fuel load
    fuel_load = ndvi_mean.add(npp_image.divide(1000)).clamp(0, 1).rename('fuel_load')
    
    # Derive canopy cover from NDVI (higher NDVI = denser canopy)
    canopy_cover = ndvi_mean.clamp(0, 1).rename('canopy_cover')
    
    # Derive canopy height from land cover type
    # Forest types (1-5) have higher canopies
    # Grasslands/shrublands (6-10) have lower canopies
    is_forest = landcover.gte(1).And(landcover.lte(5))
    is_tall_vegetation = landcover.gte(8).And(landcover.lte(10))
    is_grassland = landcover.eq(10)
    is_shrubland = landcover.gte(6).And(landcover.lte(7))
    
    # Assign canopy heights: Forests ~20m, Tall vegetation ~5m, Grass/Shrub ~2m
    canopy_height = (
        is_forest.multiply(20).add(  # Forest: ~20m
            is_tall_vegetation.multiply(5).add(  # Savanna/shrub: ~5m
                is_grassland.Or(is_shrubland).multiply(2)  # Grass/shrub: ~2m
            )
        ).add(1)  # Minimum height: 1m
    ).rename('canopy_height')
    
    # Derive fuel model categories (1-13) based on land cover + NDVI
    # Map MODIS land cover types to fuel model-like categories
    # This creates a consistent classification globally
    
    # Fuel model mapping based on vegetation type and density
    # Model 1-2: Grass (low/high load)
    # Model 3: Tall grass
    # Model 4: Chaparral (shrub)
    # Model 5-9: Shrub types (various)
    # Model 10-13: Timber types (forest, varying density)
    
    fuel_model = (
        is_grassland.multiply(  # Grasslands
            ndvi_mean.lt(0.3).multiply(1).add(  # Low NDVI = Model 1
                ndvi_mean.gte(0.3).And(ndvi_mean.lt(0.5)).multiply(2).add(  # Medium NDVI = Model 2
                    ndvi_mean.gte(0.5).multiply(3)  # High NDVI = Model 3 (tall grass)
                )
            )
        ).add(
            is_shrubland.multiply(  # Shrublands
                ndvi_mean.lt(0.4).multiply(4).add(  # Low density = Model 4
                    ndvi_mean.gte(0.4).And(ndvi_mean.lt(0.6)).multiply(5).add(  # Medium = Model 5
                        ndvi_mean.gte(0.6).multiply(6)  # High = Model 6
                    )
                )
            )
        ).add(
            is_forest.multiply(  # Forests
                ndvi_mean.lt(0.4).multiply(10).add(  # Low density = Model 10
                    ndvi_mean.gte(0.4).And(ndvi_mean.lt(0.6)).multiply(11).add(  # Medium = Model 11
                        ndvi_mean.gte(0.6).And(ndvi_mean.lt(0.8)).multiply(12).add(  # High = Model 12
                            ndvi_mean.gte(0.8).multiply(13)  # Very high = Model 13
                        )
                    )
                )
            )
        ).add(
            is_tall_vegetation.multiply(7)  # Woody savannas = Model 7
        )
    ).clamp(1, 13).rename('fuel_model')
    
    # Surface fuel load: derived from NDVI (surface vegetation)
    surface_fuel_load = ndvi_mean.clamp(0, 1).rename('surface_fuel_load')
    
    # Crown fuel load: derived from canopy cover and height (crown biomass)
    # Higher canopy cover and height = more crown fuel
    crown_fuel_load = canopy_cover.multiply(canopy_height.divide(30)).clamp(0, 1).rename('crown_fuel_load')
    
    fuel_layers = {
        'fuel_load': fuel_load,
        'fuel_model': fuel_model,
        'canopy_height': canopy_height,
        'canopy_cover': canopy_cover,
        'surface_fuel_load': surface_fuel_load,
        'crown_fuel_load': crown_fuel_load
    }
    
    return fuel_layers




def _extract_fuel_features_from_images(
    point: ee.Geometry,
    fuel_layers_dict: Dict[str, ee.Image],
    scale: float = 30.0
) -> Dict[str, float]:
    """
    Extract fuel features at a point from fuel layer images.
    
    Handles both LANDFIRE pre-computed values and derived values from vegetation.
    
    Parameters:
    -----------
    point : ee.Geometry
        Point geometry (longitude, latitude)
    fuel_layers_dict : dict
        Dictionary with fuel layer images. For LANDFIRE: 'fuel_model', 'canopy_bulk_density', 'canopy_base_height'.
        For derived: 'canopy_height', 'canopy_cover', 'surface_fuel_load', 'crown_fuel_load'.
    scale : float
        Scale/resolution in meters for sampling (default: 30m for LANDFIRE, 250m for MODIS)
        
    Returns:
    --------
    dict
        Dictionary with fuel layer features (numeric values and one-hot categorical)
    """
    fuel_features = {}
    
    try:
        # Sample all fuel layer images
        for layer_name, layer_image in fuel_layers_dict.items():
            layer_sample = layer_image.sample(
                region=point,
                scale=scale,
                numPixels=1,
                geometries=False
            )
            layer_info = layer_sample.first().getInfo()
            
            # Get the property value (band name may vary)
            props = layer_info.get('properties', {})
            if props:
                # Try to get value by layer name first, then try common band names
                layer_value = props.get(layer_name) or props.get('b1') or props.get(layer_name.lower())
                # Get first numeric property if name doesn't match
                if layer_value is None:
                    for key, val in props.items():
                        if isinstance(val, (int, float)):
                            layer_value = val
                            break
            else:
                layer_value = None
            
            if layer_value is not None:
                fuel_features[layer_name] = float(layer_value)
            else:
                fuel_features[layer_name] = 0.0
        
    except Exception as e:
        warnings.warn(f"Error sampling fuel data: {e}. Using default values.")
        # Set defaults based on what we expect
        for layer_name in fuel_layers_dict.keys():
            fuel_features[layer_name] = 0.0
    
    # Create one-hot encoding for fuel_model (1-13, consistent globally)
    if 'fuel_model' in fuel_features:
        fuel_model_val = int(round(fuel_features['fuel_model'])) if fuel_features['fuel_model'] else 0
        fuel_model_val = max(1, min(13, fuel_model_val))  # Clamp to 1-13 range
        
        # Create one-hot encoding for fuel model categories (1-13)
        for i in range(1, 14):
            fuel_features[f'fuel_model_{i}'] = 1.0 if fuel_model_val == i else 0.0
        fuel_features['fuel_model_raw'] = float(fuel_model_val)
    
    # Categorize fuel layers into fuel model-like categories based on derived values
    # This creates one-hot encoding for fuel strata categories
    
    # Fuel load categories (low, medium, high)
    fuel_load_val = fuel_features.get('fuel_load', 0.0)
    fuel_features['fuel_load_low'] = 1.0 if fuel_load_val < 0.33 else 0.0
    fuel_features['fuel_load_medium'] = 1.0 if 0.33 <= fuel_load_val < 0.67 else 0.0
    fuel_features['fuel_load_high'] = 1.0 if fuel_load_val >= 0.67 else 0.0
    
    # Canopy height categories
    canopy_height_val = fuel_features.get('canopy_height', 0.0)
    fuel_features['canopy_height_low'] = 1.0 if canopy_height_val < 5.0 else 0.0  # <5m
    fuel_features['canopy_height_medium'] = 1.0 if 5.0 <= canopy_height_val < 15.0 else 0.0  # 5-15m
    fuel_features['canopy_height_high'] = 1.0 if canopy_height_val >= 15.0 else 0.0  # >=15m
    
    # Canopy cover categories
    canopy_cover_val = fuel_features.get('canopy_cover', 0.0)
    fuel_features['canopy_cover_sparse'] = 1.0 if canopy_cover_val < 0.3 else 0.0  # <30%
    fuel_features['canopy_cover_moderate'] = 1.0 if 0.3 <= canopy_cover_val < 0.7 else 0.0  # 30-70%
    fuel_features['canopy_cover_dense'] = 1.0 if canopy_cover_val >= 0.7 else 0.0  # >=70%
    
    # Fuel layer presence (binary indicators)
    fuel_features['has_surface_fuel'] = 1.0 if fuel_features.get('surface_fuel_load', 0.0) > 0.1 else 0.0
    fuel_features['has_crown_fuel'] = 1.0 if fuel_features.get('crown_fuel_load', 0.0) > 0.1 else 0.0
    
    return fuel_features


def get_fuel_layers(
    latitude: float,
    longitude: float,
    fire_date: Optional[str] = None,
    scale_meters: float = 250.0
) -> Dict[str, float]:
    """
    Get fuel layers/load for a location (always derived globally for consistency).
    
    **Always derives fuel characteristics globally** using MODIS vegetation indices
    and land cover to avoid location-based data leakage. Uses consistent methodology
    for all locations (US and global).
    
    Fuel characteristics are derived from:
    - MODIS NDVI: Vegetation indices for fuel load and canopy cover
    - MODIS NPP: Net Primary Productivity for biomass accumulation
    - MODIS Land Cover: For fuel model classification and canopy height
    
    Parameters:
    -----------
    latitude : float
        Latitude of the location (-90 to 90)
    longitude : float
        Longitude of the location (-180 to 180)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
        If provided, derives fuel data for that time period.
    scale_meters : float, optional
        Scale/resolution in meters for sampling (default: 250m for MODIS)
        
    Returns:
    --------
    dict
        Dictionary with fuel layer features (consistent globally):
        - fuel_load: Relative fuel load (0-1, derived from NDVI + NPP)
        - fuel_model: Categorical fuel model (1-13, based on land cover + NDVI)
        - fuel_model_1 through fuel_model_13: binary one-hot encoding (0 or 1)
        - fuel_model_raw: numeric fuel model value
        - canopy_height: Estimated canopy height (meters)
        - canopy_cover: Canopy cover fraction (0-1, from NDVI)
        - surface_fuel_load: Surface layer fuel load (0-1)
        - crown_fuel_load: Crown layer fuel load (0-1)
        - Plus categorical one-hot encodings (low/medium/high for fuel_load, canopy_height, canopy_cover)
        - has_surface_fuel: Binary indicator (0 or 1)
        - has_crown_fuel: Binary indicator (0 or 1)
        
    Examples:
    --------
    >>> # Get fuel layers (always derived globally, consistent methodology)
    >>> fuel_layers = get_fuel_layers(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     fire_date='2023-07-15'
    ... )
    >>> print(fuel_layers)
    >>> 
    >>> # Same methodology for global locations
    >>> fuel_layers = get_fuel_layers(
    ...     latitude=-12.1958,
    ...     longitude=-43.9543,
    ...     fire_date='2023-07-15'
    ... )
    """
    # Validate inputs
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    
    # Initialize Google Earth Engine
    _initialize_gee()
    
    # Create point geometry
    point = ee.Geometry.Point([longitude, latitude])
    
    # Always derive fuel characteristics globally (consistent methodology)
    # This avoids location-based data leakage
    derived_layers = _derive_fuel_characteristics_globally(date=fire_date, location=point)
    
    # Extract fuel features from derived images
    features = _extract_fuel_features_from_images(
        point=point,
        fuel_layers_dict=derived_layers,
        scale=scale_meters
    )
    
    # Add metadata
    features['latitude'] = latitude
    features['longitude'] = longitude
    if fire_date:
        features['fire_date'] = fire_date
    features['data_source'] = 'derived_vegetation_global'
    
    return features


def get_vegetation_features_for_block_centroid(
    block_centroid: Tuple[float, float],
    block_size_km: float,
    fire_date: Optional[str] = None,
    include_forest_types: bool = True,
    include_fuel_layers: bool = True,
    forest_data_source: str = 'MODIS',
    scale_meters: float = 250.0
) -> Dict[str, float]:
    """
    Get both forest types and fuel layers for a block centroid.
    
    This function is designed for use with training data where locations
    are represented as blocks with centroids in a globally specified area.
    
    Parameters:
    -----------
    block_centroid : tuple
        (latitude, longitude) of the block centroid
    block_size_km : float
        Size of the block in kilometers (used for documentation/reference)
    fire_date : str, optional
        Date of the fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
    include_forest_types : bool, optional
        Whether to include forest type features (default: True)
    include_fuel_layers : bool, optional
        Whether to include fuel layer features (default: True)
    forest_data_source : str, optional
        Data source for forest types: 'MODIS' or 'ESA' (default: 'MODIS')
    scale_meters : float, optional
        Scale/resolution in meters for sampling (default: 250m)
        
    Returns:
    --------
    dict
        Dictionary containing all vegetation and fuel features
        
    Examples:
    --------
    >>> # Get all vegetation features for a block centroid
    >>> features = get_vegetation_features_for_block_centroid(
    ...     block_centroid=(40.7128, -74.0060),
    ...     block_size_km=1.0,
    ...     fire_date='2023-07-15'
    ... )
    >>> print(features)
    """
    lat, lon = block_centroid
    features = {}
    
    # Get forest types if requested
    if include_forest_types:
        forest_features = get_forest_types(
            latitude=lat,
            longitude=lon,
            fire_date=fire_date,
            data_source=forest_data_source,
            scale_meters=scale_meters
        )
        features.update(forest_features)
    
    # Get fuel layers if requested
    if include_fuel_layers:
        fuel_features = get_fuel_layers(
            latitude=lat,
            longitude=lon,
            fire_date=fire_date,
            scale_meters=scale_meters
        )
        features.update(fuel_features)
    
    # Add block metadata
    features['block_size_km'] = block_size_km
    
    return features

