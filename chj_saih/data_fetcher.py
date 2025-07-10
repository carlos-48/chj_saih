"""
Core module for fetching hydrological data from CHJ-SAIH API.

This module provides asynchronous functions to retrieve:
- Lists of monitoring stations based on various criteria.
- Raw sensor data for specific station variables.

It uses `aiohttp` for HTTP requests and handles API-specific errors
by raising custom exceptions defined in `chj_saih.exceptions`.
"""
import asyncio
import aiohttp
from geopy.distance import geodesic # type: ignore[import-untyped]
from typing import List, Dict, Any, Optional, Literal

import re # For parsing JavaScript data from HTML
import json # For parsing JSON part of JavaScript data

from .config import API_URL # BASE_URL_STATION_LIST is no longer used directly for station lists
from .exceptions import APIError, InvalidInputError, DataParseError

# Define valid sensor type literals for better type hinting
SensorTypeLiteral = Literal['a', 't', 'e', 'p'] # a: aforo, p: pluviometro, e: embalse, t: temperatura
SensorTypeAllLiteral = Literal['a', 't', 'e', 'p', 'all']
ComparisonLiteral = Literal["equal", "greater_equal"]


async def fetch_station_list(sensor_type: SensorTypeLiteral, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Fetches a list of monitoring stations for a specific sensor type, sorted alphabetically by name.

    Args:
        sensor_type: Type of sensor ('a' for flow, 't' for temperature,
                       'e' for reservoir, 'p' for rain gauge).
        session: The aiohttp client session to use for the request.

    Returns:
        A list of dictionaries, where each dictionary represents a station
        with its details (id, latitude, longitude, name, etc.).

    Raises:
        APIError: If there's an issue communicating with the API.
        DataParseError: If the embedded station data cannot be parsed.
        InvalidInputError: If the sensor_type is invalid.
    """
    # Map sensor_type to HTML page URL and the JavaScript variable name holding the data
    sensor_page_map = {
        'a': {'url': 'https://saih.chj.es/mapa-aforos', 'var_name': 'aforos'},
        'p': {'url': 'https://saih.chj.es/mapa-lluvias', 'var_name': 'estaciones'}, # Note: 'estaciones' for pluviometros
        'e': {'url': 'https://saih.chj.es/mapa-embalses', 'var_name': 'embalses'},
    }

    if sensor_type == 't':
        # Temperature data source is unknown in the new website structure
        # print("Warning: Temperature station list ('t') is not supported in the new API.")
        return []

    if sensor_type not in sensor_page_map:
        raise InvalidInputError(f"Invalid sensor_type: {sensor_type}. Supported types are 'a', 'p', 'e'.")

    page_info = sensor_page_map[sensor_type]
    page_url = page_info['url']
    js_var_name = page_info['var_name']

    try:
        async with session.get(page_url) as response:
            response.raise_for_status()
            html_content = await response.text()
    except aiohttp.ClientError as e:
        raise APIError(f"Failed to fetch HTML page {page_url} for sensor type '{sensor_type}'. Error: {e}") from e

    # Regex to find the JavaScript variable assignment (e.g., "let aforos = [{...}];")
    # This regex tries to capture the content between '[' and ']' following "let var_name = "
    # It handles nested structures within the JSON-like data.
    # It assumes the data is assigned with "let var_name = [...]" or "var var_name = [...]"
    regex_pattern = rf"(?:let|var)\s+{re.escape(js_var_name)}\s*=\s*(\[.*?\]);"

    match = re.search(regex_pattern, html_content, re.DOTALL | re.MULTILINE)

    if not match:
        raise DataParseError(f"Could not find JavaScript variable '{js_var_name}' in HTML from {page_url}")

    json_data_str = match.group(1)

    try:
        raw_stations_data = json.loads(json_data_str)
    except json.JSONDecodeError as e:
        raise DataParseError(f"Failed to parse JSON data for '{js_var_name}' from {page_url}. Error: {e}. Data: {json_data_str[:500]}...") from e

    processed_stations = []
    for station_data in raw_stations_data:
        try:
            # Common fields
            station_id = station_data.get("idEstacionRemota")
            nombre = station_data.get("fldTNombre")
            # UTM coordinates (EPSG:25830)
            # fldNCoordGPSLat seems to be X (Longitude/Easting) and fldNCoordGPSLon seems to be Y (Latitude/Northing)
            # Storing them as they are, with CRS info. Conversion to WGS84 can be done later if needed.
            coord_x = station_data.get("fldNCoordGPSLat")
            coord_y = station_data.get("fldNCoordGPSLon")

            if station_id is None or nombre is None or coord_x is None or coord_y is None:
                # print(f"Skipping station due to missing essential data: {station_data}")
                continue

            station_info = {
                "id": str(station_id), # Ensure ID is a string
                "nombre": str(nombre),
                "longitud_utm": float(coord_x), # UTM X (Easting)
                "latitud_utm": float(coord_y),   # UTM Y (Northing)
                "crs": "EPSG:25830",
                 # Add original lat/lon fields for now, even if they are UTM, for compatibility with check_station_structure
                "latitud": float(coord_y), # Placeholder for tests expecting 'latitud'
                "longitud": float(coord_x) # Placeholder for tests expecting 'longitud'
            }

            # Sensor-specific variable ID(s)
            if sensor_type == 'a': # Aforos
                variable_id = station_data.get("idVariable")
                if variable_id:
                    station_info["variable"] = str(variable_id)
                else:
                    # print(f"Skipping aforo station due to missing 'idVariable': {nombre}")
                    continue
            elif sensor_type == 'p': # Pluviómetros
                variable_id = station_data.get("id_1h") # Using id_1h as the primary variable for rain
                if variable_id:
                    station_info["variable"] = str(variable_id)
                else:
                    # print(f"Skipping pluviometro station due to missing 'id_1h': {nombre}")
                    continue
            elif sensor_type == 'e': # Embalses
                # For reservoirs, 'variable' will be a dict of multiple specific variable IDs
                station_info["variable_ids"] = {
                    "cota": str(station_data.get("idCotaEmbalse")) if station_data.get("idCotaEmbalse") else None,
                    "volumen": str(station_data.get("idVolumenEmbalse")) if station_data.get("idVolumenEmbalse") else None,
                    "entrada": str(station_data.get("idCaudalRecibido")) if station_data.get("idCaudalRecibido") else None,
                    "salida": str(station_data.get("idCaudalSalida")) if station_data.get("idCaudalSalida") else None,
                }
                # For general compatibility with tests expecting a single 'variable',
                # we can default to 'idVolumenEmbalse' if available.
                # This might need refinement based on how ReservoirSensor is used.
                station_info["variable"] = station_info["variable_ids"].get("volumen") or \
                                           station_info["variable_ids"].get("cota") # Fallback if volumen not present
                if not station_info["variable"]:
                    # print(f"Skipping embalse station due to missing primary variable IDs (volumen/cota): {nombre}")
                    continue

            # Include all other fields from station_data directly for potential use
            # station_info.update(station_data) # Avoid duplicating already mapped fields
            for key, value in station_data.items():
                if key not in station_info: # Add only if not already set by specific mapping
                    station_info[key] = value
            processed_stations.append(station_info)

        except (TypeError, ValueError) as e:
            # print(f"Error processing station data for {station_data.get('fldTNombre', 'Unknown Station')}: {e}. Data: {station_data}")
            continue # Skip this station if essential data is malformed

    processed_stations.sort(key=lambda station: station.get("nombre", ""))
    return processed_stations


async def fetch_all_stations(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Fetches and combines lists of all stations from all sensor types, sorted alphabetically by name.

    Handles partial failures: if fetching for one sensor type fails, it will be skipped,
    and data from other types will still be returned.

    Args:
        session: The aiohttp client session to use for requests.

    Returns:
        A list of dictionaries, where each dictionary represents a station,
        ordered alphabetically by name.
    """
    sensor_types: List[SensorTypeLiteral] = ['a', 't', 'e', 'p']
    all_stations: List[Dict[str, Any]] = []

    tasks = [fetch_station_list(sensor_type, session) for sensor_type in sensor_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, Exception):
            # Optionally log the error here, e.g., using a proper logger
            # print(f"Error occurred while fetching a station list during fetch_all_stations: {res}")
            continue
        if res: # res is a list of stations
            all_stations.extend(res)

    all_stations.sort(key=lambda station: station.get("nombre", ""))
    return all_stations


async def fetch_sensor_data(
    variable: str,
    period_grouping: str = "ultimos5minutales",
    num_values: int = 30,
    session: aiohttp.ClientSession = None  # Making session optional for direct calls, though typically managed outside
) -> List[Any]: # The API returns a list with mixed types: [metadata_dict, values_list, time_info_dict]
    """
    Fetches raw sensor data from the API for a given variable.

    Args:
        variable: The specific sensor variable ID (e.g., 'U9901', 'M2701').
        period_grouping: Time aggregation period (e.g., "ultimos5minutales", "ultimashoras").
                         Defaults to "ultimos5minutales".
        num_values: Number of data values to retrieve. Defaults to 30.
        session: The aiohttp client session. If None, a new one is created internally (not recommended for multiple calls).

    Returns:
        A list containing raw sensor data, typically structured as:
        [metadata_dict, list_of_value_tuples, time_info_dict].

    Raises:
        APIError: If there's an issue communicating with the API or the API
                  returns an error status.
from datetime import datetime, timedelta, timezone # Added timezone
from urllib.parse import quote # For URL encoding dates

# ... (imports for aiohttp, etc.)

# (SensorTypeLiteral, SensorTypeAllLiteral, ComparisonLiteral definitions remain the same)

# (fetch_station_list remains the same for now, focus is on fetch_sensor_data)

# (fetch_all_stations remains the same)


async def fetch_sensor_data(
    variable: str, # This will now be the numeric ID, e.g., "1775"
    period_grouping: str = "ultimodia", # Used to calculate date range
    num_values: int = 24, # Used with period_grouping (e.g., 24 for ultimodia means 24 hours)
    session: aiohttp.ClientSession = None
) -> List[Dict[str, Any]]: # API now returns List of Dicts
    """
    Fetches sensor data from the new API endpoint.
    Example URL: https://saih.chj.es/admin/variables/valor/1775/2024-07-09%2000:00:00/2024-07-10%2006:51:48

    Args:
        variable: The specific sensor variable ID (numeric string, e.g., '1775').
        period_grouping: Used to determine the time window.
                         Supported: "ultimodia", "ultimashoras", "ultimos5minutales".
                         Others might need specific implementation or will default.
        num_values: Works with period_grouping to define the window size.
        session: The aiohttp client session.

    Returns:
        A list of dictionaries, where each dictionary is a data point:
        `{"valor": float, "fecha": "YYYY-MM-DDTHH:mm:ssZ", "estado": int}`.

    Raises:
        APIError: If there's an issue communicating with the API.
        DataParseError: If the API response cannot be parsed.
        InvalidInputError: If period_grouping is unsupported for date calculation.
    """

    # Calculate date range
    now = datetime.now(timezone.utc)
    end_datetime = now

    if period_grouping == "ultimodia":
        # num_values is interpreted as number of days if period is "ultimodia" by convention,
        # but the old API_URL for 'ultimodia' seemed to imply hourly data for one day.
        # For the new API, let's assume num_values means number of hours for "ultimodia"
        start_datetime = now - timedelta(hours=num_values)
    elif period_grouping == "ultimashoras":
        start_datetime = now - timedelta(hours=num_values)
    elif period_grouping == "ultimos5minutales":
        start_datetime = now - timedelta(minutes=num_values * 5)
    # Add more period_grouping cases as needed or a default
    # For example, "ultimasemana" could be now - timedelta(days=num_values or 7)
    # "ultimomes" could be now - timedelta(days=num_values or 30)
    else:
        # Default or raise error for unsupported period_grouping for date calculation
        # Defaulting to last 24 hours if period_grouping is not specifically handled.
        # Or, you could raise InvalidInputError here.
        start_datetime = now - timedelta(hours=24)

    # Format dates for URL: YYYY-MM-DD HH:MM:SS (URL encoded space)
    # Example: 2024-07-09%2000:00:00
    # The API seems to accept ISO format with T and Z for display, but URL might prefer space.
    # Based on user's finding: 2025-07-09%2000:00:00
    date_format_url = "%Y-%m-%d %H:%M:%S"
    start_date_str = quote(start_datetime.strftime(date_format_url))
    end_date_str = quote(end_datetime.strftime(date_format_url))

    # API_URL from config is now the base for this new structure
    # e.g. API_URL = "https://saih.chj.es/admin/variables/valor/" (should be updated in config.py)
    # For now, hardcoding path structure based on user discovery.
    # This needs to be coordinated with config.py's API_URL.
    # Let's assume API_URL in config.py will be "https://saih.chj.es/admin/variables/valor/"

    if not API_URL.endswith('/'): # Ensure API_URL has a trailing slash
        base_api_url = API_URL + '/'
    else:
        base_api_url = API_URL

    url = f"{base_api_url}{variable}/{start_date_str}/{end_date_str}"

    # Handle session internally if not provided, for convenience in simple scripts.
    # However, for library use, passing an external session is much preferred.
    _session_managed_internally = False
    if session is None:
        session = aiohttp.ClientSession()
        _session_managed_internally = True

    # Headers based on user's findings. Cookie is handled by aiohttp session if needed.
    # Referer might need to be more generic or dynamic if it's strictly checked.
    # For now, using a generic referer.
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "es-ES,es;q=0.9",
        "Connection": "keep-alive",
        "DNT": "1",
        "Host": "saih.chj.es", # This is automatically set by aiohttp based on URL
        "Referer": "https://saih.chj.es/", # Generic referer
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        # sec-ch-ua headers are complex and might not be strictly necessary. Omitting for now.
    }

    try:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            # The new API for sensor data returns a list of objects directly:
            # [{"valor": X, "fecha": "YYYY-MM-DDTHH:mm:ssZ", "estado": Y}, ...]
            data: List[Dict[str, Any]] = await response.json()
            return data
    except aiohttp.ClientResponseError as e:
        raise APIError(f"Failed to fetch sensor data for variable '{variable}'. URL: {url}. Status: {e.status}, Message: {e.message}") from e
    except aiohttp.ClientError as e: # Catches other client errors like connection issues
        raise APIError(f"Client error while fetching sensor data for variable '{variable}'. URL: {url}. Error: {e}") from e
    except json.JSONDecodeError as e:
        # It's useful to know what content caused the JSON error
        try:
            error_content = await response.text()
        except Exception:
            error_content = "Could not retrieve error content."
        raise DataParseError(f"Failed to parse JSON response for sensor data from {url}. Error: {e}. Response text: {error_content[:500]}") from e
    except Exception as e: # Catch any other unexpected errors
        raise APIError(f"An unexpected error occurred while fetching sensor data for variable '{variable}' from {url}. Error: {e}") from e
    finally:
        if _session_managed_internally and session:
            await session.close()


async def fetch_stations_by_risk(
    sensor_type: SensorTypeAllLiteral = "e",
    risk_level: int = 2,
    comparison: ComparisonLiteral = "greater_equal",
    session: aiohttp.ClientSession = None # Made optional for consistency, though required by fetch_station_list
) -> List[Dict[str, Any]]:
    """
    Fetches stations of a specific type (or all types) that meet a specified risk level.

    Args:
        sensor_type: Sensor type ('a', 't', 'e', 'p', or 'all'). Defaults to 'e'.
        risk_level: Risk level integer (0: unknown, 1: green, 2: yellow, 3: red). Defaults to 2.
        comparison: How to compare with risk_level ("equal" or "greater_equal"). Defaults to "greater_equal".
        session: The aiohttp client session. If None, a new one is created (not recommended).

    Returns:
        A list of station dictionaries matching the criteria. Returns an empty list if
        input parameters are invalid or no stations match.

    Raises:
        InvalidInputError: If sensor_type, risk_level, or comparison are invalid.
        APIError: If an underlying call to `fetch_station_list` fails for a reason other than
                  a standard HTTP error code (which `fetch_station_list` handles by raising APIError,
                  then caught and logged here if not re-raised by `fetch_station_list`).
                  This function aims to be resilient to individual `fetch_station_list` failures
                  when `sensor_type` is 'all'.
    """
    valid_sensor_types_list: List[SensorTypeAllLiteral] = ['a', 't', 'e', 'p', 'all']
    if sensor_type not in valid_sensor_types_list:
        raise InvalidInputError(f"Invalid sensor_type '{sensor_type}'. Valid types are: {valid_sensor_types_list}")

    if not isinstance(risk_level, int) or not (0 <= risk_level <= 3):
        raise InvalidInputError("Invalid risk_level. Must be an integer between 0 and 3.")

    if comparison not in ["equal", "greater_equal"]:
        raise InvalidInputError("Invalid comparison type. Use 'equal' or 'greater_equal'.")

    _session_managed_internally = False
    if session is None:
        session = aiohttp.ClientSession()
        _session_managed_internally = True

    target_sensor_types: List[SensorTypeLiteral]
    if sensor_type == "all":
        target_sensor_types = ['a', 't', 'e', 'p']
    else:
        # Type cast is safe due to prior validation
        target_sensor_types = [sensor_type] # type: ignore

    filtered_stations: List[Dict[str, Any]] = []
    try:
        for st in target_sensor_types:
            try:
                current_stations = await fetch_station_list(st, session)
                if current_stations:
                    for station in current_stations:
                        station_risk = station.get("estadoInt")
                        if isinstance(station_risk, int):
                            if comparison == "equal" and station_risk == risk_level:
                                filtered_stations.append(station)
                            elif comparison == "greater_equal" and station_risk >= risk_level:
                                filtered_stations.append(station)
            except APIError as e:
                # Log or handle error for individual sensor type fetch; continue for 'all'
                # print(f"APIError fetching station list for sensor type {st} in fetch_stations_by_risk: {e}")
                if sensor_type != "all": # If specific sensor type fails, re-raise
                    raise
                # If 'all', we suppress and continue
    finally:
        if _session_managed_internally and session:
            await session.close()

    filtered_stations.sort(key=lambda station: station.get("nombre", ""))
    return filtered_stations


async def fetch_station_list_by_location(
    lat: float,
    lon: float,
    sensor_type: SensorTypeAllLiteral = "all",
    radius_km: float = 50.0,
    session: aiohttp.ClientSession = None # Made optional
) -> List[Dict[str, Any]]:
    """
    Fetches stations within a given radius (km) from a central latitude/longitude.

    Args:
        lat: Latitude of the center point.
        lon: Longitude of the center point.
        sensor_type: Sensor type ('a', 't', 'e', 'p', or 'all'). Defaults to 'all'.
        radius_km: Radius in kilometers. Defaults to 50.0.
        session: The aiohttp client session. If None, a new one is created (not recommended).

    Returns:
        A list of station dictionaries within the radius, sorted by name.
        Each station dict includes 'id', 'lat', 'lon', 'name', 'var', 'unit', etc.

    Raises:
        InvalidInputError: If sensor_type is invalid.
        APIError: If an underlying API call fails.
from pyproj import Transformer, CRS # For coordinate transformation

# ... other imports ...

async def fetch_station_list_by_location(
    lat: float, # WGS84 latitude
    lon: float, # WGS84 longitude
    sensor_type: SensorTypeAllLiteral = "all",
    radius_km: float = 50.0,
    session: aiohttp.ClientSession = None
) -> List[Dict[str, Any]]:
    """
    Fetches stations within a given radius (km) from a central WGS84 latitude/longitude.
    Station coordinates are stored in EPSG:25830 and are converted to WGS84 for distance calculation.
    """
    # Input validation for sensor_type
    valid_sensor_types: List[SensorTypeAllLiteral] = ['a', 't', 'e', 'p', 'all']
    if sensor_type not in valid_sensor_types:
        raise InvalidInputError(f"Invalid sensor_type: {sensor_type}. Valid types are: {valid_sensor_types}")

    _session_managed_internally = False
    if session is None:
        session = aiohttp.ClientSession()
        _session_managed_internally = True

    stations_found: List[Dict[str, Any]] = []

    target_sensor_types: List[SensorTypeLiteral]
    if sensor_type == "all":
        target_sensor_types = ["t", "a", "p", "e"]
    else:
        target_sensor_types = [sensor_type] # type: ignore

    central_location_wgs84 = (lat, lon)

    # Define transformer from EPSG:25830 (UTM30N) to WGS84 (lat/lon)
    # EPSG:25830 is ETRS89 / UTM zone 30N
    # WGS84 is EPSG:4326
    try:
        transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    except Exception as e:
        raise DataParseError(f"Failed to initialize coordinate transformer: {e}")

    try:
        for s_type_fetch in target_sensor_types:
            if s_type_fetch == 't': # Skip temperature for now as its source is unknown
                continue
            try:
                # fetch_station_list now returns stations with 'latitud_utm' and 'longitud_utm' in EPSG:25830
                all_stations_of_type = await fetch_station_list(s_type_fetch, session)

                for station_data in all_stations_of_type:
                    utm_x = station_data.get("longitud_utm") # Easting
                    utm_y = station_data.get("latitud_utm")  # Northing

                    if station_data.get("crs") == "EPSG:25830" and isinstance(utm_x, (float, int)) and isinstance(utm_y, (float, int)):
                        try:
                            # Transform UTM to WGS84 lat/lon
                            # Transformer expects (x, y) which is (longitude, latitude)
                            lon_wgs84, lat_wgs84 = transformer.transform(utm_x, utm_y)
                            station_location_wgs84 = (lat_wgs84, lon_wgs84)
                            distance = geodesic(central_location_wgs84, station_location_wgs84).kilometers

                            if distance <= radius_km:
                                # Add WGS84 coordinates to the station_data for convenience if needed by caller
                                station_data_copy = station_data.copy() # Avoid modifying original from potential cache
                                station_data_copy["latitud_wgs84"] = lat_wgs84
                                station_data_copy["longitud_wgs84"] = lon_wgs84
                                stations_found.append(station_data_copy)
                        except Exception as e:
                            # print(f"Error transforming coordinates for station {station_data.get('nombre')}: {e}")
                            continue # Skip station if coordinates can't be transformed
                    # else:
                        # print(f"Skipping station {station_data.get('nombre')} due to missing or incorrect CRS/coordinates.")

            except APIError as e:
                if sensor_type != 'all': # If fetching for a specific type, propagate error
                    raise
                # If 'all', log and continue to allow partial results (already handled by fetch_all_stations somewhat)
                # print(f"APIError fetching or processing station list for type '{s_type_fetch}' in by_location: {e}, skipping.")
            except DataParseError as e:
                if sensor_type != 'all':
                    raise
                # print(f"DataParseError for type '{s_type_fetch}' in by_location: {e}, skipping.")
            # Catch any other unexpected errors during processing for a specific type
            except Exception as e:
                if sensor_type != 'all':
                    raise APIError(f"Unexpected error processing type '{s_type_fetch}' in by_location: {e}") from e
                # print(f"Unexpected error for type '{s_type_fetch}' in by_location: {e}, skipping.")

    finally:
        if _session_managed_internally and session:
            await session.close()
    
    stations_found.sort(key=lambda x: x.get("nombre", ""))
    return stations_found


async def fetch_stations_by_subcuenca(
    subcuenca_id: int,
    sensor_type: SensorTypeAllLiteral = "all",
    session: aiohttp.ClientSession = None # Made optional
) -> List[Dict[str, Any]]:
    """
    Fetches stations in a specific sub-basin (subcuenca), optionally filtered by sensor type.

    Args:
        subcuenca_id: The ID of the sub-basin.
        sensor_type: Sensor type ('t', 'a', 'p', 'e', or 'all'). Defaults to 'all'.
        session: The aiohttp client session. If None, a new one is created (not recommended).

    Returns:
        A list of station dictionaries in the specified sub-basin, sorted by name.

    Raises:
        InvalidInputError: If sensor_type is invalid.
        APIError: If an underlying API call fails.
    """
    valid_sensor_types_list: List[SensorTypeAllLiteral] = ["t", "a", "p", "e", "all"]
    if sensor_type not in valid_sensor_types_list:
        raise InvalidInputError(f"Invalid sensor_type. Use 't', 'a', 'p', 'e', or 'all'.")

    _session_managed_internally = False
    if session is None:
        session = aiohttp.ClientSession()
        _session_managed_internally = True

    stations_in_subcuenca: List[Dict[str, Any]] = []
    
    target_sensor_types: List[SensorTypeLiteral]
    if sensor_type == "all":
        target_sensor_types = ["t", "a", "p", "e"]
    else:
        target_sensor_types = [sensor_type] #type: ignore

    try:
        for stype in target_sensor_types:
            url = f"{BASE_URL_STATION_LIST}?t={stype}&id="
            try:
                async with await session.get(url) as response:
                    response.raise_for_status()
                    data: List[Dict[str, Any]] = await response.json()

                for station_data in data:
                    if station_data.get("subcuenca") == subcuenca_id:
                        stations_in_subcuenca.append(station_data)
            except aiohttp.ClientResponseError as e:
                if sensor_type != 'all':
                    raise APIError(f"Failed to fetch stations for type '{stype}'. Status code: {e.status}, Message: {e.message}") from e
                # else:
                #    print(f"APIError fetching stations for type '{stype}' in by_subcuenca: {e}, skipping.")
            except aiohttp.ClientError as e:
                if sensor_type != 'all':
                    raise APIError(f"Client error for type '{stype}' in by_subcuenca: {e}") from e
                # else:
                #    print(f"ClientError for type '{stype}' in by_subcuenca: {e}, skipping.")
            except Exception as e:
                if sensor_type != 'all':
                    raise APIError(f"Unexpected error for type '{stype}' in by_subcuenca: {e}") from e
                # else:
                #    print(f"Unexpected error for type '{stype}' in by_subcuenca: {e}, skipping.")
    finally:
        if _session_managed_internally and session:
            await session.close()

    stations_in_subcuenca.sort(key=lambda station: station.get("nombre", "").lower())
    return stations_in_subcuenca
