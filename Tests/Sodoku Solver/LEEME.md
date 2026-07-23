# Sudoku — Solver y Juego 🧩

Un sudoku con interfaz gráfica (Tkinter) que hace dos cosas:

- **Resolver**: muestra al algoritmo resolviendo el puzzle *paso a paso*, en vivo.
- **Jugar**: tú escribes los números, compruebas errores o pides la solución.

Trae tres puzzles: **Fácil**, **Medio** y **Difícil**.

## Cómo ejecutarlo (un click)

Doble click en **`Ejecutar Sudoku.bat`**.

La primera vez crea un entorno virtual local (`.venv`) dentro de esta carpeta y
abre la app. No instala nada en tu sistema (Tkinter ya viene con Python) ni
modifica tu Python global. También puedes correrlo a mano:

```
python sudoku_app.py
```

## El algoritmo: backtracking (vuelta atrás)

Es la estrella del proyecto y lo que ves animado en la pestaña **Resolver**:

1. Busca la primera casilla vacía.
2. Prueba poner 1, 2, 3… 9.
3. Si un número no rompe ninguna regla (fila, columna, caja de 3×3), lo coloca
   y **avanza** recursivamente a la siguiente casilla vacía.
4. Si llega a un punto donde ningún número cabe, **deshace** la última jugada
   (eso es el *backtrack*, el destello rojo) y prueba el siguiente número atrás.

Es exhaustivo: si el puzzle tiene solución, siempre la encuentra. En la pantalla:

- **Verde** = número que el algoritmo acaba de colocar.
- **Destello rojo** = retroceso (se equivocó y borra para probar otra cosa).
- El contador de abajo te muestra jugadas totales y cuántas veces retrocedió —
  fíjate cómo el "Difícil" necesita muchísimos más retrocesos que el "Fácil".

Puedes ajustar la **velocidad** con el slider antes o durante la animación.

## El truco para animar un algoritmo recursivo

El solver está escrito como un **generador** de Python (usa `yield`): en vez de
resolver de una y devolver el resultado, va *emitiendo* cada jugada. La interfaz
guarda esa lista de jugadas y las reproduce con `root.after()` (el temporizador
de Tkinter). Esa es la idea general para animar cualquier algoritmo: separá el
"qué hace paso a paso" de "cómo se dibuja".

## Archivos

| Archivo | Rol |
|---|---|
| `sudoku_logica.py` | Puzzles, validación y el solver backtracking. Sin interfaz. |
| `sudoku_app.py` | La ventana, las dos pestañas y la animación. |
| `Ejecutar Sudoku.bat` | Lanzador de un click. |

## Ideas para seguir aprendiendo

- Agrega la heurística **MRV** (elegir siempre la casilla con menos opciones
  posibles): verás cómo los retrocesos caen en picada. Es un gran ejercicio.
- Genera puzzles aleatorios en vez de tenerlos fijos.
- Colorea también la fila/columna/caja que causó cada conflicto durante el
  backtracking, para entender *por qué* retrocede.
