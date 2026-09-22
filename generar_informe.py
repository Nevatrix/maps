"""
Genera informe_angel.md (Secciones 2 y 3 + Anexos + Referencias).

Todas las cifras y tablas se calculan desde datos/nodos.csv y datos/aristas.csv,
más los metadatos que escriben descargar_red.py (datos/metadatos.json) y
visualizar.py (datos/estadisticas_figuras.json). Nada se escribe a mano.

Uso:  python generar_informe.py   (después de descargar_red.py y visualizar.py)
"""

import json
import os

import pandas as pd

import config

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
FIGURAS = ["figuras/figura1.png", "figuras/figura2.png", "figuras/figura3.png"]
ANEXOS = ["config.py", "descargar_red.py", "visualizar.py"]


def miles(n):
    return f"{n:,}".replace(",", " ")


def decimal(x, d=1):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def fecha_larga(iso):
    a, m, d = iso.split("-")
    return f"{int(d)} de {MESES[int(m) - 1]} de {a}"


def enumerar(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def tabla_resumen(nodos, aristas):
    filas = [("Total de nodos (V)", miles(len(nodos)), "100,0 %"),
             ("Total de aristas (E)", miles(len(aristas)), "100,0 %")]
    for d, n in nodos["distrito"].value_counts().reindex(
            [d for d in config.DISTRITOS + [config.DISTRITO_RESPALDO]
             if d in set(nodos["distrito"])]).items():
        filas.append((f"Nodos en {d}", miles(n), decimal(100 * n / len(nodos)) + " %"))
    for t in config.TIPOS_VIA:
        n = int((aristas["tipo_via"] == t).sum())
        filas.append((f"Aristas de vía {t} ({config.VELOCIDAD_KMH[t]} km/h)", miles(n),
                      decimal(100 * n / len(aristas)) + " %"))
    n1 = int(aristas["un_solo_sentido"].sum())
    filas.append(("Aristas de un solo sentido", miles(n1), decimal(100 * n1 / len(aristas)) + " %"))
    filas.append(("Longitud total de las aristas", decimal(aristas["longitud_m"].sum() / 1000) + " km", "—"))
    lineas = ["| Indicador | Valor | % del total |", "|---|---:|---:|"]
    lineas += [f"| {a} | {b} | {c} |" for a, b, c in filas]
    return "\n".join(lineas)


def tabla_validacion(meta):
    lineas = ["| Distrito | Nodos totales | Intersecciones reales (street_count ≥ 3) | ¿≥ 500? |",
              "|---|---:|---:|:---:|"]
    for d, c in meta["conteos"].items():
        minimo = config.MIN_INTERSECCIONES_TOTAL if d == "TOTAL" else config.MIN_INTERSECCIONES_DISTRITO
        ok = "Sí" if c["intersecciones"] >= minimo else "No"
        nombre = f"**Total** (mín. {miles(minimo)})" if d == "TOTAL" else d
        lineas.append(f"| {nombre} | {miles(c['nodos_totales'])} | {miles(c['intersecciones'])} | {ok} |")
    return "\n".join(lineas)


def tabla_factores():
    lineas = ["| Horario | Principal | Secundaria | Local |", "|---|:---:|:---:|:---:|"]
    for ini, fin, f in config.FRANJAS_TRAFICO:
        lineas.append(f"| {ini:02d}:00–{fin:02d}:59 | {decimal(f['principal'])} | "
                      f"{decimal(f['secundaria'])} | {decimal(f['local'])} |")
    return "\n".join(lineas)


def main():
    nodos = pd.read_csv("datos/nodos.csv", encoding="utf-8")
    aristas = pd.read_csv("datos/aristas.csv", encoding="utf-8")
    with open("datos/metadatos.json", encoding="utf-8") as f:
        meta = json.load(f)
    with open("datos/estadisticas_figuras.json", encoding="utf-8") as f:
        est = json.load(f)

    V, E = len(nodos), len(aristas)
    distritos = meta["distritos"]
    fecha = fecha_larga(meta["fecha_descarga"])
    hv = meta["validacion_haversine"]
    pct_1s = 100 * aristas["un_solo_sentido"].mean()
    n_2s = int((~aristas["un_solo_sentido"]).sum())
    av = meta["verificacion_avenidas"]
    tot = meta["conteos"]["TOTAL"]
    h1, h2 = 11, 18
    pt = est["por_tipo"]
    f11 = {t: config.factor_trafico(t, h1) for t in config.TIPOS_VIA}
    f18 = {t: config.factor_trafico(t, h2) for t in config.TIPOS_VIA}
    ejemplo = config.peso_minutos(500, "principal", h1), config.peso_minutos(500, "principal", h2)

    md = f"""# 2. Descripción del Conjunto de Datos (Dataset)

## 2.1. Origen de los Datos

Los datos provienen de OpenStreetMap (OSM), una base de datos geográfica colaborativa y abierta que cartografía calles, edificaciones y otros elementos del territorio a partir de aportes voluntarios, imágenes satelitales y trazas GPS (OpenStreetMap contributors, 2026). Cada vía se almacena como una secuencia de puntos con coordenadas geográficas y un conjunto de etiquetas; entre ellas, `highway` (jerarquía de la vía), `oneway` (sentido de circulación) y `name` (nombre de la calle).

La red vial se descargó el {fecha} con la biblioteca de Python OSMnx, versión {meta['osmnx_version']} (Boeing, 2017), que consulta la API Overpass de OSM y construye directamente un grafo dirigido. Se usó la función `graph_from_place` con el tipo de red `"drive"`, que conserva solo las vías transitables por vehículos motorizados, para cada uno de los distritos de estudio: {enumerar(distritos)} (Lima, Perú). Los nombres se resolvieron con el formato `"<Distrito>, Lima, Peru"` sin necesidad de variantes. Para no perder las calles que cruzan el límite entre distritos se activó la opción `truncate_by_edge=True`; luego los tres grafos se unieron en un único multigrafo dirigido con NetworkX (Hagberg et al., 2008).

Cada nodo se asignó a un único distrito mediante un criterio geométrico: el distrito cuyo polígono oficial en OSM contiene la coordenada del nodo (en caso de caer exactamente sobre un límite compartido, se asigna al primero en el orden {enumerar(distritos)}; no se presentó ningún caso). Se descartaron {miles(meta['frontera']['fuera_eliminados'])} nodos situados fuera de los tres polígonos (extremos de calles que continúan hacia distritos vecinos como Lince o San Borja) y {meta['frontera']['aislados_eliminados']} nodos que quedaron aislados tras ese recorte. El resultado es una red débilmente conexa (una sola componente).

Los datos de OSM se distribuyen bajo la licencia Open Database License (ODbL) 1.0 (Open Data Commons, s. f.), que permite usarlos, modificarlos y redistribuirlos siempre que se reconozca la fuente y las bases de datos derivadas se compartan bajo la misma licencia. En consecuencia, todas las figuras y archivos derivados de este trabajo llevan la atribución «© Colaboradores de OpenStreetMap».

## 2.2. Motivo del Análisis

El grupo modela el tiempo de viaje en automóvil entre dos puntos de la ciudad, y ese modelo necesita tres datos por cada tramo de calle: su longitud, su sentido de circulación y su tipo de vía. OSM proporciona los tres de forma explícita. Las coordenadas reales de cada intersección permiten calcular la longitud de los tramos. La etiqueta `oneway` indica si el tramo solo puede recorrerse en un sentido, lo que es indispensable en una zona con muchas calles de sentido único. La etiqueta `highway` permite clasificar cada tramo en una de las tres categorías del modelo de pesos del grupo:

- **Principal** (40 km/h): `motorway`, `trunk` y `primary` (incluidas sus variantes `_link`).
- **Secundaria** (30 km/h): `secondary` y `tertiary` (incluidas sus variantes `_link`).
- **Local** (25 km/h): `residential`, `living_street`, `unclassified`, `service` y cualquier otro valor.

Cuando un tramo tiene varios valores de `highway`, se toma el de mayor jerarquía. Como ajuste del modelo, se clasifican como principales todas las aristas de Av. Javier Prado y Av. Arequipa, que el grupo considera avenidas principales. En OSM, Av. Arequipa figura como `secondary` en sus {av['Arequipa']['aristas']} aristas, y {av['Javier Prado']['por_tipo_osm'].get('secundaria', 0)} de las {av['Javier Prado']['aristas']} aristas de Av. Javier Prado (carriles auxiliares de su extremo este) también figuran como `secondary`. En total se reclasificaron {meta['aristas_reclasificadas_por_nombre']} aristas, y se verificó que el 100 % de las aristas de ambas avenidas quedara como «principal».

Además, la zona es adecuada porque cumple holgadamente el tamaño mínimo exigido. Se contaron como intersecciones reales los nodos donde confluyen al menos tres calles (`street_count ≥ 3`); los demás nodos son extremos de calles sin salida o puntos intermedios:

{tabla_validacion(meta)}

El requisito (mínimo {miles(config.MIN_INTERSECCIONES_TOTAL)} intersecciones en total y {config.MIN_INTERSECCIONES_DISTRITO} por distrito) se cumple tanto contando todos los nodos como contando solo intersecciones reales. Por ello no fue necesario incorporar el distrito de respaldo ({config.DISTRITO_RESPALDO}).

## 2.3. Relación con grafos

La red vial se representa como un grafo dirigido y ponderado G = (V, E):

- **Nodo (vértice):** cada intersección de calles (o extremo de una calle sin salida), identificada por su `id` de OSM y sus coordenadas (latitud, longitud).
- **Arista:** cada tramo de calle comprendido entre dos esquinas consecutivas, orientado en el sentido en que puede circular un vehículo.
- **Peso:** el tiempo en minutos necesario para recorrer el tramo, calculado con la fórmula del grupo:

  tiempo (min) = (longitud ÷ velocidad) × factor de tráfico

  donde la velocidad depende del tipo de vía y el factor de tráfico depende del tipo de vía y de la hora, según la siguiente tabla:

{tabla_factores()}

Como el peso cambia con la hora, el archivo de aristas no guarda un peso fijo, sino la longitud y el tipo de vía; el peso se calcula en el momento de la consulta con la función `peso_minutos(longitud_m, tipo_via, hora)` de `config.py` (Anexo A). Por ejemplo, 500 m de avenida principal toman {decimal(ejemplo[0], 2)} min a las 11:00 y {decimal(ejemplo[1], 2)} min a las 18:00.

La longitud de cada arista se calculó con una implementación propia de la fórmula de Haversine (radio terrestre de 6 371 000 m). Se sumó la distancia entre los puntos consecutivos de la geometría de la calle y, cuando la arista no tiene geometría, se usó la distancia directa entre sus dos nodos. Como validación, estas longitudes se compararon con la columna `length` calculada por OSMnx. La diferencia absoluta promedio fue de {decimal(hv['dif_media_m'], 4)} m por arista (máximo {decimal(hv['dif_max_m'], 3)} m), y la longitud total de la red fue de {decimal(hv['longitud_total_haversine_km'], 3)} km, frente a {decimal(hv['longitud_total_osmnx_km'], 3)} km según OSMnx. La mínima diferencia restante se explica porque OSMnx usa un radio terrestre de 6 371 009 m.

El grafo es **dirigido** porque el sentido de circulación restringe los recorridos posibles: una calle de un solo sentido se representa con una única arista (u → v), de modo que no existe el arco inverso (v → u), mientras que una calle de doble sentido se representa con dos aristas opuestas (u → v y v → u) de igual longitud. En el conjunto de datos, el {decimal(pct_1s)} % de las aristas corresponde a tramos de un solo sentido y las {miles(n_2s)} restantes corresponden a calles de doble sentido, representadas como parejas de aristas opuestas. Es un **multigrafo**, porque puede haber más de una arista entre el mismo par de nodos ({meta['aristas_paralelas']} aristas paralelas, p. ej. dos calzadas distintas) y {meta['lazos']} lazos (tramos que salen y regresan a la misma esquina, como retornos o calles en bucle). Su mayor componente fuertemente conexa abarca {miles(meta['mayor_componente_fuerte'])} de los {miles(V)} nodos.

La siguiente tabla resume el conjunto de datos final. Fue generada automáticamente a partir de `datos/nodos.csv` (columnas `id, latitud, longitud, distrito`) y `datos/aristas.csv` (columnas `origen, destino, longitud_m, un_solo_sentido, tipo_via, nombre_calle`):

**Tabla 1**

*Resumen del conjunto de datos*

{tabla_resumen(nodos, aristas)}

*Nota.* Elaboración propia con datos de © Colaboradores de OpenStreetMap, descargados el {fecha}. En `nombre_calle`, los tramos sin nombre en OSM figuran como «Sin nombre» ({miles(int((aristas['nombre_calle'] == 'Sin nombre').sum()))} aristas).

# 3. Visualización del conjunto de datos (Grafo)

Las tres figuras se generan con el script `visualizar.py` (Anexo C), que lee únicamente los archivos CSV del conjunto de datos, sin volver a consultar OSM. Las técnicas empleadas son las siguientes:

- **Lectura y proyección:** los CSV se cargan con pandas y las coordenadas geográficas (WGS 84) se proyectan con pyproj al sistema UTM zona 18 Sur (EPSG:32718), que expresa las posiciones en metros. Así las distancias se conservan en el dibujo y es posible trazar un recuadro exacto de 1 km × 1 km y barras de escala.
- **Dibujo del grafo:** se usa matplotlib (Hunter, 2007). Cada arista se traza como un segmento recto entre sus dos nodos mediante `LineCollection`, que representa el grafo tal como lo verán los algoritmos y no la curvatura real de la calle. Las figuras se exportan en PNG a 300 dpi.
- **Criterio de color:** en la Figura 1 se usa una paleta categórica de tres colores distinguibles por personas con daltonismo (un color por distrito). En la Figura 2 se usa una rampa de un solo tono (azul claro a oscuro) combinada con el grosor de línea para expresar la jerarquía de la vía. En la Figura 3 se usa una rampa continua del mismo tono para el factor de tráfico, normalizada entre el mínimo (1,0) y el máximo (2,8) de la tabla del grupo, de modo que ambos paneles comparten exactamente la misma escala de colores.

![Figura 1. Red vial dirigida de Miraflores, San Isidro y Surquillo coloreada por distrito]({FIGURAS[0]})

*Figura 1.* Red vial dirigida de {enumerar(distritos)} coloreada por distrito. Elaboración propia con datos de © Colaboradores de OpenStreetMap.

La figura muestra el grafo completo: {miles(V)} nodos y {miles(E)} aristas, con cada distrito en un color, una barra de escala de 1 km y el recuadro de la zona ampliada en las figuras 2 y 3. Se aprecia la trama en damero de Surquillo y del centro de Miraflores frente a la trama más irregular de San Isidro, así como los grandes ejes viales que estructuran la zona (Vía Expresa, Av. Arequipa, Av. Javier Prado). Las aristas que cruzan el límite entre distritos conectan las tres subredes, por lo que el grafo es una sola componente sobre la que pueden calcularse rutas entre cualquier par de distritos.

![Figura 2. Zoom de 1 km × 1 km en torno al cruce de Av. Javier Prado y Av. Arequipa, por tipo de vía]({FIGURAS[1]})

*Figura 2.* Zoom de 1 km × 1 km en torno al cruce de Av. Javier Prado y Av. Arequipa, coloreado por tipo de vía. Elaboración propia con datos de © Colaboradores de OpenStreetMap.

Se eligió esta zona de San Isidro porque en ella se cruzan las dos avenidas principales que el grupo usa como referencia, así que en un área pequeña conviven los tres tipos de vía. El cruce ({decimal(-est['cruce']['latitud'], 5)}° S, {decimal(-est['cruce']['longitud'], 5)}° O) se calculó a partir de los CSV como la intersección geométrica de las aristas de ambas avenidas, porque en OSM es un cruce a desnivel y sus calzadas no comparten ningún nodo. La ventana se desplazó {est['desplazamiento_sur_m']} m al sur del cruce porque al norte de Javier Prado comienza Lince, que no forma parte del área de estudio. El recuadro contiene {est['aristas_zoom']} aristas: {pt['principal']['aristas']} principales, {pt['secundaria']['aristas']} secundarias y {pt['local']['aristas']} locales. Las avenidas principales aparecen con doble línea porque cada calzada es una arista de un solo sentido.

![Figura 3. Mismo zoom a las 11:00 y a las 18:00 coloreado por factor de tráfico]({FIGURAS[2]})

*Figura 3.* Mismo zoom a las 11:00 y a las 18:00 coloreado según el factor de tráfico del modelo del grupo, con escala de color común. Elaboración propia con datos de © Colaboradores de OpenStreetMap.

El tráfico que muestra esta figura es **modelado** con la tabla de factores del grupo, a través de la función `factor_trafico` de `config.py`, y **no medido en tiempo real**: todas las vías de un mismo tipo reciben el mismo factor a una misma hora. A las 11:00 los factores son {decimal(f11['principal'])}, {decimal(f11['secundaria'])} y {decimal(f11['local'])} (principal, secundaria y local). A las 18:00 suben a {decimal(f18['principal'])}, {decimal(f18['secundaria'])} y {decimal(f18['local'])}, por eso las avenidas principales pasan al tono más oscuro de la escala. Recorrer una vez cada una de las {est['aristas_zoom']} aristas del zoom ({decimal(est['longitud_zoom_km'], 1)} km) toma {decimal(est['min_total_11'])} min a las 11:00 y {decimal(est['min_total_18'])} min a las 18:00, un aumento del {decimal(est['aumento_pct'])} %. El aumento se concentra en las vías principales, cuyo tiempo se multiplica por {decimal(f18['principal'] / f11['principal'])} ({decimal(pt['principal']['min_11'])} → {decimal(pt['principal']['min_18'])} min), mientras que en las locales sube solo un {decimal(100 * (f18['local'] / f11['local'] - 1), 0)} % ({decimal(pt['local']['min_11'])} → {decimal(pt['local']['min_18'])} min). En hora punta, por tanto, a un algoritmo de ruta más corta le puede convenir desviarse por calles secundarias o locales.

## Anexos
"""
    for letra, archivo in zip("ABC", ANEXOS):
        with open(archivo, encoding="utf-8") as f:
            codigo = f.read().rstrip()
        md += f"\n### Anexo {letra}. `{archivo}`\n\n```python\n{codigo}\n```\n"

    md += f"""
## Referencias

Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems, 65*, 126–139. https://doi.org/10.1016/j.compenvurbsys.2017.05.004

Hagberg, A. A., Schult, D. A., & Swart, P. J. (2008). Exploring network structure, dynamics, and function using NetworkX. En G. Varoquaux, T. Vaught, & J. Millman (Eds.), *Proceedings of the 7th Python in Science Conference* (pp. 11–15). https://doi.org/10.25080/TCWV9851

Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering, 9*(3), 90–95. https://doi.org/10.1109/MCSE.2007.55

Open Data Commons. (s. f.). *Open Database License (ODbL) v1.0*. Open Knowledge Foundation. https://opendatacommons.org/licenses/odbl/1-0/

OpenStreetMap contributors. (2026). *OpenStreetMap* [Conjunto de datos]. OpenStreetMap Foundation. Recuperado el {fecha}, de https://www.openstreetmap.org
"""
    with open("informe_angel.md", "w", encoding="utf-8") as f:
        f.write(md)

    faltantes = [p for p in FIGURAS if not os.path.isfile(p)]
    print("informe_angel.md generado.")
    print("Rutas de imágenes:", "todas existen" if not faltantes else f"FALTAN {faltantes}")
    if faltantes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
