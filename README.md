# ☄️ Cometa

**Capturas de pantalla con anotaciones para Windows.** Apretás un atajo, seleccionás un área, la marcás y la copiás o guardás. Sin instaladores, sin cuentas, sin subir nada a servidores ajenos.

Un cometa deja una estela: capturás, marcás lo importante, y lo compartís.

Nació como reemplazo de Lightshot en un entorno corporativo donde el firewall bloquea la descarga de aplicaciones. Solo necesita Python y una librería.

---

## Características

**Captura**
- Atajo global configurable (por defecto `Ctrl + Shift + S`) que funciona desde cualquier aplicación
- Selección de región con la pantalla congelada y medidas en vivo
- Corre en segundo plano, con ícono en la bandeja del sistema

**Editor**
- Flecha, línea, rectángulo, elipse, lápiz y marcador (resaltador semitransparente)
- **Difuminar**: pixela una zona para tapar datos sensibles antes de compartir
- **Texto** con selector de fuente y tamaño; doble clic para editarlo después
- **Seleccionar y mover** cualquier elemento ya dibujado, o borrarlo con `Supr`
- **Recortar** la región después de haberla capturado
- **OCR**: extrae el texto de la imagen y lo copia al portapapeles

**Salida**
- Copiar al portapapeles o guardar como PNG / JPG
- Carpeta de destino configurable

---

## Requisitos

