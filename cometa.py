"""
Cometa - Capturas de pantalla con anotaciones, para Windows
============================================================
Un cometa deja una estela: capturas, marcas lo importante y lo compartes.

Corre de fondo. Con el atajo global  Ctrl + Shift + S  captura una region de
la pantalla, la anotas (flecha, rectangulo, linea, lapiz, texto) y la copias
al portapapeles o la guardas como PNG.

Requisitos:
    - Python 3.8+ (Tkinter viene incluido en el instalador oficial de Windows)
    - Pillow  ->  py -m pip install pillow

Uso:
    py cometa.py               (queda una ventanita chica escuchando el atajo)

Atajos globales (desde cualquier app):
    Ctrl + Shift + S   capturar
    Ctrl + Shift + Q   salir de Cometa

En el editor:
    Ctrl+C copiar    Ctrl+S guardar    Ctrl+Z deshacer    Esc cerrar
    A flecha  R rect  L linea  P lapiz  T texto   1/2/3 grosor

Notas:
    - El atajo usa RegisterHotKey (API estandar de Windows). Mientras
      Cometa corre, Ctrl+Shift+S queda reservado para la captura y no
      llega a la app en foco. Cerra con Ctrl+Shift+Q para liberarlo.
    - Codigo modular pensado para extender: la lista Editor.annotations es la
      unica fuente de verdad; cada herramienta se dibuja en _draw_on_canvas
      (preview) y _draw_on_pil (render final).
"""

import io
import os
import sys
import math
import json
import queue
import base64
import tempfile
import datetime
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageFilter
except ImportError:
    print("Falta Pillow. Instalalo con:  py -m pip install pillow")
    sys.exit(1)

try:
    from PIL import ImageTk   # ruta rapida para pasar imagenes a Tkinter
except Exception:
    ImageTk = None


# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------
DEFAULT_SAVE_DIR = os.path.join(os.path.expanduser("~"), "Pictures",
                                "Capturas_Cometa")
_OLD_SAVE_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Cometa")

CONFIG = {
    "save_dir": DEFAULT_SAVE_DIR,
    "palette": ["#ff3b30", "#4c8dff", "#34c759", "#ffcc00", "#000000", "#ffffff"],
    "default_color": "#ff3b30",
    "widths": {"1": 2, "2": 4, "3": 7},   # grosores S / M / L
    "default_width_key": "2",
    "font_ratio": 5,                       # tamano de fuente = grosor * ratio + base
    "font_base": 8,
    "img_format": "png",                   # png | jpg
    "jpg_quality": 92,
    "text_font": "Bahnschrift",            # fuente por defecto del texto
    "text_size": 22,                       # tamano por defecto del texto
    "copy_after_save": False,              # copiar al portapapeles ademas de guardar
    # Atajo global: modificadores + tecla (letra). Editable desde Ajustes.
    "hk_ctrl": True,
    "hk_shift": True,
    "hk_alt": False,
    "hk_key": "S",
}

# Solo estas claves se persisten en el JSON (las demas son fijas del programa).
CONFIG_KEYS = ["save_dir", "default_color", "default_width_key", "img_format",
               "jpg_quality", "copy_after_save", "text_font", "text_size",
               "hk_ctrl", "hk_shift", "hk_alt", "hk_key"]

# Fuentes ofrecidas para el texto: (nombre visible, archivo .ttf de Windows)
FONT_CHOICES = [
    ("Bahnschrift", "bahnschrift.ttf"),
    ("Segoe UI", "segoeui.ttf"),
    ("Arial", "arial.ttf"),
    ("Calibri", "calibri.ttf"),
    ("Verdana", "verdana.ttf"),
    ("Georgia", "georgia.ttf"),
    ("Tahoma", "tahoma.ttf"),
    ("Times New Roman", "times.ttf"),
    ("Courier New", "cour.ttf"),
    ("Consolas", "consola.ttf"),
    ("Comic Sans MS", "comic.ttf"),
    ("Impact", "impact.ttf"),
]
FONT_FILES = dict(FONT_CHOICES)

CONFIG_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "Cometa", "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in CONFIG_KEYS:
            if k in data:
                CONFIG[k] = data[k]
    except Exception:
        pass   # si no existe o esta corrupto, usamos los valores por defecto
    # Migracion: si venia apuntando a la carpeta vieja, pasar a la nueva
    if CONFIG.get("save_dir") == _OLD_SAVE_DIR:
        CONFIG["save_dir"] = DEFAULT_SAVE_DIR


def save_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({k: CONFIG[k] for k in CONFIG_KEYS}, f, indent=2)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Auto-arranque con Windows
# ----------------------------------------------------------------------------
# Clave: NO dependemos del PATH. Python sabe donde esta su propio ejecutable
# (sys.executable), asi que escribimos rutas absolutas en el lanzador.
def _startup_vbs_path():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "Cometa.vbs")


def _pythonw_path():
    """El Python 'sin consola' que acompaña al interprete actual."""
    exe = sys.executable or "pythonw.exe"
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.exists(cand) else exe


def _script_path():
    return os.path.abspath(__file__)


def autostart_enabled():
    return os.path.exists(_startup_vbs_path())


def install_autostart():
    """Crea un lanzador silencioso con rutas absolutas en Inicio de Windows."""
    path = _startup_vbs_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    vbs = ('Set s = CreateObject("WScript.Shell")\r\n'
           's.Run """%s"" ""%s"" --silent", 0, False\r\n'
           % (_pythonw_path(), _script_path()))
    with open(path, "w", encoding="utf-8") as f:
        f.write(vbs)
    return path


def remove_autostart():
    path = _startup_vbs_path()
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def launch_detached():
    """Arranca otra instancia desligada de la consola y termina esta."""
    flags = 0
    for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
        flags |= getattr(subprocess, name, 0)
    subprocess.Popen([_pythonw_path(), _script_path(), "--silent"],
                     creationflags=flags, close_fds=True)

# Tema visual: paleta "espacio exterior" (negro, azul profundo, purpura,
# magenta y cian nebulosa) con superficies oscuras y acento brillante.
THEME = {
    "bg": "#0A0B18",          # negro espacio (fondo base)
    "bg_soft": "#161834",     # superficie: barra flotante y paneles
    "surface": "#1E2148",     # superficie elevada
    "border": "#2B2F63",      # bordes sutiles
    "btn": "#232653",         # boton neutro
    "btn_hover": "#2F3470",
    "txt": "#E9EFFF",
    "txt_dim": "#8B94C4",
    "accent": "#25E7F5",      # cian nebulosa: accion principal / activo
    "accent_hover": "#63F0FA",
    "accent_txt": "#03121A",  # texto oscuro sobre cian (contraste)
    "success": "#2B3FD9",     # azul profundo: accion secundaria (Guardar)
    "success_hover": "#4055F0",
    "success_txt": "#FFFFFF",
    "magenta": "#B4139A",     # magenta nebulosa
    "purple": "#4B1A78",      # purpura profundo
    "danger": "#E0248F",
    # Fuentes: apply_fonts() las resuelve a Bahnschrift si esta disponible.
    "font_family": "Segoe UI",
    "font_family_semi": "Segoe UI Semibold",
    "font": ("Segoe UI", 10),
    "font_bold": ("Segoe UI Semibold", 10),
    "font_title": ("Segoe UI Semibold", 14),
}


def apply_fonts(root):
    """Elige Bahnschrift (u otra moderna) segun lo instalado en el sistema."""
    import tkinter.font as tkfont
    fams = set(tkfont.families(root))

    def pick(candidates, fallback):
        for c in candidates:
            if c in fams:
                return c
        return fallback

    # Sans moderna y limpia, al estilo del dashboard de referencia.
    body = pick(["Segoe UI Variable Text", "Segoe UI", "Corbel", "Calibri"], "Segoe UI")
    semi = pick(["Segoe UI Variable Display", "Segoe UI Semibold", "Corbel",
                 "Segoe UI"], body)
    THEME["font_family"] = body
    THEME["font_family_semi"] = semi
    THEME["font"] = (body, 10)
    THEME["font_bold"] = (semi, 10)
    THEME["font_title"] = (semi, 15)


# ----------------------------------------------------------------------------
# Portapapeles de Windows (imagen como CF_DIB) via ctypes
# ----------------------------------------------------------------------------
def copy_image_to_clipboard(image):
    if os.name != "nt":
        raise RuntimeError("El portapapeles solo esta implementado para Windows.")

    import ctypes
    from ctypes import wintypes

    output = io.BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]   # sacar cabecera BMP -> queda el DIB
    output.close()

    CF_DIB = 8
    GMEM_MOVEABLE = 0x0002
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

    h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    lock = kernel32.GlobalLock(h_global)
    ctypes.memmove(lock, data, len(data))
    kernel32.GlobalUnlock(h_global)

    if not user32.OpenClipboard(0):
        raise RuntimeError("No se pudo abrir el portapapeles.")
    try:
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_DIB, h_global)
    finally:
        user32.CloseClipboard()


