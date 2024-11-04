import datetime

class Sensor:
    def __init__(self, variable, period_grouping, num_values):
        self.variable = variable
        self.period_grouping = period_grouping
        self.num_values = num_values

    def get_data(self):
        from chj_saih.data_fetcher import fetch_sensor_data
        raw_data = fetch_sensor_data(self.variable, self.period_grouping, self.num_values)
        return self.parse_data(raw_data) if raw_data else None

    def parse_data(self, raw_data):
        """
        Método base para parsear los datos en un formato estándar.
        Deberá ser sobrescrito por cada subclase.
        """
        raise NotImplementedError("Este método debe ser implementado por subclases.")

class RainGaugeSensor(Sensor):
    """Sensor para medir la lluvia (pluviómetro)."""

    def parse_data(self, raw_data):
        values = list(
            filter(
                lambda dv: dv[1] is not None,
                map(
                    lambda dv: (
                        datetime.datetime.strptime(dv[0], '%d/%m/%Y %H:%M'),
                        dv[1]
                    ),
                    raw_data[1]  # Asume que el JSON contiene los valores en raw_data[1]
                )
            )
        )
        values.sort(key=lambda x: x[0])  # Ordena por fecha
        return {"rainfall_data": values}

class FlowSensor(Sensor):
    """Sensor para medir el caudal de un río (aforo)."""

    def parse_data(self, raw_data):
        values = list(
            filter(
                lambda dv: dv[1] is not None,
                map(
                    lambda dv: (
                        datetime.datetime.strptime(dv[0], '%d/%m/%Y %H:%M'),
                        dv[1]
                    ),
                    raw_data[1]
                )
            )
        )
        values.sort(key=lambda x: x[0])
        return {"flow_data": values}

class ReservoirSensor(Sensor):
    """Sensor para medir la cantidad de agua almacenada en un embalse."""

    def parse_data(self, raw_data):
        values = list(
            filter(
                lambda dv: dv[1] is not None,
                map(
                    lambda dv: (
                        datetime.datetime.strptime(dv[0], '%d/%m/%Y %H:%M'),
                        dv[1]
                    ),
                    raw_data[1]
                )
            )
        )
        values.sort(key=lambda x: x[0])
        return {"reservoir_data": values}

class TemperatureSensor(Sensor):
    """Sensor para medir la temperatura ambiental."""

    def parse_data(self, raw_data):
        values = list(
            filter(
                lambda dv: dv[1] is not None,
                map(
                    lambda dv: (
                        datetime.datetime.strptime(dv[0], '%d/%m/%Y %H:%M'),
                        dv[1]
                    ),
                    raw_data[1]
                )
            )
        )
        values.sort(key=lambda x: x[0])
        return {"temperature_data": values}
