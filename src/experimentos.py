"""
Números de la sección 5 del informe (validación).

Toma pares al azar dentro de la componente más grande y mide cuánto tarda cada
algoritmo. También revisa si la ruta cambia entre las 11:00 y las 18:00, y si
cambia entre el modelo de hora fija y el dependiente del tiempo. Floyd-Warshall
se prueba solo en un pedazo de 1 km x 1 km porque con todo el grafo no acaba.

    python src/experimentos.py

Deja datos/resultados_experimentos.json y figuras/figura_tiempos.png.
"""

import json
import random
import statistics
import time
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import algoritmos as alg
import config
import grafo as gr

SEMILLA = 2026
N_PARES = 60
N_PARES_BELLMAN = 15      # Bellman-Ford es lento, con menos pares basta
HORAS = (11, 18)
HORAS_TRANSICION = (7.5, 9.5, 16.5, 20.5)  # cuando el tráfico sube o baja rápido
CENTRO_SUBGRAFO = (-12.094535, -77.033355)  # el mismo recuadro de la figura 2 de la TB1
LADO_SUBGRAFO_M = 1000


def medir(funcion, *args):
    t0 = time.perf_counter()
    r = funcion(*args)
    return r, (time.perf_counter() - t0) * 1000


def subgrafo(g, centro, lado_m):
    """Grafo solo con los nodos dentro de un cuadrado de lado_m metros."""
    lat0, lon0 = centro
    medio = lado_m / 2
    dentro = [v for v in range(g.V)
              if gr.haversine(lat0, lon0, g.lat[v], lon0) <= medio
              and gr.haversine(lat0, lon0, lat0, g.lon[v]) <= medio]
    sub = gr.Grafo()
    nuevo = {}
    for v in dentro:
        nuevo[v] = sub.V
        sub.agregar_nodo(g.ids[v], g.lat[v], g.lon[v], g.distrito[v])
    for e in range(g.E):
        u, v = g.origen[e], g.destino[e]
        if u in nuevo and v in nuevo:
            sub.agregar_arista(nuevo[u], nuevo[v], g.longitud[e], g.tipo[e], g.nombre[e])
    return sub


