import requests
from chj_saih.config import API_URL, STATION_LIST_URL

def fetch_sensor_data(variable, period_grouping, num_values):
    """
    Obtiene datos del sensor desde la API.

    Args:
        variable (str): Identificador del sensor.
        period_grouping (str): Agrupación temporal (ej. 'ultimos5minutales', 'ultimashoras').
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

def fetch_station_list():
    """
    Obtiene un listado de estaciones y selecciona aquellas con unidades específicas.

    Returns:
        list: Lista de estaciones con información relevante.
    """
    try:
        response = requests.get(STATION_LIST_URL)
        response.raise_for_status()
        stations = []
        for s in response.json():
            station = {
                'id': s['id'],
                'lat': s['latitud'],
                'lon': s['longitud'],
                'name': s['nombre'],
                'variable': s['variable'],
                'unit': s['unidades'],
                'subcuenca': s['subcuenca']
            }
            stations.append(station)
        return stations
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener la lista de estaciones: {e}")
        return []
