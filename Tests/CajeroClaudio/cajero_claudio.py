"""
cajero_claudio.py
=================
Interfaz gráfica (GUI) de un cajero automático, hecha con Tkinter.

Tkinter viene INCLUIDO con Python: no hay que instalar nada. Por eso es
perfecto para aprender GUIs sin ensuciar el equipo con dependencias.

Ideas centrales de una GUI que vas a ver acá:
  1. WIDGETS: los componentes visuales (botones, etiquetas, marcos).
  2. LAYOUT: cómo se acomodan en la ventana. Acá usamos .grid() (una grilla
     de filas y columnas), ideal para un teclado tipo cajero.
  3. EVENTOS / CALLBACKS: cada botón tiene un `command=` que apunta a una
     función. Cuando el usuario hace click, Tkinter llama a esa función.
     Programar UIs es, en el fondo, "reaccionar a eventos".
  4. ESTADO: la app guarda en qué situación está (qué monto lleva escrito).

Fíjate que este archivo NO calcula billetes: para eso importa `logica`.
La interfaz solo muestra cosas y reacciona a clicks. Esa separación es la
misma que te expliqué antes: lógica pura por un lado, interfaz por otro.
"""

import tkinter as tk
from tkinter import font as tkfont

# Importamos nuestra lógica de negocio (el otro archivo).
from logica import (
    calcular_billetes,
    total_billetes,
    formatear_clp,
    MontoInvalido,
    BILLETES,
)

# ---------------------------------------------------------------------------
# Paleta de colores. Definirlos como constantes en un solo lugar hace que
# cambiar el "tema" de la app sea trivial: tocas acá y cambia todo.
# ---------------------------------------------------------------------------
COLOR_FONDO = "#0f172a"       # azul muy oscuro (fondo de la ventana)
COLOR_PANEL = "#1e293b"       # gris azulado (marcos)
COLOR_PANTALLA = "#052e2b"    # verde oscuro (la "pantalla" del cajero)
COLOR_TEXTO_PANTALLA = "#4ade80"  # verde brillante, estilo display
COLOR_TECLA = "#334155"       # teclas numéricas
COLOR_TECLA_TEXTO = "#f1f5f9"
COLOR_ACCION = "#2563eb"      # botón principal (Retirar)
COLOR_BORRAR = "#b91c1c"      # botón borrar
COLOR_RAPIDO = "#7c3aed"      # botones de montos rápidos


