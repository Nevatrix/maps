"""
Descarga la red vial de los distritos de estudio desde OpenStreetMap (OSMnx),
clasifica las vías, calcula longitudes con Haversine, valida los conteos y
exporta datos/nodos.csv y datos/aristas.csv.

Uso:  python descargar_red.py
"""

import json
import math
import os
from collections import Counter
from datetime import datetime

import networkx as nx
import osmnx as ox
import pandas as pd
from shapely.geometry import Point
from shapely.prepared import prep

import config

CARPETA_DATOS = "datos"
RADIO_TIERRA_M = 6_371_000

# Jerarquía de los valores de "highway": mayor número = mayor jerarquía.
JERARQUIA = {"principal": 3, "secundaria": 2, "local": 1}
HIGHWAY_PRINCIPAL = {"motorway", "trunk", "primary"}
HIGHWAY_SECUNDARIA = {"secondary", "tertiary"}


# --------------------------------------------------------------------------
# 1. Descarga
# --------------------------------------------------------------------------
def variantes_nombre(distrito):
    return [
        f"{distrito}, Lima, Peru",
        f"Distrito de {distrito}, Provincia de Lima, Perú",
        f"{distrito}, Provincia de Lima, Lima, Perú",
    ]


def descargar_distrito(distrito):
    """Descarga la red 'drive' de un distrito probando variantes del nombre.

    truncate_by_edge=True conserva las calles que cruzan el límite del distrito
    (sin esto cada distrito queda como una isla desconectada de sus vecinos).
    Devuelve el grafo, el nombre que funcionó y el polígono del distrito.
    """
    for nombre in variantes_nombre(distrito):
        try:
            G = ox.graph_from_place(nombre, network_type="drive", truncate_by_edge=True)
            poligono = ox.geocode_to_gdf(nombre).geometry.iloc[0]
            print(f"  [OK] '{nombre}': {len(G.nodes)} nodos, {len(G.edges)} aristas")
            return G, nombre, poligono
        except Exception as e:  # nombre no resuelto u otro error de geocodificación
            print(f"  [X]  '{nombre}' no funcionó: {e}")
    raise RuntimeError(f"No se pudo descargar el distrito {distrito}")


def construir_grafo(distritos):
    """Descarga cada distrito, asigna distrito a cada nodo y une todo en un MultiDiGraph.

    Criterio de frontera: cada nodo se asigna al distrito cuyo polígono oficial
    (OSM) lo contiene; si cae exactamente sobre el límite de dos polígonos, gana
    el primero según el orden de `distritos`. Los nodos que no caen en ningún
    polígono (extremos de calles que salen hacia Lince, San Borja, etc.) se
    eliminan junto con sus aristas, y también los nodos que quedan aislados.
    """
    grafos, nombres_usados, poligonos = [], {}, {}
    for d in distritos:
        print(f"Descargando {d}...")
        G, nombre, poligono = descargar_distrito(d)
        nombres_usados[d] = nombre
        poligonos[d] = prep(poligono)
        grafos.append(G)
    G = nx.compose_all(grafos)  # sigue siendo MultiDiGraph dirigido

    distrito_de, en_limite, fuera = {}, 0, []
    for n, datos in G.nodes(data=True):
        punto = Point(datos["x"], datos["y"])
        contenedores = [d for d in distritos if poligonos[d].covers(punto)]
        if not contenedores:
            fuera.append(n)
            continue
        en_limite += len(contenedores) > 1
        distrito_de[n] = contenedores[0]
    G.remove_nodes_from(fuera)
    aislados = list(nx.isolates(G))  # esquinas cuyas calles salían todas del área
    G.remove_nodes_from(aislados)
    nx.set_node_attributes(G, distrito_de, "distrito")
    # street_count lo calcula OSMnx antes de recortar, así que refleja las calles
    # reales que llegan a cada esquina (incluidas las que salen del área).
    print(f"Grafo unido: {len(G.nodes)} nodos, {len(G.edges)} aristas "
          f"({len(fuera)} nodos fuera del área y {len(aislados)} aislados eliminados, "
          f"{en_limite} nodos en límite compartido)")
    return G, nombres_usados, {"fuera_eliminados": len(fuera), "aislados_eliminados": len(aislados),
                               "en_limite": en_limite}


# --------------------------------------------------------------------------
# 2. Clasificación de vías
# --------------------------------------------------------------------------
def clasificar_valor(highway):
    base = highway.replace("_link", "")
    if base in HIGHWAY_PRINCIPAL:
        return "principal"
    if base in HIGHWAY_SECUNDARIA:
        return "secundaria"
    return "local"  # residential, living_street, unclassified, service y otros


def clasificar_via(highway):
    """Tipo de vía del modelo; si 'highway' es lista, se toma la de mayor jerarquía."""
    valores = highway if isinstance(highway, list) else [highway]
    tipos = [clasificar_valor(str(v)) for v in valores if v is not None]
    return max(tipos, key=JERARQUIA.get) if tipos else "local"


