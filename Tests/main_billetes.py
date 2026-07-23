"""
main.py
------------------
Punto de entrada del cajero automático.
Ejecutar con: python3 main.py
"""

from cajero_ui import ejecutar_consulta, loop_interactivo


def main():
    # Ejemplo directo (sin necesidad de input)
    ejecutar_consulta(25000)

    # Modo interactivo
    loop_interactivo()


if __name__ == "__main__":
    main()