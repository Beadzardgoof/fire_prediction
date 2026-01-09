# Google Earth Engine - Vegetation and Fuel Features

This module provides functions to fetch forest type classification and fuel layer data using Google Earth Engine (GEE) for fire prediction models.

## Features

- **Forest Types**: One-hot categorical encoding of forest and vegetation types
- **Fuel Layers**: Fuel model classifications and load estimates (US: LANDFIRE, Global: land cover proxies)
- Works globally for forest types (MODIS/ESA), US-only for detailed fuel models (LANDFIRE)
- Temporal awareness: supports fire date to get historical land cover classifications

## Data Sources

### Forest Types
- **MODIS Land Cover (MCD12Q1)**: Global, 500m resolution, annual (2001-2023)
  - IGBP classification scheme (17 classes)
  - Other schemes: UMD, LCCS1, LCCS2, PFT, LAI
- **ESA CCI Land Cover**: Global, 10m resolution (2020+)
  - ESA WorldCover classification

### Fuel Layers
- **LANDFIRE** (US only): 30m resolution fuel models
  - Scott & Burgan fuel models (1-13)
  - Available versions: 2001, 2008, 2010, 2012, 2014, 2016, 2019, 2020
  - Geographic bounds: approximately -180 to -50 longitude, 15 to 72 latitude
- **Global Land Cover Proxies**: For non-US locations
  - Derived from MODIS land cover
  - Basic fuel categorization (forest, grassland, shrubland, urban)

## Setup

Same setup as water distance module. Ensure environment variables are set:
- `SERVICE_ACCOUNT`: Your Google Earth Engine service account email
- `GEE_KEY`: Path to JSON key file or JSON string

## Usage

### Forest Types (One-Hot Categorical)

```python
from data.google_gee.get_vegetation_features import get_forest_types

# Get forest types using MODIS
forest_types = get_forest_types(
    latitude=40.7128,
    longitude=-74.0060,
    fire_date='2023-07-15',
    data_source='MODIS',  # or 'ESA'
    classification_scheme='IGBP'  # For MODIS only
)

# Returns one-hot encoded features:
# - forest_type_evergreen_needleleaf_forest: 0 or 1
# - forest_type_evergreen_broadleaf_forest: 0 or 1
# - forest_type_deciduous_needleleaf_forest: 0 or 1
# - forest_type_deciduous_broadleaf_forest: 0 or 1
# - forest_type_mixed_forests: 0 or 1
# - forest_type_closed_shrublands: 0 or 1
# - forest_type_open_shrublands: 0 or 1
# - forest_type_woody_savannas: 0 or 1
# - forest_type_savannas: 0 or 1
# - forest_type_grasslands: 0 or 1
# - forest_type_permanent_wetlands: 0 or 1
# - forest_type_croplands: 0 or 1
# - forest_type_urban_built_up: 0 or 1
# - forest_type_cropland_natural_mosaic: 0 or 1
# - forest_type_snow_ice: 0 or 1
# - forest_type_barren: 0 or 1
# - forest_type_water: 0 or 1
# - landcover_class_raw: numeric class value
```

### Fuel Layers

```python
from data.google_gee.get_vegetation_features import get_fuel_layers

# Get fuel layers for US location (uses LANDFIRE)
fuel_layers = get_fuel_layers(
    latitude=40.7128,
    longitude=-74.0060,
    fire_date='2023-07-15'
)

# Returns fuel model features:
# - fuel_model_1 through fuel_model_13: one-hot encoding (0 or 1)
# - fuel_model_raw: numeric fuel model value (1-13)
# - fuel_model_category: numeric category

# For non-US locations (uses land cover proxies)
fuel_layers = get_fuel_layers(
    latitude=-12.1958,  # Non-US location
    longitude=-43.9543,
    fire_date='2023-07-15'
)
# Returns basic fuel proxies instead of detailed LANDFIRE models
```

### Block Centroid (For Training Data)

```python
from data.google_gee.get_vegetation_features import get_vegetation_features_for_block_centroid

# Get both forest types and fuel layers for a block centroid
features = get_vegetation_features_for_block_centroid(
    block_centroid=(40.7128, -74.0060),
    block_size_km=1.0,
    fire_date='2023-07-15',
    include_forest_types=True,
    include_fuel_layers=True,
    forest_data_source='MODIS'
)

# Returns combined dictionary with all forest type and fuel layer features
```

## Parameters

### Forest Types (`get_forest_types`)
- `latitude`: Latitude of the location (-90 to 90)
- `longitude`: Longitude of the location (-180 to 180)
- `fire_date`: Optional - Date of fire event in format 'YYYY-MM-DD'
  - If provided, gets land cover for that year
  - If None, uses most recent available year
- `data_source`: 'MODIS' or 'ESA' (default: 'MODIS')
- `classification_scheme`: For MODIS only - 'IGBP', 'UMD', 'LCCS1', 'LCCS2', 'PFT', or 'LAI' (default: 'IGBP')
- `scale_meters`: Resolution for sampling (default: 250m for MODIS)

### Fuel Layers (`get_fuel_layers`)
- `latitude`: Latitude of the location (-90 to 90)
- `longitude`: Longitude of the location (-180 to 180)
- `fire_date`: Optional - Date of fire event
- `scale_meters`: Resolution for sampling (default: 30m for LANDFIRE)
- `use_us_only`: If True, only uses LANDFIRE for US locations (default: True)

## Notes

### Forest Types
- **MODIS MCD12Q1**: Annual composites, available 2001-2023
  - For dates outside this range, uses most recent available year
  - 500m native resolution
- **ESA CCI WorldCover**: Annual updates, available 2020+
  - For dates before 2020, uses 2020 data
  - 10m native resolution (higher accuracy)
- One-hot encoding means exactly one feature will be 1.0, all others 0.0

### Fuel Layers
- **LANDFIRE**: US-only dataset with detailed fuel models
  - Geographic bounds: approximately US bounds
  - For non-US locations, uses simplified land cover proxies
  - **Note**: Global Fuel Database (GFD) mentioned in README is for future fire spread prediction implementation
- **Fuel Models**: LANDFIRE uses Scott & Burgan fuel models (13 categories)
  - Models 1-2: Grass
  - Model 3: Tall grass
  - Model 4: Chaparral
  - Models 5-9: Shrub types
  - Models 10-13: Timber types

### For Training Models
- These features are designed for **fire start time**, **duration**, and **probability** classification
- Duration may be highly uncorrelated with these features
- One-hot categorical encoding is suitable for tree-based models and neural networks

## Integration with Training Pipeline

```python
from data.google_gee.get_vegetation_features import get_vegetation_features_for_block_centroid

# Example: Get features for a fire detection block
def get_vegetation_features(lat, lon, fire_date, block_size_km=1.0):
    features = get_vegetation_features_for_block_centroid(
        block_centroid=(lat, lon),
        block_size_km=block_size_km,
        fire_date=fire_date
    )
    return features

# Use in feature extraction pipeline
vegetation_features = get_vegetation_features(
    lat=40.7128,
    lon=-74.0060,
    fire_date='2023-07-15'
)

# Features can be directly used for training (one-hot categorical)
# All forest_type_* and fuel_model_* features are ready for ML models
```


