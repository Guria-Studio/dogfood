import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from dogfood.almacen import ESQUEMA_V1, VERSION_ESQUEMA, Almacen
from dogfood.cli import app
from dogfood.config import Config
from dogfood.contrato import resultado
from dogfood.dominio import Corrida, Ejecucion, MetricasEjecucion, Paso, UsoLlm
from dogfood.drivers import ElementoUI, arbol_a_texto
from dogfood.eventos import BUS_NULO, BusVivo, EventoVivo

TS = datetime(2026, 10, 29, 12, 0)


def test_help_lista_los_seis_comandos():
    salida = CliRunner().invoke(app, ["--help"]).output
    for cmd in ("env", "datos", "personas", "run", "runs", "replay"):
        assert f" {cmd} " in salida


def test_ejecucion_f5_carga_con_valores_por_defecto():
    viejo = {
        "id": "e1",
        "persona_id": "p1",
        "escenario_id": "s1",
        "modelo": "m",
        "estado": "ok",
        "pasos": [{"n": 1, "url": "u", "pantalla": "p", "accion": "a", "ts": TS.isoformat()}],
    }
    e = Ejecucion.model_validate_json(json.dumps(viejo))
    assert e.driver == "web" and e.resultado is None and e.motor == "browser_use"
    assert e.pasos[0].punto is None and e.metricas.capturas == 0


def test_migracion_v1_a_v2(tmp_path):
    db = tmp_path / "dogfood.db"
    with closing(sqlite3.connect(db)) as con:
        con.executescript(ESQUEMA_V1)
        con.execute(
            "INSERT INTO ejecuciones VALUES ('e0', 'c1', 'p', 's', 'm', 'ok', 3, 1.0, 1, 'bien')"
        )
        con.execute("INSERT INTO uso_llm VALUES ('c1', 'e0', 'persona', 'm', 1, 2, 0.5)")
        con.execute("PRAGMA user_version = 1")
        con.commit()

    a = Almacen(tmp_path)
    a.nueva_corrida(
        Corrida(
            id="c2",
            objetivo="x",
            ref="main",
            commit="abc",
            semilla=1,
            inicio=TS,
            estado="corriendo",
            version_app="1.2.3",
        )
    )
    e = Ejecucion(
        id="e1",
        persona_id="p",
        escenario_id="s",
        modelo="m",
        estado="ok",
        driver="android",
        motor="bucle",
        backend="claude_code",
        resultado="aprobado",
        metricas=MetricasEjecucion(
            tokens_in=10, tokens_out=5, capturas=2, costo_equivalente_usd=0.1
        ),
        video=Path("video/a.mp4"),
    )
    a.guardar_ejecucion("c2", e)
    a.registrar_uso(
        UsoLlm(
            rol="persona",
            modelo="m",
            tokens_in=1,
            tokens_out=1,
            costo_usd=0,
            backend="claude_code",
            costo_equivalente_usd=0.2,
        ),
        "c2",
    )

    with closing(sqlite3.connect(db)) as con:
        con.row_factory = sqlite3.Row
        assert con.execute("PRAGMA user_version").fetchone()[0] == VERSION_ESQUEMA == 2
        viejo = con.execute("SELECT * FROM ejecuciones WHERE id = 'e0'").fetchone()
        assert viejo["motivo_juez"] == "bien" and viejo["driver"] == "web"
        assert viejo["motor"] == "browser_use" and viejo["resultado"] is None
        nuevo = con.execute("SELECT * FROM ejecuciones WHERE id = 'e1'").fetchone()
        assert (nuevo["driver"], nuevo["motor"], nuevo["backend"], nuevo["resultado"]) == (
            "android",
            "bucle",
            "claude_code",
            "aprobado",
        )
        assert (nuevo["tokens_in"], nuevo["capturas"], nuevo["video"]) == (10, 2, "video/a.mp4")
        usos = con.execute("SELECT backend, costo_equivalente_usd FROM uso_llm").fetchall()
        assert [tuple(u) for u in usos] == [("api", 0), ("claude_code", 0.2)]
        assert con.execute("SELECT version_app FROM corridas").fetchone()[0] == "1.2.3"

    Almacen(tmp_path)  # reabrir una base v2 no vuelve a migrar


