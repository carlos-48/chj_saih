"""
Module defining sensor classes for parsing data from the CHJ-SAIH API.

This module provides a base `Sensor` class and specific implementations for
different types of hydrological sensors like rain gauges, flow meters, etc.
It uses `SensorDataParser` to handle the common structure of the API's JSON response
and extract time-series data.
"""
from datetime import datetime
from typing import List, Tuple, Dict, Any, Union, Optional # Added Optional
import aiohttp

from chj_saih.data_fetcher import fetch_sensor_data
from .exceptions import DataParseError, APIError

RawSensorDataType = List[Union[Dict[str, Any], List[List[Any]], Dict[str, Any]]] # More precise for inner list

class SensorDataParser:
    """
    Parses the raw JSON data structure returned by the CHJ-SAIH API for sensor readings.
    The JSON is expected to be a list containing:
    1. Metadata dictionary.
    2. List of [timestamp, value] pairs.
    3. Time information dictionary.
    """
    def __init__(self, json_data: RawSensorDataType):
        """
        Initializes the parser with raw sensor data.

        Args:
            json_data: The raw data list from the API.

        Raises:
            DataParseError: If json_data is not in the expected format (e.g., not a list of 3 elements).
        """
        if not isinstance(json_data, list) or len(json_data) < 2: # Simplified check, API sometimes returns 2 elements
            raise DataParseError(f"Unexpected JSON data format. Expected a list of at least 2 elements, got {type(json_data)} with length {len(json_data) if isinstance(json_data, list) else 'N/A'}.")
        
        self.metadata: Dict[str, Any] = json_data[0] if len(json_data) > 0 and isinstance(json_data[0], dict) else {}
        self.values: List[List[Any]] = json_data[1] if len(json_data) > 1 and isinstance(json_data[1], list) else []
        self.time_info: Dict[str, Any] = json_data[2] if len(json_data) > 2 and isinstance(json_data[2], dict) else {}


    def get_date_format(self, period_grouping: str) -> str:
        """
        Determines the date string format based on the API's 'period_grouping'.

        Args:
            period_grouping: The time period grouping string from API metadata
                             (e.g., "ultimos5minutales", "ultimashoras").

        Returns:
            The strptime format string for parsing dates.
        """
        date_format_mapping: Dict[str, str] = {
            "ultimos5minutales": "%d/%m/%Y %H:%M",
            "ultimashoras": "%d/%m/%Y %H:%M",
            "ultimashorasaforo": "%d/%m/%Y %H:%M",
            "ultimodia": "%d/%m/%Y %Hh.",
            "ultimasemana": "%d/%m/%Y %Hh.",
            "ultimomes": "%d/%m/%Y",
            "ultimoanno": "%d/%m/%Y"
        }
        return date_format_mapping.get(period_grouping, "%d/%m/%Y %H:%M") # Default format

    def parse_date(self, date_str: str, date_format: str) -> datetime:
        """
        Converts a date string to a datetime object using the specified format.

        Args:
            date_str: The date string to parse.
            date_format: The strptime format string.

        Returns:
            The parsed datetime object.

        Raises:
            DataParseError: If the date string cannot be parsed with the given format.
        """
        try:
            return datetime.strptime(date_str, date_format)
        except ValueError as e:
            raise DataParseError(f"Error parsing date string '{date_str}' with format '{date_format}'. Original error: {e}") from e

    def extract_data(self, period_grouping: Optional[str] = None) -> List[Tuple[datetime, Optional[float]]]:
        """
        Extracts and transforms sensor values into a list of (datetime, value) tuples.
        Values are sorted by datetime.

        Args:
            period_grouping: The time period grouping string, used to determine date format.
                             If None, uses a default format.

        Returns:
            A list of (datetime, value) tuples. Value can be None if unparseable.
            Filters out entries where date parsing failed or value was originally None.

        Raises:
            DataParseError: Propagated from `parse_date` if date parsing fails.
        """
        # Determine date_format. If period_grouping is not available (e.g. from metadata), use a default.
        # self.metadata might be like {'paramVisual': [{'nombre': 'ultimos5minutales', ...}]}
        actual_period_grouping = period_grouping
        if not actual_period_grouping and isinstance(self.metadata, dict):
            param_visual = self.metadata.get('paramVisual')
            if isinstance(param_visual, list) and len(param_visual) > 0 and isinstance(param_visual[0], dict):
                actual_period_grouping = param_visual[0].get('nombre')

        date_format = self.get_date_format(actual_period_grouping or "ultimos5minutales") # Default if still None

        parsed_data: List[Tuple[datetime, Optional[float]]] = []
        for item in self.values:
            if isinstance(item, list) and len(item) == 2:
                date_str, value = item
                if value is not None and isinstance(date_str, str): # Ensure date_str is a string
                    try:
                        # Attempt to convert value to float, allowing for None if it fails
                        numeric_value: Optional[float] = None
                        try:
                            numeric_value = float(value)
                        except (ValueError, TypeError):
                            # If value cannot be cast to float, keep as None or handle as error
                            # For now, we'll let it be None if it's not float-castable.
                            # Depending on strictness, one might raise DataParseError here.
                            pass

                        dt = self.parse_date(date_str, date_format)
                        parsed_data.append((dt, numeric_value))
                    except DataParseError: # Propagate if date parsing fails critically
                        # Optionally log here or decide to skip the problematic entry
                        # print(f"Skipping entry due to date parse error for '{date_str}'")
                        pass # Skip this entry

        # Sort by datetime before returning
        parsed_data.sort(key=lambda x: x[0])
        return parsed_data

