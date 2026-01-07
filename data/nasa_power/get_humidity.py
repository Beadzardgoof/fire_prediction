"""
NASA POWER API - Weather Data Fetching

This module provides functions to fetch weather data from the NASA POWER API
for use in Jupyter notebooks. NASA POWER provides meteorological data including
humidity, temperature, wind speed, and precipitation measurements.

Available Parameters:
- RH2M: Relative Humidity at 2 Meters (%)
- RH2M_MAX: Maximum Relative Humidity at 2 Meters (%)
- RH2M_MIN: Minimum Relative Humidity at 2 Meters (%)
- T2M: Temperature at 2 Meters (°C or °F)
- PRECTOT: Precipitation (mm or inches)
- PRECTOTCORR: Corrected Precipitation (mm or inches)
- WS10M: Wind Speed at 10 Meters (m/s or mph)
- WS50M: Wind Speed at 50 Meters (m/s or mph)

Example usage in Jupyter notebook:
    from data.nasa_power.get_humidity import fetch_nasa_power_weather, fetch_fire_prediction_weather
    
    # Fetch all weather data for fire prediction
    df = fetch_fire_prediction_weather(
        latitude=40.7128,
        longitude=-74.0060,
        start_date='20240101',
        end_date='20240114'
    )
    
    # Or fetch specific parameters
    df = fetch_nasa_power_weather(
        latitude=40.7128,
        longitude=-74.0060,
        start_date='20240101',
        end_date='20240102',
        parameters='RH2M,T2M,PRECTOT,WS10M'
    )
"""

import os
import requests
import pandas as pd
from datetime import datetime
from io import StringIO

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use environment variables directly


def _parse_nasa_power_json(response_json):
    """
    Parse NASA POWER API JSON response into a pandas DataFrame.
    
    Parameters:
    -----------
    response_json : dict
        JSON response from NASA POWER API
        
    Returns:
    --------
    pandas.DataFrame
        DataFrame with datetime index and parameter columns
    """
    if 'properties' not in response_json or 'parameter' not in response_json['properties']:
        raise ValueError("Invalid NASA POWER API response format")
    
    # Extract parameter data
    parameters = response_json['properties']['parameter']
    
    # Extract header information
    header = response_json.get('properties', {}).get('header', {})
    
    # Build list of records
    records = []
    
    # Iterate through each parameter
    for param_name, param_data in parameters.items():
        # Iterate through dates
        for date_str, hourly_data in param_data.items():
            # Iterate through hours
            for hour_str, value in hourly_data.items():
                # Create datetime from date and hour
                dt_str = f"{date_str}{hour_str.zfill(2)}"
                dt = datetime.strptime(dt_str, "%Y%m%d%H")
                
                records.append({
                    'datetime': dt,
                    'parameter': param_name,
                    'value': value
                })
    
    # Create DataFrame
    df = pd.DataFrame(records)
    
    if df.empty:
        return df
    
    # Pivot to have parameters as columns
    df_pivot = df.pivot(index='datetime', columns='parameter', values='value')
    df_pivot.reset_index(inplace=True)
    
    # Add location metadata
    df_pivot['latitude'] = header.get('latitude')
    df_pivot['longitude'] = header.get('longitude')
    
    return df_pivot


