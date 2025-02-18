import asyncio
import aiohttp
from geopy.distance import geodesic
from .config import BASE_URL_STATION_LIST, API_URL

async def fetch_station_list(sensor_type: str, session: aiohttp.ClientSession):
    """
    Obtiene la lista de estaciones de acuerdo al tipo de sensor especificado,
    y ordena la lista alfabéticamente por el campo 'nombre'.
    
    Args:
        sensor_type (str): Tipo de sensor, puede ser 'a' (aforos), 't' (temperatura),
                           'e' (embalses), o 'p' (pluviómetros).
        session (aiohttp.ClientSession): La sesión HTTP para realizar la petición.

    Returns:
        list: Una lista de diccionarios, donde cada diccionario representa una estación con sus datos (id, latitud, longitud, etc.). Está ordenada alfabéticamente por 'nombre'
              Retorna None si no se pudo obtener la lista de estaciones.
    """
    url = f"{BASE_URL_STATION_LIST}?t={sensor_type}&id="
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            stations_data = await response.json()
            stations = []
            for s in stations_data:
                station = {
                    "id": s.get("id"),
                    "latitud": s.get("latitud"),
                    "longitud": s.get("longitud"),
                    "nombre": s.get("nombre"),
                    "variable": s.get("variable"),
                    "unidades": s.get("unidades"),
                    "subcuenca": s.get("subcuenca"),
                    "estado": s.get("estado"),
                    "datoActual": s.get("datoActual"),
                    "datoTotal": s.get("datoTotal"),
                    "municipioNombre": s.get("municipioNombre"),
                    "estadoInt": s.get("estadoInt"),
                    "estadoInternal": s.get("estadoInternal")
                }
                stations.append(station)
            stations.sort(key=lambda station: station["nombre"])
            return stations
    except aiohttp.ClientResponseError as e:
        print(f"Error: No se pudo obtener la lista de estaciones. Código de estado: {e.status}")
        return None
    except aiohttp.ClientError as e:
        print(f"Error de cliente: {e}")
        return None


async def fetch_all_stations(session: aiohttp.ClientSession):
    """
    Obtiene y combina la lista de todas las estaciones de todos los tipos de sensores,
    y ordena la lista alfabéticamente por el campo 'nombre'.
    
    Args:
        session (aiohttp.ClientSession): La sesión HTTP para realizar las peticiones.

    Returns:
        list: Una lista de diccionarios ordenada por 'nombre', donde cada diccionario representa una estación con sus datos.
    """
    sensor_types = ['a', 't', 'e', 'p']
    all_stations = []
    tasks = [fetch_station_list(sensor_type, session) for sensor_type in sensor_types]
    results = await asyncio.gather(*tasks)

    for stations in results:
        if stations:
            all_stations.extend(stations)

    all_stations.sort(key=lambda station: station["nombre"])
    return all_stations


async def fetch_sensor_data(variable: str, period_grouping: str = "ultimos5minutales", num_values: int = 30, session: aiohttp.ClientSession = None):
    """
    Obtiene datos del sensor desde la API.

    Args:
        variable (str): La variable del sensor (por ejemplo, 'tmax', 'precipitacion').
        period_grouping (str, optional): La agrupación del periodo de tiempo. Por defecto es "ultimos5minutales".
        num_values (int, optional): El número de valores a obtener. Por defecto es 30.
        session (aiohttp.ClientSession, optional): La sesión HTTP para realizar la petición. Si no se proporciona, se creará una nueva.

    Returns:
        dict: Un diccionario con los datos del sensor en formato JSON.
              Retorna None en caso de error al obtener los datos.
    """
    url = f"{API_URL}?v={variable}&t={period_grouping}&d={num_values}"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientResponseError as e:
        print(f"Error al obtener datos del sensor: {e}")
        return None
    except aiohttp.ClientError as e:
        print(f"Error de cliente: {e}")
        return None


async def fetch_stations_by_risk(sensor_type: str = "e", risk_level: int = 2, comparison: str = "greater_equal", session: aiohttp.ClientSession = None):
    """
    Obtiene estaciones de un tipo específico o de todos los tipos que cumplan con un nivel
    de riesgo especificado, según el tipo de comparación (igual a o mayor o igual que).
    
    Args:
        sensor_type (str, optional): Tipo de sensor ('a' para aforos, 't' para temperatura,
                           'e' para embalses, 'p' para pluviómetros, 'all' para todos). Por defecto es 'e'.
        risk_level (int, optional): Nivel de riesgo como un valor entero (0: desconocido, 1: verde,
                          2: amarillo, 3: rojo). Por defecto es 2.
        comparison (str, optional): Tipo de comparación, puede ser "equal" o "greater_equal". Por defecto es 'greater_equal'.
        session (aiohttp.ClientSession, optional): La sesión HTTP para realizar la petición. Si no se proporciona, se creará una nueva.
    
    Returns:
        list: Lista de estaciones que cumplen con el criterio de riesgo.
              Retorna una lista vacía si el tipo de sensor o el nivel de riesgo no son válidos.
    """
    # Validar el tipo de sensor
    valid_sensor_types = ['a', 't', 'e', 'p', 'all']
    if sensor_type not in valid_sensor_types:
        print(f"Error: Tipo de sensor '{sensor_type}' no válido. Use uno de {valid_sensor_types}.")
        return []

    # Validar el nivel de riesgo
    if not isinstance(risk_level, int) or risk_level < 0 or risk_level > 3:
        print("Error: Nivel de riesgo no válido. Debe ser un entero entre 0 y 3.")
        return []

    # Validar el tipo de comparación
    if comparison not in ["equal", "greater_equal"]:
        print("Error: Tipo de comparación no reconocido. Use 'equal' o 'greater_equal'.")
        return []

    # Obtener estaciones según el tipo de sensor
    if sensor_type == "all":
        sensor_types = ['a', 't', 'e', 'p']
    else:
        sensor_types = [sensor_type]

    filtered_stations = []
    for st in sensor_types:
        stations = await fetch_station_list(st, session)
        if stations:

            if comparison == "equal":
                filtered_stations.extend([station for station in stations if station["estadoInt"] == risk_level])
            elif comparison == "greater_equal":
                filtered_stations.extend([station for station in stations if station["estadoInt"] >= risk_level])

    return filtered_stations

