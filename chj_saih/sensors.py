from datetime import datetime
from typing import List, Tuple, Dict, Any, Union
from chj_saih.data_fetcher import fetch_sensor_data

class SensorDataParser:
    def __init__(self, json_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]):
        self.metadata = json_data[0]
        self.values = json_data[1]
        self.time_info = json_data[2]

    def get_date_format(self) -> str:
        """
        Obtiene el formato de fecha a partir del JSON de respuesta, utilizando
        el valor de 'formatoFechaEje' en el bloque de configuración de la consulta.
        
        Returns:
            str: Formato de fecha encontrado o un formato predeterminado.
        """
        # Buscamos el formato en el JSON; usamos un formato default si no se encuentra
        return self.time_info.get("formatoFechaEje", "%d/%m %H:%M")

    def parse_date(self, date_str: str, date_format: str) -> datetime:
        """
        Convierte una cadena de fecha a un objeto datetime usando el formato adecuado.
        
        Args:
            date_str (str): Fecha en formato string.
            date_format (str): Formato de fecha.

        Returns:
            datetime: Fecha como objeto datetime.
        """
        return datetime.strptime(date_str, date_format)

    def extract_data(self) -> List[Tuple[datetime, float]]:
        """
        Extrae y convierte los datos de fecha y valor en una lista de tuplas.
        
        Returns:
            List[Tuple[datetime, float]]: Lista de tuplas con fecha y valor.
        """
        date_format = self.get_date_format()
        parsed_data = [
            (self.parse_date(date_str, date_format), value)
            for date_str, value in self.values
        ]
        return parsed_data

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
        values = parser.extract_data()
        values.sort(key=lambda x: x[0])  # Ordena por fecha
        return {"rainfall_data": values}

class FlowSensor(Sensor):
    """Sensor para medir el caudal de un río (aforo)."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data()
        values.sort(key=lambda x: x[0])
        return {"flow_data": values}

class ReservoirSensor(Sensor):
    """Sensor para medir la cantidad de agua almacenada en un embalse."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data()
        values.sort(key=lambda x: x[0])
        return {"reservoir_data": values}

class TemperatureSensor(Sensor):
    """Sensor para medir la temperatura ambiental."""

    def parse_data(self, raw_data: List[Union[Dict[str, Any], List[List[Union[str, float]]], Dict[str, Any]]]) -> Dict[str, Any]:
        parser = SensorDataParser(raw_data)
        values = parser.extract_data()
        values.sort(key=lambda x: x[0])
        return {"temperature_data": values}
