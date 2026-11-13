"""
Parámetros que usan todos los scripts: rutas de carpetas, distritos,
velocidades, factores de tráfico y la fórmula del peso de una arista.
"""

from pathlib import Path

# el código está en src/ y los datos en la raíz
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_DATOS = RAIZ / "datos"
CARPETA_FIGURAS = RAIZ / "figuras"

# si un nodo cae en el límite de dos distritos, se queda con el primero de la lista
DISTRITOS = ["Miraflores", "San Isidro", "Surquillo"]
DISTRITO_RESPALDO = "Barranco"

# ejemplo del botón "Ver un ejemplo" y del informe: Parque Kennedy -> Surquillo
EJEMPLO = ((-12.1219, -77.0300), (-12.1120, -77.0110))

# mínimos que pide el enunciado
MIN_INTERSECCIONES_TOTAL = 1500
MIN_INTERSECCIONES_DISTRITO = 500

# velocidad sin tráfico, en km/h
TIPOS_VIA = ["principal", "secundaria", "local"]
VELOCIDAD_KMH = {
    "principal": 40,
    "secundaria": 30,
    "local": 25,
}

# en OSM Arequipa sale como secondary, pero para nosotros es principal.
# vale para toda arista cuyo nombre empiece con "Avenida <nombre>"
AVENIDAS_PRINCIPALES = ["Javier Prado", "Arequipa"]

# factor de tráfico a cada hora en punto. entre dos horas se interpola, así no
# salta de golpe. las 08:00, 11:00 y 18:00 tienen los mismos valores de la TB1
#        h:  0    1    2    3    4    5    6    7    8    9    10   11
#           12   13   14   15   16   17   18   19   20   21   22   23
FACTOR_HORA = {
    "principal": [1.0, 1.0, 1.0, 1.0, 1.0, 1.2, 1.7, 2.3, 2.5, 2.1, 1.6, 1.4,
                  1.5, 1.5, 1.4, 1.4, 1.7, 2.3, 2.8, 2.7, 2.2, 1.6, 1.3, 1.1],
    "secundaria": [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.4, 1.7, 1.8, 1.6, 1.3, 1.2,
                   1.25, 1.25, 1.2, 1.2, 1.4, 1.7, 2.0, 1.9, 1.6, 1.3, 1.1, 1.0],
    "local": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.2, 1.1, 1.0, 1.0,
              1.05, 1.05, 1.0, 1.0, 1.1, 1.2, 1.3, 1.3, 1.15, 1.05, 1.0, 1.0],
}

# solo para ponerle nombre a la hora en la interfaz
FRANJAS = [
    (0, 5, "madrugada"),
    (6, 9, "hora punta mañana"),
    (10, 16, "horario normal"),
    (17, 20, "hora punta tarde"),
    (21, 23, "noche"),
]


def nombre_franja(hora):
    h = int(hora) % 24
    for inicio, fin, nombre in FRANJAS:
        if inicio <= h <= fin:
            return nombre
    return ""


def factor_trafico(tipo_via, hora):
    """hora va con decimales: 18.5 es 18:30. si pasa de 24 es el día siguiente."""
    if tipo_via not in FACTOR_HORA:
        raise ValueError(f"Tipo de vía desconocido: {tipo_via!r}")
    if hora < 0:
        raise ValueError(f"Hora negativa: {hora!r}")
    tabla = FACTOR_HORA[tipo_via]
    h = hora % 24
    i = int(h)
    frac = h - i  # qué tan cerca está de la siguiente hora
    return tabla[i] + (tabla[(i + 1) % 24] - tabla[i]) * frac


def minutos_sin_trafico(longitud_m, tipo_via):
    """Minutos que toma el tramo sin tráfico."""
    return longitud_m / (VELOCIDAD_KMH[tipo_via] * 1000 / 60)


def peso_minutos(longitud_m, tipo_via, hora):
    """tiempo (min) = (longitud / velocidad) x factor de tráfico"""
    return minutos_sin_trafico(longitud_m, tipo_via) * factor_trafico(tipo_via, hora)


if __name__ == "__main__":
    # para ver rápido cuánto tarda 1 km de avenida a distintas horas
    for h in (3, 7.5, 8, 11, 18, 22):
        print(f"{h:5.2f} h -> 1 km principal = {peso_minutos(1000, 'principal', h):.2f} min")
