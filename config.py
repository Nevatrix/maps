"""
Configuración compartida del proyecto "Waze para Lima" (TB1 - Complejidad Algorítmica).

Contiene los distritos de estudio, las velocidades base por tipo de vía, la tabla
de factores de tráfico por franja horaria y las funciones para calcular el peso
(tiempo en minutos) de una arista. Solo usa la biblioteca estándar de Python para
que pueda reutilizarse directamente en Dijkstra, Bellman-Ford, etc.
"""

# Distritos de estudio (orden = prioridad para asignar nodos de frontera).
DISTRITOS = ["Miraflores", "San Isidro", "Surquillo"]
DISTRITO_RESPALDO = "Barranco"

# Requisitos mínimos del trabajo.
MIN_INTERSECCIONES_TOTAL = 1500
MIN_INTERSECCIONES_DISTRITO = 500

# Tipos de vía del modelo y su velocidad base (km/h).
TIPOS_VIA = ["principal", "secundaria", "local"]
VELOCIDAD_KMH = {
    "principal": 40,
    "secundaria": 30,
    "local": 25,
}

# Avenidas que el grupo considera "principal" aunque OSM las etiquete con menor
# jerarquía (p. ej. Av. Arequipa figura como highway=secondary en OSM).
# Se aplica a toda arista cuyo nombre empiece con "Avenida <nombre>".
AVENIDAS_PRINCIPALES = ["Javier Prado", "Arequipa"]

# Factor de tráfico por franja horaria: (hora_inicio, hora_fin, {tipo: factor}).
# Las horas son enteras e inclusivas: 6..9 equivale a 06:00-09:59.
FRANJAS_TRAFICO = [
    (0, 5, {"principal": 1.0, "secundaria": 1.0, "local": 1.0}),
    (6, 9, {"principal": 2.5, "secundaria": 1.8, "local": 1.2}),
    (10, 16, {"principal": 1.4, "secundaria": 1.2, "local": 1.0}),
    (17, 20, {"principal": 2.8, "secundaria": 2.0, "local": 1.3}),
    (21, 23, {"principal": 1.3, "secundaria": 1.1, "local": 1.0}),
]


def factor_trafico(tipo_via, hora):
    """Devuelve el factor de tráfico para un tipo de vía a una hora dada.

    tipo_via: "principal", "secundaria" o "local".
    hora: hora del día entre 0 y 23 (se aceptan decimales, p. ej. 18.5 = 18:30).
    """
    if tipo_via not in VELOCIDAD_KMH:
        raise ValueError(f"Tipo de vía desconocido: {tipo_via!r}")
    h = int(hora)
    if not 0 <= h <= 23:
        raise ValueError(f"Hora fuera de rango (0-23): {hora!r}")
    for inicio, fin, factores in FRANJAS_TRAFICO:
        if inicio <= h <= fin:
            return factores[tipo_via]
    raise ValueError(f"Hora sin franja definida: {hora!r}")  # no debería ocurrir


def peso_minutos(longitud_m, tipo_via, hora):
    """Peso de una arista: tiempo en minutos para recorrerla a una hora dada.

    tiempo (min) = (longitud / velocidad) x factor de tráfico
    """
    velocidad_m_por_min = VELOCIDAD_KMH[tipo_via] * 1000 / 60
    return (longitud_m / velocidad_m_por_min) * factor_trafico(tipo_via, hora)


if __name__ == "__main__":
    # Prueba rápida: 1 km de avenida principal a distintas horas.
    for h in (3, 8, 11, 18, 22):
        print(f"{h:02d}:00 -> 1 km principal = {peso_minutos(1000, 'principal', h):.2f} min")
