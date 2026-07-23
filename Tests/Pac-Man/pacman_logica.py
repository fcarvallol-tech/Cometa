"""
pacman_logica.py
================
Lógica pura del Pac-Man (jardín): laberinto, reglas de movimiento e IA de los
fantasmas. Sin ventanas ni dibujo (eso vive en pacman_app.py).

Laberinto como grilla de caracteres:
    '#' = seto (pared)
    '.' = semilla / flor pequeña (comida)
    'o' = flor grande (power pellet: deja comer fantasmas por un rato)
    ' ' = camino vacío (bocas del túnel y spawns)

Coordenadas: (fila, columna) = (r, c). Fila 0 arriba.
"""

import random
from collections import deque

ANCHO = 19          # columnas
ALTO = 21           # filas
FILA_TUNEL = 10     # fila del túnel que conecta izquierda-derecha

# Direcciones como (dc, dr): cambio de columna y de fila.
ARRIBA = (0, -1)
ABAJO = (0, 1)
IZQ = (-1, 0)
DER = (1, 0)
DIRECCIONES = (ARRIBA, IZQ, ABAJO, DER)  # orden de desempate clásico

# ---------------------------------------------------------------------------
# Mapas "jardín". Cada uno está dibujado a mano como setos (islas separadas por
# caminos). El "esqueleto" es siempre el mismo: las filas impares son caminos
# totalmente abiertos y las pares tienen los setos; la fila del medio es un
# túnel. Esa estructura garantiza que TODO el jardín queda conectado (ninguna
# flor inalcanzable, ningún Pac-Man encerrado) sin importar el patrón de setos.
# ---------------------------------------------------------------------------
_OPEN = "#.................#"
_WALL = "###################"
_TUN = " ................. "

MAPA_JARDIN = [
    _WALL, _OPEN,
    "#.###.........###.#", _OPEN,
    "#......#####......#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    _TUN, _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    "#......#####......#", _OPEN,
    "#.###.........###.#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    _WALL,
]

MAPA_PLAZA = [
    _WALL, _OPEN,
    "#.#.#.#.#.#.#.#.#.#", _OPEN,
    "#......#####......#", _OPEN,
    "#.#.#.#.#.#.#.#.#.#", _OPEN,
    "#.###.........###.#", _OPEN,
    _TUN, _OPEN,
    "#.###.........###.#", _OPEN,
    "#.#.#.#.#.#.#.#.#.#", _OPEN,
    "#......#####......#", _OPEN,
    "#.#.#.#.#.#.#.#.#.#", _OPEN,
    _WALL,
]

MAPA_LABERINTO = [
    _WALL, _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    "#.#.#.#.#.#.#.#.#.#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    _TUN, _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    "#.#.#.#.#.#.#.#.#.#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    "#.###.#.###.#.###.#", _OPEN,
    _WALL,
]

MAPAS = [MAPA_JARDIN, MAPA_PLAZA, MAPA_LABERINTO]
NOMBRES_MAPA = ["Jardín Clásico", "Plaza Abierta", "Laberinto"]

# Puntos de aparición
SPAWN_PACMAN = (19, 9)
# 4 fantasmas: rojo, rosa, naranjo y el especial "Rayo" (índice 3).
SPAWN_FANTASMAS = [(9, 9), (9, 7), (9, 11), (11, 9)]
POWER_PELLETS = [(1, 1), (1, 17), (19, 1), (19, 17)]


def generar_laberinto(indice=0):
    """Construye la grilla del jardín a partir del mapa elegido (0, 1 o 2)."""
    maze = [list(fila) for fila in MAPAS[indice]]

    for (r, c) in POWER_PELLETS:
        maze[r][c] = "o"

    # Limpiar la comida donde aparecen los personajes.
    maze[SPAWN_PACMAN[0]][SPAWN_PACMAN[1]] = " "
    for (r, c) in SPAWN_FANTASMAS:
        maze[r][c] = " "

    return maze


