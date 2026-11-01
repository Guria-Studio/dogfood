import json
from pathlib import Path

import pytest

from dogfood.config import Nodo
from dogfood.deterministico import ResultadoDeterministico, ResultadoTest
from dogfood.dominio import Escenario, Idioma, Intencion, Persona
from dogfood.nodos.cliente import ClienteNodo, ErrorNodo, a_ejecucion_ios
from dogfood.nodos.protocolo import EstadoNodo, ResultadoTrabajo, Trabajo

NODO = Nodo(host="100.101.102.103", usuario="hector")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-p", "22"]


class Fake:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    async def __call__(self, args, *, entrada=None, timeout_s=60):
        self.llamadas.append((list(args), entrada, timeout_s))
        return self.respuestas.pop(0)


def _res(id="t1", **kw) -> str:
    return ResultadoTrabajo(id=id, estado="ok", **kw).model_dump_json()


async def test_estado():
    estado = EstadoNodo(
        xcode="16.0", appium=True, dispositivos=[{"udid": "U", "nombre": "i", "os": "18"}]
    )
    f = Fake((0, estado.model_dump_json().encode(), b""))
    r = await ClienteNodo("mac", NODO, f).estado()
    assert f.llamadas[0][0] == [
        *SSH,
        "hector@100.101.102.103",
        "dogfood",
        "nodo",
        "estado",
        "--json",
    ]
    assert r == estado


async def test_enviar_stdin_logs_y_rsync(tmp_path):
    t = Trabajo(id="t1", tipo="patrol", dart_defines={"CLAVE": "S3cr3t"}, timeout_s=100)
    out = b"compilando...\nlog\n" + _res().encode() + b"\n\n"
    f = Fake((0, out, b""), (0, b"", b""))
    r = await ClienteNodo("mac", NODO, f).enviar(t, tmp_path / "c")
    assert r.id == "t1"
    (ssh, entrada, lim), (rsync, _, _) = f.llamadas
    assert ssh[-2:] == ["nodo", "ejecutar"] and lim == 160
    assert json.loads(entrada)["dart_defines"] == {"CLAVE": "S3cr3t"}
    assert all("S3cr3t" not in a for llamada in f.llamadas for a in llamada[0])
    assert rsync[:2] == ["rsync", "-a"]
    assert rsync[-2:] == ["hector@100.101.102.103:~/dogfood-nodo/t1/", f"{tmp_path / 'c'}/"]
    assert "ssh -p 22 -o BatchMode=yes" in rsync


@pytest.mark.parametrize(
    "codigo,err,esperado",
    [
        (255, b"hector@x: Permission denied (publickey).", "configura la clave SSH y Tailscale"),
        (255, b"ssh: connect to host x port 22: Connection timed out", "ios-nodo-mac.md"),
        (127, b"zsh: command not found: dogfood", "instala dogfood en el Mac"),
    ],
)
async def test_errores_accionables(tmp_path, codigo, err, esperado):
    f = Fake((codigo, b"", err))
    with pytest.raises(ErrorNodo, match=esperado):
        await ClienteNodo("mac", NODO, f).enviar(Trabajo(id="t", tipo="estado"), tmp_path)


async def test_stdout_sin_json_y_timeout(tmp_path):
    f = Fake((1, b"basura\n", b"l1\nl2\nboom\n"))
    with pytest.raises(ErrorNodo, match="boom"):
        await ClienteNodo("mac", NODO, f).enviar(Trabajo(id="t", tipo="estado"), tmp_path)

    async def lento(args, *, entrada=None, timeout_s=60):
        raise TimeoutError

    with pytest.raises(ErrorNodo, match="no respondió"):
        await ClienteNodo("mac", NODO, lento).enviar(Trabajo(id="t", tipo="estado"), tmp_path)


def test_validacion_al_construir():
    with pytest.raises(ValueError):
        ClienteNodo("mac", Nodo.model_construct(host="192.168.0.20", usuario="hector"))
    with pytest.raises(ValueError):
        ClienteNodo("mac", Nodo.model_construct(host="127.0.0.1", usuario="root;rm"))


class Proc:
    returncode = None

    def terminate(self):
        self.returncode = -15

    async def wait(self):
        return self.returncode


async def test_tunel():
    lanzados = []

    async def lanzador(args):
        lanzados.append(list(args))
        return proc

    proc = Proc()
    t = await ClienteNodo("mac", NODO, Fake(), lanzador).tunel([4723, 9100])
    a = lanzados[0]
    assert a[:7] == SSH
    assert "-N" in a and "ExitOnForwardFailure=yes" in a
    assert a.count("-L") == 2
    assert "127.0.0.1:4723:127.0.0.1:4723" in a and "127.0.0.1:9100:127.0.0.1:9100" in a
    await t.cerrar()
    assert proc.returncode == -15


def _persona() -> Persona:
    return Persona(
        id="p1", nombre="Ana", email="a@b.test", contrasena="x", empresa="E", rubro="r",
        idioma=Idioma.es, destreza=2, paciencia=3, intencion=Intencion.solo_exportar, semilla=1,
    )  # fmt: skip


def _esc() -> Escenario:
    return Escenario(id="login", titulo="L", objetivo="o", criterio_exito="c", driver="ios")


def test_a_ejecucion_ios(tmp_path):
    det = ResultadoDeterministico(
        herramienta="patrol",
        codigo_salida=0,
        tests=[ResultadoTest(nombre="a", estado="ok")],
        log=Path("salida.log"),
        captura_final=Path("c.png"),
    )
    r = ResultadoTrabajo(id="t1", estado="ok", deterministico=det)
    e = a_ejecucion_ios(r, _persona(), _esc(), "e1", tmp_path)
    assert e.resultado == "aprobado" and e.driver == "ios"
    assert e.evidencia_driver[0].ruta == tmp_path / "salida.log"
    assert e.pasos[-1].captura == tmp_path / "c.png"


def test_a_ejecucion_ios_error(tmp_path):
    r = ResultadoTrabajo(id="t1", estado="error", mensaje="sin Xcode")
    e = a_ejecucion_ios(r, _persona(), _esc(), "e1", tmp_path)
    assert e.estado == "error" and "sin Xcode" in e.motivo_juez
