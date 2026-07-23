"""
pacman_app.py
=============
Pac-Man en un jardín, con interfaz gráfica (Tkinter + Canvas).

Esta versión agrega:
  - PANTALLA INICIAL para elegir entre 3 mapas (con vista previa).
  - AJUSTES (engranaje ⚙): velocidad y dificultad.
  - Poder FLASH: cada galleta poderosa (flor grande) te da una carga; con la
    tecla F te teletransportas 2 casillas en la dirección en la que vas.
  - Un poco más rápido de base.

La lógica del mapa y la IA viven en pacman_logica.py.
"""

import math
import random
import tkinter as tk

import pacman_logica as pl

TILE = 24
VEL_PAC = 2
VEL_FANT = 2
VIDAS_INICIALES = 3

# Velocidad = milisegundos por cuadro (menos = más rápido). Mantenemos el paso
# en 2 px (que divide a TILE) para que todo siga cayendo justo en la grilla.
VEL_MS = {"Normal": 24, "Rápida": 18, "Muy rápida": 13}

# Parámetros por dificultad.
DIFICULTAD = {
    "Fácil":   {"cadencia": 3, "asustado_s": 9.0, "rayo_cd_s": 3.4, "carga_s": 0.5, "rango": 2},
    "Normal":  {"cadencia": 1, "asustado_s": 7.0, "rayo_cd_s": 2.6, "carga_s": 0.42, "rango": 2},
    "Difícil": {"cadencia": 1, "asustado_s": 4.5, "rayo_cd_s": 1.8, "carga_s": 0.34, "rango": 2},
}

# --- Colores del jardín ---
COL_FONDO = "#0a1f12"
COL_SETO = "#166534"
COL_SETO_LUZ = "#22c55e"
COL_SEMILLA = "#fde68a"
COL_TEXTO = "#e2e8f0"
COL_PAC = "#facc15"
COL_ASUSTADO = "#2563eb"
COL_ASUSTADO_FLASH = "#e0f2fe"
COL_PETALO = ["#f9a8d4", "#fca5a5", "#c4b5fd", "#fdba74"]
COL_FLOR_CENTRO = "#fde047"
COL_FANTASMAS = ["#ef4444", "#f472b6", "#fb923c", "#a855f7"]
COL_RAYO = "#fde047"
COL_FLASH = "#67e8f9"


