"""
sudoku_app.py
=============
Interfaz gráfica del Sudoku, con Tkinter (viene incluido en Python).

Tiene dos pestañas (usando ttk.Notebook):
  1. "Resolver"  -> muestra al algoritmo de backtracking resolviendo el
                    puzzle paso a paso, con control de velocidad.
  2. "Jugar"     -> tú escribes los números; puedes comprobar errores,
                    pedir la solución o borrar.

Todo el cálculo vive en `sudoku_logica.py`. Esta interfaz solo dibuja el
tablero y reacciona a los clicks (separación lógica / interfaz).
"""

import tkinter as tk
from tkinter import ttk, font as tkfont

import sudoku_logica as sl

# --- Colores (en un solo lugar para poder cambiar el tema fácil) ---
COLOR_FONDO = "#0f172a"
COLOR_LINEA = "#64748b"      # líneas de la grilla (se ven entre las casillas)
COLOR_CELDA = "#1e293b"      # fondo normal de una casilla
COLOR_GIVEN = "#f8fafc"      # números "dados" del puzzle (blancos)
COLOR_ALGO = "#4ade80"       # números que pone el algoritmo (verde)
COLOR_USUARIO = "#60a5fa"    # números que escribe el jugador (azul)
COLOR_HL = "#4338ca"         # casilla que el algoritmo está probando ahora
COLOR_BACK = "#7f1d1d"       # destello al retroceder (backtrack)
COLOR_CONFLICTO = "#dc2626"  # casilla en conflicto (error del jugador)
COLOR_OK = "#166534"         # verde de "resuelto"


class Tablero:
    """
    Un tablero 9x9 reutilizable. Puede ser de solo lectura (Labels, para la
    animación) o editable (Entries, para jugar).
    Guarda las 81 casillas en una matriz para actualizarlas por (fila, col).
    """

    def __init__(self, parent, editable, fuente):
        self.editable = editable
        self.fuente = fuente
        self.celdas = [[None] * 9 for _ in range(9)]
        # El fondo del contenedor es el color de las líneas; los pequeños
        # espacios (padx/pady) entre casillas dejan ver ese color como grilla.
        self.frame = tk.Frame(parent, bg=COLOR_LINEA)

        # Construimos por cajas de 3x3 para que las líneas gruesas de las
        # cajas se noten (separación un poco mayor entre cajas).
        for caja_r in range(3):
            for caja_c in range(3):
                caja = tk.Frame(self.frame, bg=COLOR_LINEA)
                caja.grid(row=caja_r, column=caja_c, padx=2, pady=2)
                for ir in range(3):
                    for ic in range(3):
                        r, c = caja_r * 3 + ir, caja_c * 3 + ic
                        self.celdas[r][c] = self._crear_celda(caja, ir, ic, r, c)

    def _crear_celda(self, parent, ir, ic, r, c):
        if self.editable:
            # validatecommand: solo permite vacío o un dígito 1-9.
            vcmd = (parent.register(self._validar_digito), "%P")
            e = tk.Entry(
                parent, width=2, justify="center", font=self.fuente,
                bg=COLOR_CELDA, fg=COLOR_USUARIO, insertbackground=COLOR_USUARIO,
                relief="flat", disabledbackground=COLOR_CELDA,
                disabledforeground=COLOR_GIVEN, validate="key", validatecommand=vcmd,
            )
            e.grid(row=ir, column=ic, padx=1, pady=1, ipady=6)
            return e
        else:
            lbl = tk.Label(
                parent, width=2, height=1, font=self.fuente,
                bg=COLOR_CELDA, fg=COLOR_GIVEN,
            )
            lbl.grid(row=ir, column=ic, padx=1, pady=1, ipady=4)
            return lbl

    @staticmethod
    def _validar_digito(texto):
        """Acepta el cambio solo si queda vacío o es un único dígito 1-9."""
        return texto == "" or (len(texto) == 1 and texto in "123456789")

    # --- API de dibujo ---
    def set_celda(self, r, c, valor, color=None, fondo=COLOR_CELDA):
        """Escribe un valor en una casilla tipo Label (modo animación)."""
        texto = str(valor) if valor else ""
        self.celdas[r][c].config(text=texto, bg=fondo)
        if color:
            self.celdas[r][c].config(fg=color)

    def pintar_fondo(self, r, c, fondo):
        self.celdas[r][c].config(bg=fondo)

    def leer_grid(self):
        """Lee una grilla 9x9 desde las casillas editables (Entries)."""
        grid = [[0] * 9 for _ in range(9)]
        for r in range(9):
            for c in range(9):
                txt = self.celdas[r][c].get().strip()
                grid[r][c] = int(txt) if txt.isdigit() else 0
        return grid


