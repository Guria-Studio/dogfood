"""Agente navegador contra una página local, con un LLM falso que sigue un guion."""

import asyncio
import json
import re
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

from dogfood.agente.navegador import ejecutar
from dogfood.config import Config
from dogfood.dominio import (
    DatasetSintetico,
    Escenario,
    EventoConsola,
    EventoRed,
    Idioma,
    Instancia,
    Intencion,
    Paso,
    Persona,
)
from dogfood.llm import ContadorUso

PAGINA = Path(__file__).parent / "fixtures" / "pagina_prueba"
CLAVE = "Clave-Secreta-123"


class _Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(PAGINA), **kw)

    def do_GET(self):
        if self.path == "/api/falla":
            self.send_response(500)
            self.end_headers()
        elif self.path == "/descarga.csv":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", "attachment; filename=ventas.csv")
            self.end_headers()
            self.wfile.write(b"cliente,producto\n1,2\n")
        else:
            super().do_GET()

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def instancia():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/"
    yield Instancia(base_url=url, api_url=url, proyecto_compose="prueba", commit="abc")
    srv.shutdown()


def _indice(mensajes, id_html: str) -> int:
    """Índice de browser-use del elemento con ese id, según el último estado del DOM."""
    texto = "\n".join(m.text for m in mensajes)
    return int(re.findall(rf"\[(\d+)\]<\w+ id={id_html}\b", texto)[-1])


class LlmFalso:
    """Cumple el protocolo `BaseChatModel` de browser-use y devuelve acciones guionadas."""

    model = provider = name = "falso/guion"
    _verified_api_keys = True

    def __init__(self, guion):
        self.guion, self.i = guion, 0

    async def ainvoke(self, messages, output_format=None, **kw):
        acciones = self.guion[min(self.i, len(self.guion) - 1)](messages)
        self.i += 1
        salida = output_format.model_validate(
            {"evaluation_previous_goal": "", "memory": "", "next_goal": "", "action": acciones}
        )
        uso = ChatInvokeUsage(
            prompt_tokens=100,
            completion_tokens=10,
            total_tokens=110,
            prompt_cached_tokens=None,
            prompt_cache_creation_tokens=None,
            prompt_image_tokens=None,
        )
        return ChatInvokeCompletion(completion=salida, usage=uso)


def _persona() -> Persona:
    return Persona(
        id="p1",
        nombre="Ana Prueba",
        email="ana@dogfood.test",
        contrasena=CLAVE,
        empresa="Farmacia Ana",
        rubro="farmacia",
        idioma=Idioma.es,
        destreza=2,
        paciencia=3,
        intencion=Intencion.solo_exportar,
        semilla=1,
    )


def _escenario(max_pasos: int = 20) -> Escenario:
    return Escenario(
        id="registro-y-descarga",
        titulo="Registro y descarga",
        objetivo="Regístrate y descarga el CSV.",
        criterio_exito="Se ve «Registro completo» y se descargó ventas.csv.",
        max_pasos=max_pasos,
    )


def _dataset(tmp: Path) -> DatasetSintetico:
    csv = tmp / "ventas.csv"
    csv.write_text("cliente,producto\n")
    return DatasetSintetico(
        id="d1",
        perfil="farmacia",
        ruta_csv=csv,
        ruta_verdad=tmp / "verdad.json",
        n_clientes=1,
        n_filas=1,
        semilla=1,
    )


def _leer(carpeta: Path, nombre: str, modelo):
    return [modelo.model_validate_json(x) for x in (carpeta / nombre).read_text().splitlines()]


