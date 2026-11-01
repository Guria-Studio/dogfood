import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dogfood.panel.ayuda import registrar_ayuda


def _repo(tmp_path: Path) -> Path:
    ay, ops = tmp_path / "docs" / "ayuda", tmp_path / "docs" / "ops"
    ay.mkdir(parents=True)
    ops.mkdir(parents=True)
    (ay / "a.md").write_text(
        "---\ntitulo: Vista en vivo\nseccion: referencia\norden: 2\npantallas: [vista]\n---\n\n# X\n\ntexto\n"
    )
    (ay / "b.md").write_text(
        "---\ntitulo: Empezar\nseccion: empezar\norden: 1\npantallas: [corridas]\n---\n\n"
        "# Empezar\n\nla vista se abre aparte; cada corrida deja ejecuciones\n"
    )
    (ops / "guia.md").write_text("# Guía suelta\n\nSin frontmatter.\n")
    return tmp_path


def _cliente(repo: Path) -> TestClient:
    app = FastAPI()
    registrar_ayuda(app, repo)
    return TestClient(app)


def test_frontmatter_y_valores_por_defecto(tmp_path):
    docs = {d["slug"]: d for d in _cliente(_repo(tmp_path)).get("/api/ayuda").json()}
    assert docs["a"] == {
        "slug": "a",
        "titulo": "Vista en vivo",
        "seccion": "referencia",
        "orden": 2,
        "pantallas": ["vista"],
    }
    assert docs["ops-guia"] == {
        "slug": "ops-guia",
        "titulo": "Guía suelta",
        "seccion": "guias",
        "orden": 100,
        "pantallas": [],
    }


def test_filtro_por_pantalla_y_orden_por_seccion(tmp_path):
    c = _cliente(_repo(tmp_path))
    assert [d["slug"] for d in c.get("/api/ayuda").json()] == ["b", "ops-guia", "a"]
    assert [d["slug"] for d in c.get("/api/ayuda?pantalla=vista").json()] == ["a"]


def test_busqueda_puntaje_y_acentos(tmp_path):
    c = _cliente(_repo(tmp_path))
    r = c.get("/api/ayuda/buscar", params={"q": "vista"}).json()
    assert [x["slug"] for x in r] == ["a", "b"]
    assert r[0]["puntaje"] > r[1]["puntaje"]
    assert "vista" in r[1]["fragmento"]
    assert [x["slug"] for x in c.get("/api/ayuda/buscar", params={"q": "corrída"}).json()] == ["b"]
    assert c.get("/api/ayuda/buscar", params={"q": "v"}).json() == []
    assert c.get("/api/ayuda/buscar").json() == []


def test_slug_fuera_de_carpeta_da_404(tmp_path):
    c = _cliente(_repo(tmp_path))
    assert c.get("/api/ayuda/..%2F..%2Fetc").status_code == 404
    assert c.get("/api/ayuda/a").json()["doc"]["slug"] == "a"


def test_editar_archivo_actualiza_sin_reiniciar(tmp_path):
    repo = _repo(tmp_path)
    c = _cliente(repo)
    assert c.get("/api/ayuda/buscar", params={"q": "zanahoria"}).json() == []
    f = repo / "docs" / "ayuda" / "b.md"
    f.write_text(f.read_text() + "\nzanahoria\n")
    os.utime(f, ns=(1, 1))  # fuerza otro mtime aunque el reloj sea grueso
    assert [x["slug"] for x in c.get("/api/ayuda/buscar", params={"q": "zanahoria"}).json()] == [
        "b"
    ]