def es_avenida_principal(name):
    """True si algún nombre de la arista empieza con 'Avenida <X>' para X en
    config.AVENIDAS_PRINCIPALES (ajuste del grupo sobre la etiqueta de OSM)."""
    nombres = name if isinstance(name, list) else [name]
    return any(isinstance(n, str) and n.lower().startswith(f"avenida {a.lower()}")
               for n in nombres for a in config.AVENIDAS_PRINCIPALES)


# --------------------------------------------------------------------------
# 3. Haversine
# --------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Distancia en metros sobre la esfera entre dos puntos (grados decimales)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


def longitud_arista(G, u, v, datos):
    """Suma Haversine entre puntos consecutivos de la geometría (o u->v si no hay)."""
    if "geometry" in datos:
        puntos = [(lat, lon) for lon, lat in datos["geometry"].coords]
    else:
        puntos = [(G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"])]
    return sum(haversine(*puntos[i], *puntos[i + 1]) for i in range(len(puntos) - 1))


# --------------------------------------------------------------------------
# 4. Construcción de tablas
# --------------------------------------------------------------------------
def a_booleano(oneway):
    if isinstance(oneway, list):
        return any(a_booleano(o) for o in oneway)
    if isinstance(oneway, str):
        return oneway.lower() in ("yes", "true", "1", "-1")
    return bool(oneway)


def nombre_calle(name):
    if isinstance(name, list):
        return " / ".join(str(n) for n in name)
    if name is None or (isinstance(name, float) and math.isnan(name)) or name == "":
        return "Sin nombre"
    return str(name)


def tablas(G):
    nodos = pd.DataFrame(
        [(n, d["y"], d["x"], d["distrito"], d["street_count"]) for n, d in G.nodes(data=True)],
        columns=["id", "latitud", "longitud", "distrito", "street_count"],
    )
    filas = []
    for u, v, d in G.edges(data=True):
        tipo_osm = clasificar_via(d.get("highway", "unclassified"))
        tipo = "principal" if es_avenida_principal(d.get("name")) else tipo_osm
        filas.append({
            "origen": u,
            "destino": v,
            "longitud_m": round(longitud_arista(G, u, v, d), 2),
            "un_solo_sentido": a_booleano(d.get("oneway", False)),
            "tipo_via": tipo,
            "tipo_via_osm": tipo_osm,
            "nombre_calle": nombre_calle(d.get("name")),
            "highway_osm": d.get("highway"),
            "length_osmnx": d.get("length"),
        })
    return nodos, pd.DataFrame(filas)


# --------------------------------------------------------------------------
# 5. Verificaciones
# --------------------------------------------------------------------------
def verificar_avenidas(aristas):
    resultado = {}
    for avenida in ("Javier Prado", "Arequipa"):
        sel = aristas[aristas["nombre_calle"].str.contains(rf"\bAvenida {avenida}", case=False)]
        conteo_osm = sel["tipo_via_osm"].value_counts().to_dict()
        conteo = sel["tipo_via"].value_counts().to_dict()
        print(f"\nAv. {avenida}: {len(sel)} aristas "
              f"(nombres: {sorted(sel['nombre_calle'].unique())})")
        print(f"  solo con 'highway' de OSM: {conteo_osm}")
        for (hw, nom), k in Counter(zip(sel.loc[sel["tipo_via_osm"] != "principal", "highway_osm"].astype(str),
                                         sel.loc[sel["tipo_via_osm"] != "principal", "nombre_calle"])).most_common():
            print(f"    {k:3d} x highway={hw}  '{nom}'  (reclasificada por AVENIDAS_PRINCIPALES)")
        print(f"  clasificación final:       {conteo}")
        ok = len(sel) > 0 and (sel["tipo_via"] == "principal").all()
        print(f"  => Av. {avenida} sale como 'principal': {'SÍ' if ok else 'NO'}")
        resultado[avenida] = {"aristas": len(sel), "por_tipo_osm": conteo_osm,
                              "por_tipo_final": conteo, "principal_ok": bool(ok)}
    return resultado


def validar_haversine(aristas):
    dif = (aristas["longitud_m"] - aristas["length_osmnx"]).abs()
    rel = dif / aristas["length_osmnx"].where(aristas["length_osmnx"] > 0)
    res = {
        "dif_media_m": round(float(dif.mean()), 4),
        "dif_max_m": round(float(dif.max()), 4),
        "dif_relativa_media_pct": round(float(rel.mean() * 100), 4),
        "longitud_total_haversine_km": round(float(aristas["longitud_m"].sum() / 1000), 3),
        "longitud_total_osmnx_km": round(float(aristas["length_osmnx"].sum() / 1000), 3),
    }
    print("\nValidación Haversine vs. 'length' de OSMnx:")
    print(f"  diferencia absoluta promedio: {res['dif_media_m']} m "
          f"(máx. {res['dif_max_m']} m, relativa {res['dif_relativa_media_pct']} %)")
    print(f"  longitud total: Haversine {res['longitud_total_haversine_km']} km vs "
          f"OSMnx {res['longitud_total_osmnx_km']} km")
    return res


def conteos(nodos):
    tabla = nodos.groupby("distrito").agg(
        nodos_totales=("id", "size"),
        intersecciones=("street_count", lambda s: int((s >= 3).sum())),
    )
    tabla.loc["TOTAL"] = tabla.sum()
    return tabla


def cumple(tabla, columna):
    por_distrito = tabla.drop("TOTAL")[columna]
    return (tabla.loc["TOTAL", columna] >= config.MIN_INTERSECCIONES_TOTAL
            and (por_distrito >= config.MIN_INTERSECCIONES_DISTRITO).all())


def imprimir_validacion(tabla):
    print("\nValidación de conteos (mín. "
          f"{config.MIN_INTERSECCIONES_TOTAL} total, {config.MIN_INTERSECCIONES_DISTRITO} por distrito):")
    print(tabla.to_string())
    for col, desc in (("nodos_totales", "nodos totales"),
                      ("intersecciones", "intersecciones reales (street_count >= 3)")):
        print(f"  Con {desc}: {'CUMPLE' if cumple(tabla, col) else 'NO CUMPLE'}")
        bajos = tabla.drop("TOTAL")[tabla.drop("TOTAL")[col] < config.MIN_INTERSECCIONES_DISTRITO]
        if len(bajos):
            print(f"    distritos bajo {config.MIN_INTERSECCIONES_DISTRITO}: {bajos[col].to_dict()}")


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------
def main():
    os.makedirs(CARPETA_DATOS, exist_ok=True)
    fecha = datetime.now()

    distritos = list(config.DISTRITOS)
    G, nombres_usados, compartidos = construir_grafo(distritos)
    nodos, aristas = tablas(G)
    tabla = conteos(nodos)
    imprimir_validacion(tabla)

    # Criterio oficial: intersecciones reales. Si no se cumple, se agrega Barranco.
    if not cumple(tabla, "intersecciones"):
        print(f"\nNo se cumple el requisito: se agrega {config.DISTRITO_RESPALDO} y se regenera.")
        distritos.append(config.DISTRITO_RESPALDO)
        G, nombres_usados, compartidos = construir_grafo(distritos)
        nodos, aristas = tablas(G)
        tabla = conteos(nodos)
        imprimir_validacion(tabla)
        if not cumple(tabla, "intersecciones"):
            print("\nATENCIÓN: aun con el distrito de respaldo el requisito NO se cumple "
                  "(ver distritos bajo el mínimo arriba). No se fuerza el resultado.")

    avenidas = verificar_avenidas(aristas)
    haversine_val = validar_haversine(aristas)

    # Exportación (UTF-8) con las columnas pedidas.
    nodos[["id", "latitud", "longitud", "distrito"]].to_csv(
        os.path.join(CARPETA_DATOS, "nodos.csv"), index=False, encoding="utf-8")
    aristas[["origen", "destino", "longitud_m", "un_solo_sentido", "tipo_via",
             "nombre_calle"]].to_csv(
        os.path.join(CARPETA_DATOS, "aristas.csv"), index=False, encoding="utf-8")

    V, E = len(nodos), len(aristas)
    paralelas = E - len(set(zip(aristas["origen"], aristas["destino"])))
    lazos = int((aristas["origen"] == aristas["destino"]).sum())
    n_debiles = nx.number_weakly_connected_components(G)
    mayor_fuerte = len(max(nx.strongly_connected_components(G), key=len))

    metadatos = {
        "fecha_descarga": fecha.strftime("%Y-%m-%d"),
        "hora_descarga": fecha.strftime("%H:%M"),
        "osmnx_version": ox.__version__,
        "networkx_version": nx.__version__,
        "distritos": distritos,
        "nombres_usados": nombres_usados,
        "frontera": compartidos,
        "criterio_frontera": "polígono del distrito que contiene al nodo; en empate, el primero de la lista",
        "componentes_debiles": n_debiles,
        "mayor_componente_fuerte": mayor_fuerte,
        "conteos": tabla.astype(int).to_dict(orient="index"),
        "cumple_nodos_totales": bool(cumple(tabla, "nodos_totales")),
        "cumple_intersecciones": bool(cumple(tabla, "intersecciones")),
        "verificacion_avenidas": avenidas,
        "aristas_reclasificadas_por_nombre": int((aristas["tipo_via"] != aristas["tipo_via_osm"]).sum()),
        "validacion_haversine": haversine_val,
        "V": V, "E": E, "aristas_paralelas": paralelas, "lazos": lazos,
    }
    with open(os.path.join(CARPETA_DATOS, "metadatos.json"), "w", encoding="utf-8") as f:
        json.dump(metadatos, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 50)
    print("PARA JOEL")
    print("=" * 50)
    print(f"  Distritos: {', '.join(distritos)}")
    print(f"  V (nodos)   = {V}")
    print(f"  E (aristas) = {E}")
    print(f"  (incluye {paralelas} aristas paralelas u->v adicionales y {lazos} lazos u->u)")
    print(f"  Componentes débilmente conexas: {n_debiles}; "
          f"mayor componente fuertemente conexa: {mayor_fuerte} nodos")
    print(f"  Archivos: {CARPETA_DATOS}/nodos.csv, {CARPETA_DATOS}/aristas.csv")
    print("=" * 50)


if __name__ == "__main__":
    main()
