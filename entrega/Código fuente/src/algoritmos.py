"""
Algoritmos del trabajo. Todos reciben un Grafo de grafo.py.

El principal es dijkstra_tiempo. Los demás están para comparar o verificar:
dijkstra (hora fija, como en la TB1), bfs, bellman_ford y floyd_warshall.
kosaraju se usa para saber si hay ruta de vuelta.

Las funciones de ruta devuelven un dict con "costo", "camino" (lista de aristas)
y contadores que usamos en experimentos.py.
"""

import heapq
from collections import deque

INF = float("inf")


def reconstruir(pred_arista, origen, destino, grafo):
    """Va desde el destino hacia atrás con pred y devuelve las aristas en orden."""
    camino = []
    v = destino
    while v != origen:
        e = pred_arista[v]
        if e == -1:
            return None  # se cortó: no hay camino
        camino.append(e)
        v = grafo.origen[e]
    camino.reverse()
    return camino

# Dijkstra con cola de prioridad (min-heap)
def dijkstra(grafo, origen, destino, pesos):
    dist = [INF] * grafo.V
    pred = [-1] * grafo.V
    visitado = [False] * grafo.V
    dist[origen] = 0.0
    heap = [(0.0, origen)]
    extraidos = relajaciones = 0

    while heap:
        d, u = heapq.heappop(heap)
        if visitado[u]:
            continue  # ya lo sacamos antes con una distancia menor
        visitado[u] = True
        extraidos += 1
        if u == destino:
            break  # llegamos, no hace falta seguir
        for e in grafo.ady[u]:
            v = grafo.destino[e]
            nd = d + pesos[e]
            relajaciones += 1
            if nd < dist[v]:
                dist[v] = nd
                pred[v] = e
                heapq.heappush(heap, (nd, v))

    camino = reconstruir(pred, origen, destino, grafo) if dist[destino] < INF else None
    return {"costo": dist[destino], "camino": camino,
            "extraidos": extraidos, "relajaciones": relajaciones}


# Dijkstra dependiente del tiempo
# en vez de la distancia, cada nodo guarda la hora a la que llegamos (en minutos).
# el peso de una calle se calcula con la hora en que entramos a ella:
#   llegada(v) = llegada(u) + minutos(e, llegada(u))
# funciona porque se cumple FIFO (entrar más tarde nunca te hace salir antes),
# eso lo revisa test_fifo en tests/test_algoritmos.py
def dijkstra_tiempo(grafo, origen, destino, hora_salida):
    salida = hora_salida * 60  # en minutos desde las 00:00
    llegada = [INF] * grafo.V
    pred = [-1] * grafo.V
    visitado = [False] * grafo.V
    llegada[origen] = salida
    heap = [(salida, origen)]
    extraidos = relajaciones = 0

    while heap:
        t, u = heapq.heappop(heap)
        if visitado[u]:
            continue
        visitado[u] = True
        extraidos += 1
        if u == destino:
            break
        for e in grafo.ady[u]:
            v = grafo.destino[e]
            nt = t + grafo.minutos_arista(e, t)  # el tráfico depende de la hora t
            relajaciones += 1
            if nt < llegada[v]:
                llegada[v] = nt
                pred[v] = e
                heapq.heappush(heap, (nt, v))

    if llegada[destino] == INF:
        return {"costo": INF, "camino": None, "extraidos": extraidos, "relajaciones": relajaciones}
    camino = reconstruir(pred, origen, destino, grafo)
    return {"costo": llegada[destino] - salida, "camino": camino, "llegada_min": llegada[destino],
            "extraidos": extraidos, "relajaciones": relajaciones}


def recorrer_en_tiempo(grafo, camino, hora_salida):
    """Minutos de cada arista de un camino ya hecho, saliendo a esa hora.
    Lo usamos para medir la ruta de BFS con el mismo tráfico."""
    t = hora_salida * 60
    tiempos = []
    for e in camino:
        m = grafo.minutos_arista(e, t)
        tiempos.append(m)
        t += m
    return tiempos