def main():
    rnd = random.Random(SEMILLA)
    g = gr.cargar()

    t0 = time.perf_counter()
    comp = alg.kosaraju(g)
    ms_kosaraju = (time.perf_counter() - t0) * 1000
    tamanos = Counter(comp)
    principal = tamanos.most_common(1)[0][0]
    nodos_principal = [v for v in range(g.V) if comp[v] == principal]

    pares = []
    while len(pares) < N_PARES:
        s, t = rnd.choice(nodos_principal), rnd.choice(nodos_principal)
        if s != t:
            pares.append((s, t))

    pesos = {h: g.pesos(h) for h in HORAS}
    tiempos = {"dijkstra": [], "dijkstra_tiempo": [], "bfs": [], "bellman_ford": []}
    diferencia_modelos = []
    rutas_distintas_modelos = 0
    extraidos = []
    cambios_ruta = 0
    aumento = []
    bfs_mas_lento = []

    for i, (s, t) in enumerate(pares):
        rutas = {}
        for h in HORAS:
            r, ms = medir(alg.dijkstra, g, s, t, pesos[h])
            tiempos["dijkstra"].append(ms)
            extraidos.append(r["extraidos"])
            rutas[h] = r
            b, ms = medir(alg.bfs, g, s, t, pesos[h])
            tiempos["bfs"].append(ms)
            bfs_mas_lento.append(b["costo"] / r["costo"] - 1)
            if i < N_PARES_BELLMAN:
                bf, ms = medir(alg.bellman_ford, g, s, t, pesos[h])
                tiempos["bellman_ford"].append(ms)
                assert abs(bf["costo"] - r["costo"]) < 1e-9, "Bellman-Ford y Dijkstra no coinciden"
        for h in HORAS_TRANSICION:
            fijo = alg.dijkstra(g, s, t, g.pesos(h))
            td, ms = medir(alg.dijkstra_tiempo, g, s, t, h)
            tiempos["dijkstra_tiempo"].append(ms)
            diferencia_modelos.append(abs(td["costo"] - fijo["costo"]))
            rutas_distintas_modelos += td["camino"] != fijo["camino"]
        if rutas[11]["camino"] != rutas[18]["camino"]:
            cambios_ruta += 1
        aumento.append(rutas[18]["costo"] / rutas[11]["costo"] - 1)

    # Floyd-Warshall en el pedazo chico, y revisamos que dé lo mismo que Dijkstra
    sub = subgrafo(g, CENTRO_SUBGRAFO, LADO_SUBGRAFO_M)
    w_sub = sub.pesos(18)
    d, ms_floyd = medir(alg.floyd_warshall, sub, w_sub)
    coinciden = True
    muestras = [(rnd.randrange(sub.V), rnd.randrange(sub.V)) for _ in range(300)]
    for s, t in muestras:
        c = alg.dijkstra(sub, s, t, w_sub)["costo"]
        if not (c == d[s][t] or abs(c - d[s][t]) < 1e-9):
            coinciden = False
    ms_dijkstra_sub = statistics.mean(medir(alg.dijkstra, sub, s, t, w_sub)[1] for s, t in muestras[:50])

    resumen = {
        "V": g.V, "E": g.E,
        "kosaraju": {"ms": round(ms_kosaraju, 2), "componentes": len(tamanos),
                     "mayor_componente": tamanos[principal],
                     "nodos_fuera": g.V - tamanos[principal]},
        "pares": N_PARES, "horas": HORAS,
        "ms_promedio": {k: round(statistics.mean(v), 3) for k, v in tiempos.items()},
        "ms_mediana": {k: round(statistics.median(v), 3) for k, v in tiempos.items()},
        "dijkstra_nodos_extraidos_promedio": round(statistics.mean(extraidos), 1),
        "rutas_que_cambian_11_vs_18": cambios_ruta,
        "aumento_tiempo_18_vs_11_pct": round(100 * statistics.mean(aumento), 1),
        "bfs_mas_lento_que_dijkstra_pct": round(100 * statistics.mean(bfs_mas_lento), 1),
        "bellman_ford_igual_a_dijkstra": True,
        "modelo_tiempo_vs_fijo": {
            "horas": HORAS_TRANSICION,
            "consultas": len(diferencia_modelos),
            "diferencia_promedio_min": round(statistics.mean(diferencia_modelos), 2),
            "diferencia_maxima_min": round(max(diferencia_modelos), 2),
            "rutas_distintas": rutas_distintas_modelos,
        },
        "floyd_warshall_subgrafo": {"V": sub.V, "E": sub.E, "ms": round(ms_floyd, 1),
                                    "dijkstra_ms_promedio": round(ms_dijkstra_sub, 3),
                                    "coincide_con_dijkstra": coinciden},
    }
    with open(config.CARPETA_DATOS / "resultados_experimentos.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    # gráfico de barras (en escala log, si no Bellman-Ford aplasta a los demás)
    nombres = ["BFS", "Dijkstra (hora fija)", "Dijkstra (dependiente\ndel tiempo)", "Bellman-Ford"]
    valores = [resumen["ms_promedio"][k] for k in ("bfs", "dijkstra", "dijkstra_tiempo", "bellman_ford")]
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=200)
    barras = ax.barh(nombres, valores, color=["#94a3b8", "#94a3b8", "#c2410c", "#94a3b8"], height=0.55)
    ax.set_xscale("log")
    ax.set_xlabel("Tiempo promedio por consulta (ms, escala logarítmica)")
    for b, v in zip(barras, valores):
        ax.text(v * 1.15, b.get_y() + b.get_height() / 2, f"{v:,.1f} ms".replace(".", ","),
                va="center", fontsize=9)
    ax.set_xlim(right=max(valores) * 6)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(config.CARPETA_FIGURAS / "figura_tiempos.png", bbox_inches="tight")

    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
