# Rutas Lima

Trabajo final (TB2) de Complejidad Algorítmica.

Calcula la ruta en auto de menor tiempo entre dos esquinas de Miraflores, San Isidro y Surquillo, según la hora de salida. La red vial sale de OpenStreetMap: 3,559 nodos y 7,277 aristas dirigidas. El peso de cada arista es el tiempo en minutos, que depende del largo del tramo, del tipo de vía y de un factor de tráfico por hora.

## Instalación

Con Python 3.12 o superior (lo probamos con 3.14):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Cómo correrlo

Todo se ejecuta desde la raíz del proyecto.

```
python src/app.py
```

Después abrir http://localhost:8080 en el navegador. Se marca el origen y el destino con clics en el mapa y se mueve la hora con el slider. También se puede hacer clic en una barra del gráfico para cambiar la hora.

Otros comandos:

```
python -m unittest discover -s tests -v   # pruebas
python src/experimentos.py                # tiempos y comparaciones del informe
python src/visualizar.py                  # figuras 1, 2 y 3
python src/descargar_red.py               # vuelve a descargar la red de OSM (tarda unos minutos)
```

No hace falta correr `descargar_red.py`, porque los CSV ya están en `datos/`.

## Archivos

| Archivo | Qué hace |
|---|---|
| `src/config.py` | Distritos, velocidades por tipo de vía, factor de tráfico hora por hora y la fórmula del peso |
| `src/descargar_red.py` | Descarga la red con OSMnx, clasifica las vías, calcula longitudes con Haversine y exporta los CSV y los límites de los distritos |
| `src/grafo.py` | Lee los CSV y arma la lista de adyacencia (y la del grafo transpuesto) |
| `src/algoritmos.py` | Dijkstra, Kosaraju, BFS, Bellman-Ford y Floyd-Warshall, escritos por nosotros |
| `src/app.py` | Interfaz gráfica con NiceGUI y Leaflet |
| `src/experimentos.py` | Mide los algoritmos con pares al azar y guarda `datos/resultados_experimentos.json` |
| `src/visualizar.py` | Genera las figuras del dataset |
| `tests/test_algoritmos.py` | Pruebas con grafos chicos y comparación con networkx sobre la red real |
| `datos/` | `nodos.csv`, `aristas.csv`, `distritos.geojson` y metadatos de la descarga |
| `figuras/` | Figuras del informe |

## Cómo funciona una consulta

1. Se revisa que el clic caiga dentro de los tres distritos y se busca el nodo más cercano.
2. Kosaraju (calculado una sola vez al iniciar) dice si el origen y el destino están en la misma componente fuertemente conexa. Si no lo están, no hay ruta respetando el sentido de las calles. Pasa con 81 de los 3,559 nodos.
3. Dijkstra con heap calcula la ruta de menor tiempo. El peso de cada calle usa el tráfico de la hora en que el auto llega a ella, no solo el de la hora de salida. El factor de tráfico cambia hora por hora y se interpola entre horas, así que salir más tarde nunca hace llegar antes y Dijkstra sigue dando la ruta óptima.
4. BFS calcula la ruta con menos cuadras, solo para comparar.

networkx solo se usa en `descargar_red.py` y en las pruebas, para comprobar que nuestros resultados coinciden con los suyos.

## Datos

© OpenStreetMap contributors, bajo licencia ODbL. Las velocidades y los factores de tráfico son supuestos del grupo, no mediciones reales.

## Integrantes

- Lozano Leon, Richard Enrique
- Mora Rivera, Joel Fernando
- Villarreal Bazan, Angel Martin