class CajeroApp:
    """
    Toda la app envuelta en una clase.

    ¿Por qué una clase? Porque una GUI tiene ESTADO (el monto que se va
    escribiendo) y muchas funciones que comparten ese estado. Guardarlo en
    `self.` es mucho más limpio que usar variables globales sueltas.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cajero Claudio")
        self.root.configure(bg=COLOR_FONDO)
        self.root.resizable(False, False)  # tamaño fijo, como un cajero real

        # ESTADO: el monto que el usuario va tecleando, como texto.
        # Lo guardamos como string porque se construye dígito a dígito.
        self.monto_texto = ""

        # Fuentes reutilizables.
        self.fuente_pantalla = tkfont.Font(family="Consolas", size=28, weight="bold")
        self.fuente_mensaje = tkfont.Font(family="Segoe UI", size=10)
        self.fuente_tecla = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        self.fuente_titulo = tkfont.Font(family="Segoe UI", size=14, weight="bold")

        self._construir_interfaz()
        self._actualizar_pantalla()

    # -----------------------------------------------------------------------
    # CONSTRUCCIÓN DE LA INTERFAZ (se arma una sola vez, al iniciar)
    # -----------------------------------------------------------------------
    def _construir_interfaz(self):
        # Título arriba.
        tk.Label(
            self.root, text="🏧  Cajero Claudio", bg=COLOR_FONDO, fg="#e2e8f0",
            font=self.fuente_titulo,
        ).grid(row=0, column=0, columnspan=2, pady=(14, 6))

        # --- PANTALLA (donde se ve el monto y los mensajes) ---
        pantalla = tk.Frame(self.root, bg=COLOR_PANTALLA, bd=0)
        pantalla.grid(row=1, column=0, columnspan=2, padx=16, pady=6, sticky="ew")

        # Etiqueta pequeña de instrucción / error (arriba de la pantalla).
        self.lbl_mensaje = tk.Label(
            pantalla, text="", bg=COLOR_PANTALLA, fg="#fca5a5",
            font=self.fuente_mensaje, anchor="w",
        )
        self.lbl_mensaje.pack(fill="x", padx=14, pady=(10, 0))

        # El "display" grande con el monto.
        self.lbl_pantalla = tk.Label(
            pantalla, text="$0", bg=COLOR_PANTALLA, fg=COLOR_TEXTO_PANTALLA,
            font=self.fuente_pantalla, anchor="e",
        )
        self.lbl_pantalla.pack(fill="x", padx=14, pady=(0, 12))

        # --- MONTOS RÁPIDOS (como los botones sugeridos de un cajero real) ---
        marco_rapidos = tk.Frame(self.root, bg=COLOR_FONDO)
        marco_rapidos.grid(row=2, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="ew")
        for i, monto in enumerate([10000, 20000, 50000, 100000]):
            b = tk.Button(
                marco_rapidos, text=formatear_clp(monto), bg=COLOR_RAPIDO,
                fg="white", font=self.fuente_mensaje, bd=0, relief="flat",
                activebackground="#6d28d9", cursor="hand2",
                # OJO al `m=monto`: "captura" el valor actual de monto. Sin eso,
                # por cómo funcionan los closures en Python, todos los botones
                # terminarían usando el último monto del bucle. Es un error
                # clásico al crear botones dentro de un for.
                command=lambda m=monto: self._fijar_monto(m),
            )
            b.grid(row=0, column=i, padx=3, pady=2, sticky="ew")
            marco_rapidos.columnconfigure(i, weight=1)

        # --- TECLADO NUMÉRICO ---
        teclado = tk.Frame(self.root, bg=COLOR_FONDO)
        teclado.grid(row=3, column=0, columnspan=2, padx=16, pady=10)

        # Distribución de teclas: cada tupla es (texto, fila, columna).
        botones = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("000", 3, 0), ("0", 3, 1), ("←", 3, 2),
        ]
        for texto, fila, col in botones:
            self._crear_tecla(teclado, texto, fila, col)

        # --- BOTONES DE ACCIÓN: Borrar y Retirar ---
        acciones = tk.Frame(self.root, bg=COLOR_FONDO)
        acciones.grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")

        tk.Button(
            acciones, text="Borrar", bg=COLOR_BORRAR, fg="white",
            font=self.fuente_tecla, bd=0, relief="flat", cursor="hand2",
            activebackground="#7f1d1d", command=self._borrar_todo,
        ).grid(row=0, column=0, padx=3, ipady=6, sticky="ew")

        tk.Button(
            acciones, text="Retirar 💵", bg=COLOR_ACCION, fg="white",
            font=self.fuente_tecla, bd=0, relief="flat", cursor="hand2",
            activebackground="#1d4ed8", command=self._retirar,
        ).grid(row=0, column=1, padx=3, ipady=6, sticky="ew")
        acciones.columnconfigure(0, weight=1)
        acciones.columnconfigure(1, weight=2)

        # --- ZONA DE RESULTADO (el desglose de billetes entregados) ---
        self.marco_resultado = tk.Frame(self.root, bg=COLOR_PANEL)
        self.marco_resultado.grid(
            row=5, column=0, columnspan=2, padx=16, pady=(4, 16), sticky="ew"
        )
        self.lbl_resultado = tk.Label(
            self.marco_resultado, text="", bg=COLOR_PANEL, fg="#e2e8f0",
            font=self.fuente_mensaje, justify="left", anchor="w",
        )
        self.lbl_resultado.pack(fill="x", padx=12, pady=10)

    def _crear_tecla(self, contenedor, texto, fila, col):
        """Crea un botón del teclado numérico y lo ubica en la grilla."""
        b = tk.Button(
            contenedor, text=texto, bg=COLOR_TECLA, fg=COLOR_TECLA_TEXTO,
            font=self.fuente_tecla, width=5, bd=0, relief="flat",
            activebackground="#475569", cursor="hand2",
            command=lambda t=texto: self._tecla_presionada(t),
        )
        b.grid(row=fila, column=col, padx=4, pady=4, ipady=10)

    # -----------------------------------------------------------------------
    # CALLBACKS: funciones que reaccionan a los clicks
    # -----------------------------------------------------------------------
    def _tecla_presionada(self, tecla: str):
        """Se llama cuando el usuario aprieta una tecla del teclado numérico."""
        self._limpiar_resultado()

        if tecla == "←":
            # Borra el último dígito.
            self.monto_texto = self.monto_texto[:-1]
        else:
            # Evita montos absurdamente largos (máx 7 dígitos = 9.999.999).
            if len(self.monto_texto) + len(tecla) <= 7:
                # Evita ceros a la izquierda inútiles (que "007" quede como "7").
                nuevo = self.monto_texto + tecla
                self.monto_texto = str(int(nuevo)) if nuevo else ""

        self._actualizar_pantalla()

    def _fijar_monto(self, monto: int):
        """Botón de monto rápido: reemplaza lo escrito por el monto elegido."""
        self._limpiar_resultado()
        self.monto_texto = str(monto)
        self._actualizar_pantalla()

    def _borrar_todo(self):
        """Botón Borrar: deja la pantalla en cero."""
        self.monto_texto = ""
        self._limpiar_resultado()
        self.lbl_mensaje.config(text="")
        self._actualizar_pantalla()

    def _retirar(self):
        """
        Botón Retirar: acá conectamos la interfaz con la lógica.
        Toma el monto de la pantalla, pide el cálculo a `logica` y muestra
        el resultado (o el error de validación).
        """
        if not self.monto_texto:
            self.lbl_mensaje.config(text="Ingrese un monto primero.")
            return

        monto = int(self.monto_texto)

        try:
            billetes = calcular_billetes(monto)  # <- la lógica pura
        except MontoInvalido as e:
            # La lógica avisa que el monto no sirve; lo mostramos en pantalla.
            self.lbl_mensaje.config(text=str(e))
            return

        self.lbl_mensaje.config(text="Retiro exitoso ✓")
        self._mostrar_resultado(monto, billetes)

    # -----------------------------------------------------------------------
    # HELPERS de presentación (solo tocan lo visual)
    # -----------------------------------------------------------------------
    def _actualizar_pantalla(self):
        """Refresca el display grande con el monto formateado."""
        monto = int(self.monto_texto) if self.monto_texto else 0
        self.lbl_pantalla.config(text=formatear_clp(monto))

    def _mostrar_resultado(self, monto: int, billetes: dict):
        """Arma el texto del desglose de billetes y lo muestra."""
        lineas = [f"Entregando {formatear_clp(monto)}:", ""]
        for denominacion in BILLETES:  # recorrer BILLETES mantiene el orden
            if denominacion in billetes:
                cantidad = billetes[denominacion]
                plural = "billete" if cantidad == 1 else "billetes"
                lineas.append(f"  {cantidad} × {formatear_clp(denominacion)}  ({plural})")
        lineas.append("")
        lineas.append(f"Total: {total_billetes(billetes)} billetes")
        self.lbl_resultado.config(text="\n".join(lineas), fg="#e2e8f0")

    def _limpiar_resultado(self):
        self.lbl_resultado.config(text="")

    def _mostrar_resultado_str(self):
        pass  # (reservado para futuras mejoras)


def main():
    # tk.Tk() crea la ventana principal. Toda app Tkinter empieza así.
    root = tk.Tk()
    CajeroApp(root)
    # mainloop() cede el control a Tkinter: queda esperando eventos (clicks,
    # teclas, cierre de ventana) hasta que cierras la ventana. Sin esta línea
    # la ventana se abriría y cerraría al instante.
    root.mainloop()


if __name__ == "__main__":
    main()
