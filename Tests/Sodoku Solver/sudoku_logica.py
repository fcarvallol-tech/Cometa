"""
sudoku_logica.py
================
Lógica pura del sudoku: puzzles, validación y el algoritmo que resuelve.
Sin interfaz (ni ventanas ni prints). La UI importa desde acá.

EL ALGORITMO: backtracking (vuelta atrás)
-----------------------------------------
Es una búsqueda por fuerza bruta "inteligente":
  1. Busca la primera casilla vacía.
  2. Prueba poner 1, 2, 3... hasta 9.
  3. Si un número no rompe ninguna regla (fila, columna, caja de 3x3),
     lo coloca y avanza recursivamente a la siguiente casilla vacía.
  4. Si en algún punto ningún número cabe, DESHACE la última jugada
     (backtrack) y prueba el siguiente número en la casilla anterior.
Repite hasta llenar todo. Es exhaustivo: si hay solución, la encuentra.

Para poder ANIMARLO, el solver está escrito como un "generador" que va
emitiendo cada jugada (colocar / borrar). Así la interfaz puede reproducir
esas jugadas una por una y tú ves el algoritmo pensar.
"""

# Cada puzzle es una grilla 9x9. El 0 representa una casilla vacía.
# Los tres derivan de una misma solución válida quitando cada vez más
# números, así que TODOS tienen solución garantizada.
FACIL = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]

MEDIO = [
    [5, 3, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 0, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 0],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [0, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 0, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 0, 0, 0, 7, 9],
]

DIFICIL = [
    [5, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 0, 0, 0, 0, 0, 0, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 0],
    [4, 0, 0, 0, 0, 3, 0, 0, 1],
    [0, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 0, 0, 0, 0, 0, 2, 0, 0],
    [0, 0, 0, 4, 1, 0, 0, 0, 5],
    [0, 0, 0, 0, 0, 0, 0, 7, 9],
]

# Diccionario para que la interfaz elija por nombre.
PUZZLES = {"Fácil": FACIL, "Medio": MEDIO, "Difícil": DIFICIL}


def copiar(grid):
    """Devuelve una copia independiente de la grilla (para no mutar el original)."""
    return [fila[:] for fila in grid]


def encontrar_vacia(grid):
    """Devuelve (fila, columna) de la primera casilla vacía, o None si no hay."""
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                return (r, c)
    return None


def es_valido(grid, fila, col, valor):
    """
    ¿Se puede poner `valor` en (fila, col) sin romper las reglas del sudoku?
    Revisa la fila, la columna y la caja de 3x3.
    """
    # Fila y columna
    for i in range(9):
        if grid[fila][i] == valor:
            return False
        if grid[i][col] == valor:
            return False

    # Caja de 3x3: encontramos la esquina superior-izquierda de la caja.
    caja_r, caja_c = 3 * (fila // 3), 3 * (col // 3)
    for r in range(caja_r, caja_r + 3):
        for c in range(caja_c, caja_c + 3):
            if grid[r][c] == valor:
                return False

    return True


def resolver_generador(grid):
    """
    Backtracking implementado como GENERADOR.

    Modifica `grid` en el sitio y va emitiendo (`yield`) cada jugada:
        (fila, col, valor, accion)
    donde accion es "colocar" (probó un número) o "borrar" (retrocedió).

    Devuelve True cuando el tablero queda resuelto. La recursión usa
    `yield from` para propagar tanto las jugadas como el resultado True/False.
    """
    pos = encontrar_vacia(grid)
    if pos is None:
        return True  # no quedan vacías -> resuelto

    fila, col = pos
    for valor in range(1, 10):
        if es_valido(grid, fila, col, valor):
            grid[fila][col] = valor
            yield (fila, col, valor, "colocar")

            # yield from re-emite las jugadas de la recursión y captura su
            # valor de retorno (True/False).
            if (yield from resolver_generador(grid)):
                return True

            # Si por ese camino no hubo solución, deshacemos: backtrack.
            grid[fila][col] = 0
            yield (fila, col, 0, "borrar")

    return False  # ningún número funcionó aquí -> avisa al nivel anterior


def obtener_pasos(grid):
    """
    Ejecuta el solver sobre una COPIA y devuelve la lista completa de jugadas.
    La interfaz reproduce esta lista para animar. Reproducir los pasos desde
    el puzzle inicial reconstruye exactamente la solución.
    """
    trabajo = copiar(grid)
    return list(resolver_generador(trabajo))


def resolver(grid):
    """
    Devuelve una grilla resuelta (copia) o None si no tiene solución.
    Útil para el botón 'Resolver' en el modo de juego.
    """
    trabajo = copiar(grid)
    # Agotamos el generador; el grid queda resuelto si había solución.
    for _ in resolver_generador(trabajo):
        pass
    return trabajo if encontrar_vacia(trabajo) is None else None


def conflictos(grid):
    """
    Devuelve un set de posiciones (fila, col) de las casillas que rompen las
    reglas (repiten número en su fila, columna o caja). Sirve para marcar en
    rojo los errores del jugador.
    """
    malas = set()
    for r in range(9):
        for c in range(9):
            valor = grid[r][c]
            if valor == 0:
                continue
            # Truco: sacamos el número, y preguntamos si sería válido volver a
            # ponerlo. Si NO es válido, es porque choca con otro igual.
            grid[r][c] = 0
            if not es_valido(grid, r, c, valor):
                malas.add((r, c))
            grid[r][c] = valor
    return malas


def esta_completo(grid):
    """True si no quedan casillas vacías."""
    return encontrar_vacia(grid) is None


if __name__ == "__main__":
    # Auto-test: los tres puzzles deben resolverse y la solución no debe
    # tener conflictos.
    for nombre, puzzle in PUZZLES.items():
        sol = resolver(puzzle)
        assert sol is not None, f"{nombre} no tiene solución"
        assert esta_completo(sol), f"{nombre} quedó incompleto"
        assert conflictos(sol) == set(), f"{nombre} tiene conflictos"
        pasos = obtener_pasos(puzzle)
        print(f"{nombre}: resuelto en {len(pasos)} jugadas.")
    print("Todos los puzzles OK. ✓")
