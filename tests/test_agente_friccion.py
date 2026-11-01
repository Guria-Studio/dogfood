"""Fricción automática y robustez de `al_terminar_paso` (on_step_end de browser-use)."""

from test_agente_navegador import LlmFalso, _dataset, _escenario, _indice, _persona
from test_bucle import ELEMENTOS, DriverFalso, correr, decision

from dogfood.agente.navegador import ejecutar as ejecutar_navegador
from dogfood.agente.navegador import friccion_automatica
from dogfood.drivers.base import Accion

TOCAR = Accion(tipo="tocar", elemento="entrar")


async def test_misma_accion_tres_veces_anota_friccion_con_captura(tmp_path):
    decisiones = [decision(TOCAR) for _ in range(3)] + [decision(None, terminado=True)]
    e, *_ = await correr(tmp_path, decisiones)
    (f,) = [x for x in e.fricciones if "misma acción" in x.texto]
    assert f.captura and f.captura.exists()
    assert len(e.fricciones) == 1  # una sola por racha


async def test_acciones_distintas_no_anotan_nada(tmp_path):
    otras = [Accion(tipo="tocar", elemento=i) for i in ("email", "clave", "entrar")]
    e, *_ = await correr(tmp_path, [decision(a) for a in otras] + [decision(None, terminado=True)])
    assert e.fricciones == []


async def test_error_visible_anota_friccion(tmp_path):
    class ConError(DriverFalso):
        async def observar(self, n):
            o = await super().observar(n)
            return o.model_copy(update={"texto_visible": "Ocurrió un error al guardar"})

    e, *_ = await correr(
        tmp_path,
        [decision(TOCAR), decision(None, terminado=True)],
        driver=ConError(elementos=ELEMENTOS),
    )
    assert any("error en pantalla" in f.texto for f in e.fricciones)


def test_racha_y_error_sin_repetir():
    vistos: set[str] = set()
    a = "{x}"
    assert friccion_automatica(a, "", [a, a], vistos) == []
    assert len(friccion_automatica(a, "", [a, a, a], vistos)) == 1
    assert friccion_automatica(a, "", [a, a, a, a], vistos) == []
    assert friccion_automatica("", "Error 500", [], vistos)
    assert friccion_automatica("", "Error 500", [], vistos) == []


async def test_al_terminar_paso_sobrevive_sin_pagina(tmp_path, monkeypatch):
    """Si no hay pestaña activa, el hook anota el paso sin captura en vez de abortar la corrida."""
    from browser_use import BrowserSession

    async def sin_pagina(self):
        raise RuntimeError("no hay pestaña activa")

    monkeypatch.setattr(BrowserSession, "get_current_page_url", sin_pagina)
    import threading
    from http.server import ThreadingHTTPServer

    from test_agente_navegador import _Manejador

    from dogfood.dominio import Instancia

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/"
    try:
        guion = [
            lambda m: [{"click": {"index": _indice(m, "entrar")}}],
            lambda m: [{"done": {"text": "Listo", "success": True}}],
        ]

        async def juez(prompt, esquema):
            return esquema(exito=True, motivo="ok")

        e = await ejecutar_navegador(
            _persona(),
            _escenario(),
            Instancia(base_url=url, api_url=url, proyecto_compose="p", commit="c"),
            _dataset(tmp_path),
            tmp_path / "e1",
            LlmFalso(guion),
            juez,
        )
    finally:
        srv.shutdown()
    assert e.pasos and not any("error del agente" in n for n in e.notas)
