import argparse
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import fetch_station_list

def main():
    parser = argparse.ArgumentParser(description="Herramienta CLI para interactuar con sensores")
    parser.add_argument("action", choices=["get_data", "list_stations"], help="Acción a realizar")
    parser.add_argument("--sensor_type", choices=["rain", "flow", "reservoir", "temperature"], help="Tipo de sensor")
    parser.add_argument("--variable", help="Variable del sensor")
    parser.add_argument("--num_values", type=int, help="Número de valores a obtener")
    parser.add_argument("--period_grouping", help="Agrupación temporal (ej. 'ultimos5minutales')")

    args = parser.parse_args()

    if args.action == "list_stations":
        stations = fetch_station_list()
        for station in stations:
            print(f"ID: {station['id']}, Nombre: {station['name']}, Variable: {station['variable']}, Ubicación: ({station['lat']}, {station['lon']})")
    elif args.action == "get_data":
        if not args.sensor_type or not args.variable or not args.num_values or not args.period_grouping:
            print("Para obtener datos, debes proporcionar 'sensor_type', 'variable', 'num_values' y 'period_grouping'.")
            return

        sensor_map = {
            "rain": RainGaugeSensor,
            "flow": FlowSensor,
            "reservoir": ReservoirSensor,
            "temperature": TemperatureSensor
        }

        sensor_class = sensor_map.get(args.sensor_type)
        sensor = sensor_class(args.variable, args.period_grouping, args.num_values)
        data = sensor.get_data()
        print(f"Datos obtenidos: {data}")

if __name__ == "__main__":
    main()
