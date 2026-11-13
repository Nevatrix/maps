"""
Pruebas. Desde la raíz del proyecto:

    python -m unittest discover -s tests -v

Las primeras son con grafos chicos donde sabemos la respuesta. Las otras usan
la red real y comparan con networkx o con una versión lenta del mismo cálculo.
"""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import algoritmos as alg  # noqa: E402
import grafo as gr  # noqa: E402


def grafo_chico(aristas, n):
    """aristas = [(u, v, peso), ...]. el peso va en longitud para usarlo directo."""
    g = gr.Grafo()
    for i in range(n):
        g.agregar_nodo(i, 0.0, 0.0)
    for u, v, w in aristas:
        g.agregar_arista(u, v, w, "local")
    return g, list(g.longitud)


class GrafosChicos(unittest.TestCase):
    def test_ruta_conocida(self):
        # 0 -> 1 -> 3 cuesta 2; 0 -> 2 -> 3 cuesta 5; 0 -> 3 directo cuesta 10
        g, w = grafo_chico([(0, 1, 1), (1, 3, 1), (0, 2, 1), (2, 3, 4), (0, 3, 10)], 4)
        r = alg.dijkstra(g, 0, 3, w)
        self.assertEqual(r["costo"], 2)
        self.assertEqual([g.destino[e] for e in r["camino"]], [1, 3])
        self.assertEqual(alg.bellman_ford(g, 0, 3, w)["costo"], 2)
        # BFS prefiere la arista directa (1 tramo) aunque sea la más lenta
        self.assertEqual(len(alg.bfs(g, 0, 3, w)["camino"]), 1)

    def test_un_solo_sentido(self):
        # 0 -> 1 existe, 1 -> 0 no
        g, w = grafo_chico([(0, 1, 1)], 2)
        self.assertEqual(alg.dijkstra(g, 0, 1, w)["costo"], 1)
        r = alg.dijkstra(g, 1, 0, w)
        self.assertEqual(r["costo"], float("inf"))
        self.assertIsNone(r["camino"])

    def test_origen_igual_destino(self):
        g, w = grafo_chico([(0, 1, 1), (1, 0, 1)], 2)
        r = alg.dijkstra(g, 0, 0, w)
        self.assertEqual(r["costo"], 0)
        self.assertEqual(r["camino"], [])

    def test_aristas_paralelas(self):
        # dos calzadas entre 0 y 1: debe usar la más rápida
        g, w = grafo_chico([(0, 1, 5), (0, 1, 2)], 2)
        r = alg.dijkstra(g, 0, 1, w)
        self.assertEqual(r["costo"], 2)
        self.assertEqual(r["camino"], [1])

    def test_kosaraju(self):
        # {0,1,2} es un ciclo; 3 solo recibe; 4 aislado
        g, _ = grafo_chico([(0, 1, 1), (1, 2, 1), (2, 0, 1), (2, 3, 1)], 5)
        comp = alg.kosaraju(g)
        self.assertTrue(comp[0] == comp[1] == comp[2])
        self.assertNotEqual(comp[0], comp[3])
        self.assertEqual(len(set(comp)), 3)

    def test_floyd_warshall(self):
        g, w = grafo_chico([(0, 1, 1), (1, 2, 2), (0, 2, 5)], 3)
        d = alg.floyd_warshall(g, w)
        self.assertEqual(d[0][2], 3)
        self.assertEqual(d[2][0], float("inf"))


def bellman_ford_tiempo(g, s, hora):
    """Lo mismo que dijkstra_tiempo pero a lo bruto: relaja todo hasta que no cambie nada."""
    llegada = [float("inf")] * g.V
    llegada[s] = hora * 60
    cambio = True
    while cambio:
        cambio = False
        for e in range(g.E):
            u, v = g.origen[e], g.destino[e]
            if llegada[u] == float("inf"):
                continue
            t = llegada[u] + g.minutos_arista(e, llegada[u])
            if t < llegada[v] - 1e-12:
                llegada[v] = t
                cambio = True
    return llegada


