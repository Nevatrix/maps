"""
Interfaz gráfica (NiceGUI + Leaflet).

    python src/app.py    y abrir http://localhost:8080

Cada clic en el mapa se pasa a la esquina más cercana. Con el origen, el destino
y la hora se corre dijkstra_tiempo; BFS se corre aparte para comparar.
"""

import json
import os
import time

from nicegui import ui
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.prepared import prep

import algoritmos as alg
import config
import grafo as gr

# esto se carga una vez cuando arranca el servidor, no en cada consulta
G = gr.cargar()
COMPONENTE = alg.kosaraju(G)

# límites de los distritos: para dibujarlos y para saber si un clic cae adentro
with open(config.CARPETA_DATOS / "distritos.geojson", encoding="utf-8") as f:
    DISTRITOS = json.load(f)["features"]
ZONA = unary_union([shape(d["geometry"]) for d in DISTRITOS])
ZONA_PREP = prep(ZONA.buffer(0.0003))  # unos 30 m de margen en el borde
oeste, sur, este, norte = ZONA.bounds
LIMITES_MAPA = [[sur - 0.05, oeste - 0.04], [norte + 0.03, este + 0.04]]  # más margen abajo por el panel del celular


def anillo(coords_lonlat):
    """el GeoJSON viene como (lon, lat) y Leaflet quiere (lat, lon)"""
    return [(lat, lon) for lon, lat in coords_lonlat]


# para oscurecer lo de afuera: un rectángulo enorme con un hueco donde está la zona
MASCARA = [anillo([(-77.3, -11.8), (-76.7, -11.8), (-76.7, -12.4), (-77.3, -12.4)])]
for parte in getattr(ZONA, "geoms", [ZONA]):
    MASCARA.append(anillo(parte.exterior.coords))

CENTRO = (ZONA.centroid.y, ZONA.centroid.x)
EJEMPLO = config.EJEMPLO

# colores (el número es el contraste contra blanco)
ACENTO = "#C2410C"      # la ruta y los botones, 5.2:1
TINTA = "#0F172A"       # texto principal, 17.9:1
TINTA_2 = "#475569"     # texto secundario, 7.6:1
GRIS_RUTA = "#64748B"   # ruta de BFS, 4.8:1
GRIS_BARRA = "#CBD5E1"

