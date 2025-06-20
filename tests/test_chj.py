import pytest
import aiohttp
from unittest.mock import AsyncMock, patch, MagicMock, call
import datetime
from chj_saih.exceptions import APIError, InvalidInputError
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import (
    fetch_station_list,
    fetch_all_stations,
    fetch_sensor_data,
    fetch_stations_by_risk,
    fetch_station_list_by_location,
    fetch_stations_by_subcuenca
)
from chj_saih.config import BASE_URL_STATION_LIST, API_URL
# from geopy.distance import geodesic # Not strictly needed if we mock intelligently

@pytest.mark.asyncio
class TestSensors:
    async def get_variable_for_sensor_type(self, sensor_type: str, session: aiohttp.ClientSession) -> str:
        # Hardcoded valid-looking variables for testing to avoid live calls
        test_variables = {
            "rain": "XX.PREC_ACUM.TEST",
            "flow": "XX.CAUDAL.TEST",
            "reservoir": "XX.VOLUMEN.TEST",
            "temperature": "XX.TMAX_MAX.TEST"
        }
        if sensor_type in test_variables:
            return test_variables[sensor_type]
        # Fallback or error if we want to ensure no live calls for setup either
        # For this refactoring, the goal is that test_all_sensor_combinations itself is mock-based
        # If fetch_station_list was mocked project-wide or session was a deep mock, this would be different.
        # For now, hardcoding is the simplest way to ensure this helper doesn't make live calls.
        raise ValueError(f"Test variable not found for sensor type {sensor_type} in get_variable_for_sensor_type. Consider hardcoding.")

    @patch('chj_saih.sensors.fetch_sensor_data', new_callable=AsyncMock) # Patch where it's used by Sensor.get_data
    async def test_all_sensor_combinations(self, mock_fetch_sensor_data_func):
        # Mock the return value of the low-level fetch_sensor_data
        # This is the raw data structure fetch_sensor_data is expected to return
        mock_fetch_sensor_data_func.return_value = [
            {"descripcion": "Mocked Meta Data", "nombreParam": "ultimodia"}, # Added nombreParam for SensorDataParser
            [["17/06/2024 10:00", 10.0], ["17/06/2024 10:05", 10.5]],
            {"parametro": "Mocked Param Info"}
        ]

        sensors = {
            "rain": RainGaugeSensor,
            "flow": FlowSensor,
            "reservoir": ReservoirSensor,
            "temperature": TemperatureSensor
        }
        period_groupings = [
            "ultimos5minutales",
            "ultimashoras",
            "ultimashorasaforo",
            "ultimodia",
            "ultimasemana",
            "ultimomes",
            "ultimoanno"
        ]

        async with aiohttp.ClientSession() as session:
            for sensor_type, sensor_class in sensors.items():
                # Use the refactored/hardcoded get_variable_for_sensor_type
                # The session passed here is mostly a dummy for get_variable_for_sensor_type's signature,
                # as it won't be used if variables are hardcoded.
                # For sensor.get_data(session), it's also not strictly needed for API calls if
                # fetch_sensor_data is mocked, but the method signature requires it.
                variable = await self.get_variable_for_sensor_type(sensor_type, session)

                for period in period_groupings:
                    # Update mock_fetch_sensor_data_func's return value if period matters for metadata
                    # This is important because SensorDataParser tries to get 'nombre' from 'paramVisual'
                    # which often corresponds to period_grouping.
                    mock_fetch_sensor_data_func.return_value = [
                        {"descripcion": "Mocked Meta Data", "paramVisual": [{"nombre": period}]},
                        [["17/06/2024 10:00", 10.0], ["17/06/2024 10:05", 10.5]],
                        {"parametro": "Mocked Param Info"}
                    ]

                    sensor = sensor_class(variable, period, 10)
                    data = await sensor.get_data(session) # This will now use the mocked fetch_sensor_data

                    assert data is not None
                    # Assertions for data structure remain the same
                    if sensor_type == "rain":
                        assert "rainfall_data" in data
                        assert isinstance(data["rainfall_data"], list)
                        if data["rainfall_data"]: # If list is not empty
                            assert isinstance(data["rainfall_data"][0], tuple)
                            assert len(data["rainfall_data"][0]) == 2
                            assert isinstance(data["rainfall_data"][0][0], datetime.datetime)
                            assert isinstance(data["rainfall_data"][0][1], (float, int, type(None))) # Allow None due to parser changes
                    elif sensor_type == "flow":
                        assert "flow_data" in data
                        assert isinstance(data["flow_data"], list)
                        if data["flow_data"]:
                            assert isinstance(data["flow_data"][0], tuple)
                            assert len(data["flow_data"][0]) == 2
                            assert isinstance(data["flow_data"][0][0], datetime.datetime)
                            assert isinstance(data["flow_data"][0][1], (float, int, type(None)))
                    elif sensor_type == "reservoir":
                        assert "reservoir_data" in data
                        assert isinstance(data["reservoir_data"], list)
                        if data["reservoir_data"]:
                            assert isinstance(data["reservoir_data"][0], tuple)
                            assert len(data["reservoir_data"][0]) == 2
                            assert isinstance(data["reservoir_data"][0][0], datetime.datetime)
                            assert isinstance(data["reservoir_data"][0][1], (float, int, type(None)))
                    elif sensor_type == "temperature":
                        assert "temperature_data" in data
                        assert isinstance(data["temperature_data"], list)
                        if data["temperature_data"]:
                            assert isinstance(data["temperature_data"][0], tuple)
                            assert len(data["temperature_data"][0]) == 2
                            assert isinstance(data["temperature_data"][0][0], datetime.datetime)
                            assert isinstance(data["temperature_data"][0][1], (float, int, type(None)))

            # Verify mock_fetch_sensor_data_func was called for each combination
            assert mock_fetch_sensor_data_func.call_count == len(sensors) * len(period_groupings)

