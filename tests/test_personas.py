import json

from typer.testing import CliRunner

from dogfood.cli import app
from dogfood.dominio import Idioma, Intencion
from dogfood.personas.generador import RASGOS, generar
from dogfood.personas.nombres import APELLIDOS, NOMBRES


def test_emails_unicos():
    ps = generar(120, 1)
    assert len({p.email for p in ps}) == 120


def test_misma_semilla_mismas_personas():
    assert generar(30, 7) == generar(30, 7)
    assert generar(30, 7) != generar(30, 8)


def test_proporcion_idiomas():
    ps = generar(100, 3, {"pt-BR": 0.7, "es": 0.3})
    frac = sum(p.idioma == Idioma.pt_BR for p in ps) / 100
    assert abs(frac - 0.7) <= 0.10


def test_todas_las_intenciones():
    assert {p.intencion for p in generar(20, 5)} == set(Intencion)


def test_dominio_reservado_y_rangos():
    for p in generar(50, 9):
        assert p.email.endswith("@dogfood.example.com")
        assert 1 <= p.destreza <= 5 and 1 <= p.paciencia <= 5
        assert set(p.estilo) <= set(RASGOS)
        assert len(p.contrasena) >= 12


def test_listas_suficientes():
    for lang in ("pt-BR", "es"):
        assert len(set(NOMBRES[lang])) >= 80 and len(set(APELLIDOS[lang])) >= 80


def test_cli_guarda_json(tmp_path):
    out = tmp_path / "p.json"
    r = CliRunner().invoke(app, ["personas", "--n", "5", "--seed", "1", "--salida", str(out)])
    assert r.exit_code == 0, r.output
    assert len(json.loads(out.read_text())) == 5


def test_emails_pasan_la_validacion_de_predicts() -> None:
    # predicts valida con EmailStr (email-validator), que rechaza los TLD de uso especial
    # como .test (422 en /auth/registro en la corrida M1).
    especiales = {"test", "invalid", "local", "localhost", "onion", "arpa", "internal"}
    for p in generar(20, semilla=1):
        assert p.email.rsplit(".", 1)[-1] not in especiales
