"""
NASA POWER API - Weather Data Fetching Module

This package provides functions to fetch weather data from the NASA POWER API,
including humidity, temperature, wind speed, and precipitation for fire prediction.
"""

from .get_humidity import (
    fetch_nasa_power_weather,
    fetch_fire_prediction_weather,
    fetch_nasa_power_humidity  # Backward compatibility
)

__all__ = [
    'fetch_nasa_power_weather',
    'fetch_fire_prediction_weather',
    'fetch_nasa_power_humidity'
]