@pytest.mark.asyncio
class TestDataFetcher:
    @patch('aiohttp.ClientSession.get', new_callable=MagicMock) # Standard mock for the get method
    async def test_fetch_station_list_success(self, mock_get_method): # mock_get_method is session.get

        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock() # Synchronous method
        mock_response_content.json = AsyncMock(return_value=[ # Asynchronous method
            {"id": "S01", "nombre": "Station A", "latitud": 1.0, "longitud": 1.0, "variable": "varA"},
            {"id": "S02", "nombre": "Station B", "latitud": 2.0, "longitud": 2.0, "variable": "varB"},
        ])

        # The object returned by session.get() needs to be an async context manager
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__.return_value = mock_response_content
        async_context_manager.__aexit__ = AsyncMock(return_value=None)

        # session.get() should return this context manager
        mock_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            stations = await fetch_station_list(sensor_type='a', session=session)

        assert stations is not None
        assert len(stations) == 2
        assert stations[0]["nombre"] == "Station A"
        assert stations[1]["nombre"] == "Station B"
        mock_get_method.assert_called_once_with(f"{BASE_URL_STATION_LIST}?t=a&id=")

    @patch('aiohttp.ClientSession.get', new_callable=MagicMock)
    async def test_fetch_station_list_api_error(self, mock_get_method):
        mock_response_content = AsyncMock() # This is the 'response' object
        # raise_for_status is a synchronous method, its mock should be MagicMock
        mock_response_content.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=404,
            message="Not Found"
        ))
        mock_response_content.json = AsyncMock() # json is an async method

        async_context_manager = AsyncMock() # This is the object returned by session.get()
        async_context_manager.__aenter__.return_value = mock_response_content
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            with pytest.raises(APIError) as excinfo:
                await fetch_station_list(sensor_type='a', session=session)

        assert "Failed to fetch station list for type 'a'. Status code: 404, Message: Not Found" in str(excinfo.value)

    @patch('aiohttp.ClientSession.get', new_callable=MagicMock)
    async def test_fetch_station_list_client_error(self, mock_get_method):
        # Configure session.get() itself to raise a ClientError
        mock_get_method.side_effect = aiohttp.ClientError("Connection failed")

        async with aiohttp.ClientSession() as session:
            with pytest.raises(APIError) as excinfo:
                await fetch_station_list(sensor_type='a', session=session)

        assert "Client error while fetching station list for type 'a': Connection failed" in str(excinfo.value)

    # Tests for fetch_all_stations
    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_all_stations_success(self, mock_fetch_station_list):
        def side_effect_fetch_station_list(sensor_type, session):
            if sensor_type == 'a': # Aforos
                return [{"id": "S01", "nombre": "Station A", "variable": "varA"}]
            elif sensor_type == 'p': # Pluviómetros
                return [{"id": "S03", "nombre": "Station C", "variable": "varC"}]
            elif sensor_type == 'e': # Embalses
                return [{"id": "S02", "nombre": "Station B", "variable": "varB"}]
            elif sensor_type == 't': # Temperatura
                return [{"id": "S04", "nombre": "Station D", "variable": "varD"}]
            return []

        mock_fetch_station_list.side_effect = side_effect_fetch_station_list

        async with aiohttp.ClientSession() as session:
            stations = await fetch_all_stations(session=session)

        assert stations is not None
        assert len(stations) == 4
        # Results should be sorted by 'nombre'
        assert stations[0]["nombre"] == "Station A"
        assert stations[1]["nombre"] == "Station B"
        assert stations[2]["nombre"] == "Station C"
        assert stations[3]["nombre"] == "Station D"

        # Assert that fetch_station_list was called for each sensor type
        expected_calls = [call('a', session), call('t', session), call('e', session), call('p', session)]
        # The order of calls to fetch_station_list within fetch_all_stations is fixed: ['a', 't', 'e', 'p']
        # So we can check the calls in order.
        mock_fetch_station_list.assert_has_calls(expected_calls, any_order=False)
        assert mock_fetch_station_list.call_count == 4


    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_all_stations_partial_failure(self, mock_fetch_station_list):
        def side_effect_fetch_station_list(sensor_type, session):
            if sensor_type == 'a':
                return [{"id": "S01", "nombre": "Station A", "variable": "varA"}]
            elif sensor_type == 'p':
                # Simulate failure for pluviometers by returning None
                return None
            elif sensor_type == 'e':
                return [{"id": "S02", "nombre": "Station B", "variable": "varB"}]
            elif sensor_type == 't':
                # Simulate failure for temperature by raising an APIError
                raise APIError("Simulated API Error for temperature")
            return []

        mock_fetch_station_list.side_effect = side_effect_fetch_station_list

        async with aiohttp.ClientSession() as session:
            stations = await fetch_all_stations(session=session)

        assert stations is not None
        assert len(stations) == 2
        assert stations[0]["nombre"] == "Station A"
        assert stations[1]["nombre"] == "Station B"
        assert mock_fetch_station_list.call_count == 4

    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_all_stations_all_fail(self, mock_fetch_station_list):
        # Simulate failure for all types
        mock_fetch_station_list.return_value = None

        async with aiohttp.ClientSession() as session:
            stations = await fetch_all_stations(session=session)

        assert stations is not None
        assert len(stations) == 0
        assert mock_fetch_station_list.call_count == 4

    # Tests for fetch_sensor_data
    @patch('aiohttp.ClientSession.get', new_callable=MagicMock)
    async def test_fetch_sensor_data_success(self, mock_get_method):
        sample_sensor_json = [{"metadata_key": "metadata_value"}, [["01/01/2023 10:00", 123.45]], {"time_info_key": "time_info_value"}]

        mock_response_content = AsyncMock()
        mock_response_content.raise_for_status = MagicMock()
        mock_response_content.json = AsyncMock(return_value=sample_sensor_json)

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__.return_value = mock_response_content
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_get_method.return_value = async_context_manager

        variable_test = "test_var"
        period_grouping_test = "ultimos5minutales"
        num_values_test = 10

        async with aiohttp.ClientSession() as session:
            data = await fetch_sensor_data(variable_test, period_grouping_test, num_values_test, session)

        assert data == sample_sensor_json
        expected_url = f"{API_URL}?v={variable_test}&t={period_grouping_test}&d={num_values_test}"
        mock_get_method.assert_called_once_with(expected_url)

    @patch('aiohttp.ClientSession.get', new_callable=MagicMock)
    async def test_fetch_sensor_data_api_error(self, mock_get_method):
        mock_response_content = AsyncMock()
        mock_response_content.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            request_info=None, history=None, status=500, message="Server Error"
        ))
        mock_response_content.json = AsyncMock() # Should not be called

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__.return_value = mock_response_content
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            with pytest.raises(APIError) as excinfo:
                await fetch_sensor_data("var", "period", 10, session)

        assert "Failed to fetch sensor data for variable 'var'. Status code: 500, Message: Server Error" in str(excinfo.value)

    @patch('aiohttp.ClientSession.get', new_callable=MagicMock)
    async def test_fetch_sensor_data_client_error(self, mock_get_method):
        mock_get_method.side_effect = aiohttp.ClientError("Network connection failed")

        async with aiohttp.ClientSession() as session:
            with pytest.raises(APIError) as excinfo:
                await fetch_sensor_data("var", "period", 10, session)

        assert "Client error while fetching sensor data for variable 'var': Network connection failed" in str(excinfo.value)

    # Tests for fetch_stations_by_risk
    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_stations_by_risk_success_equal(self, mock_fsl):
        mock_fsl.return_value = [
            {"id": "S01", "nombre": "Station A", "estadoInt": 1},
            {"id": "S02", "nombre": "Station B", "estadoInt": 2},
            {"id": "S03", "nombre": "Station C", "estadoInt": 2},
            {"id": "S04", "nombre": "Station D", "estadoInt": 3},
        ]
        async with aiohttp.ClientSession() as session:
            stations = await fetch_stations_by_risk(sensor_type='e', risk_level=2, comparison="equal", session=session)

        assert len(stations) == 2
        assert stations[0]["nombre"] == "Station B"
        assert stations[1]["nombre"] == "Station C"
        mock_fsl.assert_called_once_with('e', session)

    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_stations_by_risk_success_greater_equal(self, mock_fsl):
        mock_fsl.return_value = [
            {"id": "S01", "nombre": "Station A", "estadoInt": 1},
            {"id": "S02", "nombre": "Station B", "estadoInt": 2},
            {"id": "S03", "nombre": "Station C", "estadoInt": 3},
        ]
        async with aiohttp.ClientSession() as session:
            stations = await fetch_stations_by_risk(sensor_type='e', risk_level=2, comparison="greater_equal", session=session)

        assert len(stations) == 2
        assert stations[0]["nombre"] == "Station B"
        assert stations[1]["nombre"] == "Station C"
        mock_fsl.assert_called_once_with('e', session)

    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_stations_by_risk_all_types(self, mock_fsl):
        mock_fsl.return_value = [] # Return empty list for simplicity
        async with aiohttp.ClientSession() as session:
            await fetch_stations_by_risk(sensor_type="all", risk_level=1, comparison="equal", session=session)

        expected_calls = [call('a', session), call('t', session), call('e', session), call('p', session)]
        # Order of calls: 'a', 't', 'e', 'p'
        mock_fsl.assert_has_calls(expected_calls, any_order=False)
        assert mock_fsl.call_count == 4

    async def test_fetch_stations_by_risk_invalid_sensor_type(self):
        async with aiohttp.ClientSession() as session:
            with pytest.raises(InvalidInputError) as excinfo:
                await fetch_stations_by_risk(sensor_type="invalid", session=session)
        assert "Invalid sensor_type 'invalid'" in str(excinfo.value)

    async def test_fetch_stations_by_risk_invalid_risk_level(self):
        async with aiohttp.ClientSession() as session:
            with pytest.raises(InvalidInputError) as excinfo:
                await fetch_stations_by_risk(risk_level=5, session=session)
        assert "Invalid risk_level. Must be an integer between 0 and 3" in str(excinfo.value)

    async def test_fetch_stations_by_risk_invalid_comparison(self):
        async with aiohttp.ClientSession() as session:
            with pytest.raises(InvalidInputError) as excinfo:
                await fetch_stations_by_risk(comparison="wrong", session=session)
        assert "Invalid comparison type. Use 'equal' or 'greater_equal'" in str(excinfo.value)

    @patch('chj_saih.data_fetcher.fetch_station_list', new_callable=AsyncMock)
    async def test_fetch_stations_by_risk_fetch_station_list_fails(self, mock_fsl):
        mock_fsl.side_effect = APIError("Failed to fetch")
        async with aiohttp.ClientSession() as session:
            # The function re-raises APIError if sensor_type is specific and fetch_station_list fails.
            with pytest.raises(APIError) as excinfo:
                await fetch_stations_by_risk(sensor_type='e', risk_level=1, session=session)
        assert "Failed to fetch" in str(excinfo.value) # Check if the original error message is part of it
        mock_fsl.assert_called_once_with('e', session)

    # Tests for fetch_station_list_by_location
    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_station_list_by_location_success(self, mock_session_get_method): # mock_session_get_method is session.get
        # Stations: A (in), B (out), C (in, edge), D (out)
        mock_data_a_type = [
            {"id": "S01", "nombre": "Station A", "latitud": 10.0, "longitud": 10.0, "variable": "varA", "unidades": "m3/s"}, # In
            {"id": "S02", "nombre": "Station B", "latitud": 50.0, "longitud": 50.0, "variable": "varB", "unidades": "m3/s"}, # Out
        ]
        mock_data_p_type = [
            {"id": "S03", "nombre": "Station C", "latitud": 10.04, "longitud": 10.04, "variable": "varC", "unidades": "mm"}, # In (approx 5.5km for 0.04deg)
            {"id": "S04", "nombre": "Station D", "latitud": 12.0, "longitud": 12.0, "variable": "varD", "unidades": "mm"}, # Out
        ]

        # This side_effect function will be awaited by the patched session.get (mock_session_get_method)
        # It needs to return the object that 'async with' expects (an async context manager)
        async def side_effect_for_get(url):
            mock_response_ctx = AsyncMock() # This is what 'response' will be in 'async with ... as response'
            mock_response_ctx.raise_for_status = MagicMock()

            if f"{BASE_URL_STATION_LIST}?t=a&id=" in url:
                mock_response_ctx.json = AsyncMock(return_value=mock_data_a_type)
            elif f"{BASE_URL_STATION_LIST}?t=p&id=" in url:
                mock_response_ctx.json = AsyncMock(return_value=mock_data_p_type)
            else:
                mock_response_ctx.json = AsyncMock(return_value=[])

            # This is the async context manager that session.get() should return
            async_context_mgr = AsyncMock()
            async_context_mgr.__aenter__ = AsyncMock(return_value=mock_response_ctx)
            async_context_mgr.__aexit__ = AsyncMock(return_value=None)
            return async_context_mgr

        mock_session_get_method.side_effect = side_effect_for_get

        async with aiohttp.ClientSession() as session:
            # Radius is approx 10km. Station A and C should be in.
            # geodesic((10,10), (10.04, 10.04)).km is about 6.17 km
            stations = await fetch_station_list_by_location(lat=10.0, lon=10.0, sensor_type="all", radius_km=7, session=session)

        assert len(stations) == 2
        assert stations[0]["name"] == "Station A" # Sorted by name
        assert stations[1]["name"] == "Station C"

        # Check calls for all sensor types 't', 'a', 'p', 'e'
        # The specific order in fetch_station_list_by_location is 't', 'a', 'p', 'e' when 'all'
        expected_urls = [
            call(f"{BASE_URL_STATION_LIST}?t=t&id="),
            call(f"{BASE_URL_STATION_LIST}?t=a&id="),
            call(f"{BASE_URL_STATION_LIST}?t=p&id="),
            call(f"{BASE_URL_STATION_LIST}?t=e&id="),
        ]
        # mock_session_get_method.assert_has_calls(expected_urls, any_order=False) # Replaced with below
        assert mock_session_get_method.call_count == 4
        actual_urls_called = [c.args[0] for c in mock_session_get_method.call_args_list] # Use .args
        assert actual_urls_called == [ec.args[0] for ec in expected_urls] # Use the existing expected_urls variable


    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_station_list_by_location_all_types(self, mock_session_get_method): # mock_session_get_method is session.get
        # Simplified mock: just ensure it's called for all types
        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock()
        mock_response_content.json = AsyncMock(return_value=[]) # No stations needed for this test

        async_context_manager = AsyncMock() # This is the async context manager
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_response_content)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)

        # session.get() is an async method, its mock (mock_session_get_method) will be awaited.
        # The result of that await (return_value of the mock) should be the async_context_manager.
        mock_session_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            await fetch_station_list_by_location(lat=10.0, lon=10.0, sensor_type="all", radius_km=5, session=session)

        # Check calls for all sensor types 't', 'a', 'p', 'e'
        expected_calls = [
            call(f"{BASE_URL_STATION_LIST}?t=t&id="),
            call(f"{BASE_URL_STATION_LIST}?t=a&id="),
            call(f"{BASE_URL_STATION_LIST}?t=p&id="),
            call(f"{BASE_URL_STATION_LIST}?t=e&id="),
        ]
        # mock_session_get_method.assert_has_calls(expected_urls, any_order=False) # Applying same fix here
        assert mock_session_get_method.call_count == 4
        actual_urls_called = [c.args[0] for c in mock_session_get_method.call_args_list]
        assert actual_urls_called == [ec.args[0] for ec in expected_calls] # Corrected variable name


    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_station_list_by_location_no_stations_found(self, mock_session_get_method): # mock_session_get_method is session.get
        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock()
        # Return stations far away or empty list
        mock_response_content.json = AsyncMock(return_value=[
            {"id": "S05", "nombre": "Station FarAway", "latitud": 80.0, "longitud": 80.0}
        ])

        async_context_manager = AsyncMock() # This is the async context manager
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_response_content)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            stations = await fetch_station_list_by_location(lat=10.0, lon=10.0, sensor_type="a", radius_km=5, session=session)

        assert stations == []

    async def test_fetch_station_list_by_location_invalid_sensor_type(self):
        async with aiohttp.ClientSession() as session:
            with pytest.raises(InvalidInputError) as excinfo:
                await fetch_station_list_by_location(lat=10.0, lon=10.0, sensor_type="invalid", session=session)
        assert "Invalid sensor_type: invalid" in str(excinfo.value)

    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_station_list_by_location_api_error(self, mock_session_get_method): # mock_session_get_method is session.get
        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            request_info=None, history=None, status=500, message="Server Error"))
        mock_response_content.json = AsyncMock() # Should not be called

        async_context_manager = AsyncMock() # This is the async context manager
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_response_content)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            with pytest.raises(APIError) as excinfo:
                await fetch_station_list_by_location(lat=10.0, lon=10.0, sensor_type="a", session=session)
        assert "Failed to fetch station list for type 'a'. Status code: 500" in str(excinfo.value)


    # Tests for fetch_stations_by_subcuenca
    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_stations_by_subcuenca_success(self, mock_session_get_method): # mock_session_get_method is session.get
        mock_data = [
            {"id": "S01", "nombre": "Station A Sub1", "subcuenca": 1},
            {"id": "S02", "nombre": "Station B Sub2", "subcuenca": 2},
            {"id": "S03", "nombre": "Station C Sub1", "subcuenca": 1},
        ]
        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock()
        mock_response_content.json = AsyncMock(return_value=mock_data)

        async_context_manager = AsyncMock() # This is the async context manager
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_response_content)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            stations = await fetch_stations_by_subcuenca(subcuenca_id=1, sensor_type="p", session=session)

        assert len(stations) == 2
        assert stations[0]["nombre"] == "Station A Sub1" # Sorted by name
        assert stations[1]["nombre"] == "Station C Sub1"
        mock_session_get_method.assert_called_once_with(f"{BASE_URL_STATION_LIST}?t=p&id=")

    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_stations_by_subcuenca_all_types(self, mock_session_get_method): # mock_session_get_method is session.get
        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock()
        mock_response_content.json = AsyncMock(return_value=[]) # No data needed for this check

        async_context_manager = AsyncMock() # This is the async context manager
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_response_content)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            await fetch_stations_by_subcuenca(subcuenca_id=1, sensor_type="all", session=session)

        # Order of calls in function: 't', 'a', 'p', 'e'
        expected_calls = [
            call(f"{BASE_URL_STATION_LIST}?t=t&id="),
            call(f"{BASE_URL_STATION_LIST}?t=a&id="),
            call(f"{BASE_URL_STATION_LIST}?t=p&id="),
            call(f"{BASE_URL_STATION_LIST}?t=e&id="),
        ]
        # mock_session_get_method.assert_has_calls(expected_urls, any_order=False) # Replaced with below
        assert mock_session_get_method.call_count == 4
        actual_urls_called = [c.args[0] for c in mock_session_get_method.call_args_list] # Use .args
        assert actual_urls_called == [ec.args[0] for ec in expected_calls] # Corrected variable name

    async def test_fetch_stations_by_subcuenca_invalid_sensor_type(self):
        async with aiohttp.ClientSession() as session:
            with pytest.raises(InvalidInputError) as excinfo:
                await fetch_stations_by_subcuenca(subcuenca_id=1, sensor_type="invalid", session=session)
        assert "Invalid sensor_type. Use 't', 'a', 'p', 'e', or 'all'." in str(excinfo.value)

    @patch('aiohttp.ClientSession.get', new_callable=AsyncMock) # Was MagicMock
    async def test_fetch_stations_by_subcuenca_api_error(self, mock_session_get_method): # mock_session_get_method is session.get
        mock_response_content = AsyncMock() # This is the 'response' object
        mock_response_content.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            request_info=None, history=None, status=500, message="Server Error"))
        mock_response_content.json = AsyncMock()

        async_context_manager = AsyncMock() # This is the async context manager
        async_context_manager.__aenter__.return_value = mock_response_content
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_get_method.return_value = async_context_manager

        async with aiohttp.ClientSession() as session:
            with pytest.raises(APIError) as excinfo:
                await fetch_stations_by_subcuenca(subcuenca_id=1, sensor_type="p", session=session)
        assert "Failed to fetch stations for type 'p'. Status code: 500" in str(excinfo.value)
