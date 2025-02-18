import pytest
import aiohttp
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import fetch_station_list

@pytest.mark.asyncio
class TestSensors:
    async def get_variable_for_sensor_type(self, sensor_type: str, session: aiohttp.ClientSession) -> str:
        station_type_map = {
            "rain": "a",
            "flow": "a",
            "reservoir": "e",
            "temperature": "t",
        }
        station_type = station_type_map.get(sensor_type)
        stations = await fetch_station_list(station_type, session)
        assert len(stations) > 0, f"No stations found for sensor type '{sensor_type}'"
        return stations[0]["variable"]

    @pytest.mark.asyncio
    async def test_all_sensor_combinations(self):
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
                variable = await self.get_variable_for_sensor_type(sensor_type, session)
                for period in period_groupings:
                    sensor = sensor_class(variable, period, 10)
                    data = await sensor.get_data(session)
                    assert data is not None
