import unittest
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import fetch_station_list

class TestSensors(unittest.TestCase):
    def get_variable_for_sensor_type(self, sensor_type: str) -> str:
        """
        Obtiene una variable compatible con el tipo de sensor a probar,
        seleccionando una de las estaciones.
        
        Args:
            sensor_type (str): El tipo de sensor ('rain', 'flow', 'reservoir', 'temperature').

        Returns:
            str: Una variable que corresponde al tipo de sensor.
        """
        # Consultar las estaciones por tipo
        station_type_map = {
            "rain": "a",  # Estación de lluvia
            "flow": "a",  # Estación de flujo
            "reservoir": "e",  # Estación de embalse
            "temperature": "t",  # Estación de temperatura
        }

        # Seleccionamos el tipo de estación según el sensor
        station_type = station_type_map.get(sensor_type)
        if not station_type:
            raise ValueError(f"Tipo de sensor no válido: {sensor_type}")

        stations = fetch_station_list(station_type)
        self.assertGreater(len(stations), 0, f"No se encontraron estaciones de tipo '{sensor_type}'")
        
        # Seleccionamos la primera estación y obtenemos su variable
        return stations[0]["variable"]  # Asume que cada estación tiene un campo 'variable'

    def test_rain_gauge_sensor(self):
        variable = self.get_variable_for_sensor_type("rain")
        sensor = RainGaugeSensor(variable, "ultimos5minutales", 12)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_flow_sensor(self):
        variable = self.get_variable_for_sensor_type("flow")
        sensor = FlowSensor(variable, "ultimashoras", 10)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_reservoir_sensor(self):
        variable = self.get_variable_for_sensor_type("reservoir")
        sensor = ReservoirSensor(variable, "ultimosdias", 7)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_temperature_sensor(self):
        variable = self.get_variable_for_sensor_type("temperature")
        sensor = TemperatureSensor(variable, "ultimos5minutales", 15)
        data = sensor.get_data()
        self.assertIsNotNone(data)

    def test_station_list(self):
        stations = fetch_station_list("a")
        self.assertGreater(len(stations), 0)

if __name__ == "__main__":
    unittest.main()
