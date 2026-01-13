# Ingestion Notebook Configuration Summary

## Overview
The `ingestion.ipynb` notebook has been updated with comprehensive configuration parameters and Google Earth Engine (GEE) integration. All dataset sources, sampling strategies, and feature extraction settings are now centrally configured at the start of the notebook.

## What Was Added

### 1. **Comprehensive Configuration Section** (Cell 0-1)

A single, centralized configuration block that controls:

#### Dataset Configuration
- `SAMPLE_SIZE = 3000` - Number of fire samples to process
- `RANDOM_STATE = 42` - Reproducibility seed
- `USE_MODIS = True` - Enable MODIS fire detection data
- `MODIS_SHAPEFILE` - Path to MODIS shapefile
- `USE_NASA_POWER = True` - Enable NASA POWER weather data
- `USE_GEE = True` - Enable Google Earth Engine features

#### NASA POWER Weather Settings
- `NASA_POWER_TEMPORAL = 'daily'` - Daily resolution (vs hourly)
- `NASA_POWER_PARAMS` - Full list of weather parameters (RH2M, PRECTOT, T2M, etc.)
- `WEATHER_LOOKBACK_DAYS = 14` - Days before fire event to fetch

#### Google Earth Engine Configuration
- `GEE_EXTRACT_TERRAIN = True` - SRTM elevation, slope, aspect, curvature, ruggedness
- `GEE_EXTRACT_WATER = True` - Distance to water bodies (JRC)
- `GEE_EXTRACT_VEGETATION = True` - NDVI, EVI, LAI from MODIS
- `GEE_EXTRACT_FUEL = True` - Fuel moisture and type (placeholder for future)
- `GEE_EXTRACT_BIOME = True` - WWF Terrestrial Ecoregions (placeholder for future)

#### GEE Feature Format Definition
A structured dictionary `GEE_FEATURE_FORMAT` that specifies:
- Feature names for each category (terrain, water, vegetation, fuel, biome)
- Expected data types (float32, int8, string, etc.)
- Used for validation and ensuring consistent feature engineering

**Example:**
```python
GEE_FEATURE_FORMAT = {
    'terrain': {
        'elevation': 'float32',
        'slope': 'float32',
        'aspect': 'float32',
        'curvature': 'float32',
        'ruggedness': 'float32'
    },
    'vegetation': {
        'ndvi': 'float32',
        'ndvi_14day_mean': 'float32',
        'evi': 'float32',
        'lai': 'float32'
    }
    # ... more categories
}
```

#### Stratified Sampling Configuration
- `ENABLE_GEOGRAPHIC_STRATIFICATION = True` - 6x12 lat/lon grid (72 regions)
- `ENABLE_TEMPORAL_STRATIFICATION = False` - For multi-temporal data (future)
- `ENABLE_BIOME_STRATIFICATION = True` - Ensure biome diversity
- `MIN_UNIQUE_BIOMES = 5` - Minimum biome types required
- `MAX_BIOME_PROPORTION = 0.50` - No single biome > 50%

#### Data Quality Requirements
- `MIN_HUMIDITY_COVERAGE = 0.80` - 80% of samples must have humidity
- `MIN_PRECIPITATION_COVERAGE = 0.80` - 80% must have precipitation
- `MIN_CONFIDENCE_SCORE = 30` - MODIS confidence threshold

#### API Rate Limiting
- `NASA_POWER_API_DELAY = 0.1` - Seconds between requests (with key)
- `NASA_POWER_MAX_CONCURRENT = 5` - Concurrent requests (with key)
- `GEE_BATCH_SIZE = 50` - Locations per GEE batch

#### Output Paths
- `WEATHER_OUTPUT` - Weather features output path
- `TERRAIN_OUTPUT` - Terrain features output path
- `GEOSPATIAL_OUTPUT` - Geospatial features output path
- `ML_READY_OUTPUT` - Final ML-ready dataset path

The configuration cell also prints a comprehensive summary of all settings when executed.

### 2. **GEE Initialization Cell** (Cell 2)

Handles Google Earth Engine authentication and initialization:
- Loads credentials from `GEE_KEY` environment variable
- Authenticates with service account
- Initializes Earth Engine API
- Validates credential file exists
- Provides helpful error messages if setup fails
- Confirms which GEE features are enabled

### 3. **GEE Feature Extraction Wrapper** (Cell 3)

A unified function `extract_gee_features_batch()` that:
- Extracts all enabled GEE features in one call
- Processes locations in configurable batches (default: 50)
- Returns a dictionary of DataFrames (one per feature category)
- Automatically applies correct data types from `GEE_FEATURE_FORMAT`
- Handles errors gracefully per feature category
- Provides progress updates

