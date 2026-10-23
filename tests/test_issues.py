import json
import sys
from datetime import datetime

import pytest

from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.dominio import Corrida, Evidencia, Gravedad, Hallazgo, TipoHallazgo
from dogfood.reporte.issues import publicar

HUELLA_VIEJA = "a" * 39 + "1"

# Registra cada llamada en $GH_LOG; `issue list` responde con un issue si la búsqueda
# contiene HUELLA_VIEJA; `issue create` responde una URL.
GH = f"""#!{sys.executable}
import json, os, sys
a = sys.argv[1:]
with open(os.environ["GH_LOG"], "a") as f:
    f.write(json.dumps(a) + "\\n")
if a[:2] == ["issue", "list"]:
    s = a[a.index("--search") + 1]
    print(json.dumps([{{"number": 7, "url": "https://gh/x/7"}}] if "{HUELLA_VIEJA}" in s else []))
elif a[:2] == ["issue", "create"]:
    print("https://gh/x/99")
"""


@pytest.fixture
def gh(tmp_path, monkeypatch):
    exe = tmp_path / "bin" / "gh"
    exe.parent.mkdir()
    exe.write_text(GH)
    exe.chmod(0o755)
    log = tmp_path / "gh.log"
    monkeypatch.setenv("PATH", f"{exe.parent}:/usr/bin:/bin")
    monkeypatch.setenv("GH_LOG", str(log))

    def llamadas():
        return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []

    return llamadas


def escrituras(llamadas):
    return [c for c in llamadas if c[:2] != ["issue", "list"]]


CORRIDA = Corrida(
    id="c1", objetivo="predicts", ref="main", commit="abc1234", semilla=7,
    inicio=datetime(2026, 10, 23, 12, 0), estado="ok",
)  # fmt: skip
CONFIG = Config(roles={}, repo_issues="yo/predicts", umbral_publicar="media")


def hallazgo(n=0, **kw):
    return Hallazgo(
        tipo=TipoHallazgo.logica, gravedad=Gravedad.alta, pantalla="/panel", titulo=f"falla {n}",
        descripcion="el ciclo no cuadra", pasos=["subir csv", "abrir panel"],
        evidencia=[Evidencia(tipo="log", extracto="ERROR ciclo=0")], esperado="12 días",
        obtenido="0 días", huella=f"{n:040x}", ejecucion_id="e1", semilla=7, commit="abc1234",
    ).model_copy(update=kw)  # fmt: skip


def test_nuevo_crea_issue_con_etiquetas_y_huella(gh, tmp_path):
    alm = Almacen(tmp_path / "runs")
    alm.nueva_corrida(CORRIDA)
    h = hallazgo(1)
    alm.guardar_hallazgos("c1", [h])
    [r] = publicar([h], CORRIDA, CONFIG, almacen=alm)
    assert (r.accion, r.publicado, r.nuevo, r.issue_url) == ("crear", True, True, "https://gh/x/99")
    [crear] = [c for c in gh() if c[:2] == ["issue", "create"]]
    assert crear[crear.index("-R") + 1] == "yo/predicts"
    etiquetas = [crear[i + 1] for i, a in enumerate(crear) if a == "--label"]
    assert etiquetas == ["dogfood", "dogfood:logica", "gravedad:alta"]
    assert f"<!-- dogfood:huella={h.huella} -->" in crear[crear.index("--body") + 1]
    assert {c[2] for c in gh() if c[:2] == ["label", "create"]} == set(etiquetas)
    with alm._con() as con:
        fila = con.execute("SELECT issue_url, nuevo FROM hallazgos").fetchone()
    assert tuple(fila) == ("https://gh/x/99", 1)


def test_huella_existente_comenta(gh):
    [r] = publicar([hallazgo(huella=HUELLA_VIEJA)], CORRIDA, CONFIG)
    assert (r.accion, r.nuevo, r.issue_url) == ("comentar", False, "https://gh/x/7")
    [w] = escrituras(gh())
    assert w[:3] == ["issue", "comment", "7"] and "c1" in w[w.index("--body") + 1]


def test_bajo_umbral_o_solo_reporte_no_llama_a_gh(gh):
    rs = publicar(
        [hallazgo(1, gravedad=Gravedad.baja), hallazgo(2, solo_reporte=True)], CORRIDA, CONFIG
    )
    assert [r.accion for r in rs] == ["omitido", "omitido"]
    assert gh() == []


def test_secreto_bloquea(gh):
    # el secreto conocido queda partido dentro de un token sk-: tras redactar, sigue sucio
    h = hallazgo(1, obtenido="clave sk-Clave99abcdefghij")
    [r] = publicar([h], CORRIDA, CONFIG, secretos=["Clave99"])
    assert r.accion == "bloqueado_por_redaccion" and not r.publicado
    assert gh() == []


def test_sin_publicar_no_escribe(gh):
    rs = publicar([hallazgo(1), hallazgo(huella=HUELLA_VIEJA)], CORRIDA, CONFIG, publicar=False)
    assert [r.accion for r in rs] == ["crear", "comentar"]
    assert not any(r.publicado for r in rs)
    assert escrituras(gh()) == []


def test_tope_corta_y_avisa(gh):
    cfg = CONFIG.model_copy()
    object.__setattr__(cfg, "max_issues_nuevos_por_corrida", 2)
    rs = publicar([hallazgo(n) for n in range(1, 5)], CORRIDA, cfg)
    assert [r.accion for r in rs] == ["crear", "crear", "tope", "tope"]
    assert all(r.aviso and not r.publicado for r in rs[2:])
    assert len([c for c in gh() if c[:2] == ["issue", "create"]]) == 2
