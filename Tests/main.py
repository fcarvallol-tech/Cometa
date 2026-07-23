from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def inicio():
    return {"mensaje": "Hola, API funcionando"}

@app.get("/saludo/{nombre}")
def saludo(nombre: str):
    return {"mensaje": f"Hola {nombre}"}

@app.get("/suma")
def suma(a: int, b: int):
    return {"resultado": a + b}