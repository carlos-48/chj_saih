# CHJ-SAIH
Módulo para obtener datos hidrológicos del Sistema Automático de Información Hidrológica de la Confederación Hidrográfica del Júcar 

Este módulo **ahora es funcional para obtener datos hidrológicos y listas de estaciones.** Mi intención final es crear posteriormente una integración para Home Assistant, donde poder monitorizar, e incluso con algún ayudante de tipo Trend, poder detectar situaciones de riesgo y poder notificar.

La idea surge después de que la DANA de Octubre-Noviembre de 2024 arrasara varias localidades en mi tierra, Valencia.

Los datos del SAIH de la CHJ son públicos, pero no existe una API documentada ni herramientas disponibles para consumir esos datos, más allá de la propia página web. Este módulo Python solamente es una herramienta que ayuda a trabajar con esos datos públicos que pueden ser de gran utilidad e incluso salvar vidas.

## Características Principales

*   **Obtención de Listas de Estaciones:**
    *   `fetch_station_list(sensor_type, session)`: Obtiene estaciones para un tipo de sensor específico.
    *   `fetch_all_stations(session)`: Obtiene todas las estaciones de todos los tipos.
    *   Funciones especializadas para filtrar por riesgo (`fetch_stations_by_risk`), ubicación (`fetch_station_list_by_location`), y subcuenca (`fetch_stations_by_subcuenca`).
*   **Obtención de Datos de Sensores:**
    *   Clases de Sensor (ej. `RainGaugeSensor`, `FlowSensor`, `ReservoirSensor`, `TemperatureSensor`): Instanciar y usar el método `async get_data(session)` para obtener datos parseados.
    *   `fetch_sensor_data(variable, period_grouping, num_values, session)`: Función de bajo nivel para obtener datos crudos del sensor.
*   **Manejo de Errores Personalizado:**
    *   La librería utiliza excepciones personalizadas que heredan de `CHJSAIHError`:
        *   `APIError`: Para errores de comunicación con la API (problemas de red, códigos de estado HTTP erróneos).
        *   `DataParseError`: Para errores durante el parseo de la respuesta de la API.
        *   `InvalidInputError`: Para argumentos inválidos pasados a las funciones.

## Ejemplo de Uso como Librería

```python
import asyncio
import aiohttp
from chj_saih import (
    fetch_station_list,
    fetch_all_stations,
    fetch_stations_by_risk,
    fetch_station_list_by_location,
    fetch_stations_by_subcuenca,
    RainGaugeSensor,
    FlowSensor,
    ReservoirSensor,
    TemperatureSensor,
    APIError,
    InvalidInputError
)

async def main():
    async with aiohttp.ClientSession() as session:
        try:
            # Obtener lista de todos los aforos (sensor_type='a')
            aforos = await fetch_station_list(sensor_type='a', session=session)
            if aforos:
                print(f"Primeros 5 aforos encontrados: {aforos[:5]}")

                # Tomar la variable del primer aforo para obtener sus datos
                if aforos[0].get("variable"):
                    variable_aforo = aforos[0]["variable"]
                    print(f"Obteniendo datos para la variable de aforo: {variable_aforo}")

                    # Crear instancia del sensor de aforo (FlowSensor)
                    flow_sensor = FlowSensor(variable=variable_aforo, period_grouping="ultimashoras", num_values=12)
                    data_aforo = await flow_sensor.get_data(session)
                    if data_aforo:
                        print(f"Datos del aforo ({variable_aforo}): {data_aforo}")
                    else:
                        print(f"No se pudieron obtener datos para el aforo {variable_aforo}")
                else:
                    print("La primera estación de aforo no tiene una 'variable' definida.")

            else:
                print("No se encontraron aforos.")

            # Ejemplo: Obtener todos los pluviómetros (sensor_type='p') en riesgo amarillo (2) o superior
            pluvios_riesgo = await fetch_stations_by_risk(sensor_type='p', risk_level=2, comparison="greater_equal", session=session)
            print(f"Pluviómetros en riesgo amarillo o superior: {pluvios_riesgo}")

            # Ejemplo: Obtener estaciones de embalse (sensor_type='e') cerca de una coordenada
            # Nota: Lat/Lon y radio son ejemplos, ajustar según necesidad.
            embalses_cercanos = await fetch_station_list_by_location(lat=39.47, lon=-0.37, sensor_type='e', radius_km=50, session=session)
            print(f"Embalses cercanos a Valencia (ejemplo): {embalses_cercanos}")

            # Ejemplo: Obtener todas las estaciones en la subcuenca con ID 0
            estaciones_subcuenca_0 = await fetch_stations_by_subcuenca(subcuenca_id=0, sensor_type="all", session=session)
            print(f"Estaciones en subcuenca 0: {estaciones_subcuenca_0}")

        except APIError as e:
            print(f"Error de API: {e}")
        except InvalidInputError as e:
            print(f"Error de entrada inválida: {e}")
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Pruebas (Testing)

Este proyecto utiliza `pytest` para las pruebas.

### Pruebas Unitarias y de Integración (Mock)

Las pruebas principales se encuentran en `tests/test_chj.py` y utilizan mocks para simular las respuestas de la API. Esto asegura que las pruebas sean rápidas y fiables para la integración continua. Para ejecutar todas las pruebas (incluidas las basadas en mock):

```bash
python -m pytest
```
o simplemente:
```bash
pytest
```

### Pruebas de API en Vivo (Live API Tests)

Además de las pruebas unitarias y de integración basadas en mocks, el proyecto incluye un conjunto de pruebas que interactúan directamente con la API real del SAIH CHJ. Estas pruebas están diseñadas para verificar la funcionalidad de extremo a extremo y se encuentran en `tests/test_live_api.py`.

**Importante:**
*   Estas pruebas realizan llamadas reales a la red y dependen de la disponibilidad de la API externa.
*   Ejecútalas con moderación para evitar una carga excesiva en el servicio de la API. No se recomienda ejecutarlas automáticamente en cada commit en CI de forma predeterminada.

Para ejecutar únicamente las pruebas de API en vivo, utiliza el siguiente comando:

```bash
python -m pytest -m live tests/test_live_api.py
```

O si `pytest` está en el PATH y `pytest.ini` está configurado para descubrir el marcador `live`:

```bash
pytest -m live
```

Nota: no soy desarrollador, es un hobby al que por desgracia le dedico muy poco tiempo. Para agilizar, me he apoyado en IA para generar la estructura del repositorio, a falta de desarrollar mejor el código.
