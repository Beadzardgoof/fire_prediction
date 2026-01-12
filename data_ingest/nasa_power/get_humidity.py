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
import asyncio
import aiohttp
from typing import List, Dict, Optional

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
    
    # Handle case where parameters might not be a dict (shouldn't happen, but be defensive)
    if not isinstance(parameters, dict):
        # If parameters is not a dict, return empty DataFrame
        # This can happen if NASA POWER returns an error or unexpected format
        # Also happens when requesting future dates (NASA POWER doesn't have future data)
        return pd.DataFrame()
    
    # Check if parameters dict is empty (no data available, e.g., future dates)
    if len(parameters) == 0:
        return pd.DataFrame()
    
    # Iterate through each parameter
    # NOTE: NASA POWER may return data in different formats:
    #   1. Combined date+hour keys: { "2024010100": value, "2024010101": value, ... }
    #   2. Nested hourly: { "20240101": { "00": value, "01": value, ... } }
    #   3. Daily scalar: { "20240101": value, "20240102": value, ... }
    for param_name, param_data in parameters.items():
        if not isinstance(param_data, dict):
            # Unexpected structure; skip this parameter
            continue
        
        # Check the first key to determine the format
        # NASA POWER can return:
        #   1. Combined format: {'2025122200': value, '2025122201': value, ...} (10-digit YYYYMMDDHH keys)
        #   2. Nested format: {'20251222': {'00': value, '01': value, ...}}
        #   3. Daily format: {'20251222': value, '20251223': value, ...}
        first_key = next(iter(param_data.keys())) if param_data else None
        
        # Check if keys are in combined YYYYMMDDHH format (10 digits)
        if first_key:
            first_key_str = str(first_key)
            is_combined_format = (len(first_key_str) == 10 and first_key_str.isdigit())
        else:
            is_combined_format = False
        
        if is_combined_format:
            # Format 1: Combined date+hour keys (YYYYMMDDHH format, 10 digits)
            # Example: '2025122200', '2025122201', etc.
            for datetime_str, value in param_data.items():
                try:
                    # Parse YYYYMMDDHH format directly
                    datetime_str_clean = str(datetime_str).strip()
                    if len(datetime_str_clean) == 10 and datetime_str_clean.isdigit():
                        dt = datetime.strptime(datetime_str_clean, "%Y%m%d%H")
                        records.append({
                            'datetime': dt,
                            'parameter': param_name,
                            'value': value
                        })
                except (ValueError, TypeError):
                    # Skip invalid datetime or value
                    continue
        else:
            # Format 2 or 3: Nested or daily structure
            # Iterate through dates
            for date_str, daily_or_hourly in param_data.items():
                # If we get a dict, assume nested hourly values
                if isinstance(daily_or_hourly, dict):
                    for hour_str, value in daily_or_hourly.items():
                        # Create datetime from date and hour
                        try:
                            dt_str = f"{date_str}{str(hour_str).zfill(2)}"
                            dt = datetime.strptime(dt_str, "%Y%m%d%H")
                            records.append({
                                'datetime': dt,
                                'parameter': param_name,
                                'value': value
                            })
                        except (ValueError, TypeError):
                            # Skip invalid datetime or value
                            continue
                else:
                    # Scalar daily value: treat as daily at 00:00
                    try:
                        dt_str = f"{date_str}00"
                        dt = datetime.strptime(dt_str, "%Y%m%d%H")
                        records.append({
                            'datetime': dt,
                            'parameter': param_name,
                            'value': daily_or_hourly
                        })
                    except (ValueError, TypeError):
                        # If date format is unexpected, skip this entry
                        continue
    
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
    return_dataframe=True,
    temporal='daily'
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
    
    # Base API URL - use daily for efficiency (24x less data than hourly)
    base_url = f'https://power.larc.nasa.gov/api/temporal/{temporal}/point'
    
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
    
    # Make API request with retry logic
    headers = {
        'accept': 'application/json'
    }
    
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
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
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                import time
                print(f"  Timeout on attempt {attempt + 1}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Error: NASA POWER API timeout after {max_retries} attempts")
                return pd.DataFrame()  # Return empty DataFrame instead of raising
                
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                import time
                print(f"  Connection error on attempt {attempt + 1}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Error: NASA POWER API connection failed after {max_retries} attempts: {e}")
                return pd.DataFrame()
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from NASA POWER API: {e}")
            return pd.DataFrame()  # Return empty DataFrame to continue processing
    
    return pd.DataFrame()


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
    # Include min/max values for better feature engineering
    fire_params = 'RH2M,RH2M_MAX,RH2M_MIN,PRECTOT,WS10M,WS10M_MAX,T2M,T2M_MAX,T2M_MIN,PS'
    
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