# ----------------------------------------------------------------------------
# Hook global de teclado (Win+Shift+S) via WH_KEYBOARD_LL
# ----------------------------------------------------------------------------
class GlobalHotkey:
    """Registra Ctrl+Shift+S y Ctrl+Shift+Q como atajos globales.

    Usa RegisterHotKey (la API estandar de Windows para hotkeys globales),
    que es mas robusta que un keyboard hook y rara vez la bloquean entornos
    corporativos. Corre en su propio hilo con message loop; los disparos se
    encolan y el hilo de Tk los consume con poll().
    """

    def __init__(self):
        import queue
        self.events = queue.Queue()   # va poniendo "capture" / "quit"
        self.installed = False
        self._ready = None
        self._thread = None
        self._thread_id = None

    def start(self, timeout=1.0):
        if os.name != "nt":
            return False
        import threading
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout)     # esperamos a saber si el hook instalo
        return self.installed

    def _run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Modificadores y teclas
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_SHIFT = 0x0004
        MOD_NOREPEAT = 0x4000     # evita repeticiones al mantener apretado (Win7+)
        WM_HOTKEY = 0x0312
        VK_Q = 0x51
        self.ID_CAPTURE, self.ID_QUIT = 1, 2

        # Atajo tomado de CONFIG (editable desde Ajustes)
        mods_cfg = MOD_NOREPEAT
        if CONFIG.get("hk_ctrl", True):
            mods_cfg |= MOD_CONTROL
        if CONFIG.get("hk_shift", True):
            mods_cfg |= MOD_SHIFT
        if CONFIG.get("hk_alt", False):
            mods_cfg |= MOD_ALT
        key = (CONFIG.get("hk_key") or "S")[:1].upper()
        VK_CAPTURE = ord(key) if key else 0x53

        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                          wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                       wintypes.HWND, wintypes.UINT, wintypes.UINT]

        ok_capture = user32.RegisterHotKey(None, self.ID_CAPTURE, mods_cfg, VK_CAPTURE)
        # Salir: mismos modificadores + Q (si el atajo ya es Q, se omite)
        if VK_CAPTURE != VK_Q:
            user32.RegisterHotKey(None, self.ID_QUIT, mods_cfg, VK_Q)

        self.installed = bool(ok_capture)
        self._thread_id = kernel32.GetCurrentThreadId()
        self._ready.set()
        if not ok_capture:
            return

        # Message loop: recibe los WM_HOTKEY de este hilo.
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                if msg.wParam == self.ID_CAPTURE:
                    self.events.put("capture")
                elif msg.wParam == self.ID_QUIT:
                    self.events.put("quit")
        user32.UnregisterHotKey(None, self.ID_CAPTURE)
        user32.UnregisterHotKey(None, self.ID_QUIT)

    def stop(self):
        if self._thread_id:
            import ctypes
            WM_QUIT = 0x0012
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread_id = None


# ----------------------------------------------------------------------------
# Icono en la bandeja del sistema (Shell_NotifyIcon) via ctypes
# ----------------------------------------------------------------------------
class TrayIcon:
    """Cometa junto al reloj, con menu de clic derecho.

    Implementado con la API nativa de Windows por ctypes (sin dependencias,
    porque el firewall puede bloquear pip). Corre en su propio hilo con
    message loop; las acciones se encolan y el hilo de Tk las consume.
    """

    def __init__(self, icon_path, tooltip="Cometa"):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.events = queue.Queue()
        self.ok = False
        self._ready = None
        self._thread = None
        self._hwnd = None
        self._proc = None

    def start(self, timeout=3.0):
        if os.name != "nt" or not self.icon_path:
            return False
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.ok

    def _run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        WM_APP = 0x8000
        MSG_TRAY = WM_APP + 1
        WM_LBUTTONUP, WM_RBUTTONUP = 0x0202, 0x0205
        WM_CLOSE, WM_DESTROY, WM_NULL = 0x0010, 0x0002, 0x0000
        NIM_ADD, NIM_DELETE = 0x0, 0x2
        NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
        IMAGE_ICON, LR_LOADFROMFILE = 1, 0x0010
        MF_STRING, MF_SEPARATOR = 0x0, 0x800
        TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x2, 0x100

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT),
                        ("lpfnWndProc", WNDPROC),
                        ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int),
                        ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR)]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("hWnd", wintypes.HWND),
                        ("uID", wintypes.UINT),
                        ("uFlags", wintypes.UINT),
                        ("uCallbackMessage", wintypes.UINT),
                        ("hIcon", wintypes.HICON),
                        ("szTip", wintypes.WCHAR * 128),
                        ("dwState", wintypes.DWORD),
                        ("dwStateMask", wintypes.DWORD),
                        ("szInfo", wintypes.WCHAR * 256),
                        ("uVersion", wintypes.UINT),
                        ("szInfoTitle", wintypes.WCHAR * 64),
                        ("dwInfoFlags", wintypes.DWORD),
                        ("guidItem", ctypes.c_byte * 16),
                        ("hBalloonIcon", wintypes.HICON)]

        # IMPORTANTE: hay que declarar argtypes ademas de restype. Sin eso,
        # ctypes asume int de C y los handles de 64 bits desbordan.
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                      wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                      wintypes.UINT]
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT,
                                       ctypes.c_size_t, wintypes.LPCWSTR]
        user32.TrackPopupMenu.restype = ctypes.c_int
        user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT,
                                          ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                          wintypes.HWND, wintypes.LPVOID]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                        wintypes.WPARAM, wintypes.LPARAM]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                       wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = LRESULT
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                              ctypes.POINTER(NOTIFYICONDATAW)]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

        # Menu de clic derecho
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, 1, "Capturar")
        user32.AppendMenuW(menu, MF_STRING, 2, "Mostrar ventana")
        user32.AppendMenuW(menu, MF_STRING, 3, "Ajustes")
        user32.AppendMenuW(menu, MF_STRING, 4, "Abrir carpeta de capturas")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, 9, "Salir")
        actions = {1: "capture", 2: "show", 3: "settings", 4: "folder", 9: "quit"}

        nid = NOTIFYICONDATAW()   # creado antes para que el WndProc lo vea

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == MSG_TRAY:
                if lparam == WM_LBUTTONUP:
                    self.events.put("capture")
                elif lparam == WM_RBUTTONUP:
                    pt = wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    user32.SetForegroundWindow(hwnd)   # para que el menu cierre bien
                    cmd = user32.TrackPopupMenu(
                        menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                        pt.x, pt.y, 0, hwnd, None)
                    user32.PostMessageW(hwnd, WM_NULL, 0, 0)
                    if cmd in actions:
                        self.events.put(actions[cmd])
                return 0
            if msg == WM_CLOSE:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._proc = WNDPROC(wndproc)   # referencia viva mientras dure el hilo

        hinst = kernel32.GetModuleHandleW(None)
        cls = WNDCLASSW()
        cls.lpfnWndProc = self._proc
        cls.hInstance = hinst
        cls.lpszClassName = "CometaTrayClass"
        user32.RegisterClassW(ctypes.byref(cls))

        hwnd = user32.CreateWindowExW(0, "CometaTrayClass", "Cometa", 0,
                                      0, 0, 0, 0, None, None, hinst, None)
        self._hwnd = hwnd

        hicon = user32.LoadImageW(None, self.icon_path, IMAGE_ICON,
                                  16, 16, LR_LOADFROMFILE)

        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = MSG_TRAY
        nid.hIcon = hicon
        nid.szTip = self.tooltip

        self.ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
        self._ready.set()
        if not self.ok:
            return

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop(self):
        if self._hwnd:
            try:
                import ctypes
                from ctypes import wintypes
                post = ctypes.windll.user32.PostMessageW
                post.argtypes = [wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM]
                post(self._hwnd, 0x0010, 0, 0)   # WM_CLOSE
            except Exception:
                pass
            self._hwnd = None


# ----------------------------------------------------------------------------
# Helpers de UI
# ----------------------------------------------------------------------------
_tk_refs = []   # evita que el GC borre los PhotoImage


def _pil_to_tk(pil_image):
    # ImageTk es directo (sin comprimir PNG ni base64): clave para que la app
    # sea fluida con capturas grandes o de dos monitores.
    if ImageTk is not None:
        img = ImageTk.PhotoImage(pil_image)
    else:
        buf = io.BytesIO()
        pil_image.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        img = tk.PhotoImage(data=b64)   # fallback (Tk 8.6)
    _tk_refs.append(img)
    return img


def _crop_to_tk(pil_image, x1, y1, x2, y2):
    box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    return _pil_to_tk(pil_image.crop(box))


def styled_button(parent, text, command, kind="normal", width=None):
    """Boton plano con efecto hover, coherente con el tema."""
    palette = {
        "normal": (THEME["btn"], THEME["btn_hover"], THEME["txt"]),
        "accent": (THEME["accent"], THEME["accent_hover"], THEME["accent_txt"]),
        "success": (THEME["success"], THEME["success_hover"], THEME["success_txt"]),
        "ghost": (THEME["bg_soft"], THEME["btn_hover"], THEME["txt_dim"]),
    }
    base, hover, fg = palette[kind]
    b = tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                  bg=base, fg=fg, activebackground=hover, activeforeground=fg,
                  font=THEME["font"], cursor="hand2", padx=14, pady=8)
    if width:
        b.configure(width=width)
    b._base_bg = base
    b._hover_bg = hover
    # Hover dinamico: respeta el color actual (p.ej. herramienta activa).
    b.bind("<Enter>", lambda e: b.configure(bg=b._hover_bg))
    b.bind("<Leave>", lambda e: b.configure(bg=b._base_bg))
    return b


def styled_option(parent, variable, values, width=None):
    """Desplegable con el tema (el tk.OptionMenu crudo sale gris feo)."""
    om = tk.OptionMenu(parent, variable, *values)
    om.configure(bg=THEME["btn"], fg=THEME["txt"], activebackground=THEME["btn_hover"],
                 activeforeground=THEME["txt"], relief="flat", bd=0,
                 highlightthickness=0, font=THEME["font"], cursor="hand2",
                 padx=10, pady=4, anchor="w", direction="below")
    if width:
        om.configure(width=width)
    om["menu"].configure(bg=THEME["bg_soft"], fg=THEME["txt"],
                         activebackground=THEME["accent"],
                         activeforeground=THEME["accent_txt"],
                         bd=0, relief="flat", font=THEME["font"])
    return om


def styled_entry(parent, textvariable=None, width=20):
    """Campo de texto con el tema (borde sutil, cursor cian)."""
    return tk.Entry(parent, textvariable=textvariable, width=width,
                    bg=THEME["surface"], fg=THEME["txt"],
                    insertbackground=THEME["accent"], relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=THEME["border"],
                    highlightcolor=THEME["accent"], font=THEME["font"])


def styled_spin(parent, from_, to, textvariable, width=5):
    """Selector numerico con el tema."""
    return tk.Spinbox(parent, from_=from_, to=to, textvariable=textvariable,
                      width=width, bg=THEME["surface"], fg=THEME["txt"],
                      insertbackground=THEME["accent"], relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=THEME["border"],
                      highlightcolor=THEME["accent"], buttonbackground=THEME["btn"],
                      font=THEME["font"])


