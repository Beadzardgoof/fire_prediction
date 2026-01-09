# NASA SRTM DEM API - Terrain Data

This directory contains scripts and documentation for fetching elevation data from the NASA SRTM DEM (Shuttle Radar Topography Mission Digital Elevation Model) API and computing terrain features for fire prediction.

## Overview

NASA SRTM DEM provides global elevation data at 30-meter resolution. This module computes the following terrain features required for fire prediction:

- **Elevation**: Direct elevation values from DEM
- **Slope**: Terrain slope in degrees (computed from elevation gradient)
- **Ruggedness**: Terrain Roughness Index (TRI) - measures local elevation variation
- **Curvature**: Profile curvature indicating concavity/convexity
- **Canyons**: Binary detection of steep terrain features

**Note**: Distance to body of water requires additional data sources (HydroSHEDS, OpenStreetMap) and is not included in this module.

## API Endpoint

The module uses the NASA Earthdata API for SRTM data. The API key should be stored in your `.env` file as `NASA_DEM_API_KEY`.

## Usage

### Basic Usage

```python
from data.nasa_dem.get_terrain import fetch_terrain_features

# Fetch terrain features for a single location
terrain = fetch_terrain_features(
    latitude=40.7128,
    longitude=-74.0060
)

print(f"Elevation: {terrain['elevation']} m")
print(f"Slope: {terrain['slope']} degrees")
print(f"Ruggedness: {terrain['ruggedness']}")
```

### Batch Processing

```python
from data.nasa_dem.get_terrain import fetch_terrain_features_batch

# Fetch terrain for multiple locations
coordinates = [
    (40.7128, -74.0060),  # New York
    (34.0522, -118.2437),  # Los Angeles
    (41.8781, -87.6298)    # Chicago
]

df = fetch_terrain_features_batch(coordinates)
print(df)
```

### Compute Features from Elevation Array

If you already have elevation data:

```python
import numpy as np
from data.nasa_dem.get_terrain import compute_terrain_from_elevation_array

# Example elevation array
elevation = np.array([[100, 105, 110],
                      [95, 100, 105],
                      [90, 95, 100]])

# Compute all terrain features
features = compute_terrain_from_elevation_array(elevation, cell_size=30.0)

print(features['slope'])
print(features['ruggedness'])
print(features['curvature'])
```

## Terrain Features

### Elevation
- **Source**: Direct from SRTM DEM
- **Units**: Meters
- **Description**: Mean elevation at the location

### Slope
- **Source**: Computed from elevation gradient
- **Units**: Degrees
- **Description**: Terrain steepness. Higher values indicate steeper terrain.

### Ruggedness (TRI)
- **Source**: Computed from elevation differences
- **Units**: Meters
- **Description**: Terrain Roughness Index measuring local elevation variation. Higher values indicate more rugged terrain.

### Curvature
- **Source**: Computed from second derivatives of elevation
- **Units**: Dimensionless
- **Description**: Profile curvature indicating terrain shape. Positive values = convex (hills), negative = concave (valleys).

### Canyons
- **Source**: Detected from slope and depth analysis
- **Units**: Binary (0 or 1)
- **Description**: Indicates presence of steep, deep terrain features (canyons).

## API Configuration

### Environment Variable

Set your NASA DEM API key in your `.env` file:

```
NASA_DEM_API_KEY=your_api_key_here
```

### API Key Setup

1. Register for a NASA Earthdata account at https://urs.earthdata.nasa.gov/
2. Generate an API key/token
3. Add it to your `.env` file as `NASA_DEM_API_KEY`

## Integration with Fire Prediction

Terrain features from NASA SRTM DEM are used for:

1. **Slope**: Steeper slopes can increase fire spread rate
2. **Ruggedness**: Rugged terrain affects fire behavior and access
3. **Elevation**: Higher elevations may have different fuel moisture and weather conditions
4. **Curvature**: Terrain shape affects fire spread patterns
5. **Canyons**: Steep terrain features can channel winds and affect fire behavior

## Dependencies

- `numpy`: Array operations
- `scipy`: Terrain analysis (for canyon detection)
- `rasterio`: DEM data processing (optional, for advanced features)
- `requests`: API requests
- `pandas`: Data handling
- `python-dotenv`: Environment variable loading

## Notes

- The current implementation fetches point elevation data. For area-based analysis, you may need to download full SRTM tiles.
- Distance to water bodies requires additional data sources (HydroSHEDS, OpenStreetMap) and is not included in this module.
- For large-scale analysis, consider downloading SRTM tiles directly from NASA Earthdata.

## Resources

- [NASA SRTM Documentation](https://www2.jpl.nasa.gov/srtm/)
- [NASA Earthdata](https://www.earthdata.nasa.gov/)
- [OpenTopography API](https://opentopography.org/) (alternative data source)