def es_pared(maze, r, c):
    """True si (r, c) es seto o está fuera del tablero."""
    if r < 0 or r >= ALTO or c < 0 or c >= ANCHO:
        return True
    return maze[r][c] == "#"


def puede_avanzar(maze, r, c, direccion):
    """
    ¿Se puede salir de la casilla (r, c) en `direccion`?
    Considera el cruce del túnel en la fila del medio.
    """
    dc, dr = direccion
    nc, nr = c + dc, r + dr
    if r == FILA_TUNEL:                 # envolver en el túnel
        if nc < 0:
            nc = ANCHO - 1
        elif nc >= ANCHO:
            nc = 0
    return not es_pared(maze, nr, nc)


def celdas_alcanzables(maze, inicio):
    """
    BFS: set de casillas (r, c) alcanzables desde `inicio`. Se usa para poner
    comida SOLO donde se puede comer -> el juego siempre se puede ganar.
    """
    visitadas = set([inicio])
    cola = deque([inicio])
    while cola:
        r, c = cola.popleft()
        for d in DIRECCIONES:
            if puede_avanzar(maze, r, c, d):
                dc, dr = d
                nc, nr = c + dc, r + dr
                if r == FILA_TUNEL:
                    nc %= ANCHO
                if (nr, nc) not in visitadas:
                    visitadas.add((nr, nc))
                    cola.append((nr, nc))
    return visitadas


def direcciones_posibles(maze, r, c, dir_actual, permitir_reversa=False):
    """
    Direcciones válidas desde (r, c). Por defecto los fantasmas NO pueden dar
    media vuelta (regla clásica), salvo en un callejón sin salida.
    """
    reversa = (-dir_actual[0], -dir_actual[1]) if dir_actual else None
    opciones = []
    for d in DIRECCIONES:
        if not permitir_reversa and d == reversa:
            continue
        if puede_avanzar(maze, r, c, d):
            opciones.append(d)
    return opciones


def elegir_direccion_fantasma(maze, r, c, dir_actual, objetivo, asustado):
    """
    Decide el giro de un fantasma al llegar al centro de una casilla.
    - asustado: elige al azar (huye sin criterio).
    - normal: elige la dirección que MÁS lo acerca a su casilla `objetivo`.
    """
    opciones = direcciones_posibles(maze, r, c, dir_actual)
    if not opciones:
        opciones = direcciones_posibles(maze, r, c, dir_actual, permitir_reversa=True)
    if not opciones:
        return dir_actual

    if asustado:
        return random.choice(opciones)

    objr, objc = objetivo
    mejor, mejor_dist = None, float("inf")
    for d in opciones:
        dc, dr = d
        nc, nr = c + dc, r + dr
        if r == FILA_TUNEL:
            nc %= ANCHO
        dist = (nr - objr) ** 2 + (nc - objc) ** 2
        if dist < mejor_dist:
            mejor_dist, mejor = dist, d
    return mejor


def objetivo_fantasma(indice, pac_rc, pac_dir, fant_rc):
    """
    Casilla objetivo de cada fantasma (targeting con personalidad):
      0 - Blinky (rojo):     va directo a Pac-Man.
      1 - Pinky (rosa):      4 casillas ADELANTE de Pac-Man (emboscada).
      2 - Clyde (naranjo):   persigue de lejos; si se acerca, huye a su esquina.
      3 - Rayo (morado):     persigue directo para acercarse y lanzar su rayo.
    """
    pr, pc = pac_rc
    if indice == 0 or indice == 3:
        return (pr, pc)
    if indice == 1:
        return (pr + pac_dir[1] * 4, pc + pac_dir[0] * 4)
    # Clyde
    fr, fc = fant_rc
    if abs(fr - pr) + abs(fc - pc) > 8:
        return (pr, pc)
    return (ALTO - 1, 0)


def distancia_tiles(a, b):
    """Distancia Manhattan entre dos casillas (para el alcance del rayo)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
