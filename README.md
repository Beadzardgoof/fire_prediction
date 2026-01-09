# Fire Detection and Risk Assessment

This project is designed to detect fires and assess fire risk using data analysis and machine learning techniques.

## Overview

The goal of this project is to:
- Detect fires using various data sources
- Assess fire risk for different regions and conditions
- Eventually design a frontend for a website that provides risk assessment

## Project Structure

- `fire_detection.ipynb` - Jupyter notebook containing the fire detection and risk assessment analysis
- `README.md` - This file

## Future Development

We plan to develop a web frontend that will provide:
- Real-time fire risk assessment
- Interactive maps showing risk levels
- Historical fire data visualization
- Predictive analytics for fire prevention

## Getting Started

1. Install required dependencies:
   ```bash
   pip install pandas numpy matplotlib seaborn jupyter
   ```

2. Open the Jupyter notebook:
   ```bash
   jupyter notebook fire_detection.ipynb
   ```

## License

See LICENSE file for details.
## Data format

# Fire Prediction Feature Set

## 1. Weather / Temporal Features
the * * around a given data source indicates that it has been selected for use, after each row there will be a dash indiating that the fire source has the specified data needed for at least instrucitons on how to get said data

| Feature | Data Type | Notes | Source |
|---------|-----------|-------|--------|
| 3-day consecutive dry, wet, humid index | Float | Normalized numeric; each index is a column |(precipitation, humidity), ERA5 reanalysis, MODIS LST | - data/nasa_power
| 14-day fuel conditioning index | Float | Weighted sum of dryness/wetness; continuous | ERA5, NASA POWER, MODIS vegetation dryness proxies (NDVI, NBR) | - data/nasa_power
| Weighted weather extremes (wind, rain) over 12h | Float or Array | Exponential weighting of extremes; can be aggregated or sequence | HRRR (US), GFS (global) | - data/nasa_power
| Soft binary threshold (humidity/wetness vs temperature) | Float (0–1) | Represents probability of exceeding ignition thresholds | Computed from weather features | - data/nasa_power

## 2. Geospatial / Terrain Features

| Feature | Data Type | Notes | Source |
|---------|-----------|-------|--------|
| Slope | Float | Degrees or percent | SRTM DEM (30m), NASADEM | -data_ingest/nasa_dem
| Ruggedness | Float | Terrain roughness index | Computed from DEM | -data_ingestion/nasa_dem
| Elevation | Float | Meters | SRTM / NASADEM | -data_ingest/nasa_dem
| Curvature | Float | Concavity/convexity measure | Derived from DEM | -data_ingest/nasa_dem
| Canyons | Float / Binary | Depth or presence of steep terrain | DEM-derived | -data_ingest/nasa_dem
| Distance to body of water | Float | Meters; continuous | HydroSHEDS, OpenStreetMap rivers/lakes | -data_ingest/google_gee

## 3. Vegetation / Fuel Features

| Feature | Data Type | Notes | Source |
|---------|-----------|-------|--------|
| Forest types | One-hot categorical | Each type is a binary column | MODIS Land Cover (MCD12Q1), ESA CCI Land Cover |-data_ingest/google_gee
| Fuel layers / load | One-hot categorical or numeric | Encodes multiple fuel strata | LANDFIRE (US), Global Fuel Database, FAO forest layers | -data_ingest/google_gee & -data_ingest/gfd (to be implemented later)

## 4. Temporal / Circular Features

| Feature | Data Type | Notes | Source |
|---------|-----------|-------|--------|
| Season | 2 numeric features (sin/cos) | Encodes circularity of seasons | -Derived from date | - calculated
| Time of day | 2 numeric features (sin/cos) | Encodes circularity of hours | -Derived from fire detection time |

## 5. Target Variables

| Feature | Data Type | Notes | Source |
|---------|-----------|-------|--------|
| Start time | Float / datetime | Timestamp or numeric hours since reference | MODIS/VIIRS detection dataset | -data_ingest/modis_fire
| End time | Float / datetime | Timestamp or numeric hours | MODIS/VIIRS detection dataset | -data_ingest/modis_fire
| Ignition probability | Float (0–1) | Scaled confidence from satellite detection | MODIS/VIIRS confidence column | -data_ingest/modis_fire











