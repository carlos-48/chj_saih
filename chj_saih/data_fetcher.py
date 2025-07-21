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

from .config import BASE_URL_STATION_LIST, API_URL
from .exceptions import APIError, InvalidInputError

# Define valid sensor type literals for better type hinting
SensorTypeLiteral = Literal['a', 't', 'e', 'p']
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
        APIError: If there's an issue communicating with the API or the API
                  returns an error status.
    """
    url = f"{BASE_URL_STATION_LIST}?t={sensor_type}&id="
    try:
        async with session.get(url) as response:
            response.raise_for_status()  # Raises ClientResponseError for 4xx/5xx
            stations_data: List[Dict[str, Any]] = await response.json()
            # It's good practice to sort by a consistent key if the API doesn't guarantee order
            stations_data.sort(key=lambda station: station.get("nombre", ""))
            return stations_data
    except aiohttp.ClientResponseError as e:
        raise APIError(f"Failed to fetch station list for type '{sensor_type}'. Status code: {e.status}, Message: {e.message}") from e
    except aiohttp.ClientError as e: # Catches other client errors like connection issues
        raise APIError(f"Client error while fetching station list for type '{sensor_type}': {e}") from e
    except Exception as e: # Catch potential other errors like JSONDecodeError
        raise APIError(f"An unexpected error occurred while fetching station list for type '{sensor_type}': {e}") from e


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
    """
    url = f"{API_URL}?v={variable}&t={period_grouping}&d={num_values}"

    # Handle session internally if not provided, for convenience in simple scripts.
    # However, for library use, passing an external session is much preferred.
    _session_managed_internally = False
    if session is None:
        session = aiohttp.ClientSession()
        _session_managed_internally = True

    try:
        async with session.get(url) as response:
            response.raise_for_status()
            # Assuming the API returns a list, but could be Dict if error JSON
            data: List[Any] = await response.json()
            return data
    except aiohttp.ClientResponseError as e:
        raise APIError(f"Failed to fetch sensor data for variable '{variable}'. Status code: {e.status}, Message: {e.message}") from e
    except aiohttp.ClientError as e:
        raise APIError(f"Client error while fetching sensor data for variable '{variable}': {e}") from e
    except Exception as e: # Catch potential other errors like JSONDecodeError
        raise APIError(f"An unexpected error occurred while fetching sensor data for variable '{variable}': {e}") from e
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
    """
    valid_sensor_types_set: set[SensorTypeAllLiteral] = {"t", "a", "p", "e", "all"}
    if sensor_type not in valid_sensor_types_set:
        raise InvalidInputError(f"Invalid sensor_type: {sensor_type}. Valid types are: {valid_sensor_types_set}")

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

    central_location = (lat, lon)
    try:
        for s_type in target_sensor_types:
            url = f"{BASE_URL_STATION_LIST}?t={s_type}&id="
            try:
                async with await session.get(url) as response:
                    response.raise_for_status()
                    data: List[Dict[str, Any]] = await response.json()
                for station_data in data:
                    s_lat = station_data.get("latitud")
                    s_lon = station_data.get("longitud")
                    if isinstance(s_lat, (float, int)) and isinstance(s_lon, (float, int)):
                        station_location = (s_lat, s_lon)
                        distance = geodesic(central_location, station_location).kilometers
                        if distance <= radius_km:
                            stations_found.append({
                                "id": station_data.get("id"),
                                "lat": s_lat,
                                "lon": s_lon,
                                "name": station_data.get("nombre"),
                                "var": station_data.get("variable"),
                                "unit": station_data.get("unidades"), # Assuming 'unidades' exists
                                "subcuenca": station_data.get("subcuenca"),
                                "estado": station_data.get("estado"),
                                "estadoInternal": station_data.get("estadoInternal"),
                                "estadoInt": station_data.get("estadoInt")
                            })
            except aiohttp.ClientResponseError as e:
                # If fetching for a specific type fails, and it's not 'all', re-raise
                # If 'all', log and continue to allow partial results.
                if sensor_type != 'all':
                    raise APIError(f"Failed to fetch station list for type '{s_type}'. Status code: {e.status}, Message: {e.message}") from e
                # else:
                #    print(f"APIError fetching station list for type '{s_type}' in by_location: {e}, skipping.")
            except aiohttp.ClientError as e:
                if sensor_type != 'all':
                    raise APIError(f"Client error for type '{s_type}' in by_location: {e}") from e
                # else:
                #    print(f"ClientError for type '{s_type}' in by_location: {e}, skipping.")
            except Exception as e:
                if sensor_type != 'all':
                    raise APIError(f"Unexpected error for type '{s_type}' in by_location: {e}") from e
                # else:
                #    print(f"Unexpected error for type '{s_type}' in by_location: {e}, skipping.")

    finally:
        if _session_managed_internally and session:
            await session.close()
    
    stations_found.sort(key=lambda x: x.get("name", ""))
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