def styled_check(parent, text, variable, bg=None):
    """Casilla con el tema."""
    bg = bg or THEME["bg"]
    return tk.Checkbutton(parent, text=text, variable=variable, bg=bg,
                          fg=THEME["txt"], activebackground=bg,
                          activeforeground=THEME["txt"],
                          selectcolor=THEME["surface"], font=THEME["font"],
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2")


def _center(window, y_ratio=3):
    window.update_idletasks()
    w, h = window.winfo_width(), window.winfo_height()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry("+%d+%d" % (max(0, (sw - w) // 2), max(0, (sh - h) // y_ratio)))


def _load_font(size, family=None):
    """Carga la fuente para el render final; cae a alternativas si no esta."""
    candidates = []
    if family and family in FONT_FILES:
        candidates.append(FONT_FILES[family])
    candidates += ["bahnschrift.ttf", "segoeui.ttf", "arial.ttf", "calibri.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, int(size))
        except Exception:
            continue
    return ImageFont.load_default()


def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Dibuja un rectangulo de esquinas redondeadas en un Canvas."""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def make_comet_icon(px=64):
    """Dibuja el icono de la app: un cometa con estela cian -> magenta."""
    s = px * 4                      # supersample para bordes suaves
    rs = getattr(Image, "Resampling", Image)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Cabeza abajo-izquierda, estela larga y delgada hacia arriba-derecha,
    # con una curvatura sutil (como en un cometa real).
    head = (s * 0.27, s * 0.71)     # nucleo, cerca del observador
    tip = (s * 0.93, s * 0.11)      # punta de la estela, perdiendose lejos
    ctrl = (s * 0.52, s * 0.35)     # control: curva suave de la trayectoria

    def bezier(t):
        u = 1.0 - t
        return (u * u * head[0] + 2 * u * t * ctrl[0] + t * t * tip[0],
                u * u * head[1] + 2 * u * t * ctrl[1] + t * t * tip[1])

    # --- estela: ancha y blanca junto al nucleo, se afina y se apaga al fondo
    tail = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    td = ImageDraw.Draw(tail)
    steps = 220
    for i in range(steps + 1):
        t = i / steps               # 0 = cabeza, 1 = punta lejana
        x, y = bezier(t)
        r = s * 0.052 * ((1 - t) ** 0.85) + s * 0.004
        cr = int(235 * (1 - t) + 70 * t)      # blanco -> azul profundo
        cg = int(250 * (1 - t) + 130 * t)
        cb = int(255 * (1 - t) + 205 * t)
        a = int(200 * ((1 - t) ** 1.7) + 4)
        td.ellipse([x - r, y - r, x + r, y + r], fill=(cr, cg, cb, a))
    tail = tail.filter(ImageFilter.GaussianBlur(s * 0.011))
    img = Image.alpha_composite(img, tail)

    hx, hy = head

    # --- resplandor difuso alrededor del nucleo
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gr = s * 0.21
    ImageDraw.Draw(glow).ellipse([hx - gr, hy - gr, hx + gr, hy + gr],
                                 fill=(150, 240, 255, 130))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(s * 0.05)))

    # --- nucleo en gota: circulos que se achican hacia adelante (abajo-izq)
    core = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    cd = ImageDraw.Draw(core)
    for k in range(7):
        f = k / 6.0
        cxk = hx - s * 0.045 * f
        cyk = hy + s * 0.038 * f
        rk = s * (0.072 - 0.048 * f)
        cd.ellipse([cxk - rk, cyk - rk, cxk + rk, cyk + rk],
                   fill=(205, 248, 255, 245))
    nr = s * 0.050
    cd.ellipse([hx - nr, hy - nr, hx + nr, hy + nr], fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, core.filter(ImageFilter.GaussianBlur(s * 0.007)))

    # --- estrellitas de fondo
    stars = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    for sx, sy, sr, sa in ((0.13, 0.24, 0.010, 210), (0.30, 0.11, 0.006, 150),
                           (0.78, 0.80, 0.009, 185), (0.55, 0.90, 0.006, 135),
                           (0.90, 0.55, 0.007, 160), (0.09, 0.52, 0.005, 120)):
        cxp, cyp, rp = s * sx, s * sy, s * sr
        sd.ellipse([cxp - rp, cyp - rp, cxp + rp, cyp + rp],
                   fill=(255, 255, 255, sa))
    img = Image.alpha_composite(img, stars)

    return img.resize((px, px), rs.LANCZOS)


def write_icon_file():
    """Genera un .ico temporal del cometa (lo necesita la bandeja de Windows)."""
    path = os.path.join(tempfile.gettempdir(), "cometa_icon.ico")
    try:
        make_comet_icon(128).save(path, format="ICO",
                                  sizes=[(16, 16), (24, 24), (32, 32), (48, 48)])
        return path
    except Exception:
        return None


_APP_ICON = None


def set_app_icon(root):
    """Pone el cometa como icono de la app (ventanas y barra de tareas)."""
    global _APP_ICON
    try:
        if _APP_ICON is None:
            _APP_ICON = _pil_to_tk(make_comet_icon(64))
        root.iconphoto(True, _APP_ICON)   # True = por defecto en toda la app
    except Exception:
        pass


def make_pencil_icon(px=20):
    """Dibuja un lapiz a color (cuerpo amarillo, punta, goma) con Pillow."""
    s = px * 4   # supersample para bordes suaves
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = s / 2
    w = s * 0.30
    top, bot = s * 0.12, s * 0.88
    body_top = top + (bot - top) * 0.20
    body_bot = bot - (bot - top) * 0.18
    # goma (rosada) y virola metalica arriba
    d.rectangle([cx - w / 2, top, cx + w / 2, top + (body_top - top) * 0.6],
                fill=(242, 120, 150, 255))
    d.rectangle([cx - w / 2, top + (body_top - top) * 0.6, cx + w / 2, body_top],
                fill=(196, 199, 206, 255))
    # cuerpo amarillo con una franja mas oscura (volumen)
    d.rectangle([cx - w / 2, body_top, cx + w / 2, body_bot], fill=(245, 182, 40, 255))
    d.rectangle([cx + w * 0.08, body_top, cx + w / 2, body_bot], fill=(214, 150, 22, 255))
    # madera de la punta y grafito
    d.polygon([(cx - w / 2, body_bot), (cx + w / 2, body_bot), (cx, bot)],
              fill=(226, 190, 140, 255))
    tip = bot - (bot - top) * 0.10
    d.polygon([(cx - w * 0.18, tip), (cx + w * 0.18, tip), (cx, bot)],
              fill=(40, 40, 46, 255))
    rs = getattr(Image, "Resampling", Image)   # compat Pillow viejo/nuevo
    img = img.rotate(-42, resample=rs.BICUBIC, expand=False,
                     fillcolor=(0, 0, 0, 0))
    return img.resize((px, px), rs.LANCZOS)


def _swatch_img(color, px=14):
    """Cuadradito solido del color dado (para el boton Color)."""
    img = Image.new("RGB", (px, px), color)
    ImageDraw.Draw(img).rectangle([0, 0, px - 1, px - 1], outline=(230, 230, 235))
    return img


def _hex_to_rgba(hexc, alpha):
    """'#rrggbb' -> (r, g, b, alpha)  para dibujar semitransparente."""
    from PIL import ImageColor
    r, g, b = ImageColor.getrgb(hexc)[:3]
    return (r, g, b, alpha)


# Script PowerShell que usa el motor OCR nativo de Windows (Windows.Media.Ocr).
_OCR_PS = r'''
param([string]$ImagePath)
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$asTaskGeneric=([System.WindowsRuntimeSystemExtensions].GetMethods()|?{$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'})[0]
function Await($t,$rt){ $m=$asTaskGeneric.MakeGenericMethod($rt); $nt=$m.Invoke($null,@($t)); $nt.Wait(-1)|Out-Null; $nt.Result }
$file=Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream=Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder=Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap=Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if($engine -eq $null){ [Console]::Error.WriteLine('No hay idioma OCR instalado'); exit 1 }
$result=Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
[Console]::Out.Write($result.Text)
'''


def run_windows_ocr(image_path):
    """Corre el OCR nativo de Windows sobre una imagen y devuelve el texto."""
    if os.name != "nt":
        raise RuntimeError("OCR solo disponible en Windows.")
    ps_path = os.path.join(tempfile.gettempdir(), "cometa_ocr.ps1")
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(_OCR_PS)
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         ps_path, "-ImagePath", image_path],
        capture_output=True, timeout=40,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(err or "PowerShell devolvio un error")
    return proc.stdout.decode("utf-8", "replace")


# Grilla amplia de colores para el selector (8x8 = 64 tonos)
COLOR_GRID = [
    ["#ffffff", "#d9d9d9", "#b3b3b3", "#808080", "#4d4d4d", "#1a1a1a", "#000000", "#607d8b"],
    ["#ffcdd2", "#ef9a9a", "#e57373", "#f44336", "#e53935", "#c62828", "#b71c1c", "#7f0000"],
    ["#ffe0b2", "#ffcc80", "#ffb74d", "#ff9800", "#fb8c00", "#ef6c00", "#e65100", "#bf360c"],
    ["#fff9c4", "#fff176", "#ffee58", "#ffeb3b", "#fdd835", "#fbc02d", "#f9a825", "#f57f17"],
    ["#c8e6c9", "#a5d6a7", "#81c784", "#4caf50", "#43a047", "#2e7d32", "#1b5e20", "#00897b"],
    ["#bbdefb", "#90caf9", "#64b5f6", "#2196f3", "#1e88e5", "#1565c0", "#0d47a1", "#01579b"],
    ["#e1bee7", "#ce93d8", "#ba68c8", "#9c27b0", "#8e24aa", "#6a1b9a", "#4a148c", "#880e4f"],
    ["#f8bbd0", "#f48fb1", "#f06292", "#e91e63", "#d81b60", "#ad1457", "#c2185b", "#3e2723"],
]


def set_dpi_awareness():
    """Hace que Tk trabaje en pixeles fisicos, igual que ImageGrab.

    Sin esto, en pantallas con escalado (125%/150%) Tk usa coordenadas
    logicas y la captura de Pillow usa fisicas -> se desalinean. Debe
    llamarse ANTES de crear la ventana Tk.
    """
    if os.name != "nt":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen_origin():
    """Esquina superior-izquierda del escritorio virtual (multi-monitor).

    Puede ser negativa si hay un monitor a la izquierda/arriba del principal.
    ImageGrab.grab(all_screens=True) usa este mismo origen, asi que las coords
    de la captura calzan con la pantalla sumando este offset.
    """
    if os.name != "nt":
        return (0, 0)
    import ctypes
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    gm = ctypes.windll.user32.GetSystemMetrics
    return (gm(SM_XVIRTUALSCREEN), gm(SM_YVIRTUALSCREEN))


# ----------------------------------------------------------------------------
# Selector de region (overlay a pantalla completa)
# ----------------------------------------------------------------------------
class RegionSelector:
    def __init__(self, root, screenshot, on_done, origin=(0, 0)):
        self.root = root
        self.screenshot = screenshot
        self.on_done = on_done
        self.w, self.h = screenshot.size

        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)      # cubre TODO el escritorio virtual
        self.top.geometry("%dx%d+%d+%d" % (self.w, self.h, origin[0], origin[1]))
        self.top.attributes("-topmost", True)
        self.top.configure(cursor="crosshair", bg="#000000")

        self.canvas = tk.Canvas(self.top, width=self.w, height=self.h,
                                highlightthickness=0, bd=0, bg="#000000")
        self.canvas.pack(fill="both", expand=True)

        self.tk_bg = _pil_to_tk(screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_bg)

        # Enmascarado con 4 rectangulos (top/bottom/left/right): en vez de
        # re-cortar la imagen en cada movimiento (lento), solo movemos coords.
        vel = {"fill": "#000000", "stipple": "gray50", "outline": ""}
        self.m_top = self.canvas.create_rectangle(0, 0, self.w, self.h, **vel)
        self.m_bottom = self.canvas.create_rectangle(0, 0, 0, 0, **vel)
        self.m_left = self.canvas.create_rectangle(0, 0, 0, 0, **vel)
        self.m_right = self.canvas.create_rectangle(0, 0, 0, 0, **vel)

        self.hint = self.canvas.create_text(
            self.w // 2, 34, fill="#ffffff", font=(THEME["font_family"], 15),
            text="Arrastra para seleccionar    ·    Esc para cancelar")

        self.start = None
        self.rect_id = None
        self.badge = None
        self.badge_bg = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.top.bind("<Escape>", lambda e: self.finish(None))

        self.top.grab_set()
        self.top.focus_force()

    def on_press(self, event):
        self.start = (event.x, event.y)
        self.canvas.itemconfig(self.hint, state="hidden")
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline=THEME["accent"], width=2)

    def on_drag(self, event):
        if not self.start:
            return
        x1, y1 = self.start
        x2, y2 = event.x, event.y
        sx1, sy1 = min(x1, x2), min(y1, y2)
        sx2, sy2 = max(x1, x2), max(y1, y2)
        W, H = self.w, self.h
        # atenuar TODO menos la seleccion, moviendo los 4 rectangulos
        self.canvas.coords(self.m_top, 0, 0, W, sy1)
        self.canvas.coords(self.m_bottom, 0, sy2, W, H)
        self.canvas.coords(self.m_left, 0, sy1, sx1, sy2)
        self.canvas.coords(self.m_right, sx2, sy1, W, sy2)
        self.canvas.coords(self.rect_id, x1, y1, x2, y2)
        self.canvas.tag_raise(self.rect_id)
        self._update_badge(x1, y1, x2, y2)

    def _update_badge(self, x1, y1, x2, y2):
        w, h = abs(x2 - x1), abs(y2 - y1)
        bx, by = max(x1, x2), min(y1, y2) - 14
        if by < 12:
            by = max(y1, y2) + 16
        for item in (self.badge_bg, self.badge):
            if item:
                self.canvas.delete(item)
        text = "%d x %d" % (w, h)
        self.badge = self.canvas.create_text(
            bx, by, text=text, anchor="e", fill=THEME["accent_txt"],
            font=(THEME["font_family_semi"], 11), tags="hole")
        bbox = self.canvas.bbox(self.badge)
        self.badge_bg = self.canvas.create_rectangle(
            bbox[0] - 6, bbox[1] - 3, bbox[2] + 6, bbox[3] + 3,
            fill=THEME["accent"], outline="")
        self.canvas.tag_raise(self.badge)

    def on_release(self, event):
        if not self.start:
            return
        x1, y1 = self.start
        x2, y2 = event.x, event.y
        bx1, by1 = min(x1, x2), min(y1, y2)
        bx2, by2 = max(x1, x2), max(y1, y2)
        if (bx2 - bx1) < 8 or (by2 - by1) < 8:
            self.finish(None)
            return
        self.finish((bx1, by1, bx2, by2))

    def finish(self, bbox):
        cb = self.on_done
        self.on_done = None
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()
        if cb:
            cb(bbox)


# ----------------------------------------------------------------------------
# Editor
# ----------------------------------------------------------------------------
class Editor:
    # (clave, icono, tooltip, atajo de teclado)
    TOOLS = [
        ("select", "⤢", "Seleccionar / mover", "v"),
        ("arrow", "↗", "Flecha", "a"),
        ("line", "／", "Linea", "l"),
        ("rect", "▭", "Rectangulo", "r"),
        ("ellipse", "◯", "Elipse", "e"),
        ("pen", "✎", "Lapiz", "p"),
        ("marker", "▨", "Marcador", "m"),
        ("blur", "░", "Difuminar", "b"),
        ("text", "T", "Texto", "t"),
    ]
    DEFAULT_STATUS = "Ctrl+C · Ctrl+S · Supr borra"

    def __init__(self, root, screenshot, bbox, on_close, origin=(0, 0)):
        self.root = root
        self.on_close = on_close
        self.screenshot = screenshot        # captura completa congelada
        self.bbox = bbox                     # (x1, y1, x2, y2) en px de la captura
        self.sw, self.sh = screenshot.size
        self.ox, self.oy = origin            # origen del escritorio virtual

        self.tool = "arrow"
        self.color = CONFIG["default_color"]
        self.width_key = CONFIG["default_width_key"]
        self.text_font = CONFIG.get("text_font", "Bahnschrift")
        self.text_size = int(CONFIG.get("text_size", 22))
        self.annotations = []
        self.canvas_items = []
        self._item_to_ann = {}       # id de canvas -> anotacion (para seleccionar)
        self._sel_ann = None         # anotacion seleccionada
        self._sel_last = None
        self._prev_tool = "arrow"    # para volver tras el cuentagotas
        self._drag_start = None
        self._temp_item = None
        self._pen_points = []

        # --- Overlay a pantalla completa: se ve TODO; la region va resaltada
        #     y el resto atenuado. Ese contraste es el "marco".
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)      # cubre TODO el escritorio virtual
        self.win.geometry("%dx%d+%d+%d" % (self.sw, self.sh, self.ox, self.oy))
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#000000", cursor="crosshair")
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self.canvas = tk.Canvas(self.win, width=self.sw, height=self.sh,
                                highlightthickness=0, bd=0, bg="#000000")
        self.canvas.pack(fill="both", expand=True)
        self.tk_bg = _pil_to_tk(screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_bg, tags="bg")
        self._draw_frame()   # velo + region nitida + marco (todo con tag "frame")

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.bar = None
        try:
            self._build_toolbar()   # barra flotante redondeada (estilo Snip)
        except Exception:
            # si algo falla, cerramos las ventanas para no dejar la pantalla
            # "pegada" y que el error sea visible
            for w in (getattr(self, "bar", None), self.win):
                try:
                    if w:
                        w.destroy()
                except Exception:
                    pass
            raise

        for target in (self.win, self.bar):
            target.bind("<Control-c>", lambda e: self.copy())
            target.bind("<Control-s>", lambda e: self.save())
            target.bind("<Control-z>", lambda e: self.undo())
            target.bind("<Escape>", lambda e: self.close())
            target.bind("<Delete>", lambda e: self._delete_selected())
            target.bind("<BackSpace>", lambda e: self._delete_selected())
            for _key, _ico, _tip, _sc in self.TOOLS:
                target.bind(_sc, lambda e, t=_key: self.set_tool(t))
            for k in ("1", "2", "3"):
                target.bind(k, lambda e, kk=k: self.set_width(kk))

        self.win.focus_force()
        self.win.after(10, self.bar.lift)   # asegurar la barra por encima

    def _draw_frame(self):
        """(Re)dibuja velo, region nitida y marco segun self.bbox."""
        self.canvas.delete("frame")
        x1, y1, x2, y2 = self.bbox
        self.canvas.create_rectangle(0, 0, self.sw, self.sh, fill="#000000",
                                     stipple="gray50", outline="", tags="frame")
        self._tk_region = _pil_to_tk(self.screenshot.crop(self.bbox))
        self.canvas.create_image(x1, y1, anchor="nw", image=self._tk_region,
                                 tags="frame")
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=THEME["accent"],
                                     width=2, tags="frame")
        # z-order: bg abajo, frame sobre bg, anotaciones (tag "ann") arriba
        self.canvas.tag_lower("frame")
        self.canvas.tag_lower("bg")

    def _raise_bar(self):
        try:
            self.bar.lift()
            pop = getattr(self, "_color_pop", None)
            if pop and pop.winfo_exists():
                pop.lift()   # el popup de color va por encima de la barra
        except Exception:
            pass

    # ---- toolbar flotante -------------------------------------------------
    def _build_toolbar(self):
        KEY = "#0b0b0d"   # color clave para transparencia (no lo usamos en la UI)
        self.bar = tk.Toplevel(self.root)
        self.bar.overrideredirect(True)
        self.bar.attributes("-topmost", True)
        try:
            self.bar.attributes("-transparentcolor", KEY)
        except Exception:
            KEY = THEME["bg_soft"]   # si no hay soporte, sin esquinas transparentes
        self.bar.configure(bg=KEY)

        shell = tk.Canvas(self.bar, bg=KEY, highlightthickness=0, bd=0)
        shell.pack()
        inner = tk.Frame(shell, bg=THEME["bg_soft"])

        self.status_var = tk.StringVar(value=self.DEFAULT_STATUS)

        def tip(widget, text):
            widget.bind("<Enter>", lambda e: self.status_var.set(text), add="+")
            widget.bind("<Leave>",
                        lambda e: self.status_var.set(self.DEFAULT_STATUS), add="+")

        self.tool_buttons = {}
        for key, icon, name, sc in self.TOOLS:
            b = styled_button(inner, icon, lambda t=key: self.set_tool(t), width=2)
            if key == "pen":
                b._icon = _pil_to_tk(make_pencil_icon(20))
                b.configure(image=b._icon, text="")
            tip(b, "%s  (%s)" % (name, sc))
            b.pack(side="left", padx=1, pady=2)
            self.tool_buttons[key] = b

        self._sep(inner)
        self.width_btn = styled_button(inner, "●", self._cycle_width, width=2)
        tip(self.width_btn, "Grosor (1/2/3)")
        self.width_btn.pack(side="left", padx=1, pady=2)

        self.color_btn = styled_button(inner, "  Color ▾", self._toggle_color_popup)
        tip(self.color_btn, "Color y cuentagotas")
        self.color_btn.pack(side="left", padx=2, pady=2)
        self._update_color_btn()

        self._sep(inner)
        b = styled_button(inner, "↶", self.undo, kind="ghost", width=2)
        tip(b, "Deshacer (Ctrl+Z)")
        b.pack(side="left", padx=1, pady=2)
        b = styled_button(inner, "✂", lambda: self.set_tool("crop"), kind="ghost", width=2)
        tip(b, "Recortar region")
        b.pack(side="left", padx=1, pady=2)
        b = styled_button(inner, "OCR", self.ocr_copy, kind="ghost")
        tip(b, "Copiar el texto de la imagen (OCR)")
        b.pack(side="left", padx=1, pady=2)

        self._sep(inner)
        styled_button(inner, "\U0001f4cb Copiar", self.copy, kind="accent").pack(
            side="left", padx=2, pady=2)
        styled_button(inner, "\U0001f4be Guardar", self.save, kind="success").pack(
            side="left", padx=2, pady=2)
        styled_button(inner, "✕", self.close, kind="ghost", width=2).pack(
            side="left", padx=2, pady=2)

        tk.Label(inner, textvariable=self.status_var, width=26, anchor="w",
                 bg=THEME["bg_soft"], fg=THEME["txt_dim"],
                 font=THEME["font"]).pack(side="left", padx=(8, 6), pady=2)

        # medir contenido y dibujar la pastilla con puntas redondas (stadium)
        inner.update_idletasks()
        iw, ih = inner.winfo_reqwidth(), inner.winfo_reqheight()
        pad = 14
        W, H = iw + pad * 2, ih + pad * 2
        r = (H - 2) // 2   # radio = mitad del alto dibujado -> extremos curvos exactos
        shell.configure(width=W, height=H)
        _round_rect(shell, 1, 1, W - 1, H - 1, r,
                    fill=THEME["bg_soft"], outline=THEME["border"])
        shell.create_window(W // 2, H // 2, window=inner)

        self._bar_wh = (W, H)
        self._place_bar(W, H)
        self._refresh_tools()
        self._refresh_width_btn()

    def _place_bar(self, W, H):
        """Ubica la barra pegada a la region (arriba; si no cabe, abajo)."""
        x1, y1, x2, y2 = self.bbox
        cx = (x1 + x2) // 2
        x = min(max(8, cx - W // 2), self.sw - W - 8)
        margin = 14
        if y1 - H - margin >= 8:
            y = y1 - H - margin
        elif y2 + margin + H <= self.sh - 8:
            y = y2 + margin
        else:
            y = 12
        # sumar el origen del escritorio virtual -> coords absolutas de pantalla
        self.bar.geometry("+%d+%d" % (int(x) + self.ox, int(y) + self.oy))

    def _sep(self, parent):
        tk.Frame(parent, width=1, bg=THEME["border"], height=24).pack(
            side="left", padx=7, pady=4, fill="y")

    def _refresh_tools(self):
        for t, b in self.tool_buttons.items():
            active = (t == self.tool)
            bg = THEME["accent"] if active else THEME["btn"]
            hover = THEME["accent_hover"] if active else THEME["btn_hover"]
            b.configure(bg=bg, fg=THEME["accent_txt"] if active else THEME["txt"])
            b._base_bg, b._hover_bg = bg, hover

    def _refresh_width_btn(self):
        # el punto crece segun el grosor elegido
        size = {"1": 9, "2": 13, "3": 18}[self.width_key]
        self.width_btn.configure(font=(THEME["font_family"], size))

    def _cycle_width(self):
        order = ["1", "2", "3"]
        nxt = order[(order.index(self.width_key) + 1) % len(order)]
        self.set_width(nxt)

    # ---- selector de color ------------------------------------------------
    def _update_color_btn(self):
        img = _pil_to_tk(_swatch_img(self.color))
        self.color_btn._sw = img   # referencia viva
        self.color_btn.configure(image=img, compound="left")

    def _toggle_color_popup(self):
        pop = getattr(self, "_color_pop", None)
        if pop and pop.winfo_exists():
            pop.destroy()
            self._color_pop = None
            return
        self._open_color_popup()

    def _open_color_popup(self):
        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=THEME["bg_soft"])
        frame = tk.Frame(pop, bg=THEME["bg_soft"], padx=8, pady=8)
        frame.pack()
        for r, row in enumerate(COLOR_GRID):
            for c, hexc in enumerate(row):
                tk.Button(frame, bg=hexc, width=2, height=1, relief="flat", bd=0,
                          cursor="hand2", highlightthickness=1,
                          highlightbackground=THEME["bg_soft"],
                          activebackground=hexc,
                          command=lambda hc=hexc: self._pick_color(hc)
                          ).grid(row=r, column=c, padx=1, pady=1)
        tk.Button(frame, text="Personalizado…", relief="flat", bg=THEME["btn"],
                  fg=THEME["txt"], activebackground=THEME["btn_hover"],
                  activeforeground=THEME["txt"], cursor="hand2", bd=0,
                  font=THEME["font"], command=self._pick_custom
                  ).grid(row=len(COLOR_GRID), column=0, columnspan=8,
                         sticky="ew", pady=(6, 0), ipady=3)
        tk.Button(frame, text="⛏  Tomar color de la imagen", relief="flat",
                  bg=THEME["btn"], fg=THEME["txt"], activebackground=THEME["btn_hover"],
                  activeforeground=THEME["txt"], cursor="hand2", bd=0,
                  font=THEME["font"], command=self._start_pick
                  ).grid(row=len(COLOR_GRID) + 1, column=0, columnspan=8,
                         sticky="ew", pady=(4, 0), ipady=3)
        pop.update_idletasks()
        bx = self.color_btn.winfo_rootx()
        by = self.color_btn.winfo_rooty() + self.color_btn.winfo_height() + 4
        # que no se salga por el borde derecho
        bx = min(bx, self.sw - pop.winfo_reqwidth() - 8)
        pop.geometry("+%d+%d" % (max(8, bx), by))
        pop.bind("<Escape>", lambda e: self._close_color_popup())
        pop.lift()
        self._color_pop = pop

    def _close_color_popup(self):
        pop = getattr(self, "_color_pop", None)
        if pop and pop.winfo_exists():
            pop.destroy()
        self._color_pop = None

    def _pick_color(self, hexc):
        self.color = hexc
        self._update_color_btn()
        self._close_color_popup()

    def _pick_custom(self):
        from tkinter import colorchooser
        self._close_color_popup()
        res = colorchooser.askcolor(color=self.color, parent=self.root,
                                    title="Elegir color")
        if res and res[1]:
            self.color = res[1]
            self._update_color_btn()

    # ---- estado -----------------------------------------------------------
    def set_tool(self, tool):
        if tool != "pick" and self.tool != "pick":
            self._prev_tool = self.tool
        self.tool = tool
        self._refresh_tools()
        if tool != "select":
            self.canvas.delete("sel")
            self._sel_ann = None
        names = {k: n for k, _i, n, _s in self.TOOLS}
        self._toast(names.get(tool, tool.capitalize()))

    def set_color(self, color):
        self.color = color
        self._update_color_btn()

    def set_width(self, key):
        self.width_key = key
        self._refresh_width_btn()

    @property
    def width(self):
        return CONFIG["widths"][self.width_key]

    @property
    def font_size(self):
        return self.width * CONFIG["font_ratio"] + CONFIG["font_base"]

    # ---- cuentagotas ------------------------------------------------------
    def _start_pick(self):
        self._close_color_popup()
        self._prev_tool = self.tool if self.tool != "pick" else "arrow"
        self.set_tool("pick")
        self._toast("Click en la imagen para tomar un color")

    def _apply_pick(self, x, y):
        try:
            xi = min(max(0, int(x)), self.sw - 1)
            yi = min(max(0, int(y)), self.sh - 1)
            px = self.screenshot.getpixel((xi, yi))
            hexc = "#%02x%02x%02x" % (px[0], px[1], px[2])
            self.color = hexc
            self._update_color_btn()
            self._toast("Color tomado: " + hexc)
        except Exception:
            pass
        self.set_tool(self._prev_tool if self._prev_tool != "pick" else "arrow")

    # ---- seleccionar / mover / borrar ------------------------------------
    def _select_at(self, x, y):
        for it in reversed(self.canvas.find_overlapping(x - 3, y - 3, x + 3, y + 3)):
            ann = self._item_to_ann.get(it)
            if ann is not None:
                return ann
        return None

    def _draw_sel_outline(self):
        self.canvas.delete("sel")
        ann = self._sel_ann
        if not ann:
            return
        item = ann.get("_item")
        first = item[0] if isinstance(item, (list, tuple)) else item
        bb = self.canvas.bbox(first)
        if bb:
            self.canvas.create_rectangle(bb[0] - 3, bb[1] - 3, bb[2] + 3, bb[3] + 3,
                                         outline=THEME["accent"], dash=(4, 3), tags="sel")

    def _move_ann(self, ann, dx, dy):
        item = ann.get("_item")
        for i in (item if isinstance(item, (list, tuple)) else [item]):
            self.canvas.move(i, dx, dy)
        t = ann["type"]
        if t in ("arrow", "line", "rect", "ellipse", "blur"):
            ann["x1"] += dx; ann["y1"] += dy; ann["x2"] += dx; ann["y2"] += dy
        elif t in ("pen", "marker"):
            ann["points"] = [(px + dx, py + dy) for px, py in ann["points"]]
        elif t == "text":
            ann["x"] += dx; ann["y"] += dy

    def _delete_selected(self):
        ann = self._sel_ann
        if not ann:
            return
        item = ann.get("_item")
        for i in (item if isinstance(item, (list, tuple)) else [item]):
            self.canvas.delete(i)
            self._item_to_ann.pop(i, None)
        if ann in self.annotations:
            self.annotations.remove(ann)
        self._sel_ann = None
        self.canvas.delete("sel")
        self._toast("Elemento borrado")

    # ---- interaccion ------------------------------------------------------
    def on_press(self, event):
        self._close_color_popup()
        self._raise_bar()
        if self.tool == "select":
            self._sel_ann = self._select_at(event.x, event.y)
            self._sel_last = (event.x, event.y)
            self._draw_sel_outline()
            self._drag_start = None
            return
        if self.tool == "pick":
            self._apply_pick(event.x, event.y)
            self._drag_start = None
            return
        self.canvas.delete("sel")
        self._sel_ann = None
        self._drag_start = (event.x, event.y)
        if self.tool in ("pen", "marker"):
            self._pen_points = [(event.x, event.y)]
        elif self.tool == "text":
            # si hay un texto justo ahi, lo editamos en vez de crear otro
            existing = self._select_at(event.x, event.y)
            if existing and existing.get("type") == "text":
                self._edit_text(existing)
            else:
                self._place_text(event.x, event.y)
            self._drag_start = None

    def on_drag(self, event):
        if self.tool == "select":
            if self._sel_ann and self._sel_last:
                dx = event.x - self._sel_last[0]
                dy = event.y - self._sel_last[1]
                self._sel_last = (event.x, event.y)
                self._move_ann(self._sel_ann, dx, dy)
                self._draw_sel_outline()
            return
        if not self._drag_start:
            return
        x1, y1 = self._drag_start
        x2, y2 = event.x, event.y
        if self._temp_item:
            self.canvas.delete(self._temp_item)
            self._temp_item = None
        t = self.tool
        if t == "arrow":
            self._temp_item = self.canvas.create_line(
                x1, y1, x2, y2, fill=self.color, width=self.width,
                arrow=tk.LAST, arrowshape=(14, 16, 6))
        elif t == "rect":
            self._temp_item = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=self.color, width=self.width)
        elif t == "ellipse":
            self._temp_item = self.canvas.create_oval(
                x1, y1, x2, y2, outline=self.color, width=self.width)
        elif t == "line":
            self._temp_item = self.canvas.create_line(
                x1, y1, x2, y2, fill=self.color, width=self.width)
        elif t in ("blur", "crop"):
            self._temp_item = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=THEME["accent"], width=2, dash=(4, 3))
        elif t == "pen":
            self._pen_points.append((x2, y2))
            self._temp_item = self.canvas.create_line(
                *self._flatten(self._pen_points), fill=self.color,
                width=self.width, capstyle="round", joinstyle="round")
        elif t == "marker":
            self._pen_points.append((x2, y2))
            self._temp_item = self.canvas.create_line(
                *self._flatten(self._pen_points), fill=self.color,
                width=self.width * 4, capstyle="round", joinstyle="round",
                stipple="gray50")

    def on_release(self, event):
        if self.tool == "select":
            return
        if not self._drag_start:
            return
        x1, y1 = self._drag_start
        x2, y2 = event.x, event.y
        self._drag_start = None
        if self._temp_item:
            self.canvas.delete(self._temp_item)
            self._temp_item = None
        if self.tool in ("pen", "marker"):
            if len(self._pen_points) >= 2:
                self._add({"type": self.tool, "points": list(self._pen_points),
                           "color": self.color, "width": self.width})
            self._pen_points = []
            return
        if abs(x2 - x1) < 3 and abs(y2 - y1) < 3:
            return
        if self.tool == "blur":
            self._add_blur(x1, y1, x2, y2)
            return
        if self.tool == "crop":
            self._apply_crop(x1, y1, x2, y2)
            return
        self._add({"type": self.tool, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                   "color": self.color, "width": self.width})

    # ---- texto: crear y editar -------------------------------------------
    def _available_font_names(self):
        """Solo las fuentes del catalogo que realmente esten instaladas."""
        try:
            import tkinter.font as tkfont
            fams = set(tkfont.families(self.root))
            names = [n for n, _f in FONT_CHOICES if n in fams]
            if names:
                return names
        except Exception:
            pass
        return [n for n, _f in FONT_CHOICES]

    def _text_dialog(self, title, init_text, init_font, init_size, on_ok):
        if getattr(self, "_txt_open", False):
            return   # ya hay un dialogo de texto abierto
        self._txt_open = True
        dialog = tk.Toplevel(self.win)
        dialog.title(title)
        dialog.configure(bg=THEME["bg"])
        dialog.attributes("-topmost", True)
        frm = tk.Frame(dialog, bg=THEME["bg"], padx=14, pady=12)
        frm.pack()

        tk.Label(frm, text="Texto:", bg=THEME["bg"], fg=THEME["txt"],
                 font=THEME["font"]).grid(row=0, column=0, sticky="w", pady=4)
        entry = styled_entry(frm, width=36)
        entry.grid(row=0, column=1, columnspan=3, sticky="we", pady=4,
                   padx=(8, 0), ipady=4)
        entry.insert(0, init_text)
        entry.focus_set()
        entry.select_range(0, "end")

        tk.Label(frm, text="Fuente:", bg=THEME["bg"], fg=THEME["txt"],
                 font=THEME["font"]).grid(row=1, column=0, sticky="w", pady=4)
        names = self._available_font_names()
        font_var = tk.StringVar(value=init_font if init_font in names else names[0])
        styled_option(frm, font_var, names, width=16).grid(
            row=1, column=1, sticky="w", padx=(8, 0))

        tk.Label(frm, text="Tamano:", bg=THEME["bg"], fg=THEME["txt"],
                 font=THEME["font"]).grid(row=1, column=2, sticky="e", padx=(12, 0))
        size_var = tk.StringVar(value=str(init_size))
        styled_spin(frm, 8, 200, size_var, width=5).grid(
            row=1, column=3, sticky="w", padx=(8, 0), ipady=3)

        def ok(event=None):
            txt = entry.get().strip()
            fam = font_var.get()
            try:
                size = max(8, min(200, int(size_var.get())))
            except ValueError:
                size = init_size
            self._txt_open = False
            dialog.destroy()
            self._raise_bar()
            # recordar la eleccion para el proximo texto
            self.text_font, self.text_size = fam, size
            CONFIG["text_font"], CONFIG["text_size"] = fam, size
            save_config()
            on_ok(txt, fam, size)

        def cancel(event=None):
            self._txt_open = False
            dialog.destroy()
            self._raise_bar()

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        entry.bind("<Return>", ok)
        entry.bind("<Escape>", lambda e: cancel())

        btns = tk.Frame(frm, bg=THEME["bg"])
        btns.grid(row=2, column=0, columnspan=4, sticky="e", pady=(12, 0))
        styled_button(btns, "Cancelar", cancel, kind="ghost").pack(side="right", padx=4)
        styled_button(btns, "OK", ok, kind="accent").pack(side="right", padx=4)
        _center(dialog)

    def _place_text(self, x, y):
        def add(txt, fam, size):
            if txt:
                self._add({"type": "text", "x": x, "y": y, "text": txt,
                           "color": self.color, "size": size, "font": fam})
        self._text_dialog("Texto", "", self.text_font, self.text_size, add)

    def _edit_text(self, ann):
        def apply(txt, fam, size):
            if not txt:
                return
            ann["text"], ann["font"], ann["size"] = txt, fam, size
            try:
                self.canvas.itemconfigure(ann.get("_item"), text=txt,
                                          font=(fam, size))
            except Exception:
                pass
            self._draw_sel_outline()
            self._toast("Texto actualizado")
        self._text_dialog("Editar texto", ann.get("text", ""),
                          ann.get("font", self.text_font),
                          ann.get("size", self.text_size), apply)

    def on_double_click(self, event):
        """Doble clic sobre un texto existente -> editarlo."""
        ann = self._select_at(event.x, event.y)
        if ann and ann.get("type") == "text":
            self._sel_ann = ann
            self._draw_sel_outline()
            self._edit_text(ann)

    # ---- modelo -----------------------------------------------------------
    def _add(self, ann):
        self.annotations.append(ann)
        item = self._draw_on_canvas(ann)
        ann["_item"] = item
        self.canvas_items.append(item)
        for i in (item if isinstance(item, (list, tuple)) else [item]):
            self._item_to_ann[i] = ann

    def _draw_on_canvas(self, ann):
        t = ann["type"]
        if t == "arrow":
            return self.canvas.create_line(
                ann["x1"], ann["y1"], ann["x2"], ann["y2"], fill=ann["color"],
                width=ann["width"], arrow=tk.LAST, arrowshape=(14, 16, 6), tags="ann")
        if t == "line":
            return self.canvas.create_line(
                ann["x1"], ann["y1"], ann["x2"], ann["y2"],
                fill=ann["color"], width=ann["width"], tags="ann")
        if t == "rect":
            return self.canvas.create_rectangle(
                ann["x1"], ann["y1"], ann["x2"], ann["y2"],
                outline=ann["color"], width=ann["width"], tags="ann")
        if t == "ellipse":
            return self.canvas.create_oval(
                ann["x1"], ann["y1"], ann["x2"], ann["y2"],
                outline=ann["color"], width=ann["width"], tags="ann")
        if t == "pen":
            return self.canvas.create_line(
                *self._flatten(ann["points"]), fill=ann["color"],
                width=ann["width"], capstyle="round", joinstyle="round", tags="ann")
        if t == "marker":
            return self.canvas.create_line(
                *self._flatten(ann["points"]), fill=ann["color"],
                width=ann["width"] * 4, capstyle="round", joinstyle="round",
                stipple="gray50", tags="ann")
        if t == "text":
            return self.canvas.create_text(
                ann["x"], ann["y"], text=ann["text"], fill=ann["color"],
                font=(ann.get("font", THEME["font_family"]), ann["size"]),
                anchor="nw", tags="ann")

    def _pixelate(self, crop, block=10):
        w, h = crop.size
        if w < 1 or h < 1:
            return crop
        small = crop.resize((max(1, w // block), max(1, h // block)))
        return small.resize((w, h), Image.NEAREST)

    def _add_blur(self, x1, y1, x2, y2):
        bx1, by1 = int(min(x1, x2)), int(min(y1, y2))
        bx2, by2 = int(max(x1, x2)), int(max(y1, y2))
        ann = {"type": "blur", "x1": bx1, "y1": by1, "x2": bx2, "y2": by2}
        self.annotations.append(ann)
        img = _pil_to_tk(self._pixelate(self.screenshot.crop((bx1, by1, bx2, by2))))
        item = self.canvas.create_image(bx1, by1, anchor="nw", image=img, tags="ann")
        ann["_item"] = item
        ann["_tk"] = img   # referencia viva
        self.canvas_items.append(item)
        self._item_to_ann[item] = ann

    def _apply_crop(self, x1, y1, x2, y2):
        nx1 = int(max(self.bbox[0], min(x1, x2)))
        ny1 = int(max(self.bbox[1], min(y1, y2)))
        nx2 = int(min(self.bbox[2], max(x1, x2)))
        ny2 = int(min(self.bbox[3], max(y1, y2)))
        if nx2 - nx1 < 8 or ny2 - ny1 < 8:
            self.set_tool("arrow")
            return
        self.bbox = (nx1, ny1, nx2, ny2)
        self._draw_frame()
        self._place_bar(*self._bar_wh)   # reubicar la barra junto a la nueva region
        self.set_tool("arrow")
        self._toast("Region recortada")

    def undo(self):
        if not self.annotations:
            return
        ann = self.annotations.pop()
        if self.canvas_items:
            self.canvas_items.pop()
        item = ann.get("_item")
        for i in (item if isinstance(item, (list, tuple)) else [item]):
            self.canvas.delete(i)
            self._item_to_ann.pop(i, None)
        if self._sel_ann is ann:
            self._sel_ann = None
            self.canvas.delete("sel")

    @staticmethod
    def _flatten(points):
        flat = []
        for px, py in points:
            flat.extend([px, py])
        return flat

    # ---- render final -----------------------------------------------------
    def render(self):
        # Las anotaciones estan en coords de pantalla: dibujamos sobre la
        # captura completa y recortamos la region -> la salida coincide 1:1.
        base = self.screenshot.convert("RGBA").copy()
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))   # para el marcador
        odraw = ImageDraw.Draw(overlay)
        sdraw = ImageDraw.Draw(base)
        for ann in self.annotations:
            t = ann["type"]
            if t == "blur":
                self._apply_blur_pil(base, ann)
            elif t == "marker":
                self._draw_marker_pil(odraw, ann)
            else:
                self._draw_on_pil(sdraw, ann)
        out = Image.alpha_composite(base, overlay).convert("RGB")
        return out.crop(self.bbox)

    def _apply_blur_pil(self, base, ann):
        box = (ann["x1"], ann["y1"], ann["x2"], ann["y2"])
        region = base.crop(box).convert("RGB")
        base.paste(self._pixelate(region).convert("RGBA"), box)

    def _draw_marker_pil(self, draw, ann):
        if len(ann["points"]) < 2:
            return
        draw.line(self._flatten(ann["points"]), fill=_hex_to_rgba(ann["color"], 90),
                  width=ann["width"] * 4, joint="curve")

    def _draw_on_pil(self, draw, ann):
        t = ann["type"]
        color = ann.get("color", self.color)
        width = ann.get("width", self.width)
        if t == "line":
            draw.line([ann["x1"], ann["y1"], ann["x2"], ann["y2"]], fill=color, width=width)
        elif t == "rect":
            x1, y1, x2, y2 = ann["x1"], ann["y1"], ann["x2"], ann["y2"]
            draw.rectangle([min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                           outline=color, width=width)
        elif t == "ellipse":
            x1, y1, x2, y2 = ann["x1"], ann["y1"], ann["x2"], ann["y2"]
            draw.ellipse([min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                         outline=color, width=width)
        elif t == "pen":
            if len(ann["points"]) >= 2:
                draw.line(self._flatten(ann["points"]), fill=color, width=width, joint="curve")
        elif t == "arrow":
            self._draw_arrow_pil(draw, ann["x1"], ann["y1"], ann["x2"], ann["y2"], color, width)
        elif t == "text":
            draw.text((ann["x"], ann["y"]), ann["text"], fill=color,
                      font=_load_font(ann.get("size", self.text_size),
                                      ann.get("font")))

    @staticmethod
    def _draw_arrow_pil(draw, x1, y1, x2, y2, color, width):
        draw.line([x1, y1, x2, y2], fill=color, width=width)
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 10 + width * 2
        for offset in (math.pi - 0.5, math.pi + 0.5):
            ax = x2 + size * math.cos(angle + offset)
            ay = y2 + size * math.sin(angle + offset)
            draw.line([x2, y2, ax, ay], fill=color, width=width)

    # ---- acciones ---------------------------------------------------------
    def copy(self):
        try:
            copy_image_to_clipboard(self.render())
        except Exception as exc:
            messagebox.showerror("Cometa", "No se pudo copiar:\n%s" % exc)
            return
        self.close()   # copiar = operacion terminada; cerramos para pegar directo

    def save(self):
        ext = "jpg" if CONFIG.get("img_format", "png").lower() == "jpg" else "png"
        name = datetime.datetime.now().strftime("cometa_%Y%m%d_%H%M%S." + ext)
        folder = CONFIG.get("save_dir") or DEFAULT_SAVE_DIR
        try:
            # crear la carpeta DENTRO del try: si la ruta configurada no se
            # puede crear, caemos a la carpeta por defecto en vez de fallar.
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                folder = DEFAULT_SAVE_DIR
                os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, name)
            img = self.render()
            if ext == "jpg":
                img.convert("RGB").save(path, "JPEG",
                                        quality=int(CONFIG.get("jpg_quality", 92)))
            else:
                img.save(path, "PNG")
            if CONFIG.get("copy_after_save"):
                try:
                    copy_image_to_clipboard(img)
                except Exception:
                    pass
            self._toast("Guardado ✓  (%s)" % name)
            self._last_saved_dir = folder
        except Exception as exc:
            messagebox.showerror("Cometa", "No se pudo guardar en:\n%s\n\n%s"
                                 % (folder, exc))

    def ocr_copy(self):
        self._toast("Leyendo texto… (OCR)")
        try:
            self.bar.update_idletasks()
        except Exception:
            pass
        try:
            tmp = os.path.join(tempfile.gettempdir(), "cometa_ocr.png")
            self.render().save(tmp, "PNG")
            text = run_windows_ocr(tmp).strip()
        except Exception as exc:
            messagebox.showerror("Cometa", "No se pudo leer el texto (OCR):\n%s" % exc)
            self._toast(self.DEFAULT_STATUS)
            return
        if not text:
            self._toast("OCR: no se encontro texto")
            return
        try:
            self.win.clipboard_clear()
            self.win.clipboard_append(text)
        except Exception:
            pass
        self._toast("Texto copiado (OCR) ✓")

    def _toast(self, text):
        if len(text) > 26:          # que no ensanche la barra
            text = text[:25] + "…"
        self.status_var.set(text)
        self.bar.after(2600, lambda: self.status_var.set(self.DEFAULT_STATUS))

    def close(self):
        cb = self.on_close
        self.on_close = None
        self._close_color_popup()
        for w in (getattr(self, "bar", None), self.win):
            try:
                w.destroy()
            except Exception:
                pass
        if cb:
            cb()


# ----------------------------------------------------------------------------
# Aplicacion / controlador (modo residente)
# ----------------------------------------------------------------------------
class App:
    def __init__(self, silent=False):
        set_dpi_awareness()   # antes de crear la ventana Tk
        self.silent = silent   # arranca invisible, solo escuchando el atajo
        self.screenshot = None
        self.origin = (0, 0)
        self.root = tk.Tk()
        self.root.title("Cometa")
        self.root.configure(bg=THEME["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self.capturing = False

        apply_fonts(self.root)   # resuelve la tipografia antes de construir la UI
        set_app_icon(self.root)  # el cometa como icono de la app
        self._build_home()

        self.hotkey = GlobalHotkey()
        self.hook_ok = self.hotkey.start()
        self._update_hotkey_label()

        # Icono en la bandeja (si falla, la app sigue funcionando igual)
        try:
            self.tray = TrayIcon(write_icon_file(), "Cometa  ·  %s para capturar"
                                 % self._hotkey_str())
            self.tray_ok = self.tray.start()
        except Exception:
            self.tray, self.tray_ok = None, False
        self._update_hotkey_label()   # ahora ya sabemos si hay bandeja

        self.root.after(60, self._poll_hotkey)   # consumir eventos del hook

        if self.silent:
            self.root.withdraw()   # sin ventana; vive de fondo por el atajo

    # ---- ventana "home" ---------------------------------------------------
    def _build_home(self):
        pad = tk.Frame(self.root, bg=THEME["bg"], padx=22, pady=18)
        pad.pack()

        head = tk.Frame(pad, bg=THEME["bg"])
        head.pack(anchor="w")
        self._logo = _pil_to_tk(make_comet_icon(30))
        tk.Label(head, image=self._logo, bg=THEME["bg"]).pack(side="left",
                                                             padx=(0, 8))
        tk.Label(head, text="Cometa", bg=THEME["bg"], fg=THEME["txt"],
                 font=THEME["font_title"]).pack(side="left")
        self.sub = tk.Label(pad, text="", bg=THEME["bg"], fg=THEME["txt_dim"],
                            font=THEME["font"], justify="left")
        self.sub.pack(anchor="w", pady=(2, 14))

        styled_button(pad, "\U0001f4f7  Capturar ahora", self.request_capture,
                      kind="accent").pack(fill="x", pady=3)
        styled_button(pad, "\U0001f4c1  Abrir carpeta de capturas",
                      self.open_folder, kind="normal").pack(fill="x", pady=3)
        styled_button(pad, "⚙  Ajustes", self.open_settings,
                      kind="normal").pack(fill="x", pady=3)
        styled_button(pad, "Salir", self.quit, kind="ghost").pack(fill="x", pady=3)

        _center(self.root, y_ratio=4)

    def _hotkey_str(self):
        parts = []
        if CONFIG.get("hk_ctrl", True):
            parts.append("Ctrl")
        if CONFIG.get("hk_shift", True):
            parts.append("Shift")
        if CONFIG.get("hk_alt", False):
            parts.append("Alt")
        parts.append((CONFIG.get("hk_key") or "S").upper())
        return " + ".join(parts)

    def _update_hotkey_label(self):
        if self.hook_ok:
            txt = ("Atajo global activo:\n"
                   "%s  ·  capturar\n"
                   "Ctrl + Shift + Q  ·  salir" % self._hotkey_str())
        else:
            txt = ("Atajo global no disponible.\n"
                   "Usa el boton “Capturar ahora”.")
        if getattr(self, "tray_ok", False):
            txt += "\nIcono en la bandeja: clic izquierdo captura,\nclic derecho abre el menu."
        self.sub.configure(text=txt)

    # ---- puente hilos (atajo / bandeja) -> hilo de Tk ----------------------
    def _poll_hotkey(self):
        try:
            while True:
                evt = self.hotkey.events.get_nowait()
                if evt == "capture":
                    self.start_capture()
                elif evt == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass

        tray = getattr(self, "tray", None)
        if tray is not None:
            try:
                while True:
                    evt = tray.events.get_nowait()
                    if evt == "capture":
                        self.start_capture()
                    elif evt == "show":
                        self.show_home()
                    elif evt == "settings":
                        self.show_home()
                        self.open_settings()
                    elif evt == "folder":
                        self.open_folder()
                    elif evt == "quit":
                        self.quit()
                        return
            except queue.Empty:
                pass

        self.root.after(60, self._poll_hotkey)

    def show_home(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    # ---- flujo de captura -------------------------------------------------
    def request_capture(self):
        # Usado por el boton "Capturar ahora" (ya estamos en el hilo de Tk).
        self.root.after(0, self.start_capture)

    def start_capture(self):
        if self.capturing:
            return
        self.capturing = True
        self.root.withdraw()                 # esconder home para que no salga
        self.root.after(160, self._grab)     # dar tiempo a que desaparezca

    def _grab(self):
        try:
            _tk_refs.clear()   # liberar imagenes de la captura anterior (ya cerrada)
            # all_screens=True -> captura TODO el escritorio virtual (multi-monitor)
            self.screenshot = ImageGrab.grab(all_screens=True)
            self.origin = virtual_screen_origin()   # (x, y) del monitor mas a la izq/arriba
            RegionSelector(self.root, self.screenshot, self._after_select,
                           origin=self.origin)
        except Exception:
            self._fail("No se pudo iniciar la captura")

    def _after_select(self, bbox):
        if not bbox:
            self._restore_home()
            return
        try:
            # El editor recibe la captura completa + bbox: muestra todo con la
            # region resaltada y recorta al exportar.
            Editor(self.root, self.screenshot, bbox, self._restore_home,
                   origin=self.origin)
        except Exception:
            self._fail("No se pudo abrir el editor")

    def _fail(self, titulo):
        # Ante cualquier error: reseteamos el estado (para que el atajo siga
        # vivo) y mostramos el detalle en vez de fallar en silencio.
        import traceback
        detalle = traceback.format_exc()
        self._restore_home()
        try:
            messagebox.showerror("Cometa", "%s:\n\n%s" % (titulo, detalle))
        except Exception:
            print(titulo, detalle)

    def _restore_home(self):
        self.capturing = False
        if self.silent:
            return   # en modo silencioso no mostramos ventana
        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass

    def _on_window_close(self):
        # La X no cierra la app: la esconde para que el atajo siga vivo.
        # Para salir de verdad: boton "Salir" o Ctrl+Shift+Q.
        self.root.withdraw()

    # ---- utilidades -------------------------------------------------------
    def open_folder(self):
        os.makedirs(CONFIG["save_dir"], exist_ok=True)
        if os.name == "nt":
            os.startfile(CONFIG["save_dir"])   # noqa
        else:
            messagebox.showinfo("Cometa", CONFIG["save_dir"])

    # ---- panel de ajustes -------------------------------------------------
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Ajustes - Cometa")
        win.configure(bg=THEME["bg"])
        win.attributes("-topmost", True)
        frm = tk.Frame(win, bg=THEME["bg"], padx=18, pady=16)
        frm.pack(fill="both", expand=True)

        def lbl(text, r):
            tk.Label(frm, text=text, bg=THEME["bg"], fg=THEME["txt"],
                     font=THEME["font"]).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 12))

        # Carpeta de guardado
        lbl("Carpeta de capturas:", 0)
        dir_var = tk.StringVar(value=CONFIG["save_dir"])
        styled_entry(frm, dir_var, width=34).grid(row=0, column=1, sticky="we", ipady=4)

        def choose_dir():
            from tkinter import filedialog
            d = filedialog.askdirectory(parent=win, initialdir=CONFIG["save_dir"])
            if d:
                dir_var.set(d)
        styled_button(frm, "…", choose_dir, width=2).grid(row=0, column=2, padx=(6, 0))

        # Color por defecto
        lbl("Color por defecto:", 1)
        color_var = tk.StringVar(value=CONFIG["default_color"])
        color_prev = tk.Label(frm, bg=CONFIG["default_color"], width=4, relief="flat")
        color_prev.grid(row=1, column=1, sticky="w")

        def choose_color():
            from tkinter import colorchooser
            res = colorchooser.askcolor(color=color_var.get(), parent=win)
            if res and res[1]:
                color_var.set(res[1])
                color_prev.configure(bg=res[1])
        styled_button(frm, "Cambiar", choose_color).grid(row=1, column=1, sticky="e")

        # Grosor por defecto
        lbl("Grosor por defecto:", 2)
        width_var = tk.StringVar(value=CONFIG["default_width_key"])
        styled_option(frm, width_var, ["1", "2", "3"], width=4).grid(
            row=2, column=1, sticky="w")

        # Formato
        lbl("Formato de imagen:", 3)
        fmt_var = tk.StringVar(value=CONFIG.get("img_format", "png"))
        styled_option(frm, fmt_var, ["png", "jpg"], width=6).grid(
            row=3, column=1, sticky="w")

        # Copiar al guardar
        copy_var = tk.BooleanVar(value=bool(CONFIG.get("copy_after_save")))
        styled_check(frm, "Copiar al portapapeles al guardar", copy_var).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=6)

        # Auto-arranque
        auto_var = tk.BooleanVar(value=autostart_enabled())
        styled_check(frm, "Iniciar Cometa junto con Windows", auto_var).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=6)

        # Atajo global: Ctrl es la base, mas modificadores opcionales y letra
        lbl("Atajo global:", 5)
        hk = tk.Frame(frm, bg=THEME["bg"])
        hk.grid(row=5, column=1, columnspan=2, sticky="w")
        tk.Label(hk, text="Ctrl  +", bg=THEME["bg"], fg=THEME["accent"],
                 font=THEME["font_bold"]).pack(side="left", padx=(0, 4))
        shift_var = tk.BooleanVar(value=bool(CONFIG.get("hk_shift", True)))
        alt_var = tk.BooleanVar(value=bool(CONFIG.get("hk_alt", False)))
        for txt, var in (("Shift +", shift_var), ("Alt +", alt_var)):
            styled_check(hk, txt, var).pack(side="left")
        letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
        key_var = tk.StringVar(value=(CONFIG.get("hk_key") or "S").upper())
        styled_option(hk, key_var, letters, width=3).pack(side="left", padx=(6, 0))

        tk.Label(frm, text="Ojo: Ctrl + letra sola puede pisar atajos comunes\n"
                           "(Ctrl+C, Ctrl+V…). Conviene dejar Shift activado.",
                 bg=THEME["bg"], fg=THEME["txt_dim"], font=THEME["font"],
                 justify="left").grid(row=6, column=0, columnspan=3, sticky="w", pady=(2, 0))

        def apply_and_close():
            CONFIG["save_dir"] = dir_var.get().strip() or CONFIG["save_dir"]
            CONFIG["default_color"] = color_var.get()
            CONFIG["default_width_key"] = width_var.get()
            CONFIG["img_format"] = fmt_var.get()
            CONFIG["copy_after_save"] = copy_var.get()
            CONFIG["hk_ctrl"] = True   # Ctrl es siempre la base
            CONFIG["hk_shift"] = shift_var.get()
            CONFIG["hk_alt"] = alt_var.get()
            k = (key_var.get() or "S").strip()[:1].upper()
            CONFIG["hk_key"] = k if k else "S"
            save_config()
            # auto-arranque: crear o borrar el lanzador segun la casilla
            try:
                if auto_var.get():
                    install_autostart()
                else:
                    remove_autostart()
            except Exception as exc:
                messagebox.showwarning(
                    "Cometa", "No se pudo cambiar el auto-arranque:\n%s" % exc)
            self._restart_hotkey()
            self._update_hotkey_label()
            win.destroy()
            if not self.hook_ok:
                messagebox.showwarning(
                    "Cometa",
                    "No se pudo registrar %s.\n\nProbablemente otra aplicacion "
                    "ya usa ese atajo. Elegi otra combinacion en Ajustes."
                    % self._hotkey_str())

        btns = tk.Frame(frm, bg=THEME["bg"])
        btns.grid(row=9, column=0, columnspan=3, pady=(16, 0), sticky="e")
        styled_button(btns, "Cancelar", win.destroy, kind="ghost").pack(side="right", padx=4)
        styled_button(btns, "Guardar", apply_and_close, kind="accent").pack(side="right", padx=4)

        _center(win)

    def _restart_hotkey(self):
        try:
            self.hotkey.stop()
        except Exception:
            pass
        self.hotkey = GlobalHotkey()
        self.hook_ok = self.hotkey.start()

    def quit(self):
        try:
            self.hotkey.stop()
        except Exception:
            pass
        try:
            if getattr(self, "tray", None):
                self.tray.stop()   # saca el icono de la bandeja
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def main():
    load_config()   # cargar ajustes guardados (JSON) antes de arrancar

    # Comandos de instalacion (los usan los .bat)
    if "--install-autostart" in sys.argv:
        try:
            print("Auto-arranque instalado en:\n  %s" % install_autostart())
            print("Iniciando Cometa en segundo plano...")
            launch_detached()
        except Exception as exc:
            print("Error: %s" % exc)
        return
    if "--remove-autostart" in sys.argv:
        print("Auto-arranque quitado." if remove_autostart()
              else "No estaba instalado.")
        return
    # Arranca desligado de la consola y termina este proceso
    if "--detach" in sys.argv:
        launch_detached()
        return

    silent = "--silent" in sys.argv   # arranque de fondo (auto-inicio)
    App(silent=silent).run()


if __name__ == "__main__":
    main()