class SudokuApp:
    def __init__(self, root):
        self.root = root
        root.title("Sudoku — Solver y Juego")
        root.configure(bg=COLOR_FONDO)
        root.resizable(False, False)

        self.fuente_celda = tkfont.Font(family="Consolas", size=20, weight="bold")
        self.fuente_ui = tkfont.Font(family="Segoe UI", size=10)
        self.fuente_titulo = tkfont.Font(family="Segoe UI", size=13, weight="bold")

        # Estado de la animación
        self.pasos = []
        self.idx = 0
        self.retrocesos = 0
        self.ultima = None
        self.after_id = None
        self.corriendo = False
        self.grid_anim_inicial = None

        # Estilo de las pestañas (ttk necesita un Style aparte)
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TNotebook", background=COLOR_FONDO, borderwidth=0)
        estilo.configure("TNotebook.Tab", padding=(18, 8), font=("Segoe UI", 10, "bold"))

        self.nb = ttk.Notebook(root)
        self.nb.pack(padx=12, pady=12)

        self._construir_pestana_resolver()
        self._construir_pestana_jugar()

        # Cargar el fácil de entrada en ambas pestañas
        self._cargar_animacion("Fácil")
        self._cargar_juego("Fácil")

    # =======================================================================
    # PESTAÑA 1: RESOLVER (animación del backtracking)
    # =======================================================================
    def _construir_pestana_resolver(self):
        tab = tk.Frame(self.nb, bg=COLOR_FONDO)
        self.nb.add(tab, text="  Resolver  ")

        tk.Label(tab, text="Mira al algoritmo resolver", bg=COLOR_FONDO,
                 fg="#e2e8f0", font=self.fuente_titulo).pack(pady=(10, 2))
        tk.Label(tab, text="Verde = número colocado · destello rojo = retroceso (backtrack)",
                 bg=COLOR_FONDO, fg="#94a3b8", font=self.fuente_ui).pack(pady=(0, 8))

        self.tablero_anim = Tablero(tab, editable=False, fuente=self.fuente_celda)
        self.tablero_anim.frame.pack(padx=12)

        # Selector de dificultad
        fila_dif = tk.Frame(tab, bg=COLOR_FONDO)
        fila_dif.pack(pady=(12, 4))
        tk.Label(fila_dif, text="Dificultad:", bg=COLOR_FONDO, fg="#cbd5e1",
                 font=self.fuente_ui).pack(side="left", padx=(0, 6))
        for nombre in ("Fácil", "Medio", "Difícil"):
            tk.Button(fila_dif, text=nombre, font=self.fuente_ui, bd=0,
                      bg="#334155", fg="white", activebackground="#475569",
                      cursor="hand2", padx=10,
                      command=lambda n=nombre: self._cargar_animacion(n)
                      ).pack(side="left", padx=3)

        # Control de velocidad
        fila_vel = tk.Frame(tab, bg=COLOR_FONDO)
        fila_vel.pack(pady=4)
        tk.Label(fila_vel, text="Velocidad:", bg=COLOR_FONDO, fg="#cbd5e1",
                 font=self.fuente_ui).pack(side="left", padx=(0, 6))
        # El slider es "ms por jugada" al revés: a la derecha = más rápido.
        self.velocidad = tk.IntVar(value=30)
        tk.Scale(fila_vel, from_=120, to=1, orient="horizontal", length=200,
                 variable=self.velocidad, showvalue=False, bg=COLOR_FONDO,
                 fg="white", troughcolor="#334155", highlightthickness=0,
                 label="lento → rápido", font=("Segoe UI", 8)).pack(side="left")

        # Botones de acción
        fila_acc = tk.Frame(tab, bg=COLOR_FONDO)
        fila_acc.pack(pady=(6, 12))
        self.btn_play = tk.Button(fila_acc, text="▶  Resolver", font=self.fuente_ui,
                                  bd=0, bg="#2563eb", fg="white", cursor="hand2",
                                  activebackground="#1d4ed8", padx=14, pady=4,
                                  command=self._toggle_animacion)
        self.btn_play.pack(side="left", padx=4)
        tk.Button(fila_acc, text="↺  Reiniciar", font=self.fuente_ui, bd=0,
                  bg="#334155", fg="white", cursor="hand2",
                  activebackground="#475569", padx=14, pady=4,
                  command=self._reiniciar_animacion).pack(side="left", padx=4)

        self.lbl_estado = tk.Label(tab, text="", bg=COLOR_FONDO, fg="#4ade80",
                                   font=self.fuente_ui)
        self.lbl_estado.pack(pady=(0, 10))

    def _cargar_animacion(self, nombre):
        """Carga un puzzle en el tablero de animación y precalcula sus pasos."""
        self._detener_animacion()
        self.dificultad_anim = nombre
        self.grid_anim_inicial = sl.copiar(sl.PUZZLES[nombre])
        # Precalculamos toda la secuencia de jugadas de una vez.
        self.pasos = sl.obtener_pasos(self.grid_anim_inicial)
        self._reiniciar_animacion()

    def _reiniciar_animacion(self):
        """Vuelve a mostrar el puzzle inicial, listo para animar de nuevo."""
        self._detener_animacion()
        self.idx = 0
        self.retrocesos = 0
        self.ultima = None
        self._pintar_puzzle_inicial()
        self.lbl_estado.config(
            text=f"{self.dificultad_anim}: {len(self.pasos)} jugadas por delante",
            fg="#94a3b8")
        self.btn_play.config(text="▶  Resolver")

    def _pintar_puzzle_inicial(self):
        """Dibuja los números 'dados' (blancos) y deja el resto vacío."""
        g = self.grid_anim_inicial
        for r in range(9):
            for c in range(9):
                if g[r][c] != 0:
                    self.tablero_anim.set_celda(r, c, g[r][c], COLOR_GIVEN)
                else:
                    self.tablero_anim.set_celda(r, c, 0, COLOR_ALGO)

    def _toggle_animacion(self):
        """Play / Pausa."""
        if self.corriendo:
            self._detener_animacion()
            self.btn_play.config(text="▶  Continuar")
        else:
            if self.idx >= len(self.pasos):  # si ya terminó, reinicia
                self._reiniciar_animacion()
            self.corriendo = True
            self.btn_play.config(text="⏸  Pausar")
            self._animar()

    def _detener_animacion(self):
        self.corriendo = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def _animar(self):
        """Reproduce UNA jugada y se agenda a sí misma para la siguiente."""
        if self.idx >= len(self.pasos):
            self._detener_animacion()
            # limpia el resaltado de la última casilla
            if self.ultima:
                r, c = self.ultima
                self.tablero_anim.pintar_fondo(r, c, COLOR_OK)
            self.lbl_estado.config(
                text=f"¡Resuelto! {self.idx} jugadas, {self.retrocesos} retrocesos.",
                fg="#4ade80")
            self.btn_play.config(text="▶  Resolver")
            return

        fila, col, valor, accion = self.pasos[self.idx]
        self.idx += 1

        # Restaura el fondo de la casilla resaltada anteriormente
        if self.ultima and self.ultima != (fila, col):
            pr, pc = self.ultima
            self.tablero_anim.pintar_fondo(pr, pc, COLOR_CELDA)

        if accion == "colocar":
            self.tablero_anim.set_celda(fila, col, valor, COLOR_ALGO, COLOR_HL)
        else:  # borrar (backtrack)
            self.retrocesos += 1
            self.tablero_anim.set_celda(fila, col, 0, COLOR_ALGO, COLOR_BACK)

        self.ultima = (fila, col)
        self.lbl_estado.config(
            text=f"Jugada {self.idx}/{len(self.pasos)} · retrocesos: {self.retrocesos}",
            fg="#cbd5e1")

        self.after_id = self.root.after(self.velocidad.get(), self._animar)

    # =======================================================================
    # PESTAÑA 2: JUGAR
    # =======================================================================
    def _construir_pestana_jugar(self):
        tab = tk.Frame(self.nb, bg=COLOR_FONDO)
        self.nb.add(tab, text="  Jugar  ")

        tk.Label(tab, text="Juega tú", bg=COLOR_FONDO, fg="#e2e8f0",
                 font=self.fuente_titulo).pack(pady=(10, 2))
        tk.Label(tab, text="Escribe dígitos 1-9. Los números blancos vienen dados.",
                 bg=COLOR_FONDO, fg="#94a3b8", font=self.fuente_ui).pack(pady=(0, 8))

        self.tablero_juego = Tablero(tab, editable=True, fuente=self.fuente_celda)
        self.tablero_juego.frame.pack(padx=12)

        fila_dif = tk.Frame(tab, bg=COLOR_FONDO)
        fila_dif.pack(pady=(12, 4))
        tk.Label(fila_dif, text="Nuevo juego:", bg=COLOR_FONDO, fg="#cbd5e1",
                 font=self.fuente_ui).pack(side="left", padx=(0, 6))
        for nombre in ("Fácil", "Medio", "Difícil"):
            tk.Button(fila_dif, text=nombre, font=self.fuente_ui, bd=0,
                      bg="#334155", fg="white", activebackground="#475569",
                      cursor="hand2", padx=10,
                      command=lambda n=nombre: self._cargar_juego(n)
                      ).pack(side="left", padx=3)

        fila_acc = tk.Frame(tab, bg=COLOR_FONDO)
        fila_acc.pack(pady=(10, 6))
        tk.Button(fila_acc, text="✓  Comprobar", font=self.fuente_ui, bd=0,
                  bg="#2563eb", fg="white", cursor="hand2",
                  activebackground="#1d4ed8", padx=12, pady=4,
                  command=self._comprobar_juego).pack(side="left", padx=4)
        tk.Button(fila_acc, text="Resolver", font=self.fuente_ui, bd=0,
                  bg="#7c3aed", fg="white", cursor="hand2",
                  activebackground="#6d28d9", padx=12, pady=4,
                  command=self._resolver_juego).pack(side="left", padx=4)
        tk.Button(fila_acc, text="Borrar mis números", font=self.fuente_ui, bd=0,
                  bg="#b91c1c", fg="white", cursor="hand2",
                  activebackground="#7f1d1d", padx=12, pady=4,
                  command=lambda: self._cargar_juego(self.dificultad_juego)
                  ).pack(side="left", padx=4)

        self.lbl_estado_juego = tk.Label(tab, text="", bg=COLOR_FONDO,
                                         fg="#cbd5e1", font=self.fuente_ui)
        self.lbl_estado_juego.pack(pady=(0, 10))

    def _cargar_juego(self, nombre):
        """Carga un puzzle en el tablero editable, bloqueando los dados."""
        self.dificultad_juego = nombre
        g = sl.PUZZLES[nombre]
        for r in range(9):
            for c in range(9):
                celda = self.tablero_juego.celdas[r][c]
                celda.config(state="normal")
                celda.delete(0, tk.END)
                if g[r][c] != 0:
                    celda.insert(0, str(g[r][c]))
                    # 'disabled' bloquea la edición: son los números dados.
                    celda.config(state="disabled")
                else:
                    celda.config(fg=COLOR_USUARIO, bg=COLOR_CELDA)
        self.lbl_estado_juego.config(text=f"Nuevo juego: {nombre}", fg="#cbd5e1")

    def _comprobar_juego(self):
        """Marca en rojo los conflictos; felicita si está completo y correcto."""
        grid = self.tablero_juego.leer_grid()
        # Primero limpia rojos previos en las casillas editables
        for r in range(9):
            for c in range(9):
                celda = self.tablero_juego.celdas[r][c]
                if celda["state"] != "disabled":
                    celda.config(bg=COLOR_CELDA)

        malas = sl.conflictos(grid)
        for (r, c) in malas:
            self.tablero_juego.celdas[r][c].config(bg=COLOR_CONFLICTO)

        if malas:
            self.lbl_estado_juego.config(
                text=f"Hay {len(malas)} casilla(s) en conflicto (en rojo).",
                fg="#fca5a5")
        elif sl.esta_completo(grid):
            self.lbl_estado_juego.config(text="¡Resuelto! Perfecto. 🎉", fg="#4ade80")
        else:
            self.lbl_estado_juego.config(
                text="Sin errores por ahora. Sigue así.", fg="#4ade80")

    def _resolver_juego(self):
        """Rellena la solución (respeta los números dados del puzzle)."""
        base = sl.PUZZLES[self.dificultad_juego]
        solucion = sl.resolver(base)
        if solucion is None:
            self.lbl_estado_juego.config(text="Este puzzle no tiene solución.",
                                         fg="#fca5a5")
            return
        for r in range(9):
            for c in range(9):
                celda = self.tablero_juego.celdas[r][c]
                if celda["state"] == "disabled":
                    continue  # no tocar los dados
                celda.delete(0, tk.END)
                celda.insert(0, str(solucion[r][c]))
                celda.config(fg=COLOR_ALGO, bg=COLOR_CELDA)
        self.lbl_estado_juego.config(text="Solución mostrada (en verde).",
                                     fg="#4ade80")


def main():
    root = tk.Tk()
    SudokuApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
