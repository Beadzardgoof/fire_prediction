# NASA POWER API - Humidity Data

This directory contains scripts and documentation for fetching humidity data from the NASA POWER (Prediction of Worldwide Energy Resources) API.

## Overview

NASA POWER provides meteorological and solar data including:
- **RH2M**: Relative humidity at 2 meters above ground
- **RH2M_MAX**: Maximum relative humidity at 2 meters
- **RH2M_MIN**: Minimum relative humidity at 2 meters

These humidity parameters are essential for fire risk assessment as low humidity conditions increase fire danger.

## API Endpoint

**Base URL**: `https://power.larc.nasa.gov/api/temporal/hourly/point`

## URL Configuration

### Standard GET Request

The NASA POWER API uses query parameters to specify the data request. Here's the standard configuration:

```
https://power.larc.nasa.gov/api/temporal/hourly/point?start={START}&end={END}&latitude={LAT}&longitude={LON}&community={COMMUNITY}&parameters={PARAMS}&format={FORMAT}&units={UNITS}&user={USER}&header={HEADER}&time-standard={TIME_STD}&site-elevation={SITE_ELEV}&wind-elevation={WIND_ELEV}&wind-surface={WIND_SURFACE}
```

### Example cURL Command

```bash
curl -X 'GET' \
  'https://power.larc.nasa.gov/api/temporal/hourly/point?start=20240101&end=20240102&latitude=40.7128&longitude=-74.0060&community=ag&parameters=RH2M&format=json&units=imperial&user=Drew&header=true&time-standard=lst&site-elevation=10&wind-elevation=20&wind-surface=10m' \
  -H 'accept: application/json'
```

### Parameter Reference

| Parameter | Type | Required | Description | Example Values |
|-----------|------|----------|-------------|----------------|
| `start` | string | Yes | Start date/time | `20240101` (YYYYMMDD) or `2024010112` (YYYYMMDDHH) |
| `end` | string | Yes | End date/time | `20240102` (YYYYMMDD) or `2024010212` (YYYYMMDDHH) |
| `latitude` | float | Yes | Latitude (-90 to 90) | `40.7128` |
| `longitude` | float | Yes | Longitude (-180 to 180) | `-74.0060` |
| `community` | string | Yes | Data community | `ag` (agriculture), `re` (renewable energy), `sb` (sustainable buildings) |
| `parameters` | string | Yes | Comma-separated parameter codes | `RH2M`, `RH2M,RH2M_MAX,RH2M_MIN`, `T2M,RH2M,PRECTOTCORR` |
| `format` | string | No | Output format | `json`, `csv`, `epw`, `ascii` (default: `json`) |
| `units` | string | No | Measurement units | `imperial`, `metric` (default: `metric`) |
| `user` | string | No | User identifier | `Drew`, `your_name` |
| `header` | boolean | No | Include header row | `true`, `false` (default: `true`) |
| `time-standard` | string | No | Time standard | `lst` (local solar time), `utc` (default: `lst`) |
| `site-elevation` | float | No | Site elevation in meters | `10`, `500`, `1000` |
| `wind-elevation` | float | No | Wind measurement elevation | `10`, `50`, `100` |
| `wind-surface` | string | No | Wind surface type | `10m`, `50m`, `100m`, `wind-surface` |

### Humidity Parameters

For humidity data, use these parameter codes:

- **`RH2M`**: Relative humidity at 2 meters (%) - most commonly used
- **`RH2M_MAX`**: Maximum relative humidity at 2 meters (%) - daily maximum
- **`RH2M_MIN`**: Minimum relative humidity at 2 meters (%) - daily minimum

**Example**: To get all humidity parameters: `parameters=RH2M,RH2M_MAX,RH2M_MIN`

## Usage Examples

### Python Script

Use the provided `get_humidity.py` script:

