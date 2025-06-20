import pytest
import aiohttp
import datetime
from typing import List, Dict, Any

from chj_saih import (
    fetch_station_list,
    fetch_all_stations, # Though we might test fetch_station_list per type first
    RainGaugeSensor,
    FlowSensor,
    ReservoirSensor,
    TemperatureSensor,
    APIError  # To potentially catch and provide better messages for live test failures
)
from chj_saih.config import API_URL, BASE_URL_STATION_LIST # For info if needed, not for mocking

# Helper function to check station structure (can be expanded)
def check_station_structure(station: Dict[str, Any]):
    assert "id" in station
    assert "nombre" in station
    assert "latitud" in station
    assert "longitud" in station
    assert "variable" in station # Important for fetching sensor data

@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_station_list_live_for_each_type():
    """Tests fetching station lists for each sensor type from the live API."""
    sensor_types_to_test = ['a', 'p', 'e', 't'] # Aforos, Pluviómetros, Embalses, Temperatura
    min_expected_stations = 1 # Expect at least one station of each type

    async with aiohttp.ClientSession() as session:
        for sensor_type in sensor_types_to_test:
            try:
                stations = await fetch_station_list(sensor_type=sensor_type, session=session)
                assert stations is not None, f"Station list for type '{sensor_type}' should not be None"
                assert isinstance(stations, list), f"Station list for type '{sensor_type}' should be a list"
                assert len(stations) >= min_expected_stations, \
                    f"Expected at least {min_expected_stations} station(s) for type '{sensor_type}', got {len(stations)}"

                for station in stations:
                    check_station_structure(station)
                    # Could add more specific checks, e.g., variable prefixes based on type

            except APIError as e:
                pytest.fail(f"APIError while fetching station list for type '{sensor_type}': {e}")
            except Exception as e:
                pytest.fail(f"Unexpected error while fetching station list for type '{sensor_type}': {e}")

@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("sensor_type_char, sensor_class, data_key_name", [
    ('p', RainGaugeSensor, "rainfall_data"),
    ('a', FlowSensor, "flow_data"), # Assuming 'a' can also be used for FlowSensors based on variable
    ('e', ReservoirSensor, "reservoir_data"),
    ('t', TemperatureSensor, "temperature_data"),
])
async def test_fetch_sample_sensor_data_live(sensor_type_char, sensor_class, data_key_name):
    """Tests fetching data for one station of a given sensor type from the live API."""
    station_name = "Unknown" # Initialize for potential use in error messages
    station_variable = "Unknown" # Initialize for potential use in error messages
    async with aiohttp.ClientSession() as session:
        try:
            stations = await fetch_station_list(sensor_type=sensor_type_char, session=session)
            assert stations, f"No stations found for type '{sensor_type_char}' to test data fetching."

            # Try to find a station that seems active or has a common variable pattern if possible
            # For now, just pick the first one
            target_station = stations[0]
            station_variable = target_station.get("variable")
            station_name = target_station.get("nombre")

            assert station_variable, f"Station '{station_name}' for type '{sensor_type_char}' has no 'variable' field."

            sensor = sensor_class(variable=station_variable, period_grouping="ultimodia", num_values=5)
            data = await sensor.get_data(session)

            assert data is not None, f"Sensor data for '{station_name}' ({station_variable}) should not be None"
            assert data_key_name in data, f"'{data_key_name}' not in sensor data for '{station_name}'"
            assert isinstance(data[data_key_name], list), f"'{data_key_name}' should be a list for '{station_name}'"

            # If data is present, check structure of the first element
            if data[data_key_name]:
                first_record = data[data_key_name][0]
                assert isinstance(first_record, tuple), "Sensor data record should be a tuple"
                assert len(first_record) == 2, "Sensor data tuple should have 2 elements (datetime, value)"
                assert isinstance(first_record[0], datetime.datetime), "First element of data tuple should be datetime"
                # Value can be int, float, or None (if parsing failed for a specific value)
                assert isinstance(first_record[1], (int, float, type(None))), \
                    "Second element of data tuple should be int, float, or None"

        except APIError as e:
            pytest.fail(f"APIError while testing {sensor_class.__name__} for station '{station_name}' (variable: {station_variable}): {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error testing {sensor_class.__name__} for station '{station_name}' (variable: {station_variable}): {e}")
