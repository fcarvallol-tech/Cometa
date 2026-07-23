# Cajero Claudio 🏧

Un cajero automático con interfaz gráfica (GUI) hecho en Python con **Tkinter**.
Clickeable como un cajero real: teclado numérico, montos rápidos y botón de retiro.

## Cómo ejecutarlo (un click)

Haz **doble click en `Ejecutar Cajero.bat`**.

La primera vez crea un entorno virtual local (`.venv`) dentro de esta misma
carpeta y luego abre la app. No instala nada en tu sistema ni modifica tu
Python global — todo queda contenido acá. Tkinter ya viene con Python, así que
en realidad no se descarga ninguna dependencia.

> ¿No tienes Python? Instálalo desde https://www.python.org/downloads/ y marca
> la casilla **"Add Python to PATH"** durante la instalación.

También puedes abrirlo a mano desde una terminal:

```
python cajero_claudio.py
```

## Qué archivo hace qué

| Archivo | Rol |
|---|---|
| `logica.py` | **Lógica pura**: calcula los billetes. Sin ventanas ni prints. |
| `cajero_claudio.py` | **Interfaz gráfica**: la ventana, los botones y los clicks. |
| `Ejecutar Cajero.bat` | Lanzador de un click (crea el `.venv` y ejecuta). |

Esta división —lógica por un lado, interfaz por otro— es la misma idea que te
expliqué antes: se llama **separación de responsabilidades**. Te deja testear
el cálculo sin abrir la ventana, y cambiar la interfaz sin tocar la lógica.

## Conceptos de GUI que aparecen en el código

Todo está comentado en `cajero_claudio.py`, pero en resumen:

1. **Widgets**: los componentes visuales (`Button`, `Label`, `Frame`).
2. **Layout con `.grid()`**: acomoda los widgets en una grilla de filas y
   columnas. Perfecto para un teclado tipo cajero.
3. **Eventos / callbacks**: cada botón tiene un `command=` que apunta a una
   función. Programar una GUI es, en el fondo, reaccionar a eventos.
4. **Estado**: la app recuerda el monto que vas tecleando (`self.monto_texto`).
5. **`mainloop()`**: el "motor" que mantiene la ventana viva escuchando clicks.

## Para seguir aprendiendo (ideas de mejora)

- Agrega un saldo de cuenta y descuéntalo en cada retiro.
- Simula el **stock de billetes** del cajero (que se pueda quedar sin billetes
  de cierta denominación) — ahí el algoritmo greedy se pone interesante.
- Soporta el teclado físico además de los botones (eventos `bind`).
- Reemplaza Tkinter por una interfaz web con **FastAPI** (que ya viste en un
  import) + HTML, reutilizando `logica.py` tal cual. Ese es el mejor ejemplo de
  por qué separar la lógica valió la pena.
