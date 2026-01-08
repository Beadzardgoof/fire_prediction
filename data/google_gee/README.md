# Google Earth Engine - Water Distance Data

This module provides functions to calculate the distance to the nearest body of water using Google Earth Engine (GEE).

## Features

- Calculates distance to nearest body of water in meters
- Uses HydroSHEDS and JRC Global Surface Water datasets
- Works globally for any location
- Designed for use with block centroids in training data

## Setup

1. Install required dependencies:
   ```bash
   pip install earthengine-api
   ```

2. Set up environment variables:
   - `SERVICE_ACCOUNT`: Your Google Earth Engine service account email
   - `GEE_KEY`: Either:
     - Path to your service account JSON key file, or
     - JSON string containing the service account credentials

   Example `.env` file:
   ```
   SERVICE_ACCOUNT=your-service-account@project.iam.gserviceaccount.com
   GEE_KEY=/path/to/your/key.json
   # OR
   GEE_KEY={"type": "service_account", "project_id": "...", ...}
   ```

## Usage

### Single Location

```python
from data.google_gee.get_water_distance import get_distance_to_water

# Get distance to nearest water at fire time
distance = get_distance_to_water(
    latitude=40.7128,
    longitude=-74.0060,
    max_search_radius_km=50.0,
    fire_date='2023-07-15'  # Optional: date of fire event
)

print(f"Distance to nearest water: {distance:.2f} meters")

# Without specific date (uses permanent water)
distance = get_distance_to_water(
    latitude=40.7128,
    longitude=-74.0060,
    max_search_radius_km=50.0
)
```

### Block Centroid (For Training Data)

```python
from data.google_gee.get_water_distance import get_distance_to_water_for_block_centroid

# Get distance for a block centroid at fire time
result = get_distance_to_water_for_block_centroid(
    block_centroid=(40.7128, -74.0060),
    block_size_km=1.0,
    max_search_radius_km=50.0,
    fire_date='2023-07-15'  # Optional: date of fire event
)

print(f"Distance: {result['distance_to_water_meters']:.2f} meters")
```

### Batch Processing

```python
from data.google_gee.get_water_distance import get_distance_to_water_batch

# Process multiple locations at fire time
coordinates = [
    (40.7128, -74.0060),  # New York
    (34.0522, -118.2437), # Los Angeles
    (51.5074, -0.1278)    # London
]

df = get_distance_to_water_batch(
    coordinates=coordinates,
    max_search_radius_km=50.0,
    fire_date='2023-07-15'  # Optional: date of fire event
)

print(df)
```

## Data Sources

- **HydroSHEDS**: Global hydrological datasets providing drainage networks and river systems
- **JRC Global Surface Water**: Permanent water bodies dataset from the Joint Research Centre
- **USGS HydroSHEDS**: Additional water body features

## Parameters

- `latitude`: Latitude of the location (-90 to 90)
- `longitude`: Longitude of the location (-180 to 180)
- `max_search_radius_km`: **Required** - Maximum radius to search for water in kilometers
- `block_size_km`: **Required** for block centroid function - Size of the block in kilometers
- `fire_date`: Optional - Date of fire event in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm:ss'
  - If provided, calculates distance to water bodies that existed at that time
  - If None, uses permanent water bodies (occurrence > 99%)
- `scale_meters`: Resolution for distance calculation (default: 30 meters)

## Output

Returns distance in **meters** as a float. If no water is found within the search radius, returns `max_search_radius_km * 1000`.

## Temporal Water Data

The script supports temporal awareness for water bodies:
- **With `fire_date`**: Uses JRC Global Surface Water to identify water bodies that existed at the fire time
  - Considers water with >30% occurrence and checks if water existed at the fire date
  - Filters out water that disappeared before the fire date
- **Without `fire_date`**: Uses permanent water bodies (occurrence > 99%)

## Notes

- First call will initialize Google Earth Engine (may take a few seconds)
- GEE API has usage quotas and rate limits
- Distance calculation accuracy depends on the `scale_meters` parameter (default: 30m)
- For faster processing with lower accuracy, increase `scale_meters` (e.g., 100m or 250m)
- Temporal water data uses JRC dataset (covers 1984-2021). For dates outside this range, falls back to permanent water

