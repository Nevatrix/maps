"""
Figuras del dataset (las de la TB1). Solo lee los CSV, no descarga nada.

  figura1.png  el grafo completo por distrito
  figura2.png  zoom de 1 km x 1 km por tipo de vía
  figura3.png  el mismo zoom a las 11:00 y a las 18:00

Pasamos las coordenadas a UTM 18S para poder medir en metros, y cada arista se
dibuja como una línea recta entre sus dos nodos.

    python src/visualizar.py
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from pyproj import Transformer

import config

CARPETA_DATOS = config.CARPETA_DATOS
CARPETA_FIGURAS = config.CARPETA_FIGURAS
DPI = 300

LADO_ZOOM_M = 1000
# el recuadro se baja 250 m porque al norte de Javier Prado ya es Lince y
# quedaba media figura vacía
DESPLAZAMIENTO_SUR_M = 250
HORAS_COMPARADAS = (11, 18)

# colores: los 3 primeros se distinguen con daltonismo; el tráfico va de azul claro a oscuro
FONDO = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
COLOR_DISTRITO = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
COLOR_TIPO = {"local": "#86b6ef", "secundaria": "#2a78d6", "principal": "#0d366b"}
GROSOR_TIPO = {"local": 0.7, "secundaria": 1.6, "principal": 3.2}
RAMPA_TRAFICO = LinearSegmentedColormap.from_list(
    "trafico", ["#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "figure.facecolor": FONDO,
    "axes.facecolor": FONDO,
    "text.color": TINTA,
})


# carga de datos
def cargar():
    nodos = pd.read_csv(os.path.join(CARPETA_DATOS, "nodos.csv"), encoding="utf-8")
    aristas = pd.read_csv(os.path.join(CARPETA_DATOS, "aristas.csv"), encoding="utf-8")
    a_utm = Transformer.from_crs("EPSG:4326", "EPSG:32718", always_xy=True)
    nodos["x"], nodos["y"] = a_utm.transform(nodos["longitud"].values, nodos["latitud"].values)
    pos = nodos.set_index("id")[["x", "y", "distrito"]]
    aristas = aristas.join(pos[["x", "y"]], on="origen").join(
        pos[["x", "y"]], on="destino", rsuffix="_d")
    aristas["distrito"] = aristas["origen"].map(pos["distrito"])
    aristas["xm"] = (aristas["x"] + aristas["x_d"]) / 2
    aristas["ym"] = (aristas["y"] + aristas["y_d"]) / 2
    return nodos, aristas


def miles(n):
    return f"{n:,}".replace(",", "\u00a0")  # 3 559 con espacio no separable


def segmentos(df):
    return np.stack([df[["x", "y"]].values, df[["x_d", "y_d"]].values], axis=1)


def cruce_avenidas(aristas):
    """Dónde se cruzan Javier Prado y Arequipa.

    Como el cruce es a desnivel no hay un nodo en común, así que buscamos dónde se
    cortan los segmentos de las dos avenidas y promediamos esos puntos.
    """
    jp = aristas[aristas["nombre_calle"].str.contains("Avenida Javier Prado", case=False)]
    aq = aristas[aristas["nombre_calle"].str.contains("Avenida Arequipa", case=False)]
    p, r = jp[["x", "y"]].values, jp[["x_d", "y_d"]].values - jp[["x", "y"]].values
    q, t = aq[["x", "y"]].values, aq[["x_d", "y_d"]].values - aq[["x", "y"]].values
    cruz = lambda a, b: a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]
    den = cruz(r[:, None], t[None, :])
    qp = q[None, :] - p[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = cruz(qp, t[None, :]) / den
        v = cruz(qp, r[:, None]) / den
    i, j = np.where((den != 0) & (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1))
    puntos = p[i] + u[i, j][:, None] * r[i]
    return float(puntos[:, 0].mean()), float(puntos[:, 1].mean()), len(puntos)


def en_ventana(aristas, cx, cy, lado):
    m = lado / 2
    return aristas[(aristas["xm"].between(cx - m, cx + m)) & (aristas["ym"].between(cy - m, cy + m))]


# cosas que usan todas las figuras
def preparar_ejes(ax, xlim=None, ylim=None):
    ax.set_aspect("equal")
    if xlim:
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#c3c2b7")
        s.set_linewidth(0.6)


def barra_escala(ax, metros, texto, derecha=False):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    bx = x1 - 0.05 * (x1 - x0) - metros if derecha else x0 + 0.05 * (x1 - x0)
    by = y0 + 0.05 * (y1 - y0)
    ax.plot([bx, bx + metros], [by, by], color=TINTA, lw=2, solid_capstyle="butt", zorder=8)
    ax.text(bx + metros / 2, by + 0.015 * (y1 - y0), texto, ha="center", va="bottom",
            fontsize=8, color=TINTA, bbox=dict(boxstyle="round,pad=0.15", fc=FONDO, ec="none"))


def flecha_norte(ax):
    ax.annotate("N", xy=(0.95, 0.95), xytext=(0.95, 0.86), xycoords="axes fraction",
                ha="center", va="center", fontsize=9, fontweight="bold", color=TINTA,
                arrowprops=dict(arrowstyle="-|>", color=TINTA, lw=1.2))


def dibujar_por_tipo(ax, sel, colores):
    """Primero las locales y al final las principales, para que queden encima."""
    for tipo in ("local", "secundaria", "principal"):
        t = sel[sel["tipo_via"] == tipo]
        c = colores[tipo] if isinstance(colores, dict) else colores.loc[t.index]
        ax.add_collection(LineCollection(segmentos(t), colors=c, linewidths=GROSOR_TIPO[tipo],
                                         capstyle="round", zorder=JERARQUIA_Z[tipo]))


JERARQUIA_Z = {"local": 1, "secundaria": 2, "principal": 3}


def atribucion(ax, y=-0.01):
    """La licencia de OSM pide citarlos en cada mapa."""
    ax.text(1, y, "Datos: © Colaboradores de OpenStreetMap (ODbL)", transform=ax.transAxes,
            ha="right", va="top", fontsize=7, color=TINTA_SECUNDARIA)


# las figuras
def figura1(nodos, aristas, ventana):
    fig, ax = plt.subplots(figsize=(8, 7.2))
    distritos = list(dict.fromkeys(config.DISTRITOS + sorted(nodos["distrito"].unique())))
    distritos = [d for d in distritos if d in set(nodos["distrito"])]
    manijas = []
    for i, d in enumerate(distritos):
        color = COLOR_DISTRITO[i]
        sub = aristas[aristas["distrito"] == d]
        ax.add_collection(LineCollection(segmentos(sub), colors=color, linewidths=0.45))
        nd = nodos[nodos["distrito"] == d]
        ax.scatter(nd["x"], nd["y"], s=0.6, color=color, linewidths=0)
        manijas.append(Line2D([], [], color=color, lw=3,
                              label=f"{d} ({miles(len(nd))} nodos)"))
    cx, cy = ventana
    ax.add_patch(Rectangle((cx - LADO_ZOOM_M / 2, cy - LADO_ZOOM_M / 2), LADO_ZOOM_M, LADO_ZOOM_M,
                           fill=False, edgecolor=TINTA, lw=1.1, ls="--", zorder=5))
    ax.text(cx + LADO_ZOOM_M / 2 + 60, cy + LADO_ZOOM_M / 2, "Zona de zoom\n(Figuras 2 y 3)",
            fontsize=7.5, color=TINTA, va="top", zorder=5,
            bbox=dict(boxstyle="round,pad=0.2", fc=FONDO, ec="none", alpha=0.9))
    manijas.append(Line2D([], [], color=TINTA, lw=1.1, ls="--", label="Zona de zoom (1 km × 1 km)"))
    margen = 250
    preparar_ejes(ax, (nodos["x"].min() - margen, nodos["x"].max() + margen),
                  (nodos["y"].min() - margen, nodos["y"].max() + margen))
    barra_escala(ax, 1000, "1 km", derecha=True)
    flecha_norte(ax)
    ax.legend(handles=manijas, loc="lower left", frameon=True, fontsize=8.5,
              title="Distrito", title_fontsize=9, facecolor=FONDO, edgecolor="#e1e0d9")
    ax.set_title("Figura 1. Red vial dirigida de Miraflores, San Isidro y Surquillo\n"
                 f"V = {miles(len(nodos))} nodos, E = {miles(len(aristas))} aristas",
                 fontsize=11, loc="left")
    atribucion(ax)
    fig.savefig(os.path.join(CARPETA_FIGURAS, "figura1.png"), dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def figura2(zoom, cx, cy, cruce):
    m = LADO_ZOOM_M / 2
    fig, ax = plt.subplots(figsize=(7.5, 8))
    dibujar_por_tipo(ax, zoom, COLOR_TIPO)
    preparar_ejes(ax, (cx - m, cx + m), (cy - m, cy + m))
    kx, ky = cruce
    ax.scatter([kx], [ky], s=90, facecolor="none", edgecolor="#e34948", lw=1.8, zorder=6)
    ax.annotate("Cruce Av. Javier Prado\n× Av. Arequipa", xy=(kx, ky), xytext=(kx + 180, ky + 150),
                fontsize=8.5, color=TINTA, zorder=7, ha="left",
                arrowprops=dict(arrowstyle="-", color=TINTA_SECUNDARIA, lw=0.8),
                bbox=dict(boxstyle="round,pad=0.3", fc=FONDO, ec="#e1e0d9"))
    barra_escala(ax, 200, "200 m")
    flecha_norte(ax)
    conteo = zoom["tipo_via"].value_counts()
    manijas = [Line2D([], [], color=COLOR_TIPO[t], lw=GROSOR_TIPO[t] + 0.4,
                      label=f"{t.capitalize()} ({config.VELOCIDAD_KMH[t]} km/h) · {conteo.get(t, 0)} aristas")
               for t in ("principal", "secundaria", "local")]
    ax.legend(handles=manijas, loc="lower right", fontsize=8, title="Tipo de vía",
              title_fontsize=9, facecolor=FONDO, edgecolor="#e1e0d9", framealpha=0.95)
    ax.set_title("Figura 2. Zoom de 1 km × 1 km en torno al cruce de Av. Javier Prado y Av. Arequipa\n"
                 "Color y grosor según el tipo de vía", fontsize=11, loc="left")
    atribucion(ax)
    fig.savefig(os.path.join(CARPETA_FIGURAS, "figura2.png"), dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def figura3(zoom, cx, cy):
    m = LADO_ZOOM_M / 2
    todos = [f for fs in config.FACTOR_HORA.values() for f in fs]
    norma = Normalize(vmin=min(todos), vmax=max(todos))  # misma escala en ambos paneles
    fig, ejes = plt.subplots(1, 2, figsize=(12, 6.8))
    resumen = {}
    for ax, hora in zip(ejes, HORAS_COMPARADAS):
        factores = zoom["tipo_via"].map(lambda t: config.factor_trafico(t, hora))
        colores = pd.Series([RAMPA_TRAFICO(norma(f)) for f in factores], index=zoom.index)
        dibujar_por_tipo(ax, zoom, colores)
        preparar_ejes(ax, (cx - m, cx + m), (cy - m, cy + m))
        barra_escala(ax, 200, "200 m")
        flecha_norte(ax)
        minutos = sum(config.peso_minutos(l, t, hora)
                      for l, t in zip(zoom["longitud_m"], zoom["tipo_via"]))
        resumen[hora] = minutos
        fs = {t: config.factor_trafico(t, hora) for t in ("principal", "secundaria", "local")}
        ax.set_title(f"{hora:02d}:00  ·  factores P {fs['principal']} / S {fs['secundaria']} / "
                     f"L {fs['local']}\nTiempo total del zoom: {minutos:.1f} min",
                     fontsize=10, loc="left")
    barra = fig.colorbar(plt.cm.ScalarMappable(norm=norma, cmap=RAMPA_TRAFICO), ax=ejes,
                         orientation="horizontal", fraction=0.05, pad=0.04, aspect=45)
    barra.set_label("Factor de tráfico (modelado con la tabla del grupo; grosor = jerarquía de la vía)",
                    fontsize=9, color=TINTA)
    barra.ax.tick_params(labelsize=8, colors=TINTA_SECUNDARIA)
    fig.suptitle("Figura 3. Mismo zoom a las 11:00 y a las 18:00 coloreado por factor de tráfico",
                 fontsize=12, x=0.02, ha="left")
    atribucion(barra.ax, y=-3.2)
    fig.savefig(os.path.join(CARPETA_FIGURAS, "figura3.png"), dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return resumen


def main():
    os.makedirs(CARPETA_FIGURAS, exist_ok=True)
    nodos, aristas = cargar()
    kx, ky, n_cruces = cruce_avenidas(aristas)
    cx, cy = kx, ky - DESPLAZAMIENTO_SUR_M
    zoom = en_ventana(aristas, cx, cy, LADO_ZOOM_M)

    figura1(nodos, aristas, (cx, cy))
    figura2(zoom, cx, cy, (kx, ky))
    tiempos = figura3(zoom, cx, cy)

    a_geo = Transformer.from_crs("EPSG:32718", "EPSG:4326", always_xy=True)
    lon, lat = a_geo.transform(cx, cy)
    klon, klat = a_geo.transform(kx, ky)
    h1, h2 = HORAS_COMPARADAS
    por_tipo = {}
    for t in ("principal", "secundaria", "local"):
        sub = zoom[zoom["tipo_via"] == t]
        por_tipo[t] = {
            "aristas": int(len(sub)),
            "longitud_km": round(float(sub["longitud_m"].sum() / 1000), 3),
            **{f"min_{h:02d}": round(sum(config.peso_minutos(l, t, h) for l in sub["longitud_m"]), 2)
               for h in HORAS_COMPARADAS},
        }
    stats = {
        "cruce": {"latitud": round(klat, 6), "longitud": round(klon, 6),
                  "puntos_de_cruce_de_calzadas": n_cruces},
        "centro_zoom": {"latitud": round(lat, 6), "longitud": round(lon, 6)},
        "desplazamiento_sur_m": DESPLAZAMIENTO_SUR_M,
        "lado_zoom_m": LADO_ZOOM_M,
        "aristas_zoom": int(len(zoom)),
        "longitud_zoom_km": round(float(zoom["longitud_m"].sum() / 1000), 3),
        "distritos_zoom": zoom["distrito"].value_counts().to_dict(),
        f"min_total_{h1:02d}": round(tiempos[h1], 2),
        f"min_total_{h2:02d}": round(tiempos[h2], 2),
        "aumento_pct": round((tiempos[h2] / tiempos[h1] - 1) * 100, 1),
        "por_tipo": por_tipo,
    }
    with open(os.path.join(CARPETA_DATOS, "estadisticas_figuras.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"Cruce Javier Prado x Arequipa: {klat:.6f}, {klon:.6f}; centro del zoom: {lat:.6f}, {lon:.6f}")
    print(f"Aristas en el zoom: {len(zoom)}  ({stats['distritos_zoom']})")
    print(f"Tiempo total del zoom: {tiempos[h1]:.1f} min a las {h1}:00 vs "
          f"{tiempos[h2]:.1f} min a las {h2}:00 (+{stats['aumento_pct']} %)")
    print(f"Figuras guardadas en {CARPETA_FIGURAS}/ (figura1.png, figura2.png, figura3.png)")


if __name__ == "__main__":
    main()
