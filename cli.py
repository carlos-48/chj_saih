import argparse
import asyncio
import aiohttp
from chj_saih.sensors import RainGaugeSensor, FlowSensor, ReservoirSensor, TemperatureSensor
from chj_saih.data_fetcher import fetch_all_stations

async def main():
    parser = argparse.ArgumentParser(description="Herramienta CLI para interactuar con sensores")
    parser.add_argument("action", choices=["get_data", "list_stations"], nargs="?", help="Acción a realizar")
    parser.add_argument("--sensor_type", choices=["rain", "flow", "reservoir", "temperature"], help="Tipo de sensor")
    parser.add_argument("--variable", help="Variable del sensor")
    parser.add_argument("--num_values", type=int, help="Número de valores a obtener")
    parser.add_argument("--period_grouping", help="Agrupación temporal (ej. 'ultimos5minutales')")

    args = parser.parse_args()

    # Inicia el menú interactivo si no se proporcionan argumentos
    if args.action is None:
        print("Seleccione una acción:")
        print("1. Obtener datos de un sensor")
        print("2. Listar todas las estaciones")
        option = input("Ingrese el número de la opción deseada: ")

        if option == "1":
            action = "get_data"
            sensor_type = input("Ingrese el tipo de sensor (rain, flow, reservoir, temperature): ")
            variable = input("Ingrese la variable del sensor: ")
            num_values = int(input("Ingrese el número de valores a obtener: "))
            period_grouping = input("Ingrese la agrupación temporal (ej. 'ultimos5minutales'): ")
        elif option == "2":
            action = "list_stations"
            sensor_type = variable = period_grouping = None
            num_values = 0
        else:
            print("Opción inválida.")
            return
    else:
        # Si se proporcionan argumentos, toma los valores de argparse
        action = args.action
        sensor_type = args.sensor_type
        variable = args.variable
        num_values = args.num_values
        period_grouping = args.period_grouping

    async with aiohttp.ClientSession() as session:
        # Ejecuta la acción basada en los argumentos o la entrada del usuario
        if action == "list_stations":
            stations = await fetch_all_stations(session)
            for station in stations:
                print(f"ID: {station['id']}, Nombre: {station['nombre']}, Variable: {station['variable']}, Ubicación: ({station['latitud']}, {station['longitud']})")
        elif action == "get_data":
            if not sensor_type or not variable or not num_values or not period_grouping:
                print("Para obtener datos, debes proporcionar 'sensor_type', 'variable', 'num_values' y 'period_grouping'.")
                return

            sensor_map = {
                "rain": RainGaugeSensor,
                "flow": FlowSensor,
                "reservoir": ReservoirSensor,
                "temperature": TemperatureSensor
            }

            sensor_class = sensor_map.get(sensor_type)
            sensor = sensor_class(variable, period_grouping, num_values)
            data = await sensor.get_data(session)
            print(f"Datos obtenidos: {data}")

if __name__ == "__main__":
    asyncio.run(main())
