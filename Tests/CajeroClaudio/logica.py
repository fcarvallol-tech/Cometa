"""
logica.py
=========
Lógica de negocio del cajero. NO tiene interfaz (ni print ni input ni ventanas).
Solo funciones "puras": reciben datos, devuelven datos.

¿Por qué separar la lógica de la interfaz?
- Puedes testear el cálculo sin abrir la ventana.
- Si mañana cambias Tkinter por una web, esta parte no se toca.
Esto se llama "separation of concerns" (separación de responsabilidades).
"""

# Denominaciones disponibles en Chile, de mayor a menor.
# Es una constante: por convención en Python las constantes van en MAYÚSCULAS.
BILLETES = [20000, 10000, 5000, 2000, 1000]

# El billete más chico define el múltiplo mínimo que el cajero puede entregar.
MULTIPLO_MINIMO = min(BILLETES)  # 1000


class MontoInvalido(Exception):
    """
    Excepción propia para montos inválidos.

    Crear tu propia excepción (en vez de usar ValueError genérico) le permite
    a la interfaz distinguir "el usuario se equivocó" de cualquier otro error
    inesperado del programa. Es una práctica muy común en código profesional.
    """
    pass


def calcular_billetes(monto: int) -> dict[int, int]:
    """
    Calcula el mínimo de billetes para entregar `monto`.

    Usa el algoritmo "greedy" (avaro): en cada paso toma la mayor cantidad
    posible del billete más grande que quepa, y sigue con el resto.
    Para el sistema monetario chileno esto SIEMPRE da el mínimo de billetes.

    Args:
        monto: cantidad solicitada. Debe ser entero, positivo y múltiplo de 1000.

    Returns:
        dict {denominacion: cantidad}. Ej: {20000: 1, 5000: 1} para 25000.
        Se devuelve un diccionario (no una lista) para que cada cantidad viaje
        siempre junto a su denominación y nunca se desalineen.

    Raises:
        MontoInvalido: si el monto no es válido.
    """
    if monto <= 0:
        raise MontoInvalido("El monto debe ser mayor a 0.")

    if monto % MULTIPLO_MINIMO != 0:
        raise MontoInvalido(f"El monto debe ser múltiplo de {MULTIPLO_MINIMO}.")

    restante = monto
    resultado: dict[int, int] = {}

    for billete in BILLETES:
        # divmod(a, b) devuelve (a // b, a % b) de una sola vez: cuántos billetes
        # de esta denominación caben, y cuánto sobra. Es el "truco" pythónico que
        # reemplaza toda la aritmética manual de módulos.
        cantidad, restante = divmod(restante, billete)
        if cantidad > 0:
            resultado[billete] = cantidad

    return resultado


def total_billetes(billetes: dict[int, int]) -> int:
    """Cantidad total de billetes que se entregan (suma de todas las cantidades)."""
    return sum(billetes.values())


def formatear_clp(monto: int) -> str:
    """
    Formatea un número como pesos chilenos con separador de miles: 25000 -> '$25.000'.

    Truco: f"{monto:,}" pone comas (formato inglés), y luego cambiamos las
    comas por puntos, que es como se escribe en Chile.
    """
    return f"${monto:,}".replace(",", ".")


# Bloque de auto-test. Solo corre si ejecutas este archivo directamente
# (python logica.py); no corre cuando la interfaz lo importa.
if __name__ == "__main__":
    assert calcular_billetes(25000) == {20000: 1, 5000: 1}
    assert calcular_billetes(1000) == {1000: 1}
    assert calcular_billetes(48000) == {20000: 2, 5000: 1, 2000: 1, 1000: 1}
    assert total_billetes(calcular_billetes(48000)) == 5
    assert formatear_clp(1250000) == "$1.250.000"
    print("Todos los tests pasaron. ✓")
