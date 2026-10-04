from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import engine, Base, get_db
from .routers import users
from .routers import auth
from .routers import diagnostic
from .routers import challenges

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PENSAR API",
    description="API para la plataforma de Pensamiento Computacional",
    version="0.1.0",
)

app.include_router(users.router)
app.include_router(challenges.router)
app.include_router(auth.router)
app.include_router(diagnostic.router)


@app.get("/")
def read_root():
    return {"mensaje": "¡Bienvenido a la API de PENSAR! El backend está funcionando."}


@app.get("/test-db")
def test_db_connection(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"estado": "exitoso", "mensaje": "Conexión a PostgreSQL correcta."}
    except Exception as e:
        return {"estado": "error", "mensaje": str(e)}