def centro(r, c):
    return (c * TILE + TILE // 2, r * TILE + TILE // 2)


def alineado(x, y):
    return (x - TILE // 2) % TILE == 0 and (y - TILE // 2) % TILE == 0


def tile_de(x, y):
    return ((y - TILE // 2) // TILE, (x - TILE // 2) // TILE)


def tile_cercano(x, y):
    return (round((y - TILE // 2) / TILE), round((x - TILE // 2) / TILE))


class Entidad:
    def __init__(self, r, c, direccion):
        self.x, self.y = centro(r, c)
        self.dir = direccion
        self.spawn = (r, c)

    def reset(self):
        self.x, self.y = centro(*self.spawn)


class PacManApp:
    def __init__(self, root):
        self.root = root
        root.title("Pac-Man Jardín")
        root.configure(bg=COL_FONDO)
        root.resizable(False, False)

        # Ajustes (se guardan en variables de Tkinter).
        self.var_vel = tk.StringVar(value="Rápida")
        self.var_dif = tk.StringVar(value="Normal")
        self.mapa_sel = 0
        self.jugando = False
        self._after_id = None

        # Enlaces de teclado (funcionan solo cuando se está jugando).
        teclas = {
            "Up": pl.ARRIBA, "w": pl.ARRIBA, "W": pl.ARRIBA,
            "Down": pl.ABAJO, "s": pl.ABAJO, "S": pl.ABAJO,
            "Left": pl.IZQ, "a": pl.IZQ, "A": pl.IZQ,
            "Right": pl.DER, "d": pl.DER, "D": pl.DER,
        }
        for tecla, direccion in teclas.items():
            root.bind(f"<{tecla}>", lambda e, d=direccion: self._tecla(d))
        root.bind("<f>", lambda e: self._usar_flash())
        root.bind("<F>", lambda e: self._usar_flash())
        root.bind("<r>", lambda e: self._reiniciar())
        root.bind("<R>", lambda e: self._reiniciar())

        self._construir_menu()
        self._construir_juego()
        self._mostrar_menu()

    # =======================================================================
    # PANTALLA INICIAL (menú)
    # =======================================================================
    def _construir_menu(self):
        self.menu = tk.Frame(self.root, bg=COL_FONDO)

        tk.Label(self.menu, text="Pac-Man  🌼", bg=COL_FONDO, fg=COL_PAC,
                 font=("Segoe UI", 26, "bold")).pack(pady=(24, 2))
        tk.Label(self.menu, text="Elige tu jardín", bg=COL_FONDO, fg="#4ade80",
                 font=("Segoe UI", 13)).pack(pady=(0, 14))

        fila = tk.Frame(self.menu, bg=COL_FONDO)
        fila.pack(padx=20)
        self.previews = []
        for i, nombre in enumerate(pl.NOMBRES_MAPA):
            self._crear_preview(fila, i, nombre)

        botones = tk.Frame(self.menu, bg=COL_FONDO)
        botones.pack(pady=24)
        tk.Button(botones, text="⚙  Ajustes", font=("Segoe UI", 12), bd=0,
                  bg="#334155", fg="white", activebackground="#475569",
                  cursor="hand2", padx=16, pady=8,
                  command=self._abrir_ajustes).pack(side="left", padx=8)
        tk.Button(botones, text="▶  Jugar", font=("Segoe UI", 14, "bold"), bd=0,
                  bg="#16a34a", fg="white", activebackground="#15803d",
                  cursor="hand2", padx=28, pady=8,
                  command=self._iniciar_juego).pack(side="left", padx=8)

        self._marcar_seleccion()

    def _crear_preview(self, parent, indice, nombre):
        esc = 6  # px por casilla en la miniatura
        marco = tk.Frame(parent, bg=COL_FONDO, bd=3, relief="flat")
        marco.pack(side="left", padx=10)
        cv = tk.Canvas(marco, width=pl.ANCHO * esc, height=pl.ALTO * esc,
                       bg=COL_FONDO, highlightthickness=0, cursor="hand2")
        cv.pack()
        for r in range(pl.ALTO):
            for c in range(pl.ANCHO):
                if pl.MAPAS[indice][r][c] == "#":
                    cv.create_rectangle(c * esc, r * esc, c * esc + esc, r * esc + esc,
                                        fill=COL_SETO, outline="")
        etq = tk.Label(marco, text=nombre, bg=COL_FONDO, fg=COL_TEXTO,
                       font=("Segoe UI", 10, "bold"))
        etq.pack(pady=(4, 0))
        # Click en cualquier parte selecciona ese mapa.
        for w in (cv, etq, marco):
            w.bind("<Button-1>", lambda e, i=indice: self._seleccionar_mapa(i))
        self.previews.append(marco)

    def _seleccionar_mapa(self, indice):
        self.mapa_sel = indice
        self._marcar_seleccion()

    def _marcar_seleccion(self):
        for i, marco in enumerate(self.previews):
            marco.config(bg=(COL_PAC if i == self.mapa_sel else COL_FONDO))

    def _mostrar_menu(self):
        self.jugando = False
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.juego.pack_forget()
        self.menu.pack()

    # =======================================================================
    # AJUSTES (engranaje)
    # =======================================================================
    def _abrir_ajustes(self):
        top = tk.Toplevel(self.root)
        top.title("Ajustes ⚙")
        top.configure(bg=COL_FONDO)
        top.resizable(False, False)
        top.transient(self.root)

        def grupo(titulo, variable, opciones):
            tk.Label(top, text=titulo, bg=COL_FONDO, fg=COL_PAC,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
            for op in opciones:
                tk.Radiobutton(top, text=op, variable=variable, value=op,
                               bg=COL_FONDO, fg=COL_TEXTO, selectcolor="#166534",
                               activebackground=COL_FONDO, activeforeground="white",
                               font=("Segoe UI", 11), anchor="w",
                               ).pack(anchor="w", padx=28)

        grupo("Velocidad", self.var_vel, list(VEL_MS.keys()))
        grupo("Dificultad", self.var_dif, list(DIFICULTAD.keys()))

        tk.Button(top, text="Listo", font=("Segoe UI", 11, "bold"), bd=0,
                  bg="#16a34a", fg="white", cursor="hand2", padx=20, pady=6,
                  command=top.destroy).pack(pady=16)

    def _frame_ms(self):
        return VEL_MS[self.var_vel.get()]

    def _dif(self):
        return DIFICULTAD[self.var_dif.get()]

    def _fr(self, segundos):
        """Convierte segundos a cuadros según la velocidad actual."""
        return max(1, int(segundos * 1000 / self._frame_ms()))

    # =======================================================================
    # JUEGO
    # =======================================================================
    def _construir_juego(self):
        self.juego = tk.Frame(self.root, bg=COL_FONDO)

        barra = tk.Frame(self.juego, bg=COL_FONDO)
        barra.pack(fill="x", padx=8, pady=(8, 0))
        self.lbl_info = tk.Label(barra, text="", bg=COL_FONDO, fg=COL_TEXTO,
                                 font=("Consolas", 12, "bold"))
        self.lbl_info.pack(side="left")
        tk.Button(barra, text="⚙", font=("Segoe UI", 11), bd=0, bg="#334155",
                  fg="white", cursor="hand2", command=self._abrir_ajustes
                  ).pack(side="right", padx=(6, 0))
        tk.Button(barra, text="☰ Menú", font=("Segoe UI", 10), bd=0, bg="#334155",
                  fg="white", cursor="hand2", command=self._mostrar_menu
                  ).pack(side="right")

        self.canvas = tk.Canvas(self.juego, width=pl.ANCHO * TILE, height=pl.ALTO * TILE,
                                bg=COL_FONDO, highlightthickness=0)
        self.canvas.pack(padx=8, pady=8)

    def _iniciar_juego(self):
        self.menu.pack_forget()
        self.juego.pack()
        self.maze = pl.generar_laberinto(self.mapa_sel)
        self.alcanzables = pl.celdas_alcanzables(self.maze, pl.SPAWN_PACMAN)
        self.canvas.delete("all")
        self._dibujar_setos()
        self._nuevo_juego()

    def _reiniciar(self):
        if self.jugando:
            self._nuevo_juego()

    def _nuevo_juego(self):
        self.jugando = True
        self.puntaje = 0
        self.vidas = VIDAS_INICIALES
        self.asustado = 0
        self.flash_cargas = 0
        self.flash_destello = 0
        self.game_over = False
        self.ganado = False
        self.frame = 0
        self.rayo_cd = self._fr(self._dif()["rayo_cd_s"])
        self.rayo_carga = 0
        self.rayo_destello = 0

        self.canvas.delete("comida")
        self.puntos = {}
        self.restantes = 0
        for r in range(pl.ALTO):
            for c in range(pl.ANCHO):
                if (r, c) not in self.alcanzables:
                    continue
                cel = self.maze[r][c]
                if cel == ".":
                    self.puntos[(r, c)] = self._dibujar_semilla(r, c)
                    self.restantes += 1
                elif cel == "o":
                    self.puntos[(r, c)] = self._dibujar_flor(r, c)
                    self.restantes += 1

        self.pac = Entidad(*pl.SPAWN_PACMAN, direccion=pl.IZQ)
        self.pac_deseada = pl.IZQ
        self.dirs_ini = [pl.ARRIBA, pl.IZQ, pl.DER, pl.ARRIBA]
        self.fantasmas = [Entidad(r, c, self.dirs_ini[i])
                          for i, (r, c) in enumerate(pl.SPAWN_FANTASMAS)]

        self.canvas.delete("mensaje")
        self.canvas.delete("rayo")
        self._actualizar_info()

        if self._after_id:
            self.root.after_cancel(self._after_id)
        self._tick()

    def _tecla(self, direccion):
        if self.jugando:
            self.pac_deseada = direccion

    # -----------------------------------------------------------------------
    # Poder FLASH (tecla F): teletransporta 2 casillas hacia adelante.
    # -----------------------------------------------------------------------
    def _usar_flash(self):
        if not self.jugando or self.game_over or self.ganado:
            return
        if self.flash_cargas <= 0:
            return
        r, c = tile_cercano(self.pac.x, self.pac.y)
        dx, dy = self.pac.dir
        destino = (r, c)
        for paso in (1, 2):
            nc, nr = c + dx * paso, r + dy * paso
            if r == pl.FILA_TUNEL:
                nc %= pl.ANCHO
            if pl.es_pared(self.maze, nr, nc):
                break
            destino = (nr, nc)
        if destino == (r, c):
            return  # no había espacio para saltar
        self.flash_cargas -= 1
        self.flash_destello = self._fr(0.18)
        self.pac.x, self.pac.y = centro(*destino)

    # -----------------------------------------------------------------------
    # BUCLE DE JUEGO
    # -----------------------------------------------------------------------
    def _tick(self):
        if self.jugando and not self.game_over and not self.ganado:
            self.frame += 1
            if self.asustado > 0:
                self.asustado -= 1
            self._mover_pac()
            self._comer()
            self._mover_fantasmas()
            self._actualizar_rayo()
            self._chequear_colisiones()
            self._redibujar_actores()
            self._actualizar_info()
        self._after_id = self.root.after(self._frame_ms(), self._tick)

    def _mover_pac(self):
        p = self.pac
        if alineado(p.x, p.y):
            r, c = tile_de(p.x, p.y)
            if r == pl.FILA_TUNEL and c == 0 and p.dir == pl.IZQ:
                p.x, p.y = centro(r, pl.ANCHO - 1); r, c = tile_de(p.x, p.y)
            elif r == pl.FILA_TUNEL and c == pl.ANCHO - 1 and p.dir == pl.DER:
                p.x, p.y = centro(r, 0); r, c = tile_de(p.x, p.y)
            if pl.puede_avanzar(self.maze, r, c, self.pac_deseada):
                p.dir = self.pac_deseada
            if not pl.puede_avanzar(self.maze, r, c, p.dir):
                return
        p.x += p.dir[0] * VEL_PAC
        p.y += p.dir[1] * VEL_PAC

    def _mover_fantasmas(self):
        cadencia = self._dif()["cadencia"]
        # Asustados = mitad de velocidad. Además la dificultad Fácil ralentiza.
        if self.asustado > 0 and self.frame % 2 == 0:
            return
        if cadencia > 1 and self.frame % cadencia == 0:
            return
        pac_rc = tile_cercano(self.pac.x, self.pac.y)
        for i, g in enumerate(self.fantasmas):
            if alineado(g.x, g.y):
                r, c = tile_de(g.x, g.y)
                if r == pl.FILA_TUNEL and c == 0 and g.dir == pl.IZQ:
                    g.x, g.y = centro(r, pl.ANCHO - 1); r, c = tile_de(g.x, g.y)
                elif r == pl.FILA_TUNEL and c == pl.ANCHO - 1 and g.dir == pl.DER:
                    g.x, g.y = centro(r, 0); r, c = tile_de(g.x, g.y)
                objetivo = pl.objetivo_fantasma(i, pac_rc, self.pac.dir, (r, c))
                g.dir = pl.elegir_direccion_fantasma(
                    self.maze, r, c, g.dir, objetivo, self.asustado > 0)
            g.x += g.dir[0] * VEL_FANT
            g.y += g.dir[1] * VEL_FANT

    # -----------------------------------------------------------------------
    # Poder de rayo (fantasma 3)
    # -----------------------------------------------------------------------
    def _actualizar_rayo(self):
        self.canvas.delete("rayo")
        g = self.fantasmas[3]
        gr, gc = tile_cercano(g.x, g.y)
        pr, pc = tile_cercano(self.pac.x, self.pac.y)
        dist = abs(gr - pr) + abs(gc - pc)
        rango = self._dif()["rango"]

        if self.asustado > 0:
            self.rayo_carga = 0
            self.rayo_destello = 0
            self.rayo_cd = max(self.rayo_cd, self._fr(self._dif()["carga_s"]))
            return
        if self.rayo_carga > 0:
            self.rayo_carga -= 1
            self._dibujar_chispas(g.x, g.y)
            if self.rayo_carga == 0:
                self._dibujar_rayo(g.x, g.y, self.pac.x, self.pac.y)
                self.rayo_destello = self._fr(0.16)
                self.rayo_cd = self._fr(self._dif()["rayo_cd_s"])
                if dist <= rango:
                    self._perder_vida()
            return
        if self.rayo_destello > 0:
            self.rayo_destello -= 1
            self._dibujar_rayo(g.x, g.y, self.pac.x, self.pac.y)
            return
        if self.rayo_cd > 0:
            self.rayo_cd -= 1
            return
        if dist <= rango:
            self.rayo_carga = self._fr(self._dif()["carga_s"])

    def _dibujar_chispas(self, x, y):
        for _ in range(4):
            a = random.uniform(0, 2 * math.pi)
            r = random.randint(9, 17)
            self.canvas.create_line(x, y, x + r * math.cos(a), y + r * math.sin(a),
                                    fill=COL_FANTASMAS[3], width=2, tags="rayo")

    def _dibujar_rayo(self, x1, y1, x2, y2):
        pts = [x1, y1]
        for i in range(1, 5):
            t = i / 5
            pts += [x1 + (x2 - x1) * t + random.randint(-6, 6),
                    y1 + (y2 - y1) * t + random.randint(-6, 6)]
        pts += [x2, y2]
        self.canvas.create_line(*pts, fill=COL_RAYO, width=4, tags="rayo")
        self.canvas.create_line(*pts, fill="white", width=1, tags="rayo")

    # -----------------------------------------------------------------------
    # Comer y colisiones
    # -----------------------------------------------------------------------
    def _comer(self):
        if not alineado(self.pac.x, self.pac.y):
            return
        pos = tile_de(self.pac.x, self.pac.y)
        if pos in self.puntos:
            es_power = self.maze[pos[0]][pos[1]] == "o"
            self.canvas.delete(self.puntos.pop(pos))
            self.restantes -= 1
            if es_power:
                self.puntaje += 50
                self.asustado = self._fr(self._dif()["asustado_s"])
                self.flash_cargas += 1        # ¡galleta = carga de Flash!
            else:
                self.puntaje += 10
            if self.restantes == 0:
                self.ganado = True
                self._mensaje("¡GANASTE!  🌼", "#4ade80")

    def _chequear_colisiones(self):
        for g in self.fantasmas:
            if abs(g.x - self.pac.x) < 16 and abs(g.y - self.pac.y) < 16:
                if self.asustado > 0:
                    self.puntaje += 200
                    g.reset()
                    g.dir = pl.ARRIBA
                else:
                    self._perder_vida()
                    return

    def _perder_vida(self):
        if self.game_over:
            return
        self.vidas -= 1
        self.rayo_carga = 0
        self.rayo_destello = 0
        self.rayo_cd = self._fr(self._dif()["rayo_cd_s"])
        if self.vidas <= 0:
            self.game_over = True
            self._mensaje("GAME OVER\nR para reiniciar", "#f87171")
        else:
            self.pac.reset()
            self.pac.dir = pl.IZQ
            self.pac_deseada = pl.IZQ
            for i, g in enumerate(self.fantasmas):
                g.reset()
                g.dir = self.dirs_ini[i]
            self.asustado = 0

    # -----------------------------------------------------------------------
    # Dibujo del jardín
    # -----------------------------------------------------------------------
    def _dibujar_setos(self):
        for r in range(pl.ALTO):
            for c in range(pl.ANCHO):
                if self.maze[r][c] == "#":
                    x0, y0 = c * TILE, r * TILE
                    self.canvas.create_rectangle(
                        x0 + 1, y0 + 1, x0 + TILE - 1, y0 + TILE - 1,
                        fill=COL_SETO, outline="")
                    for _ in range(3):
                        hx = x0 + random.randint(4, TILE - 4)
                        hy = y0 + random.randint(4, TILE - 4)
                        self.canvas.create_oval(hx - 3, hy - 3, hx + 3, hy + 3,
                                                fill=COL_SETO_LUZ, outline="")

    def _dibujar_semilla(self, r, c):
        x, y = centro(r, c)
        return self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2,
                                       fill=COL_SEMILLA, outline="", tags="comida")

    def _dibujar_flor(self, r, c):
        x, y = centro(r, c)
        color = COL_PETALO[(r + c) % len(COL_PETALO)]
        tag = f"flor{r}_{c}"
        for ang in range(0, 360, 72):
            px = x + 5 * math.cos(math.radians(ang))
            py = y + 5 * math.sin(math.radians(ang))
            item = self.canvas.create_oval(px - 4, py - 4, px + 4, py + 4,
                                           fill=color, outline="", tags="comida")
            self.canvas.addtag_withtag(tag, item)
        item = self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3,
                                       fill=COL_FLOR_CENTRO, outline="", tags="comida")
        self.canvas.addtag_withtag(tag, item)
        return tag

    # -----------------------------------------------------------------------
    # Dibujo de personajes (cada cuadro)
    # -----------------------------------------------------------------------
    def _redibujar_actores(self):
        self.canvas.delete("actor")
        if self.flash_destello > 0:
            self.flash_destello -= 1
            dx, dy = self.pac.dir
            self.canvas.create_line(self.pac.x - dx * 40, self.pac.y - dy * 40,
                                    self.pac.x, self.pac.y, fill=COL_FLASH,
                                    width=6, tags="actor")
        self._dibujar_pac()
        for i, g in enumerate(self.fantasmas):
            self._dibujar_fantasma(i, g)
        self.canvas.tag_raise("mensaje")

    def _dibujar_pac(self):
        abertura = 42 if (self.frame // 3) % 2 == 0 else 8
        base = {pl.DER: 0, pl.ARRIBA: 90, pl.IZQ: 180, pl.ABAJO: 270}[self.pac.dir]
        x, y, rad = self.pac.x, self.pac.y, TILE // 2 - 2
        self.canvas.create_arc(x - rad, y - rad, x + rad, y + rad,
                               start=base + abertura, extent=360 - 2 * abertura,
                               fill=COL_PAC, outline="", style="pieslice", tags="actor")

    def _dibujar_fantasma(self, i, g):
        x, y, R = g.x, g.y, TILE // 2 - 1
        if self.asustado > 0:
            if self.asustado < self._fr(2.0) and (self.frame // 4) % 2 == 0:
                color = COL_ASUSTADO_FLASH
            else:
                color = COL_ASUSTADO
        elif i == 3 and self.rayo_carga > 0:
            color = COL_RAYO
        else:
            color = COL_FANTASMAS[i]

        pts = []
        for k in range(11):
            theta = math.pi * (1 - k / 10)
            pts += [x + R * math.cos(theta), y - R * math.sin(theta)]
        pts += [x + R, y + R * 0.7]
        patas = 4
        for k in range(patas + 1):
            px = x + R - (2 * R) * (k / patas)
            py = y + R if k % 2 == 0 else y + R * 0.5
            pts += [px, py]
        self.canvas.create_polygon(*pts, fill=color, outline="", tags="actor")

        if self.asustado > 0:
            for ex in (-R * 0.35, R * 0.35):
                self.canvas.create_oval(x + ex - 2, y - 3, x + ex + 2, y + 1,
                                        fill="#1e3a8a", outline="", tags="actor")
        else:
            dx, dy = g.dir[0] * R * 0.18, g.dir[1] * R * 0.18
            for ex in (-R * 0.35, R * 0.35):
                self.canvas.create_oval(x + ex - 4, y - R * 0.35 - 2,
                                        x + ex + 4, y + R * 0.35 - 2,
                                        fill="white", outline="", tags="actor")
                self.canvas.create_oval(x + ex - 2 + dx, y - 4 + dy,
                                        x + ex + 2 + dx, y + dy,
                                        fill="#1e293b", outline="", tags="actor")
        if i == 3:
            self.canvas.create_polygon(
                x - 6, y - R + 1, x - 3, y - R - 4, x, y - R + 1,
                x + 3, y - R - 4, x + 6, y - R + 1,
                fill=COL_RAYO, outline="", tags="actor")

    def _mensaje(self, texto, color):
        cx, cy = pl.ANCHO * TILE // 2, pl.ALTO * TILE // 2
        self.canvas.create_rectangle(cx - 135, cy - 45, cx + 135, cy + 45,
                                     fill="#0a1f12", outline=color, width=2,
                                     tags="mensaje")
        self.canvas.create_text(cx, cy, text=texto, fill=color,
                                font=("Consolas", 18, "bold"),
                                justify="center", tags="mensaje")
        self.canvas.tag_raise("mensaje")

    def _actualizar_info(self):
        estado = ""
        if self.asustado > 0:
            estado = "   ¡A COMER!"
        elif self.rayo_carga > 0:
            estado = "   ⚡ ¡RAYO!"
        self.lbl_info.config(
            text=f"Puntaje: {self.puntaje}   Vidas: {'♥' * self.vidas}   "
                 f"Flash(F): {self.flash_cargas}{estado}")


def main():
    root = tk.Tk()
    PacManApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
