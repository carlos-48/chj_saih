from datetime import datetime
from typing import List, Tuple, Dict, Any, Union
from chj_saih.data_fetcher import fetch_sensor_data

class SensorDataParser:
    def __init__(self, json_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]):
        self.metadata = json_data[0]
        self.values = json_data[1]
        self.time_info = json_data[2]

    def get_date_format(self, period_grouping: str) -> str:
        """
        Obtiene el formato de fecha en función del tipo de agrupación temporal.
        
        Args:
            period_grouping (str): Tipo de agrupación temporal.

        Returns:
            str: Formato de fecha correspondiente.
        """
        date_format_mapping = {
            "ultimos5minutales": "%d/%m/%Y %H:%M",
            "ultimashoras": "%d/%m/%Y %H:%M",
            "ultimashorasaforo": "%d/%m/%Y %H:%M",
            "ultimodia": "%d/%m/%Y %Hh.",
            "ultimasemana": "%d/%m/%Y %Hh.",
            "ultimomes": "%d/%m/%Y",
            "ultimoanno": "%d/%m/%Y"
        }
        # Intenta obtener el formato a partir del mapeo, si no, usa el formato predeterminado
        return date_format_mapping.get(period_grouping, "%d/%m/%Y %H:%M")

    def parse_date(self, date_str: str, date_format: str) -> datetime:
        """
        Convierte una cadena de fecha a un objeto datetime usando el formato adecuado.
        
        Args:
            date_str (str): Fecha en formato string.
            date_format (str): Formato de fecha.

        Returns:
            datetime: Fecha como objeto datetime.
        """
        try:
            return datetime.strptime(date_str, date_format)
        except ValueError:
            print(f"Error al parsear la fecha '{date_str}' con el formato '{date_format}'")
            return None

    def extract_data(self, period_grouping: str) -> List[Tuple[datetime, float]]:
        """
        Extrae y convierte los datos de fecha y valor en una lista de tuplas.
        
        Args:
            period_grouping (str): Tipo de agrupación temporal.

        Returns:
            List[Tuple[datetime, float]]: Lista de tuplas con fecha y valor.
        """
        date_format = self.get_date_format(period_grouping)
        parsed_data = [
            (self.parse_date(date_str, date_format), value)
            for date_str, value in self.values if value is not None
        ]
        return [(dt, val) for dt, val in parsed_data if dt is not None]

class Sensor:
    def __init__(self, variable: str, period_grouping: str, num_values: int):
        self.variable = variable
        self.period_grouping = period_grouping
        self.num_values = num_values

    def get_data(self) -> Union[Dict[str, Any], None]:
        raw_data = fetch_sensor_data(self.variable, self.period_grouping, self.num_values)
        return self.parse_data(raw_data) if raw_data else None

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Método base para parsear los datos en un formato estándar.
        Deberá ser sobrescrito por cada subclase.
        """
        raise NotImplementedError("Este método debe ser implementado por subclases.")

class RainGaugeSensor(Sensor):
    """Sensor para medir la lluvia (pluviómetro)."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        values.sort(key=lambda x: x[0])  # Ordena por fecha
        return {"rainfall_data": values}

class FlowSensor(Sensor):
    """Sensor para medir el caudal de un río (aforo)."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        values.sort(key=lambda x: x[0])
        return {"flow_data": values}

class ReservoirSensor(Sensor):
    """Sensor para medir la cantidad de agua almacenada en un embalse."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        values.sort(key=lambda x: x[0])
        return {"reservoir_data": values}

class TemperatureSensor(Sensor):
    """Sensor para medir la temperatura ambiental."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data(self.period_grouping)
        values.sort(key=lambda x: x[0])
        return {"temperature_data": values}