def _ejecucion(estado="ok", exito=False, motivo="", captura=True) -> Ejecucion:
    paso = Paso(
        n=1,
        url="u",
        pantalla="p",
        accion="a",
        ts=TS,
        captura=Path("capturas/paso-001.png") if captura else None,
    )
    return Ejecucion(
        id="e",
        persona_id="p",
        escenario_id="s",
        modelo="m",
        estado=estado,
        pasos=[paso],
        exito=exito,
        motivo_juez=motivo,
    )


def test_resultado():
    assert resultado(_ejecucion(exito=True, motivo="ok", captura=False)) == "no_concluyente"
    assert resultado(_ejecucion(exito=True, motivo="se descargó el CSV")) == "aprobado"
    assert resultado(_ejecucion(exito=True, motivo="")) == "no_concluyente"
    assert resultado(_ejecucion(estado="fallo")) == "fallo"
    assert resultado(_ejecucion(estado="error", exito=True, motivo="x")) == "no_concluyente"


def test_bus_no_bloquea_y_respeta_el_tope():
    bus = BusVivo()
    sub = bus.suscribir(max_cola=3)
    for n in range(10):
        bus.publicar(EventoVivo(corrida_id="c", ejecucion_id="e", tipo="frame", n_paso=n))
        assert sub.cola.qsize() <= 3
    assert [sub.cola.get_nowait().n_paso for _ in range(3)] == [7, 8, 9]
    sub.close()
    bus.publicar(EventoVivo(corrida_id="c", ejecucion_id="e", tipo="fin"))
    assert sub.cola.empty()
    assert bus.activo and not BUS_NULO.activo
    BUS_NULO.publicar(EventoVivo(corrida_id="c", ejecucion_id="e", tipo="inicio"))


async def test_suscripcion_es_iterable():
    bus = BusVivo()
    sub = bus.suscribir()
    bus.publicar(EventoVivo(corrida_id="c", ejecucion_id="e", tipo="inicio"))
    async for ev in sub:
        assert ev.tipo == "inicio"
        break


def test_config_vieja_carga_con_bloques_por_defecto(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path))
    (tmp_path / "dogfood.yaml").write_text("roles:\n  persona: [m]\n")
    cfg = Config.cargar(tmp_path)
    assert cfg.motores.persona == "api" and cfg.motores["juez"] == "api"
    assert (cfg.vista.host, cfg.vista.puerto) == ("127.0.0.1", 7460)
    assert (cfg.panel.host, cfg.panel.puerto) == ("127.0.0.1", 7470)
    assert cfg.driver.tipo == "web" and cfg.agente.max_capturas_por_paso == 1


def test_ejemplo_carga():
    cfg = Config.cargar(Path(__file__).parent.parent)
    assert cfg.claude_code.timeout_s == 180


def test_arbol_a_texto():
    texto = arbol_a_texto(
        [
            ElementoUI(
                id="com.app:id/entrar",
                texto="Entrar",
                clase="android.widget.Button",
                bounds=(0, 0, 100, 50),
                clicable=True,
            ),
            ElementoUI(
                id="e2",
                descripcion="Email",
                clase="android.widget.EditText",
                bounds=(10, 60, 30, 80),
                editable=True,
            ),
        ]
    )
    l1, l2 = texto.splitlines()
    assert "com.app:id/entrar" in l1 and "(50,25)" in l1 and "Button" in l1 and "clicable" in l1
    assert "e2" in l2 and "(20,70)" in l2 and "Email" in l2 and "editable" in l2
