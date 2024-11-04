class Sensor:
    def __init__(self, variable, period_grouping, num_values):
        self.variable = variable
        self.period_grouping = period_grouping
        self.num_values = num_values

    def get_data(self):
        from chj_saih.data_fetcher import fetch_sensor_data
        return fetch_sensor_data(self.variable, self.period_grouping, self.num_values)

class RainGaugeSensor(Sensor):
    """Sensor para medir la lluvia (pluviómetro)."""
    pass

class FlowSensor(Sensor):
    """Sensor para medir el caudal de un río (aforo)."""
    pass

class ReservoirSensor(Sensor):
    """Sensor para medir la cantidad de agua almacenada en un embalse."""
    pass

class TemperatureSensor(Sensor):
    """Sensor para medir la temperatura ambiental."""
    pass