async def fetch_fire_prediction_weather_async(
    session: aiohttp.ClientSession,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    community: str = 'ag',
    units: str = 'metric',
    temporal: str = 'daily',
    api_key: Optional[str] = None
) -> Dict:
    """
    Async version of fetch_fire_prediction_weather for concurrent requests.
    
    Parameters:
    -----------
    session : aiohttp.ClientSession
        Active aiohttp session for making requests
    latitude : float
        Latitude of the location
    longitude : float
        Longitude of the location
    start_date : str
        Start date in YYYYMMDD format
    end_date : str
        End date in YYYYMMDD format
    community : str
        Data community (default: 'ag')
    units : str
        Units system (default: 'metric')
    temporal : str
        Temporal resolution: 'daily' or 'hourly' (default: 'daily')
    api_key : str, optional
        NASA API key (if not provided, uses environment variable)
        
    Returns:
    --------
    dict
        Dictionary with weather data or error info
    """
    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.getenv('NASA_POWER_API_KEY')
    
    # Build URL and parameters
    base_url = f'https://power.larc.nasa.gov/api/temporal/{temporal}/point'
    fire_params = 'RH2M,RH2M_MAX,RH2M_MIN,PRECTOT,WS10M,WS10M_MAX,T2M,T2M_MAX,T2M_MIN,PS'
    
    params = {
        'start': start_date,
        'end': end_date,
        'latitude': latitude,
        'longitude': longitude,
        'community': community,
        'parameters': fire_params,
        'format': 'json',
        'units': units,
        'header': 'true',
        'time-standard': 'lst'
    }
    
    if api_key:
        params['key'] = api_key
    
    # Make async request with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.get(base_url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    json_data = await response.json()
                    df = _parse_nasa_power_json(json_data)
                    return {
                        'success': True,
                        'latitude': latitude,
                        'longitude': longitude,
                        'data': df
                    }
                elif response.status == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    else:
                        return {
                            'success': False,
                            'latitude': latitude,
                            'longitude': longitude,
                            'error': 'Rate limit exceeded'
                        }
                else:
                    return {
                        'success': False,
                        'latitude': latitude,
                        'longitude': longitude,
                        'error': f'HTTP {response.status}'
                    }
                    
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                return {
                    'success': False,
                    'latitude': latitude,
                    'longitude': longitude,
                    'error': 'Timeout'
                }
        except Exception as e:
            return {
                'success': False,
                'latitude': latitude,
                'longitude': longitude,
                'error': str(e)
            }
    
    return {
        'success': False,
        'latitude': latitude,
        'longitude': longitude,
        'error': 'Max retries exceeded'
    }


async def fetch_fire_prediction_weather_batch(
    locations: List[Dict],
    start_dates: List[str],
    end_dates: List[str],
    max_concurrent: int = 5,
    units: str = 'metric',
    temporal: str = 'daily'
) -> List[Dict]:
    """
    Fetch weather data for multiple locations concurrently.
    
    Parameters:
    -----------
    locations : List[Dict]
        List of location dicts with 'latitude', 'longitude', and optional 'fire_index'
    start_dates : List[str]
        List of start dates (one per location)
    end_dates : List[str]
        List of end dates (one per location)
    max_concurrent : int
        Maximum number of concurrent requests (default: 5)
    units : str
        Units system (default: 'metric')
    temporal : str
        Temporal resolution: 'daily' or 'hourly' (default: 'daily')
        
    Returns:
    --------
    List[Dict]
        List of result dictionaries
    """
    api_key = os.getenv('NASA_POWER_API_KEY')
    
    async with aiohttp.ClientSession() as session:
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(loc, start, end):
            async with semaphore:
                result = await fetch_fire_prediction_weather_async(
                    session=session,
                    latitude=loc['latitude'],
                    longitude=loc['longitude'],
                    start_date=start,
                    end_date=end,
                    units=units,
                    temporal=temporal,
                    api_key=api_key
                )
                # Add fire_index if provided
                if 'fire_index' in loc:
                    result['fire_index'] = loc['fire_index']
                return result
        
        # Create tasks
        tasks = [
            fetch_with_semaphore(loc, start, end)
            for loc, start, end in zip(locations, start_dates, end_dates)
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)
        
    return results


def fetch_fire_prediction_weather_batch_sync(
    locations: List[Dict],
    start_dates: List[str],
    end_dates: List[str],
    max_concurrent: int = 5,
    units: str = 'metric',
    temporal: str = 'daily'
) -> List[Dict]:
    """
    Synchronous wrapper for batch fetching weather data concurrently.
    
    This is the main function to use in notebooks/scripts for concurrent fetching.
    
    Parameters:
    -----------
    locations : List[Dict]
        List of location dicts with 'latitude', 'longitude', and optional 'fire_index'
    start_dates : List[str]
        List of start dates (one per location)
    end_dates : List[str]
        List of end dates (one per location)
    max_concurrent : int
        Maximum number of concurrent requests (default: 5)
    units : str
        Units system (default: 'metric')
    temporal : str
        Temporal resolution: 'daily' or 'hourly' (default: 'daily')
        
    Returns:
    --------
    List[Dict]
        List of result dictionaries with weather data
        
    Examples:
    ---------
    >>> locations = [
    ...     {'latitude': 40.0, 'longitude': -100.0, 'fire_index': 0},
    ...     {'latitude': 41.0, 'longitude': -101.0, 'fire_index': 1}
    ... ]
    >>> start_dates = ['20250101', '20250101']
    >>> end_dates = ['20250114', '20250114']
    >>> results = fetch_fire_prediction_weather_batch_sync(locations, start_dates, end_dates)
    >>> for r in results:
    ...     if r['success']:
    ...         print(f"Fire {r['fire_index']}: {len(r['data'])} days of data")
    """
    # Check if we're already in an event loop (e.g., Jupyter with IPython)
    try:
        loop = asyncio.get_running_loop()
        # We're in an existing event loop, use nest_asyncio if available
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(fetch_fire_prediction_weather_batch(
                locations, start_dates, end_dates, max_concurrent, units, temporal
            ))
        except ImportError:
            # nest_asyncio not available, fall back to creating tasks
            return loop.run_until_complete(fetch_fire_prediction_weather_batch(
                locations, start_dates, end_dates, max_concurrent, units, temporal
            ))
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        return asyncio.run(fetch_fire_prediction_weather_batch(
            locations, start_dates, end_dates, max_concurrent, units, temporal
        ))


# Backward compatibility alias
fetch_nasa_power_humidity = fetch_nasa_power_weather