- **Windows 10 u 11** — usa APIs nativas para portapapeles, atajos globales, bandeja y OCR
- **Python 3.8 o superior** ([python.org](https://www.python.org/downloads/), marcá "Add Python to PATH")
- **Pillow**

---

## Instalación

```bash
git clone https://github.com/TU-USUARIO/cometa.git
cd cometa
py -m pip install pillow
```

Probá que arranca:

```bash
py cometa.py
```

Debería abrirse una ventanita chica y aparecer el ícono del cometa junto al reloj.

> Si `py` no funciona, probá `python`. Si `pip` no se reconoce, usá `py -m pip` como está arriba.

---

## Dejarlo corriendo en segundo plano

Esta es la parte importante: **si lo ejecutás desde una terminal, el proceso muere al cerrar esa ventana**. Es cómo funciona Windows: el proceso hijo cuelga de la consola. Para que sobreviva hay que lanzarlo desacoplado.

### Opción recomendada: auto-arranque

Doble clic en **`Instalar auto-arranque.bat`**.

Eso hace dos cosas:
1. Arranca Cometa ahora mismo, en segundo plano y sin consola
2. Lo deja configurado para iniciarse solo cada vez que prendas el PC

Desde ese momento podés cerrar todas las terminales: el atajo sigue funcionando.

### Desde la app

En la ventana principal → **⚙ Ajustes** → marcá **"Iniciar Cometa junto con Windows"** → Guardar.

### Solo por esta vez

Si querés levantarlo suelto sin dejarlo permanente:

```bash
py cometa.py --detach
```

Devuelve el prompt enseguida y podés cerrar la terminal.

### Cómo funciona por dentro

El instalador crea un archivo `Cometa.vbs` en la carpeta de Inicio de Windows:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Cometa.vbs
```

Ese script lanza `pythonw.exe` (el Python sin consola) con la **ruta absoluta** del intérprete y del script. Usa rutas absolutas a propósito: no depende de que Python esté en el `PATH`, que es la causa más común de que un auto-arranque falle en silencio.

### Verificar que está corriendo

- Buscá el ícono del cometa junto al reloj (puede estar escondido en la flechita `^`)
- O en el Administrador de tareas, buscá `pythonw.exe`

### Cerrarlo

- `Ctrl + Shift + Q`, o
- Clic derecho en el ícono de la bandeja → **Salir**

### Desinstalar el auto-arranque

Doble clic en **`Quitar auto-arranque.bat`**, o destildá la casilla en Ajustes.

---

## Atajos

### Globales (desde cualquier aplicación)

| Atajo | Acción |
|---|---|
| `Ctrl + Shift + S` | Capturar (configurable) |
| `Ctrl + Shift + Q` | Salir de Cometa |

### En el editor

| Atajo | Acción |
|---|---|
| `Ctrl + C` | Copiar al portapapeles |
| `Ctrl + S` | Guardar |
| `Ctrl + Z` | Deshacer |
| `Supr` | Borrar el elemento seleccionado |
| `Esc` | Cerrar sin guardar |
| `1` `2` `3` | Grosor del trazo |
| `V` | Seleccionar / mover |
| `A` | Flecha |
| `L` | Línea |
| `R` | Rectángulo |
| `E` | Elipse |
| `P` | Lápiz |
| `M` | Marcador |
| `B` | Difuminar |
| `T` | Texto |

**Doble clic sobre un texto** ya dibujado lo abre para editarlo.

### Ícono de la bandeja

- **Clic izquierdo**: capturar
- **Clic derecho**: menú con Capturar, Mostrar ventana, Ajustes, Abrir carpeta y Salir

---

## Configuración

Todo se edita desde **⚙ Ajustes** y se guarda en:

```
%APPDATA%\Cometa\config.json
```

Se puede configurar: carpeta de capturas, color y grosor por defecto, fuente y tamaño del texto, formato de imagen (PNG/JPG), copiar automáticamente al guardar, el atajo global y el auto-arranque.

El atajo usa `Ctrl` como base, con `Shift` y `Alt` opcionales más una letra.

> ⚠️ **Cuidado con `Ctrl` + letra sola.** Windows le da propiedad exclusiva del atajo a la aplicación que lo registra. Si elegís `Ctrl + C`, te quedás sin "copiar" en todo el sistema mientras Cometa corre. Conviene dejar `Shift` activado.

Las capturas se guardan por defecto en `Imágenes\Capturas_Cometa` con nombres tipo `cometa_20260720_143000.png`. La forma más rápida de llegar es el botón **"Abrir carpeta de capturas"** en la ventana principal, o clic derecho en el ícono de la bandeja → Abrir carpeta.

---

## Solución de problemas

**Cierro la terminal y deja de funcionar el atajo.**
Es lo esperado si lo lanzaste con `py cometa.py`. Usá `Instalar auto-arranque.bat` o `py cometa.py --detach`.

**La ventana dice "Atajo global no disponible".**
Otra aplicación ya tiene registrada esa combinación. Cambiala en Ajustes por otra letra.

**No veo el ícono en la bandeja.**
Windows esconde los íconos nuevos. Hacé clic en la flechita `^` junto al reloj y arrastrá el cometa hacia la barra para fijarlo.

**El OCR falla.**
Necesita un idioma con OCR instalado en Windows: Configuración → Hora e idioma → Idioma → tu idioma → Opciones → instalar OCR.

**El atajo no responde después de instalar el auto-arranque.**
Puede haber dos instancias corriendo, y la segunda no logra registrar el atajo. Cerrá todo (`Ctrl + Shift + Q`, o matá `pythonw.exe` en el Administrador de tareas) y volvé a arrancar.

**La selección aparece corrida respecto del cursor.**
No debería: la app se declara *DPI-aware* al iniciar para que Tkinter y la captura trabajen en píxeles físicos. Si te pasa en un monitor con escalado, abrí un issue con tu configuración de pantalla.

---

## Estructura del proyecto

```
cometa.py                    Toda la aplicación (un solo archivo)
Instalar auto-arranque.bat   Registra el inicio automático
Quitar auto-arranque.bat     Lo desinstala
README.md
```

### Cómo extenderlo

El código está pensado para crecer. Las piezas clave:

- **`Editor.annotations`** es la única fuente de verdad de todo lo dibujado. Cada anotación es un diccionario con su tipo y sus coordenadas.
- Cada herramienta se dibuja en **dos lugares**: `_draw_on_canvas` (la vista previa interactiva en Tkinter) y `_draw_on_pil` (el render final con Pillow). Para agregar una herramienta nueva, sumá su tipo en ambos y una entrada en `Editor.TOOLS`.
- **`THEME`** concentra toda la paleta y la tipografía.
- **`GlobalHotkey`** y **`TrayIcon`** corren en hilos propios con su bucle de mensajes de Windows, y se comunican con el hilo de Tkinter mediante colas. Es el patrón a seguir si agregás algo que necesite APIs nativas.

### Línea de comandos

```bash
py cometa.py                       # normal, con ventana
py cometa.py --silent              # en segundo plano, sin ventana
py cometa.py --detach              # se desliga de la consola y sale
py cometa.py --install-autostart   # instala el inicio automático
py cometa.py --remove-autostart    # lo quita
```

---

## Limitaciones conocidas

- **Solo Windows.** El portapapeles, el atajo global, la bandeja y el OCR usan APIs nativas.
- **Un solo monitor.** Captura la pantalla principal; falta soporte multi-monitor.
- **Sin sombras ni animaciones.** La interfaz es Tkinter, que no soporta esos efectos.

## Ideas para próximas versiones

Pasos numerados para documentar procesos, historial de capturas, captura de ventana activa y con temporizador, multi-monitor, y compartir vía link auto-hospedado.

---

## Licencia

Sugerencia: [MIT](https://choosealicense.com/licenses/mit/) — permisiva y simple. Agregá un archivo `LICENSE` antes de publicarlo.