ui.add_head_html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{ --acento: {ACENTO}; --tinta: {TINTA}; --tinta-2: {TINTA_2}; }}
  body {{ font-family: 'Plus Jakarta Sans', system-ui, sans-serif; color: var(--tinta); }}
  .nicegui-content {{ padding: 0; }}
  .num {{ font-variant-numeric: tabular-nums; }}
  .panel {{ position: fixed; z-index: 1000; top: 16px; left: 16px; bottom: 16px; width: 380px;
            background: #fff; border-radius: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.08), 0 8px 24px rgba(15,23,42,.12);
            overflow-y: auto; padding: 20px; gap: 18px; flex-wrap: nowrap; }}
  .asa {{ display: none; }}
  @media (max-width: 640px) {{
    .panel {{ top: auto; left: 0; right: 0; bottom: 0; width: auto; max-height: 46vh;
              border-radius: 20px 20px 0 0; padding: 4px 16px 20px; gap: 14px;
              transition: max-height .25s ease-out; }}
    .panel.expandido {{ max-height: 85vh; }}
    .asa {{ display: flex; justify-content: center; width: 100%; min-height: 28px; cursor: pointer;
            position: sticky; top: -4px; background: #fff; z-index: 1; }}
    .asa div {{ width: 40px; height: 5px; border-radius: 3px; background: #CBD5E1; margin-top: 10px; }}
    .titulo {{ display: none; }}
    .leaflet-bottom.leaflet-right {{ bottom: calc(46vh + 8px); }}
  }}
  .q-btn.dense {{ min-height: 44px; padding: 0 8px; }}
  .parada {{ border: 1.5px solid #E2E8F0; border-radius: 12px; padding: 10px 12px; cursor: pointer;
             min-height: 56px; transition: border-color .15s, background-color .15s; }}
  .parada:hover {{ background: #F8FAFC; }}
  .parada.activa {{ border-color: var(--acento); background: #FFF7F2; }}
  .parada:focus-visible, .asa:focus-visible {{ outline: 2px solid var(--acento); outline-offset: 2px; }}
  .letra {{ width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-weight: 700; font-size: 13px; flex-shrink: 0; }}
  .letra-a {{ background: #fff; color: var(--tinta); border: 2px solid var(--tinta); }}
  .letra-b {{ background: var(--acento); color: #fff; }}
  .etiqueta {{ font-size: 12px; font-weight: 600; letter-spacing: .02em; color: var(--tinta-2); text-transform: uppercase; }}
  /* mapa en gris para que se note la ruta */
  .mapa-base {{ filter: grayscale(.85) contrast(.92) brightness(1.04); }}
  .leaflet-tooltip.pin {{ background: transparent; border: 0; box-shadow: none; padding: 0;
                          font-weight: 700; font-size: 12px; }}
  .leaflet-tooltip.pin::before, .leaflet-tooltip.etiqueta-distrito::before {{ display: none; }}
  .pin-a {{ color: {TINTA}; }}
  .pin-b {{ color: #fff; }}
  .leaflet-tooltip.etiqueta-distrito {{ background: transparent; border: 0; box-shadow: none; padding: 0;
                                        color: #334155; font-weight: 700; font-size: 12px; letter-spacing: .06em;
                                        text-transform: uppercase; text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff; }}
  .leaflet-container {{ font-family: inherit; }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>
""", shared=True)


def nombre_cruce(v):
    """Nombre de la esquina con las calles que llegan a ella, p. ej. "Av. Arequipa y Calle X"."""
    calles = []
    for e in G.ady[v] + G.ady_inv[v]:
        n = G.nombre[e]
        if n and n != "Sin nombre" and n not in calles:
            calles.append(n)
    calles = [c.replace("Avenida ", "Av. ").replace("Jirón ", "Jr. ") for c in calles]
    # en OSM a veces sale "Calle Jean Paul Sartre" y también "Jean Paul Sartre"
    unicas = []
    for c in calles:
        base = c.removeprefix("Calle ")
        if all(base != u.removeprefix("Calle ") for u in unicas):
            unicas.append(c)
    if not unicas:
        return "Intersección sin nombre"
    return " y ".join(unicas[:2])


def dec(x, d=1):
    """12.5 -> '12,5'"""
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def reloj(hora):
    """18.25 -> '18:15'"""
    minutos = round(hora * 60) % (24 * 60)
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def horas_con(por_hora, valor):
    """Si varias horas seguidas dan lo mismo, devuelve el rango ('entre las 00:00 y las 03:00')."""
    horas = [h for h, m in enumerate(por_hora) if abs(m - valor) < 0.05]
    if len(horas) > 1 and horas[-1] - horas[0] == len(horas) - 1:
        return f"entre las {horas[0]:02d}:00 y las {horas[-1]:02d}:00"
    return f"a las {horas[0]:02d}:00"


def coords(camino):
    puntos = [(G.lat[G.origen[camino[0]]], G.lon[G.origen[camino[0]]])]
    puntos += [(G.lat[G.destino[e]], G.lon[G.destino[e]]) for e in camino]
    return puntos


@ui.page("/")
def pagina():
    ui.page_title("Rutas Lima")
    estado = {"origen": None, "destino": None, "activa": "origen", "hora": 18.0, "bfs": False}
    capas = []  # lo que dibujamos de la ruta, para poder borrarlo después

    # mapa
    mapa = ui.leaflet(center=CENTRO, zoom=14, options={
        "zoomControl": False, "minZoom": 12, "zoomSnap": 0.25, "zoomDelta": 0.5,
        "maxBounds": LIMITES_MAPA, "maxBoundsViscosity": 0.8,
    }).classes("w-full h-screen")
    mapa.clear_layers()
    etiquetas = []
    with mapa:
        mapa.tile_layer(
            url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            options={"maxZoom": 19, "className": "mapa-base",
                     "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
                                    'contributors (ODbL)'})
        # lo de afuera se oscurece y cada distrito tiene borde punteado y nombre
        mapa.generic_layer(name="polygon", args=[MASCARA, {
            "stroke": False, "fillColor": TINTA, "fillOpacity": 0.22, "interactive": False}])
        for d in DISTRITOS:
            geo = shape(d["geometry"])
            for parte in getattr(geo, "geoms", [geo]):
                mapa.generic_layer(name="polyline", args=[anillo(parte.exterior.coords), {
                    "color": TINTA_2, "weight": 1.5, "dashArray": "4 6", "interactive": False}])
            centro = geo.representative_point()
            nombre = mapa.generic_layer(name="circleMarker", args=[(centro.y, centro.x), {
                "radius": 0, "stroke": False, "fill": False, "interactive": False}])
            etiquetas.append((nombre, d["properties"]["distrito"]))

    def al_iniciar():
        # si esto se manda antes de que cargue el mapa, se pierde
        mapa.run_map_method(":addControl", "L.control.zoom({position: 'bottomright'})")
        for capa, texto in etiquetas:
            capa.run_method("bindTooltip", texto, {"permanent": True, "direction": "center",
                                                   "className": "etiqueta-distrito"})
        # sin esta espera el encuadre sale mal en celular
        ui.timer(0.4, encuadrar_zona, once=True)

    mapa.on("init", al_iniciar)

    def limpiar_mapa():
        for c in capas:
            mapa.remove_layer(c)
        capas.clear()

    def dibujar():
        limpiar_mapa()
        with mapa:
            r = estado.get("ruta")
            if r and estado["bfs"] and estado.get("ruta_bfs"):
                capas.append(mapa.generic_layer(name="polyline", args=[coords(estado["ruta_bfs"]),
                             {"color": GRIS_RUTA, "weight": 4, "dashArray": "6 8", "opacity": .9}]))
            if r and r["camino"]:
                pts = coords(r["camino"])
                capas.append(mapa.generic_layer(name="polyline", args=[pts, {"color": "#fff", "weight": 10}]))
                capas.append(mapa.generic_layer(name="polyline", args=[pts, {"color": ACENTO, "weight": 6}]))
            for clave, letra, relleno, borde in (("origen", "A", "#fff", TINTA), ("destino", "B", ACENTO, "#fff")):
                v = estado[clave]
                if v is None:
                    continue
                pin = mapa.generic_layer(name="circleMarker", args=[(G.lat[v], G.lon[v]), {
                    "radius": 11, "fillColor": relleno, "fillOpacity": 1, "color": borde, "weight": 2.5}])
                pin.run_method("bindTooltip", letra, {"permanent": True, "direction": "center",
                                                      "className": f"pin pin-{letra.lower()}"})
                capas.append(pin)

    def ajustar(caja):
        """Encuadra la caja sin que la tape el panel (izquierda en PC, abajo en celular)."""
        relleno = ("window.innerWidth <= 640"
                   " ? {paddingTopLeft: [24, 24],"
                   "    paddingBottomRight: [24, document.querySelector('.panel').offsetHeight + 24]}"
                   " : {paddingTopLeft: [440, 40], paddingBottomRight: [40, 40]}")
        mapa.run_map_method(":fitBounds", json.dumps(caja), relleno)

    def encuadrar_zona():
        ajustar([[sur, oeste], [norte, este]])

    def encuadrar():
        if estado.get("ruta") and estado["ruta"]["camino"]:
            pts = coords(estado["ruta"]["camino"])
        else:
            pts = [(G.lat[v], G.lon[v]) for v in (estado["origen"], estado["destino"]) if v is not None]
            if len(pts) < 2:
                return
        lats, lons = [p[0] for p in pts], [p[1] for p in pts]
        ajustar([[min(lats), min(lons)], [max(lats), max(lons)]])

    # cálculo
    def calcular(mover=True):
        estado["ruta"] = estado["ruta_bfs"] = None
        estado["error"] = estado["solo_ida"] = None
        o, d = estado["origen"], estado["destino"]
        if o is not None and d is not None:
            hora = estado["hora"]
            t0 = time.perf_counter()
            r = alg.dijkstra_tiempo(G, o, d, hora)
            r["ms"] = (time.perf_counter() - t0) * 1000
            # misma componente = hay ida y vuelta. si no, quizá solo hay ida, o nada
            mismo_scc = COMPONENTE[o] == COMPONENTE[d]
            if r["camino"] is None:
                estado["error"] = ("No hay forma de llegar en auto respetando el sentido de las calles: "
                                   "el destino no es alcanzable desde el origen.")
            else:
                estado["solo_ida"] = not mismo_scc
                estado["ruta"] = r
                estado["resumen"] = alg.resumen_ruta(G, r["camino"], alg.recorrer_en_tiempo(G, r["camino"], hora))
                b = alg.bfs(G, o, d)
                estado["ruta_bfs"] = b["camino"]
                estado["bfs_min"] = sum(alg.recorrer_en_tiempo(G, b["camino"], hora))
                # como en la TB1: todo el viaje con el tráfico de la hora de salida
                estado["fijo_min"] = alg.dijkstra(G, o, d, G.pesos(hora))["costo"]
                # para el gráfico: el mismo viaje a cada hora. solo se recalcula si cambia el par
                if estado.get("par") != (o, d):
                    estado["par"] = (o, d)
                    estado["por_hora"] = [alg.dijkstra_tiempo(G, o, d, h)["costo"] for h in range(24)]
        dibujar()
        panel.refresh()
        if mover:
            encuadrar()

    def al_hacer_clic(e):
        ll = e.args["latlng"]
        if not ZONA_PREP.contains(Point(ll["lng"], ll["lat"])):
            ui.notify("Ese punto está fuera de Miraflores, San Isidro y Surquillo.", type="warning")
            return
        v, _ = G.nodo_mas_cercano(ll["lat"], ll["lng"])
        estado[estado["activa"]] = v
        if estado["activa"] == "origen" and estado["destino"] is None:
            estado["activa"] = "destino"
        calcular(mover=estado["origen"] is not None and estado["destino"] is not None)

    mapa.on("map-click", al_hacer_clic)

    def activar(clave):
        estado["activa"] = clave
        panel.refresh()

    def intercambiar():
        estado["origen"], estado["destino"] = estado["destino"], estado["origen"]
        calcular(mover=False)

    def borrar():
        estado.update(origen=None, destino=None, activa="origen", ruta=None, ruta_bfs=None, error=None, par=None)
        dibujar()
        panel.refresh()

    def ejemplo():
        estado["origen"] = G.nodo_mas_cercano(*EJEMPLO[0])[0]
        estado["destino"] = G.nodo_mas_cercano(*EJEMPLO[1])[0]
        estado["activa"] = "destino"
        calcular()

    def cambiar_hora(h):
        estado["hora"] = float(h)
        calcular(mover=False)

    def alternar_bfs(valor):
        estado["bfs"] = valor
        dibujar()

    # panel
    with ui.column().classes("panel") as contenedor:
        asa = ui.element("div").classes("asa").props('role=button tabindex=0 aria-label="Mostrar u ocultar detalles"')
        asa.on("click", lambda: contenedor.classes(toggle="expandido"))
        asa.on("keydown.enter", lambda: contenedor.classes(toggle="expandido"))
        with asa:
            ui.element("div")

        @ui.refreshable
        def panel():
            with ui.column().classes("gap-0 titulo"):
                ui.label("Rutas Lima").classes("text-xl font-bold")
                ui.label("Miraflores, San Isidro y Surquillo").classes("text-sm").style(f"color:{TINTA_2}")

            # Paradas
            with ui.column().classes("w-full gap-2"):
                for clave, letra, texto in (("origen", "A", "Origen"), ("destino", "B", "Destino")):
                    v = estado[clave]
                    activa = estado["activa"] == clave
                    fila = ui.row().classes(f"parada w-full items-center no-wrap gap-3 {'activa' if activa else ''}")
                    fila.props(f'tabindex=0 role=button aria-label="Elegir {texto.lower()} en el mapa"')
                    fila.on("click", lambda c=clave: activar(c))
                    fila.on("keydown.enter", lambda c=clave: activar(c))
                    with fila:
                        ui.html(f'<div class="letra letra-{letra.lower()}">{letra}</div>')
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(texto if v is None else f"{texto} · {G.distrito[v]}").classes("etiqueta")
                            if v is None:
                                pista = "Haz clic en el mapa" if activa else "Toca aquí para elegirlo"
                                ui.label(pista).classes("text-sm").style(f"color:{TINTA_2}")
                            else:
                                ui.label(nombre_cruce(v)).classes("text-sm font-medium truncate w-full")
                with ui.row().classes("w-full gap-1 items-center"):
                    ui.button("Intercambiar", icon="swap_vert", on_click=intercambiar) \
                        .props("flat no-caps dense text-color=blue-grey-10")
                    ui.button("Borrar", icon="close", on_click=borrar).props("flat no-caps dense text-color=blue-grey-10")
                    ui.space()
                    ui.button("Ver un ejemplo", on_click=ejemplo).props("flat no-caps dense").style(f"color:{ACENTO} !important")

            # Hora
            h = estado["hora"]
            with ui.column().classes("w-full gap-1"):
                with ui.row().classes("w-full items-baseline justify-between"):
                    ui.label("Hora de salida").classes("etiqueta")
                    ui.label(f"{reloj(h)} · {config.nombre_franja(h)}").classes("text-sm font-semibold num")
                ui.slider(min=0, max=23.75, step=0.25, value=h, on_change=lambda e: cambiar_hora(e.value)) \
                    .props('color="orange-10" aria-label="Hora de salida"').classes("w-full")

            # Resultado
            if estado.get("error"):
                with ui.row().classes("w-full no-wrap gap-2 p-3 rounded-xl").style("background:#FEF2F2"):
                    ui.icon("block").style("color:#B91C1C")
                    ui.label(estado["error"]).classes("text-sm").style("color:#7F1D1D")
                return
            if not estado.get("ruta"):
                if estado["origen"] is None:
                    ui.label("Marca el punto de partida con un clic dentro de la zona iluminada, "
                             "o prueba con el ejemplo.").classes("text-sm").style(f"color:{TINTA_2}")
                return

            res = estado["resumen"]
            r = estado["ruta"]
            with ui.column().classes("w-full gap-0"):
                with ui.row().classes("items-baseline gap-2"):
                    ui.label(dec(res["minutos"])).classes("text-4xl font-bold num").style(f"color:{ACENTO}")
                    ui.label("min").classes("text-lg font-semibold").style(f"color:{ACENTO}")
                ui.label(f"Llegas a las {reloj(r['llegada_min'] / 60)} · {dec(res['metros'] / 1000)} km · "
                         f"{res['aristas']} tramos").classes("text-sm num").style(f"color:{TINTA_2}")
                if estado.get("solo_ida"):
                    with ui.row().classes("w-full no-wrap gap-2 p-3 mt-2 rounded-xl").style("background:#FFFBEB"):
                        ui.icon("info").style("color:#B45309")
                        ui.label("Hay ruta de ida, pero no de vuelta: el destino está en otra componente "
                                 "fuertemente conexa (Kosaraju).").classes("text-sm").style("color:#78350F")

            # El mismo viaje a cada hora
            with ui.column().classes("w-full gap-1"):
                ui.label("El mismo viaje a otras horas").classes("etiqueta")
                valores = [round(m, 1) for m in estado["por_hora"]]
                datos = [{"value": m, "itemStyle": {"color": ACENTO if i == int(h) else GRIS_BARRA,
                                                    "borderRadius": [3, 3, 0, 0]}} for i, m in enumerate(valores)]
                ui.echart({
                    "animation": False,
                    "grid": {"left": 30, "right": 4, "top": 8, "bottom": 22},
                    "tooltip": {"trigger": "item", "formatter": "{b}:00 · {c} min"},
                    "xAxis": {"type": "category", "data": [f"{i:02d}" for i in range(24)],
                              "axisTick": {"show": False}, "axisLine": {"show": False},
                              "axisLabel": {"interval": 5, "color": TINTA_2, "fontSize": 11}},
                    "yAxis": {"type": "value", "splitNumber": 2, "axisLabel": {"color": TINTA_2, "fontSize": 11},
                              "splitLine": {"lineStyle": {"color": "#F1F5F9"}}},
                    "series": [
                        {"type": "bar", "data": datos, "stack": "h", "barCategoryGap": "20%"},
                        # barra invisible encima, para que se pueda hacer clic en toda la columna
                        {"type": "bar", "stack": "h", "data": [max(valores) - m for m in valores],
                         "itemStyle": {"color": "rgba(0,0,0,0)"}, "tooltip": {"show": False},
                         "emphasis": {"disabled": True}},
                    ],
                }, on_point_click=lambda e: cambiar_hora(e.data_index)).classes("w-full h-28")
                ph = estado["por_hora"]
                ui.label(f"Lo más rápido es salir {horas_con(ph, min(ph))} ({dec(min(ph))} min) "
                         f"y lo más lento, {horas_con(ph, max(ph))} ({dec(max(ph))} min).") \
                    .classes("text-xs").style(f"color:{TINTA_2}")

            # Calles
            with ui.expansion("Por dónde ir", icon="turn_right").classes("w-full").props("dense"):
                for t in res["calles"]:
                    with ui.row().classes("w-full no-wrap justify-between gap-2 py-1"):
                        ui.label(t["calle"]).classes("text-sm truncate")
                        ui.label(f"{dec(t['metros'], 0)} m · {dec(t['minutos'])} min").classes("text-xs num shrink-0") \
                            .style(f"color:{TINTA_2}")

            # Comparaciones
            with ui.column().classes("w-full gap-2 pt-3").style("border-top:1px solid #E2E8F0"):
                ui.label("Comparación").classes("etiqueta")
                extra = estado["bfs_min"] - res["minutos"]
                ui.label(f"La ruta con menos cuadras (BFS) tomaría {dec(estado['bfs_min'])} min, "
                         f"{dec(extra)} min más." if extra > 0.05 else
                         "La ruta con menos cuadras (BFS) tarda lo mismo que la de Dijkstra.").classes("text-sm")
                ui.switch("Mostrar ruta de BFS en el mapa", value=estado["bfs"],
                          on_change=lambda e: alternar_bfs(e.value)).props("dense color=grey-8").classes("text-sm")
                ui.label(f"Si todo el viaje tuviera el tráfico de las {reloj(h)}, "
                         f"saldría {dec(estado['fijo_min'])} min.").classes("text-sm")
                ui.label(f"Dijkstra: {dec(r['ms'])} ms, {dec(r['extraidos'], 0)} nodos visitados "
                         f"de {dec(G.V, 0)}.").classes("text-xs num").style(f"color:{TINTA_2}")

        panel()


if __name__ in {"__main__", "__mp_main__"}:
    # en Render el puerto viene en la variable PORT; en la compu se usa el 8080
    ui.run(title="Rutas Lima", host=os.environ.get("HOST", "127.0.0.1"),
           port=int(os.environ.get("PORT", 8080)), reload=False, show=False)
