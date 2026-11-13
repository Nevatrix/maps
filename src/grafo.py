"""
Lee nodos.csv y aristas.csv y arma el grafo como listas de adyacencia (sin networkx).

Cada nodo y cada arista se identifican por su posición en las listas (0..V-1 y
0..E-1). Así los algoritmos trabajan con enteros y no con los ids de OSM.
"""

import csv
import math

import config

RADIO_TIERRA_M = 6_371_000


def haversine(lat1, lon1, lat2, lon2):
    """Distancia en metros entre dos puntos (lat, lon)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


class Grafo:
    def __init__(self):
        # datos de cada nodo
        self.ids = []        # id de OSM de cada nodo
        self.indice = {}     # id de OSM -> índice
        self.lat = []
        self.lon = []
        self.distrito = []
        # datos de cada arista
        self.origen = []
        self.destino = []
        self.longitud = []
        self.tipo = []
        self.nombre = []
        self.minutos_base = []  # minutos sin tráfico, para no recalcularlo siempre
        # listas de adyacencia (guardan el índice de la arista, no el nodo)
        self.ady = []        # aristas que salen de cada nodo
        self.ady_inv = []    # aristas que llegan a cada nodo, para Kosaraju

    @property
    def V(self):
        return len(self.ids)

    @property
    def E(self):
        return len(self.origen)

    def agregar_nodo(self, id_osm, lat, lon, distrito=""):
        self.indice[id_osm] = len(self.ids)
        self.ids.append(id_osm)
        self.lat.append(lat)
        self.lon.append(lon)
        self.distrito.append(distrito)
        self.ady.append([])
        self.ady_inv.append([])

    def agregar_arista(self, u, v, longitud_m, tipo_via, nombre=""):
        """ojo: u y v son índices, no ids de OSM."""
        e = len(self.origen)
        self.origen.append(u)
        self.destino.append(v)
        self.longitud.append(longitud_m)
        self.tipo.append(tipo_via)
        self.nombre.append(nombre)
        self.minutos_base.append(config.minutos_sin_trafico(longitud_m, tipo_via))
        self.ady[u].append(e)
        self.ady_inv[v].append(e)
        return e

    def pesos(self, hora):
        """Peso de todas las aristas usando una sola hora (el modelo de la TB1)."""
        return [config.peso_minutos(self.longitud[e], self.tipo[e], hora)
                for e in range(self.E)]

    def minutos_arista(self, e, t_min):
        """Minutos de la arista e si entras a ella en el minuto t_min del día."""
        return self.minutos_base[e] * config.factor_trafico(self.tipo[e], t_min / 60)

    def nodo_mas_cercano(self, lat, lon):
        """Recorre todos los nodos, O(V). Con 3559 nodos es instantáneo."""
        mejor, mejor_d = -1, float("inf")
        for i in range(self.V):
            d = haversine(lat, lon, self.lat[i], self.lon[i])
            if d < mejor_d:
                mejor, mejor_d = i, d
        return mejor, mejor_d


def cargar(carpeta=config.CARPETA_DATOS):
    g = Grafo()
    with open(carpeta / "nodos.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            g.agregar_nodo(int(fila["id"]), float(fila["latitud"]),
                           float(fila["longitud"]), fila["distrito"])
    with open(carpeta / "aristas.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            g.agregar_arista(g.indice[int(fila["origen"])], g.indice[int(fila["destino"])],
                             float(fila["longitud_m"]), fila["tipo_via"], fila["nombre_calle"])
    return g


if __name__ == "__main__":
    g = cargar()
    print(f"V = {g.V}, E = {g.E}")