# Kosaraju con DFS iterativo (con recursión Python se cae por el límite de 1000)
def kosaraju(grafo):
    """comp[v] dice en qué componente fuertemente conexa está v."""
    n = grafo.V

    # primera pasada. DFS normal, guardamos el orden en que terminan los nodos
    visitado = [False] * n
    orden = []
    for s in range(n):
        if visitado[s]:
            continue
        visitado[s] = True
        pila = [(s, 0)]  # (nodo, por cuál de sus aristas vamos)
        while pila:
            u, i = pila[-1]
            if i < len(grafo.ady[u]):
                pila[-1] = (u, i + 1)
                v = grafo.destino[grafo.ady[u][i]]
                if not visitado[v]:
                    visitado[v] = True
                    pila.append((v, 0))
            else:
                pila.pop()
                orden.append(u)  # ya no tiene vecinos sin visitar

    # segunda pasada. DFS en el grafo al revés, empezando por el último que terminó.
    # todo lo que se alcanza desde s es su componente
    comp = [-1] * n
    c = 0
    for s in reversed(orden):
        if comp[s] != -1:
            continue
        comp[s] = c
        pila = [s]
        while pila:
            u = pila.pop()
            for e in grafo.ady_inv[u]:
                v = grafo.origen[e]
                if comp[v] == -1:
                    comp[v] = c
                    pila.append(v)
        c += 1
    return comp


# BFS: la ruta con menos cuadras, sin importar el tiempo
def bfs(grafo, origen, destino, pesos=None):
    pred = [-1] * grafo.V
    visto = [False] * grafo.V
    visto[origen] = True
    cola = deque([origen])
    extraidos = relajaciones = 0
    while cola:
        u = cola.popleft()
        extraidos += 1
        if u == destino:
            break
        for e in grafo.ady[u]:
            v = grafo.destino[e]
            relajaciones += 1
            if not visto[v]:
                visto[v] = True
                pred[v] = e
                cola.append(v)

    camino = reconstruir(pred, origen, destino, grafo) if visto[destino] else None
    costo = INF
    if camino is not None:
        costo = sum(pesos[e] for e in camino) if pesos else len(camino)
    return {"costo": costo, "camino": camino,
            "extraidos": extraidos, "relajaciones": relajaciones}


# Bellman-Ford. si en una pasada no cambia nada, ya terminó
def bellman_ford(grafo, origen, destino, pesos):
    dist = [INF] * grafo.V
    pred = [-1] * grafo.V
    dist[origen] = 0.0
    relajaciones = pasadas = 0
    for _ in range(grafo.V - 1):
        pasadas += 1
        cambio = False
        for e in range(grafo.E):
            u = grafo.origen[e]
            if dist[u] == INF:
                continue
            relajaciones += 1
            nd = dist[u] + pesos[e]
            v = grafo.destino[e]
            if nd < dist[v]:
                dist[v] = nd
                pred[v] = e
                cambio = True
        if not cambio:
            break

    camino = reconstruir(pred, origen, destino, grafo) if dist[destino] < INF else None
    return {"costo": dist[destino], "camino": camino,
            "pasadas": pasadas, "relajaciones": relajaciones}


# Floyd-Warshall. arma una matriz V x V, así que solo lo usamos con un subgrafo chico
def floyd_warshall(grafo, pesos):
    n = grafo.V
    d = [[INF] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = 0.0
    for e in range(grafo.E):
        u, v = grafo.origen[e], grafo.destino[e]
        if pesos[e] < d[u][v]:
            d[u][v] = pesos[e]
    for k in range(n):
        dk = d[k]
        for i in range(n):
            dik = d[i][k]
            if dik == INF:
                continue
            di = d[i]
            for j in range(n):
                if dik + dk[j] < di[j]:
                    di[j] = dik + dk[j]
    return d


# para mostrar la ruta en la interfaz
def resumen_ruta(grafo, camino, minutos):
    """Junta los tramos seguidos de la misma calle.
    minutos[i] es lo que tarda camino[i] (sale de recorrer_en_tiempo)."""
    tramos = []
    for e, m in zip(camino, minutos):
        nombre = grafo.nombre[e] or "Sin nombre"
        if tramos and tramos[-1]["calle"] == nombre:
            t = tramos[-1]
            t["metros"] += grafo.longitud[e]
            t["minutos"] += m
        else:
            tramos.append({"calle": nombre, "tipo": grafo.tipo[e],
                           "metros": grafo.longitud[e], "minutos": m})
    return {
        "minutos": sum(minutos),
        "metros": sum(grafo.longitud[e] for e in camino),
        "aristas": len(camino),
        "calles": tramos,
    }