class Sensor:
    """
    Base class for different types of hydrological sensors.

    Attributes:
        variable (str): The variable ID for the sensor (e.g., 'U9901').
        period_grouping (str): The time period grouping for data fetching.
        num_values (int): The number of data values to fetch.
    """
    def __init__(self, variable: str, period_grouping: str, num_values: int):
        """
        Initializes a Sensor instance.

        Args:
            variable: The variable ID for the sensor.
            period_grouping: Time aggregation (e.g., "ultimos5minutales").
            num_values: Number of data values to retrieve.
        """
        self.variable = variable
        self.period_grouping = period_grouping
        self.num_values = num_values

    async def get_data(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """
        Fetches and parses sensor data.

        Args:
            session: The aiohttp client session to use for the request.

        Returns:
            A dictionary containing parsed sensor data, specific to the sensor type.

        Raises:
            APIError: If `fetch_sensor_data` encounters an API or client error.
            DataParseError: If `parse_data` (or `SensorDataParser`) fails to parse
                            the raw data due to format issues or unparseable values.
        """
        raw_data = await fetch_sensor_data(self.variable, self.period_grouping, self.num_values, session)
        if raw_data is None: # Should not happen if fetch_sensor_data raises APIError
            raise DataParseError("Received no raw data from fetch_sensor_data.")
        return self.parse_data(raw_data)

    def parse_data(self, raw_data: RawSensorDataType) -> Dict[str, Any]:
        """
        Abstract method to parse raw sensor data into a structured format.
        This method must be implemented by subclasses.

        Args:
            raw_data: The raw data list from the API.

        Returns:
            A dictionary containing the parsed data.

        Raises:
            NotImplementedError: If not implemented by a subclass.
            DataParseError: If parsing fails.
        """
        raise NotImplementedError("This method must be implemented by subclasses.")

class RainGaugeSensor(Sensor):
    """Sensor for measuring rainfall (pluviómetro)."""

    def parse_data(self, raw_data: RawSensorDataType) -> Dict[str, List[Tuple[datetime, Optional[float]]]]:
        """
        Parses raw data for a rain gauge sensor.

        Args:
            raw_data: The raw data list from the API.

        Returns:
            A dictionary with "rainfall_data": list of (datetime, rainfall_value) tuples.
            Rainfall value is in mm.

        Raises:
            DataParseError: If raw_data is malformed or values cannot be parsed.
        """
        parser = SensorDataParser(raw_data)
        # Pass period_grouping to extract_data for correct date parsing
        values = parser.extract_data(self.period_grouping)
        return {"rainfall_data": values}

class FlowSensor(Sensor):
    """Sensor for measuring river flow (aforo)."""

    def parse_data(self, raw_data: RawSensorDataType) -> Dict[str, List[Tuple[datetime, Optional[float]]]]:
        """
        Parses raw data for a flow sensor.

        Args:
            raw_data: The raw data list from the API.

        Returns:
            A dictionary with "flow_data": list of (datetime, flow_value) tuples.
            Flow value is typically in m³/s.

        Raises:
            DataParseError: If raw_data is malformed or values cannot be parsed.
        """
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        return {"flow_data": values}

class ReservoirSensor(Sensor):
    """Sensor for measuring water level or volume in a reservoir (embalse)."""

    def parse_data(self, raw_data: RawSensorDataType) -> Dict[str, List[Tuple[datetime, Optional[float]]]]:
        """
        Parses raw data for a reservoir sensor.

        Args:
            raw_data: The raw data list from the API.

        Returns:
            A dictionary with "reservoir_data": list of (datetime, reservoir_value) tuples.
            Value can be level (m) or volume (hm³), check API for specific station.

        Raises:
            DataParseError: If raw_data is malformed or values cannot be parsed.
        """
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        return {"reservoir_data": values}

class TemperatureSensor(Sensor):
    """Sensor for measuring environmental temperature."""

    def parse_data(self, raw_data: RawSensorDataType) -> Dict[str, List[Tuple[datetime, Optional[float]]]]:
        """
        Parses raw data for a temperature sensor.

        Args:
            raw_data: The raw data list from the API.

        Returns:
            A dictionary with "temperature_data": list of (datetime, temperature_value) tuples.
            Temperature value is typically in °C.

        Raises:
            DataParseError: If raw_data is malformed or values cannot be parsed.
        """
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        return {"temperature_data": values}
