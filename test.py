import unittest
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import fetch_station_list

class TestSensors(unittest.TestCase):
    def test_rain_gauge_sensor(self):
        sensor = RainGaugeSensor("rain_variable", "ultimos5minutales", 12)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_flow_sensor(self):
        sensor = FlowSensor("flow_variable", "ultimashoras", 10)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_reservoir_sensor(self):
        sensor = ReservoirSensor("reservoir_variable", "ultimosdias", 7)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_temperature_sensor(self):
        sensor = TemperatureSensor("temperature_variable", "ultimos5minutales", 15)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_station_list(self):
        stations = fetch_station_list()
        self.assertGreater(len(stations), 0)

if __name__ == "__main__":
    unittest.main()