```bash
# Basic usage
python get_humidity.py --latitude 40.7128 --longitude -74.0060 --start 20240101 --end 20240102

# Multiple parameters
python get_humidity.py --latitude 40.7128 --longitude -74.0060 --start 20240101 --end 20240102 --parameters "RH2M,RH2M_MAX,RH2M_MIN"

# CSV output
python get_humidity.py --latitude 40.7128 --longitude -74.0060 --start 20240101 --end 20240102 --format csv --output humidity_data.csv

# Metric units
python get_humidity.py --latitude 40.7128 --longitude -74.0060 --start 20240101 --end 20240102 --units metric
```

### Direct API Call (Python)

```python
import requests

url = 'https://power.larc.nasa.gov/api/temporal/hourly/point'
params = {
    'start': '20240101',
    'end': '20240102',
    'latitude': 40.7128,
    'longitude': -74.0060,
    'community': 'ag',
    'parameters': 'RH2M',
    'format': 'json',
    'units': 'imperial',
    'user': 'Drew',
    'header': 'true',
    'time-standard': 'lst'
}
headers = {'accept': 'application/json'}

response = requests.get(url, params=params, headers=headers)
data = response.json()
```

### cURL Examples

```bash
# Basic humidity request
curl -X 'GET' \
  'https://power.larc.nasa.gov/api/temporal/hourly/point?start=20240101&end=20240102&latitude=40.7128&longitude=-74.0060&community=ag&parameters=RH2M&format=json&units=imperial&user=Drew&header=true&time-standard=lst' \
  -H 'accept: application/json'

# Multiple humidity parameters
curl -X 'GET' \
  'https://power.larc.nasa.gov/api/temporal/hourly/point?start=20240101&end=20240102&latitude=40.7128&longitude=-74.0060&community=ag&parameters=RH2M,RH2M_MAX,RH2M_MIN&format=json&units=imperial&user=Drew&header=true&time-standard=lst' \
  -H 'accept: application/json'

# CSV format output
curl -X 'GET' \
  'https://power.larc.nasa.gov/api/temporal/hourly/point?start=20240101&end=20240102&latitude=40.7128&longitude=-74.0060&community=ag&parameters=RH2M&format=csv&units=imperial&user=Drew&header=true&time-standard=lst' \
  -H 'accept: application/json' > humidity_data.csv
```

## Response Format

### JSON Response Structure

When using `format=json`, the response includes:

```json
{
  "geometry": {
    "type": "Point",
    "coordinates": [-74.0060, 40.7128]
  },
  "properties": {
    "parameter": {
      "RH2M": {
        "20240101": {
          "01": 65.0,
          "02": 64.5,
          ...
        }
      }
    },
    "header": {
      "longitude": -74.0060,
      "latitude": 40.7128,
      ...
    }
  }
}
```

### CSV Response

When using `format=csv`, the response is a comma-separated table with headers.

## Date/Time Formats

- **Daily data**: Use `YYYYMMDD` format (e.g., `20240101`)
- **Hourly data**: Use `YYYYMMDDHH` format (e.g., `2024010112` for January 1, 2024 at 12:00)

## Notes

- The API supports data from **January 1, 1981** to present
- Hourly data is available for the most recent 2 years
- Daily/monthly/annual data is available for the full period
- Maximum date range depends on temporal resolution (hourly: ~2 years, daily: full period)
- Rate limiting may apply for large requests

## Integration with Fire Prediction

Humidity data from NASA POWER can be used for:

1. **3-day consecutive dry, wet, humid index**: Calculate consecutive days of low/high humidity
2. **14-day fuel conditioning index**: Track humidity trends over 2 weeks
3. **Soft binary threshold**: Compare humidity vs temperature for ignition probability

## Resources

- [NASA POWER API Documentation](https://power.larc.nasa.gov/docs/)
- [NASA POWER Data Access Methods](https://power.larc.nasa.gov/data-access-viewer/)
- [Parameter Definitions](https://power.larc.nasa.gov/#resources)




