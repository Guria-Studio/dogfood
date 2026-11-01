import asyncio
from datetime import datetime

from fastapi.testclient import TestClient

from dogfood.config import Config
from dogfood.dominio import Corrida, Evidencia, Gravedad, Hallazgo, TipoHallazgo
from dogfood.panel.app import crear_app_panel
from dogfood.reporte.issues import cuerpo
from dogfood.reporte.sugerencia import Sugerencia, guardar, sugerir

SECRETO = "hunter2-super-secreto"


def hallazgo(extracto="GET /calidad -> 404"):
    return Hallazgo(
        tipo=TipoHallazgo.tecnico, gravedad=Gravedad.alta, pantalla="/calidad", titulo="404 en /calidad",
        descripcion="la ruta responde 404", evidencia=[Evidencia(tipo="red", extracto=extracto)],
        semilla=1, commit="abc1234", ejecucion_id="c1-E1",
    )  # fmt: skip


class LlmFalso:
    def __init__(self, archivos=("src/rutas.py",), confianza="alta"):
        self.prompts, self.archivos, self.confianza = [], archivos, confianza

    async def __call__(self, rol, prompt, esquema, cfg=None):
        assert rol == "redactor"
        self.prompts.append(prompt)
        return Sugerencia(
            causa=f"falta la ruta ({SECRETO})",
            archivos=[{"ruta": a} for a in self.archivos],
            cambio="registrar /calidad",
            confianza=self.confianza,
        )


def repo_falso(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/rutas.py").write_text('x = 1\nRUTAS = ["/inicio"]\n@get("/calidad")\n')
    (tmp_path / "src/otro.py").write_text("nada\n")
    return tmp_path


def test_cita_el_archivo_de_la_ruta(tmp_path):
    llm = LlmFalso(archivos=("src/rutas.py", "src/inventado.py"))
    s = asyncio.run(sugerir(hallazgo(), hallazgo().evidencia, repo_falso(tmp_path), completar=llm))
    assert [(a.ruta, a.linea) for a in s.archivos] == [("src/rutas.py", 3)]
    assert s.confianza == "alta"
    assert "src/rutas.py" in llm.prompts[0] and "otro.py" not in llm.prompts[0]


def test_sin_repo_confianza_baja():
    s = asyncio.run(sugerir(hallazgo(), hallazgo().evidencia, None, completar=LlmFalso()))
    assert s.confianza == "baja" and s.archivos == [] and "hipótesis" in s.causa


def test_secreto_no_llega_al_prompt_ni_a_la_sugerencia(tmp_path):
    h = hallazgo(f"GET /calidad -> 404 token={SECRETO}")
    llm = LlmFalso()
    s = asyncio.run(
        sugerir(h, h.evidencia, repo_falso(tmp_path), secretos=[SECRETO], completar=llm)
    )
    assert SECRETO not in llm.prompts[0]
    assert SECRETO not in s.model_dump_json()


def test_cuerpo_del_issue_incluye_la_seccion():
    c = Corrida(
        id="c1",
        objetivo="p",
        ref="m",
        commit="a",
        semilla=1,
        inicio=datetime(2026, 1, 1),
        estado="ok",
    )
    s = Sugerencia(causa="falta la ruta", cambio="registrarla", confianza="baja")
    assert "## Posible causa y arreglo (sugerido por dogfood, revisar)" in cuerpo(hallazgo(), c, s)
    assert "Posible causa" not in cuerpo(hallazgo(), c)


def test_api_hallazgo(tmp_path):
    (tmp_path / "c1").mkdir()
    (tmp_path / "c1/hallazgos.json").write_text(f"[{hallazgo().model_dump_json()}]")
    guardar(tmp_path / "c1", {"c1-H1": Sugerencia(causa="x", cambio="y", confianza="media")})
    r = TestClient(crear_app_panel(tmp_path, Config(roles={}, repo_issues="yo/predicts")))
    d = r.get("/api/hallazgos/c1-H1", headers={"X-Dogfood": "1"}).json()
    assert d["sugerencia"]["confianza"] == "media" and d["repo"] == "yo/predicts"
    assert len(r.get("/api/ejecuciones/c1-E1/hallazgos").json()) == 1
    assert r.get("/api/hallazgos/c1-H9").status_code == 404