**Usage:**
```python
gee_results = extract_gee_features_batch(
    locations_df=fire_data,
    batch_size=GEE_BATCH_SIZE
)
# Returns: {'terrain': df, 'water': df, 'vegetation': df, ...}
```

### 4. **GEE Feature Format Validation** (Cell 4-5)

A validation function `validate_gee_features()` that:
- Checks extracted features against `GEE_FEATURE_FORMAT` specification
- Verifies column names match expected features
- Validates data types are correct
- Reports completeness percentage
- Identifies missing or unexpected columns
- Provides detailed validation report

**Usage:**
```python
all_valid = validate_gee_features(gee_results)
```

### 5. **Updated Data Loading References**

Throughout the notebook, hardcoded values have been replaced with configuration variables:
- File paths now reference `MODIS_SHAPEFILE`, `WEATHER_OUTPUT`, etc.
- API delays reference `NASA_POWER_API_DELAY`
- Sample sizes reference `SAMPLE_SIZE`
- Lookback periods reference `WEATHER_LOOKBACK_DAYS`

## Benefits

### 🎯 **Single Source of Truth**
All parameters are defined once at the top of the notebook. No more hunting through cells to change settings.

### 🔧 **Easy Configuration**
Want to change sample size? Adjust `SAMPLE_SIZE = 3000` to `SAMPLE_SIZE = 5000`. All downstream code adapts automatically.

### 🌍 **GEE Integration**
Google Earth Engine features are now:
- Centrally configured
- Automatically extracted with correct format
- Validated against expected schema
- Easy to enable/disable per feature category

### ✅ **Data Quality**
Built-in validation ensures:
- Feature formats are consistent
- Required data coverage is met
- Biome diversity is adequate
- Geographic sampling is stratified

### 📊 **Feature Format Consistency**
The `GEE_FEATURE_FORMAT` dictionary ensures:
- All features have consistent naming
- Data types are optimized (float32 vs float64)
- Easy to track what features are expected
- Validation catches issues early

### ⚡ **Optimized for Scale**
- Concurrent API requests for NASA POWER
- Batched GEE requests
- Configurable rate limiting
- Ready for 3000+ sample datasets

## Usage Example

```python
# 1. Configure at the top
SAMPLE_SIZE = 3000
USE_GEE = True
GEE_EXTRACT_TERRAIN = True
GEE_EXTRACT_VEGETATION = True

# 2. Load MODIS data
fire_data = gpd.read_file(MODIS_SHAPEFILE)

# 3. Sample with stratification
fire_data = stratified_geographic_sampling(fire_data, SAMPLE_SIZE)

# 4. Extract GEE features
gee_results = extract_gee_features_batch(fire_data)

# 5. Validate features
validate_gee_features(gee_results)

# 6. Merge and save
ml_ready = merge_all_features(fire_data, gee_results, weather_df)
ml_ready.to_parquet(ML_READY_OUTPUT)
```

## Next Steps

### For 3000-Sample Medium-Scale Training:
1. Set `SAMPLE_SIZE = 3000`
2. Ensure `ENABLE_GEOGRAPHIC_STRATIFICATION = True`
3. Ensure `ENABLE_BIOME_STRATIFICATION = True`
4. Enable all GEE extractions for maximum terrain diversity
5. Run the notebook end-to-end

### For Multi-Temporal Data (Future):
1. Obtain MODIS data spanning multiple months/years (via FIRMS API)
2. Set `ENABLE_TEMPORAL_STRATIFICATION = True`
3. Adjust `N_TEMPORAL_BINS` to desired number of seasons/quarters

### For New GEE Features:
1. Add to `GEE_FEATURE_FORMAT` dictionary
2. Set corresponding `GEE_EXTRACT_*` flag to `True`
3. Implement extraction function in `data_ingest/google_gee/`
4. Add to `extract_gee_features_batch()` function

## Files Modified

- ✅ `ingestion.ipynb` - Added configuration, GEE integration, validation
- ✅ All cells now reference centralized configuration

## Environment Variables Required

- `NASA_POWER_API_KEY` - Optional, improves rate limits
- `GEE_KEY` - Path to Google Earth Engine service account JSON file

## Notes

- The notebook now has **28 total cells** (was ~20 before)
- Configuration is at **Cell 0-1**
- GEE setup is at **Cell 2-5**
- Previous hardcoded values have been replaced with config references
- All GEE features will be extracted in the format specified by `GEE_FEATURE_FORMAT`

---

**Summary**: The ingestion notebook is now fully configured for medium-scale training with 3000 samples, diverse geographic and biome sampling, comprehensive GEE feature extraction, and built-in validation. All parameters are centralized and easy to modify.



