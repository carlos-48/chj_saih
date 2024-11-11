import requests
from geopy.distance import geodesic
from .config import BASE_URL_STATION_LIST, API_URL

def fetch_station_list(sensor_type: str):
    """
    Obtiene la lista de estaciones de acuerdo al tipo de sensor especificado,
    y ordena la lista alfabéticamente por el campo 'nombre'.
    
    Parámetros:
        sensor_type (str): Tipo de sensor, puede ser 'a' (aforos), 't' (temperatura),
                           'e' (embalses), o 'p' (pluviómetros).
    
    Retorna:
        list: Lista de estaciones en formato de diccionario con información estructurada,
              ordenada alfabéticamente por 'nombre'.
    """
    url = f"{BASE_URL_STATION_LIST}?t={sensor_type}&id="
    response = requests.get(url)
    
    if response.status_code == 200:
        stations_data = response.json()
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
        
        # Ordenar la lista de estaciones por el campo 'nombre'
        stations.sort(key=lambda station: station["nombre"])
        return stations
    else:
        print(f"Error: No se pudo obtener la lista de estaciones. Status code: {response.status_code}")
        return None

def fetch_all_stations():
    """
    Obtiene y combina la lista de todas las estaciones de todos los tipos de sensores,
    y ordena la lista alfabéticamente por el campo 'nombre'.
    
    Retorna:
        list: Lista de todas las estaciones, ordenada por 'nombre'.
    """
    sensor_types = ['a', 't', 'e', 'p']
    all_stations = []

    for sensor_type in sensor_types:
        stations = fetch_station_list(sensor_type)
        if stations:
            all_stations.extend(stations)

    # Ordenar la lista combinada por el campo 'nombre'
    all_stations.sort(key=lambda station: station["nombre"])
    
    return all_stations

def fetch_sensor_data(variable: str, period_grouping: str = "ultimos5minutales", num_values:int = 30):
    """
    Obtiene datos del sensor desde la API.
    
    Args:
        variable (str): Identificador del sensor.
        period_grouping (str): Agrupación temporal (ej. 'ultimos5minutales', 'ultimashoras' (8h), 'ultimashorasaforo' (solo para aforos, 8h, valores medios horarios), 'ultimodia' (24h, valores medios horarios), 'ultimasemana' (valores medios horarios), 'ultimomes', 'ultimoanno').
        num_values (int): Número de valores a obtener.
    
    Returns:
        dict: Datos JSON de la respuesta de la API.
    """
    url = f"{API_URL}?v={variable}&t={period_grouping}&d={num_values}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos del sensor: {e}")
        return None

def fetch_stations_by_risk(sensor_type: str = "e", risk_level:int = 2, comparison: str = "greater_equal"):
    """
    Obtiene estaciones de un tipo específico o de todos los tipos que cumplan con un nivel
    de riesgo especificado, según el tipo de comparación (igual a o mayor o igual que).
    
    Parámetros:
        sensor_type (str): Tipo de sensor ('a' para aforos, 't' para temperatura,
                           'e' para embalses, 'p' para pluviómetros, 'all' para todos).
        risk_level (int): Nivel de riesgo como un valor entero (0: desconocido, 1: verde,
                          2: amarillo, 3: rojo).
        comparison (str): Tipo de comparación, puede ser "equal" o "greater_equal".
    
    Retorna:
        list: Lista de estaciones que cumplen con el criterio de riesgo.
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
        stations = fetch_station_list(st)
        if stations:
            # Filtrar estaciones según el nivel de riesgo y el tipo de comparación
            if comparison == "equal":
                filtered_stations.extend([station for station in stations if station["estadoInt"] == risk_level])
            elif comparison == "greater_equal":
                filtered_stations.extend([station for station in stations if station["estadoInt"] >= risk_level])

    return filtered_stations

def fetch_station_list_by_location(lat: float, lon: float, sensor_type: str = "all", radius_km: float = 50.0):
    """
    Obtiene una lista de estaciones de un tipo específico ubicadas dentro de un radio en kilómetros de una ubicación dada.
    
    Parámetros:
        sensor_type (str): Tipo de sensor ("t", "a", "p", "e" o "all").
        lat (float): Latitud de la ubicación central.
        lon (float): Longitud de la ubicación central.
        radius_km (float): Radio en kilómetros.

    Retorna:
        dict: Diccionario de estaciones dentro del radio especificado, ordenadas por nombre.
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
            response = requests.get(f"{BASE_URL_STATION_LIST}?t={s_type}&id=")
            response.raise_for_status()
            data = response.json()
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
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener la lista de estaciones para el tipo '{s_type}': {e}")
    
    # Ordena las estaciones alfabéticamente por el campo "name"
    stations_sorted = sorted(stations, key=lambda x: x["name"])
    
    return stations_sorted

def fetch_stations_by_subcuenca(subcuenca_id: int, sensor_type: str = "all"):
    """
    Obtiene una lista de estaciones en una subcuenca específica, opcionalmente filtrada por tipo de sensor.

    Args:
        subcuenca_id (int): El ID de la subcuenca (0 a 11). (Pendiente de actualizar con los nombres de cada subcuenca)
        sensor_type (str): Tipo de sensor ('t', 'a', 'p', 'e', o 'all' para todos los tipos).

    Returns:
        list: Lista de estaciones en la subcuenca especificada.
    """
    # Validar el tipo de sensor
    if sensor_type not in ["t", "a", "p", "e", "all"]:
        raise ValueError("Tipo de sensor inválido. Utilice 't', 'a', 'p', 'e' o 'all'.")

    stations = []

    # Si sensor_type es 'all', consultar cada tipo de sensor
    sensor_types = [sensor_type] if sensor_type != "all" else ["t", "a", "p", "e"]

    for stype in sensor_types:
        try:
            response = requests.get(f"{BASE_URL_STATION_LIST}?t={stype}&id=")
            response.raise_for_status()
            data = response.json()

            # Filtrar estaciones por subcuenca
            filtered_stations = [
                station for station in data if station.get("subcuenca") == subcuenca_id
            ]

            stations.extend(filtered_stations)

        except requests.exceptions.RequestException as e:
            print(f"Error al obtener estaciones para el tipo '{stype}': {e}")

    # Ordenar estaciones alfabéticamente por nombre
    stations.sort(key=lambda station: station.get("nombre", "").lower())
    
    return stations