@pytest.fixture(scope="module")
def recorrido(instancia, tmp_path_factory):
    """Un solo recorrido completo que alimenta los cinco primeros tests."""
    carpeta = tmp_path_factory.mktemp("ejec") / "e1"
    guion = [
        lambda m: [
            {"input": {"index": _indice(m, "email"), "text": "ana@dogfood.test"}},
            {"input": {"index": _indice(m, "clave"), "text": CLAVE}},
        ],
        lambda m: [{"click": {"index": _indice(m, "entrar")}}],
        lambda m: [{"click": {"index": _indice(m, "descargar")}}],
        lambda m: [{"click": {"index": _indice(m, "romper")}}],
        lambda m: [{"click": {"index": _indice(m, "externo")}}],
        lambda m: [
            {
                "anotar_friccion": {
                    "texto": "No sé qué hace «Analizar»",
                    "severidad": "media",
                    "cita": "Analizar",
                }
            }
        ],
        lambda m: [{"done": {"text": "Listo", "success": True}}],
    ]
    prompts_juez: list[str] = []

    async def juez(prompt, esquema):
        prompts_juez.append(prompt)
        ok = "Registro completo" in prompt and "ventas.csv" in prompt
        return esquema(exito=ok, motivo="se registró y descargó" if ok else "falta evidencia")

    contador = ContadorUso(Config(roles={"persona": ["falso/guion"]}))
    e = asyncio.run(
        ejecutar(
            _persona(),
            _escenario(),
            instancia,
            _dataset(carpeta.parent),
            carpeta,
            LlmFalso(guion),
            juez,
            contador=contador,
        )
    )
    return e, carpeta, prompts_juez, contador


def test_formulario_y_descarga_terminan_con_exito(recorrido):
    e, carpeta, prompts_juez, contador = recorrido
    assert e.estado == "ok" and e.exito, e.motivo_juez
    assert [d.name for d in e.descargas] == ["ventas.csv"]
    assert (carpeta / "descargas" / "ventas.csv").read_text().startswith("cliente,producto")
    assert (carpeta / "historial.json").exists()
    pasos = _leer(carpeta, "pasos.jsonl", Paso)
    assert pasos and all(p.captura and p.captura.exists() for p in pasos)
    assert any("Registro completo" in p.texto_visible for p in pasos)
    assert len(prompts_juez) == 1
    assert contador.usos and contador.usos[0].rol == "persona" and contador.usos[0].tokens_in > 0
    # La contraseña nunca sale en los logs de dogfood.
    for nombre in ("pasos.jsonl", "red.jsonl", "consola.jsonl"):
        assert CLAVE not in (carpeta / nombre).read_text()
    assert CLAVE not in e.model_dump_json()


def test_respuesta_500_queda_en_red(recorrido):
    _, carpeta, _, _ = recorrido
    red = _leer(carpeta, "red.jsonl", EventoRed)
    assert any(r.estado == 500 and r.url.endswith("/api/falla") and r.metodo == "GET" for r in red)


def test_console_error_queda_en_consola(recorrido):
    _, carpeta, _, _ = recorrido
    consola = _leer(carpeta, "consola.jsonl", EventoConsola)
    assert any(c.nivel == "error" and "falla de prueba en consola" in c.texto for c in consola)


def test_origen_no_permitido_queda_bloqueado(recorrido):
    e, carpeta, _, _ = recorrido
    red = _leer(carpeta, "red.jsonl", EventoRed)
    assert any(r.estado == 0 and "externo.invalid" in r.url for r in red)
    assert not any("externo.invalid" in p.url for p in e.pasos)


def test_anotar_friccion_guarda_captura(recorrido):
    e, _, _, _ = recorrido
    (f,) = [x for x in e.fricciones if x.cita]  # las automáticas no llevan cita
    assert f.texto == "No sé qué hace «Analizar»" and f.severidad == "media"
    assert f.cita == "Analizar" and f.pantalla == "/"
    assert f.captura and f.captura.exists()


async def test_max_pasos_termina_en_fallo(instancia, tmp_path):
    async def juez(prompt, esquema):
        raise AssertionError("no se juzga una ejecución cortada")

    e = await ejecutar(
        _persona(),
        _escenario(max_pasos=2),
        instancia,
        None,
        tmp_path / "e2",
        LlmFalso([lambda m: [{"wait": {"seconds": 0}}]]),
        juez,
    )
    assert (e.estado, e.motivo_juez, e.exito) == ("fallo", "max_pasos", False)
    assert isinstance(e.pasos[0].ts, datetime)
    assert json.loads(e.pasos[0].accion) == [{"wait": {"seconds": 0}}]