async def fetch_station_list_by_location(lat: float, lon: float, sensor_type: str = "all", radius_km: float = 50.0, session: aiohttp.ClientSession = None):
    """
    Obtiene una lista de estaciones de un tipo específico ubicadas dentro de un radio en kilómetros de una ubicación dada.
    
    Args:
        lat (float): La latitud de la ubicación central.
        lon (float): La longitud de la ubicación central.
        sensor_type (str, optional): El tipo de sensor ('a', 't', 'e', 'p' o 'all'). Por defecto es 'all'.
        radius_km (float, optional): El radio en kilómetros alrededor de la ubicación central. Por defecto es 50.0.
        session (aiohttp.ClientSession, optional): La sesión HTTP para realizar la petición. Si no se proporciona, se creará una nueva.

    Returns:
        list: Una lista de estaciones dentro del radio especificado, ordenadas por nombre.
    """
    # Validación del tipo de sensor
    valid_sensor_types = {"t", "a", "p", "e", "all"}
    if sensor_type not in valid_sensor_types:
        raise ValueError(f"Tipo de sensor no válido: {sensor_type}")

    stations = []
    if sensor_type == "all":
        sensor_types = ["t", "a", "p", "e"]
    else:
        sensor_types = [sensor_type]

    # Realiza la consulta para cada tipo de sensor y filtra por ubicación
    central_location = (lat, lon)
    for s_type in sensor_types:
        try:            
            async with session.get(f"{BASE_URL_STATION_LIST}?t={s_type}&id=") as response:
                response.raise_for_status()
                data = await response.json()
            for station in data:
                station_location = (station["latitud"], station["longitud"])
                distance = geodesic(central_location, station_location).kilometers
                if distance <= radius_km:
                    stations.append({
                        "id": station["id"],
                        "lat": station["latitud"],
                        "lon": station["longitud"],
                        "name": station["nombre"],
                        "var": station["variable"],
                        "unit": station["unidades"],
                        "subcuenca": station.get("subcuenca"),
                        "estado": station.get("estado"),
                        "estadoInternal": station.get("estadoInternal"),
                        "estadoInt": station.get("estadoInt")
                    })
        except aiohttp.ClientResponseError as e:
            print(f"Error al obtener la lista de estaciones para el tipo '{s_type}': {e}")
    
    # Ordena las estaciones alfabéticamente por el campo "name"
    stations_sorted = sorted(stations, key=lambda x: x["name"])
    
    return stations_sorted

async def fetch_stations_by_subcuenca(subcuenca_id: int, sensor_type: str = "all", session: aiohttp.ClientSession = None):
    """
    Obtiene una lista de estaciones en una subcuenca específica, opcionalmente filtrada por tipo de sensor.

    Args:
        subcuenca_id (int): El ID de la subcuenca (0 a 11). (Pendiente de actualizar con los nombres de cada subcuenca)
        sensor_type (str, optional): Tipo de sensor ('t', 'a', 'p', 'e', o 'all' para todos los tipos). Por defecto es 'all'.
        session (aiohttp.ClientSession, optional): La sesión HTTP para realizar la petición. Si no se proporciona, se creará una nueva.

    Returns:
        list: Lista de estaciones en la subcuenca especificada.
              Retorna una lista vacía si el tipo de sensor no es válido
    """
    # Validar el tipo de sensor
    if sensor_type not in ["t", "a", "p", "e", "all"]:
        raise ValueError("Tipo de sensor inválido. Utilice 't', 'a', 'p', 'e' o 'all'.")

    stations = []

    # Si sensor_type es 'all', consultar cada tipo de sensor
    sensor_types = [sensor_type] if sensor_type != "all" else ["t", "a", "p", "e"]

    for stype in sensor_types:
        try:
            async with session.get(f"{BASE_URL_STATION_LIST}?t={stype}&id=") as response:
                response.raise_for_status()
                data = await response.json()
                filtered_stations = [
                    station for station in data if station.get("subcuenca") == subcuenca_id
                ]
                stations.extend(filtered_stations)
        except aiohttp.ClientResponseError as e:
            print(f"Error al obtener estaciones para el tipo '{stype}': {e}")

    # Ordenar estaciones alfabéticamente por nombre
    stations.sort(key=lambda station: station.get("nombre", "").lower())
    
    return stations

