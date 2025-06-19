"""
Python client for accessing hydrological data from Confederación Hidrográfica del Júcar (CHJ) SAIH.

This package provides tools to fetch:
- Lists of monitoring stations (overall, by sensor type, risk, location, or sub-basin).
- Time-series data for various hydrological sensors (rain gauges, flow meters, reservoirs, temperature).

It includes custom exceptions for error handling related to API communication and data parsing.

Main components:
- `data_fetcher.py`: Contains functions to fetch data from API endpoints.
- `sensors.py`: Defines sensor classes for parsing specific sensor data types.
- `exceptions.py`: Defines custom exception classes.
- `config.py`: Stores API base URLs.
"""

from .sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from .data_fetcher import (
    fetch_sensor_data,
    fetch_station_list,
    fetch_all_stations,
    fetch_stations_by_risk,
    fetch_station_list_by_location,
    fetch_stations_by_subcuenca
)
from .exceptions import CHJSAIHError, APIError, DataParseError, InvalidInputError

__all__ = [
    "RainGaugeSensor",
    "FlowSensor",
    "ReservoirSensor",
    "TemperatureSensor",
    "fetch_sensor_data",
    "fetch_station_list",
    "fetch_all_stations",
    "fetch_stations_by_risk",
    "fetch_station_list_by_location",
    "fetch_stations_by_subcuenca",
    "CHJSAIHError",
    "APIError",
    "DataParseError",
    "InvalidInputError"
]