def fetch_nasa_power_weather(
    latitude,
    longitude,
    start_date,
    end_date,
    community='ag',
    parameters='RH2M',
    output_format='json',
    units='imperial',
    user='Drew',
    header=True,
    time_standard='lst',
    site_elevation=None,
    wind_elevation=None,
    wind_surface=None,
    return_dataframe=True
):
    """
    Fetch weather data from NASA POWER API.
    
    Parameters:
    -----------
    latitude : float
        Latitude of the location (-90 to 90)
    longitude : float
        Longitude of the location (-180 to 180)
    start_date : str
        Start date in format YYYYMMDD or YYYYMMDDHH
    end_date : str
        End date in format YYYYMMDD or YYYYMMDDHH
    community : str, optional
        Data community (default: 'ag' for agriculture)
    parameters : str, optional
        Comma-separated list of parameters (default: 'RH2M' for relative humidity at 2m)
        Available parameters:
        - Humidity: RH2M, RH2M_MAX, RH2M_MIN
        - Temperature: T2M
        - Precipitation: PRECTOT, PRECTOTCORR
        - Wind: WS10M, WS50M
    output_format : str, optional
        Output format: 'json', 'csv', 'epw', or 'ascii' (default: 'json')
    units : str, optional
        Units: 'imperial' or 'metric' (default: 'imperial')
    user : str, optional
        User identifier (default: 'Drew')
    header : bool, optional
        Include header row (default: True)
    time_standard : str, optional
        Time standard: 'lst' (local solar time) or 'utc' (default: 'lst')
    site_elevation : float, optional
        Site elevation in meters
    wind_elevation : float, optional
        Wind measurement elevation in meters
    wind_surface : str, optional
        Wind surface type
    return_dataframe : bool, optional
        If True and output_format='json', return a pandas DataFrame instead of raw JSON (default: True)
    
    Returns:
    --------
    pandas.DataFrame or dict or str
        - If output_format='json' and return_dataframe=True: pandas.DataFrame with datetime index
        - If output_format='json' and return_dataframe=False: dict with raw JSON response
        - If output_format='csv': pandas.DataFrame
        - Otherwise: str with response text
        
    Examples:
    --------
    >>> # Basic usage - returns DataFrame with humidity
    >>> df = fetch_nasa_power_weather(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     start_date='20240101',
    ...     end_date='20240102'
    ... )
    >>> 
    >>> # Multiple weather parameters
    >>> df = fetch_nasa_power_weather(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     start_date='20240101',
    ...     end_date='20240102',
    ...     parameters='RH2M,T2M,PRECTOT,WS10M'
    ... )
    >>> 
    >>> # Get raw JSON response
    >>> data = fetch_nasa_power_weather(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     start_date='20240101',
    ...     end_date='20240102',
    ...     return_dataframe=False
    ... )
    """
    
    # Base API URL
    base_url = 'https://power.larc.nasa.gov/api/temporal/hourly/point'
    
    # Build query parameters
    params = {
        'start': start_date,
        'end': end_date,
        'latitude': latitude,
        'longitude': longitude,
        'community': community,
        'parameters': parameters,
        'format': output_format,
        'units': units,
        'user': user,
        'header': str(header).lower(),
        'time-standard': time_standard
    }
    
    # Add optional parameters if provided
    if site_elevation is not None:
        params['site-elevation'] = site_elevation
    if wind_elevation is not None:
        params['wind-elevation'] = wind_elevation
    if wind_surface is not None:
        params['wind-surface'] = wind_surface
    
    # Get API key from environment variable
    api_key = os.getenv('NASA_POWER_API_KEY')
    
    # Add API key to query parameters if available
    if api_key:
        params['key'] = api_key
    
    # Make API request
    headers = {
        'accept': 'application/json'
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        if output_format == 'json':
            json_data = response.json()
            if return_dataframe:
                return _parse_nasa_power_json(json_data)
            else:
                return json_data
        elif output_format == 'csv':
            # Parse CSV response
            return pd.read_csv(StringIO(response.text))
        else:
            return response.text
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from NASA POWER API: {e}")
        raise


def fetch_fire_prediction_weather(
    latitude,
    longitude,
    start_date,
    end_date,
    community='ag',
    output_format='json',
    units='imperial',
    user='Drew',
    header=True,
    time_standard='lst',
    site_elevation=None,
    wind_elevation=None,
    wind_surface=None,
    return_dataframe=True
):
    """
    Fetch all weather data needed for fire prediction features from NASA POWER API.
    
    This function fetches the following parameters required for fire prediction:
    - RH2M: Relative Humidity (for 3-day humid index, 14-day fuel conditioning, soft binary threshold)
    - PRECTOT: Precipitation (for 3-day dry/wet index, 14-day fuel conditioning, weighted extremes)
    - WS10M: Wind Speed (for weighted weather extremes over 12h)
    - T2M: Temperature (for soft binary threshold with humidity)
    
    Parameters:
    -----------
    latitude : float
        Latitude of the location (-90 to 90)
    longitude : float
        Longitude of the location (-180 to 180)
    start_date : str
        Start date in format YYYYMMDD or YYYYMMDDHH
    end_date : str
        End date in format YYYYMMDD or YYYYMMDDHH
        Note: For 14-day fuel conditioning index, ensure at least 14 days of data
    community : str, optional
        Data community (default: 'ag' for agriculture)
    output_format : str, optional
        Output format: 'json', 'csv', 'epw', or 'ascii' (default: 'json')
    units : str, optional
        Units: 'imperial' or 'metric' (default: 'imperial')
    user : str, optional
        User identifier (default: 'Drew')
    header : bool, optional
        Include header row (default: True)
    time_standard : str, optional
        Time standard: 'lst' (local solar time) or 'utc' (default: 'lst')
    site_elevation : float, optional
        Site elevation in meters
    wind_elevation : float, optional
        Wind measurement elevation in meters
    wind_surface : str, optional
        Wind surface type
    return_dataframe : bool, optional
        If True and output_format='json', return a pandas DataFrame instead of raw JSON (default: True)
    
    Returns:
    --------
    pandas.DataFrame or dict or str
        DataFrame or response containing:
        - datetime: Timestamp for each measurement
        - RH2M: Relative Humidity at 2 Meters (%)
        - PRECTOT: Precipitation (mm or inches)
        - WS10M: Wind Speed at 10 Meters (m/s or mph)
        - T2M: Temperature at 2 Meters (°C or °F)
        - latitude: Location latitude
        - longitude: Location longitude
        
    Examples:
    --------
    >>> # Fetch weather data for fire prediction (14 days for fuel conditioning)
    >>> df = fetch_fire_prediction_weather(
    ...     latitude=40.7128,
    ...     longitude=-74.0060,
    ...     start_date='20240101',
    ...     end_date='20240114'
    ... )
    >>> 
    >>> # Calculate 3-day consecutive dry/wet/humid index
    >>> # Calculate 14-day fuel conditioning index
    >>> # Calculate weighted weather extremes (wind, rain) over 12h
    >>> # Calculate soft binary threshold (humidity/wetness vs temperature)
    """
    # Parameters needed for all fire prediction features
    fire_params = 'RH2M,PRECTOT,WS10M,T2M'
    
    return fetch_nasa_power_weather(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        community=community,
        parameters=fire_params,
        output_format=output_format,
        units=units,
        user=user,
        header=header,
        time_standard=time_standard,
        site_elevation=site_elevation,
        wind_elevation=wind_elevation,
        wind_surface=wind_surface,
        return_dataframe=return_dataframe
    )


# Backward compatibility alias
fetch_nasa_power_humidity = fetch_nasa_power_weather

