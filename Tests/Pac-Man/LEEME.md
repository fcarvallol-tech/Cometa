# Pac-Man Jardín 🟡🌼

Un Pac-Man jugable con interfaz gráfica en Python (Tkinter + Canvas), ambientado
en un jardín: setos verdes en vez de paredes, semillas y flores en vez de puntos.

## Cómo ejecutarlo (un click)

Doble click en **`Ejecutar Pac-Man.bat`**. La primera vez crea un `.venv` local
en esta carpeta y abre el juego. No instala nada (Tkinter viene con Python) ni
modifica tu equipo. También sirve:

```
python pacman_app.py
```

> Importante: haz **click sobre la ventana del juego** para que reciba el teclado.

## Pantalla inicial y ajustes

Al abrir el juego ves un **menú** para elegir entre 3 jardines (con vista
previa): *Jardín Clásico*, *Plaza Abierta* y *Laberinto*. Haz click en el que
quieras y luego en **▶ Jugar**.

El botón **⚙ Ajustes** (en el menú y dentro del juego) te deja configurar:

- **Velocidad**: Normal / Rápida / Muy rápida.
- **Dificultad**: Fácil / Normal / Difícil (afecta la rapidez de los fantasmas,
  cuánto duran asustados y qué tan seguido dispara el rayo).

## Controles

- **Flechas** o **WASD**: mover.
- **F**: usar **Flash** (ver abajo).
- **R**: reiniciar la partida.
- **☰ Menú**: volver a elegir mapa.

## Reglas

- Cómete todas las semillas y flores para **ganar**.
- Si un fantasma te toca sin estar asustado, pierdes una vida. Tienes 3.
- Los dos extremos de la fila del medio son un **túnel**: sales por un lado y
  apareces por el otro.

## Las flores grandes (galletas poderosas) = dos poderes

Cada una de las 4 **flores grandes** de las esquinas te da DOS cosas:

1. Pone a los fantasmas **asustados** unos segundos: durante ese rato te los
   puedes comer (+200).
2. Te suma una **carga de Flash ⚡**. Con la tecla **F** te **teletransportas
   2 casillas** en la dirección en la que vas (si hay un seto, saltas hasta
   donde alcances). Ideal para escapar de un fantasma o del rayo. El contador
   de Flash se ve arriba, junto al puntaje.

## Cómo piensan los fantasmas (la parte interesante)

Cada fantasma, al llegar al centro de una casilla, elige el giro que más lo
acerca a su casilla **objetivo**. Lo que cambia es el objetivo, y eso les da
personalidad (igual que en el arcade original):

- **Rojo (Blinky)**: te persigue directo.
- **Rosa (Pinky)**: apunta 4 casillas *adelante* tuyo, para emboscarte.
- **Naranjo (Clyde)**: te persigue si está lejos, pero si se acerca demasiado
  se asusta y huye a su esquina.
- **Morado (Rayo) ⚡**: el fantasma especial. Te persigue directo y, cuando
  quedas a **2 casillas o menos**, se pone a **cargar** (destella amarillo y
  suelta chispas) por un instante y luego dispara un **rayo**. Si el rayo te
  pilla dentro del alcance, pierdes una vida — ¡pero tienes ese instante de
  aviso para escapar! Tras disparar necesita unos segundos para recargar, y
  mientras está asustado no puede usar el poder.

Regla clásica: los fantasmas no pueden dar media vuelta (180°), salvo en un
callejón sin salida. Cuando están asustados, se mueven al azar.

## Cómo funciona por dentro

- **Bucle de juego**: `_tick()` se re-agenda con `root.after()` ~25 veces por
  segundo. En cada vuelta: mover → comer → mover fantasmas → colisiones →
  redibujar. Ese patrón es el corazón de casi cualquier videojuego.
- **Movimiento alineado a la grilla**: los personajes se mueven de a 2 px
  (suave), pero solo pueden **girar cuando están centrados** en una casilla.
  Como 2 divide a 24 (el tamaño de casilla), siempre caen justo en el centro.
- **Laberinto garantizado conexo**: se genera con un patrón de pilares, así que
  nunca hay un punto inalcanzable. Además un BFS marca las casillas alcanzables
  y solo ahí se ponen puntos, para que el juego siempre se pueda ganar.

Como siempre, la lógica (`pacman_logica.py`) está separada del dibujo
(`pacman_app.py`).

## Ideas para seguir

- Agrega un 4º fantasma (Inky, que combina la posición de Blinky y Pac-Man).
- Sube la dificultad por nivel (fantasmas más rápidos).
- Reemplaza la IA "greedy" por búsqueda **BFS** hacia el objetivo y compara el
  comportamiento.
