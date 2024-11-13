import unittest
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import fetch_station_list

class TestSensors(unittest.TestCase):
    def get_variable_for_sensor_type(self, sensor_type: str) -> str:
        station_type_map = {
            "rain": "a",
            "flow": "a",
            "reservoir": "e",
            "temperature": "t",
        }
        station_type = station_type_map.get(sensor_type)
        stations = fetch_station_list(station_type)
        self.assertGreater(len(stations), 0, f"No stations found for sensor type '{sensor_type}'")
        return stations[0]["variable"]

    def test_all_sensor_combinations(self):
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

        for sensor_type, sensor_class in sensors.items():
            variable = self.get_variable_for_sensor_type(sensor_type)
            for period in period_groupings:
                with self.subTest(sensor_type=sensor_type, period=period):
                    print(f"Testing {sensor_type} sensor with period '{period}' and variable '{variable}'")
                    sensor = sensor_class(variable, period, 10)
                    data = sensor.get_data()
                    self.assertIsNotNone(data)
                    print(f"Data received: {data}")

if __name__ == "__main__":
    unittest.main()
