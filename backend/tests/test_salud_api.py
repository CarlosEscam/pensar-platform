"""Pruebas de humo: la aplicación arranca y expone su documentación."""


def test_raiz_responde_mensaje_de_bienvenida(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "PENSAR" in r.json()["mensaje"]


def test_conexion_a_la_base_de_datos(client):
    assert client.get("/test-db").json()["estado"] == "exitoso"


def test_openapi_publica_los_13_endpoints_documentados(client):
    rutas = client.get("/openapi.json").json()["paths"]
    metodos = sum(len(v) for v in rutas.values())
    assert metodos == 13