class TraficoPorHora(unittest.TestCase):
    def test_valores_de_la_tb1(self):
        import config
        self.assertEqual(config.factor_trafico("principal", 18), 2.8)
        self.assertEqual(config.factor_trafico("secundaria", 11), 1.2)
        self.assertEqual(config.factor_trafico("local", 3), 1.0)
        # a las 07:30 está a medio camino entre las 07:00 y las 08:00
        self.assertAlmostEqual(config.factor_trafico("principal", 7.5), 2.4)
        # después de medianoche sigue con el día siguiente
        self.assertEqual(config.factor_trafico("principal", 24 + 18), 2.8)


class RedReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import networkx as nx
        cls.nx = nx
        cls.g = gr.cargar()
        cls.G = nx.MultiDiGraph()
        cls.G.add_nodes_from(range(cls.g.V))
        for e in range(cls.g.E):
            cls.G.add_edge(cls.g.origen[e], cls.g.destino[e], key=e)

    def test_tamano(self):
        self.assertEqual((self.g.V, self.g.E), (3559, 7277))

    def test_kosaraju_igual_a_networkx(self):
        comp = alg.kosaraju(self.g)
        nuestras = {}
        for v, c in enumerate(comp):
            nuestras.setdefault(c, set()).add(v)
        de_nx = list(self.nx.strongly_connected_components(self.G))
        self.assertEqual(len(nuestras), len(de_nx))
        self.assertEqual(sorted(map(frozenset, nuestras.values()), key=min),
                         sorted(map(frozenset, de_nx), key=min))
        self.assertEqual(max(len(c) for c in nuestras.values()), 3478)

    def test_dijkstra_y_bellman_ford_igual_a_networkx(self):
        rnd = random.Random(42)
        for hora in (3, 11, 18):
            w = self.g.pesos(hora)
            H = self.nx.DiGraph()
            for e in range(self.g.E):
                u, v = self.g.origen[e], self.g.destino[e]
                if not H.has_edge(u, v) or w[e] < H[u][v]["w"]:
                    H.add_edge(u, v, w=w[e])
            for _ in range(15):
                s, t = rnd.randrange(self.g.V), rnd.randrange(self.g.V)
                r = alg.dijkstra(self.g, s, t, w)
                try:
                    esperado = self.nx.dijkstra_path_length(H, s, t, weight="w")
                except self.nx.NetworkXNoPath:
                    esperado = float("inf")
                self.assertAlmostEqual(r["costo"], esperado, places=9)
                if r["camino"] is not None:
                    # el camino es continuo y su costo coincide
                    nodo = s
                    for e in r["camino"]:
                        self.assertEqual(self.g.origen[e], nodo)
                        nodo = self.g.destino[e]
                    self.assertEqual(nodo, t)
                    self.assertAlmostEqual(sum(w[e] for e in r["camino"]), r["costo"], places=9)
            # Bellman-Ford es lento: solo un par por hora
            self.assertAlmostEqual(alg.bellman_ford(self.g, s, t, w)["costo"],
                                   alg.dijkstra(self.g, s, t, w)["costo"], places=9)

    def test_fifo(self):
        # salir un minuto después por una calle nunca hace llegar antes
        for e in range(self.g.E):
            for t in range(0, 24 * 60, 7):
                self.assertLessEqual(t + self.g.minutos_arista(e, t),
                                     t + 1 + self.g.minutos_arista(e, t + 1) + 1e-12)

    def test_dijkstra_tiempo(self):
        rnd = random.Random(7)
        for hora in (6.5, 8, 17.25, 23.5):
            s = rnd.randrange(self.g.V)
            llegada = bellman_ford_tiempo(self.g, s, hora)
            for _ in range(10):
                t = rnd.randrange(self.g.V)
                r = alg.dijkstra_tiempo(self.g, s, t, hora)
                self.assertAlmostEqual(r["costo"] + hora * 60, llegada[t], places=9)
                if r["camino"]:
                    tramos = alg.recorrer_en_tiempo(self.g, r["camino"], hora)
                    self.assertAlmostEqual(sum(tramos), r["costo"], places=9)

    def test_tiempo_igual_a_fijo_sin_trafico(self):
        # de 00:00 a 04:00 el factor es 1.0: los dos modelos dan lo mismo
        w = self.g.pesos(2)
        for s, t in [(0, 100), (500, 2000), (3000, 10)]:
            self.assertAlmostEqual(alg.dijkstra_tiempo(self.g, s, t, 1)["costo"],
                                   alg.dijkstra(self.g, s, t, w)["costo"], places=9)


if __name__ == "__main__":
    unittest.main()
