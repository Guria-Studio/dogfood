"""Integración M7 (F7.9.T1): panel y vista en un Chromium real.

uv run pytest -m integracion tests/integracion/test_panel_vista.py -v
"""

import asyncio
import base64
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

from dogfood.almacen import Almacen
from dogfood.config import Config, Motores
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Corrida, Ejecucion, Escenario, Instancia, Paso, Persona
from dogfood.eventos import BusVivo, EventoVivo
from dogfood.vista.servidor import iniciar_vista

pytestmark = pytest.mark.integracion

PERSONA = Persona(
    id="p1", nombre="Ana", email="ana@correo-real.com", contrasena="hunter2-pw",
    empresa="Farmacia Luna", rubro="farmacia", idioma="es", destreza=3, paciencia=3,
    intencion="explorar", semilla=1,
)  # fmt: skip
YAML = "roles: {persona: [m], juez: [m], dedupe: [m], redactor: [m]}\nrepo_issues: yo/dogfood\n"
ISSUE_URL = "https://github.com/yo/dogfood/issues/77"
# gh falso: `issue list` no encuentra nada, `issue create` imprime la URL.
GH_FALSO = f"""#!{sys.executable}
import sys
a = sys.argv[1:]
if a[:2] == ["issue", "list"]:
    print("[]")
elif a[:2] == ["issue", "create"]:
    print("{ISSUE_URL}")
"""


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _esperar(url: str, timeout: float = 20) -> None:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(url)


def _png(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (64, 40), color).save(b, "PNG")
    return b.getvalue()


def _jpeg_b64(color: tuple[int, int, int]) -> str:
    b = io.BytesIO()
    Image.new("RGB", (320, 200), color).save(b, "JPEG")
    return base64.b64encode(b.getvalue()).decode()


def _video(navegador, destino: Path) -> None:
    """Un webm real: lo graba el propio Chromium (el ffmpeg de Playwright no trae lavfi)."""
    ctx = navegador.new_context(record_video_dir=destino.parent / "grabacion")
    pag = ctx.new_page()
    pag.set_content("<body style='background:#36c'><h1>video de prueba</h1>")
    pag.wait_for_timeout(800)
    ruta = Path(pag.video.path())
    ctx.close()
    shutil.move(ruta, destino)


@pytest.fixture
def navegador():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"no hay Chromium de Playwright: {e}")
        yield b
        b.close()


def _guardar(a: Almacen, eid: str, driver: str, resultado: str, video: Path) -> None:
    d = a.dir_ejecucion("c1", eid)
    pasos = []
    for n, color in enumerate([(200, 30, 30), (30, 200, 30), (30, 30, 200)], 1):
        cap = d / "capturas" / f"{n}.png"
        cap.parent.mkdir(parents=True, exist_ok=True)
        cap.write_bytes(_png(color))
        pasos.append(
            Paso(n=n, url="http://app/login", pantalla="/login", accion=f"clic {n}", captura=cap,
                 ts=datetime(2026, 1, 1), razonamiento=f"porque {n}", esperado=f"ver {n}",
                 observado=f"visto {n}")
        )  # fmt: skip
    v = d / "video" / video.name
    v.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(video, v)
    e = Ejecucion(
        id=eid, persona_id="p1", escenario_id="login", modelo="m", estado="ok", driver=driver,
        motor="bucle", backend="claude_code" if driver == "android" else "api",
        exito=resultado == "aprobado", resultado=resultado, pasos=pasos, video=v,
        motivo_juez="de prueba",
    )  # fmt: skip
    a.guardar_ejecucion("c1", e)
    (d / "pasos.jsonl").write_text("\n".join(p.model_dump_json() for p in pasos) + "\n")


def _panel(raiz: Path, tmp: Path):
    """`dogfood panel` real en un puerto libre; cwd con su dogfood.yaml y `gh` falso en el PATH."""
    (tmp / "dogfood.yaml").write_text(YAML)
    bin_ = tmp / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "gh").write_text(GH_FALSO)
    (bin_ / "gh").chmod(0o755)
    puerto = _puerto_libre()
    env = os.environ | {
        "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}",
        "DOGFOOD_CONFIG_DIR": str(tmp / "cfg"),
    }
    proc = subprocess.Popen(
        [str(Path(sys.executable).with_name("dogfood")), "panel", "--host", "127.0.0.1",
         "--puerto", str(puerto), "--raiz", str(raiz)],
        cwd=tmp, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )  # fmt: skip
    try:
        _esperar(f"http://127.0.0.1:{puerto}/")
    except TimeoutError:
        proc.kill()
        pytest.fail(f"el panel no arrancó: {proc.stderr.read().decode()}")
    return proc, f"http://127.0.0.1:{puerto}"


def test_panel_filtra_detalle_pasos_video_e_issue(navegador, tmp_path):
    raiz = tmp_path / "runs"
    a = Almacen(raiz)
    a.nueva_corrida(
        Corrida(id="c1", objetivo="predicts", ref="main", commit="abc1234", semilla=7,
                inicio=datetime(2026, 1, 1), estado="completa")
    )  # fmt: skip
    a.guardar_personas("c1", [PERSONA])
    video = tmp_path / "v.webm"
    _video(navegador, video)
    _guardar(a, "web-ok", "web", "aprobado", video)
    _guardar(a, "web-fallo", "web", "fallo", video)
    _guardar(a, "and-fallo", "android", "fallo", video)

    proc, base = _panel(raiz, tmp_path)
    try:
        pag = navegador.new_page()
        pag.goto(base + "/")
        assert pag.locator("tbody tr").count() == 3
        pag.select_option("select[name=resultado]", "fallo")
        pag.click("text=Filtrar")
        assert pag.locator("tbody tr").count() == 2
        assert "resultado=fallo" in pag.url
        assert "web-ok" not in pag.content()

        pag.locator("a:text('detalle')").first.click()
        assert "/ejecuciones/" in pag.url
        pasos = pag.locator(".paso")
        assert pasos.count() == 3
        visibles = lambda: [i for i in range(3) if pasos.nth(i).is_visible()]
        assert visibles() == [0]
        pag.keyboard.press("ArrowRight")
        pag.keyboard.press("ArrowRight")
        assert visibles() == [2]
        pag.keyboard.press("ArrowLeft")
        assert visibles() == [1]
        assert "porque 2" in pasos.nth(1).inner_text()
        assert pasos.nth(1).locator("img").evaluate("i => i.complete && i.naturalWidth > 0")

        video_el = pag.locator("video")
        pag.wait_for_function(
            "() => document.querySelector('video').videoWidth > 0"
        )  # metadatos cargados
        assert video_el.evaluate("v => v.error === null")

        pag.click("button:text('Crear issue')")
        pag.wait_for_selector(f"#issue-resultado a[href='{ISSUE_URL}']")
        assert ISSUE_URL in pag.locator("#issue-resultado").inner_text()
    finally:
        proc.terminate()
        proc.wait(10)


def test_vista_tres_ejecuciones_frames_razonamiento_latencia(navegador):
    puerto = _puerto_libre()
    listo, parar = threading.Event(), threading.Event()
    colores = {"e1": (220, 40, 40), "e2": (40, 220, 40), "e3": (40, 40, 220)}

    async def servidor():  # servidor y publicador en el mismo loop (BusVivo)
        bus = BusVivo()
        tarea = await iniciar_vista(bus, "127.0.0.1", puerto)
        for e in colores:
            bus.publicar(EventoVivo(corrida_id="c", ejecucion_id=e, tipo="inicio", persona=e,
                                    escenario="login"))  # fmt: skip
        listo.set()
        n = 0
        while not parar.is_set():
            n += 1
            for e, color in colores.items():
                if n % 5 == 1:  # un paso cada ~1 s, un frame cada 200 ms
                    bus.publicar(EventoVivo(
                        corrida_id="c", ejecucion_id=e, tipo="paso", n_paso=n // 5 + 1,
                        paso_contrato="abrir", accion="clic", razonamiento=f"razón {e} #{n // 5 + 1}",
                        punto=(100, 80),
                    ))  # fmt: skip
                bus.publicar(EventoVivo(corrida_id="c", ejecucion_id=e, tipo="frame",
                                        frame_jpeg_b64=_jpeg_b64(color)))  # fmt: skip
            await asyncio.sleep(0.2)
        tarea.cancel()

    hilo = threading.Thread(target=lambda: asyncio.run(servidor()), daemon=True)
    hilo.start()
    assert listo.wait(15)
    try:
        _esperar(f"http://127.0.0.1:{puerto}/")
        pag = navegador.new_page()
        pag.goto(f"http://127.0.0.1:{puerto}/")
        tarjetas = pag.locator(".tarjeta")
        pag.wait_for_function("() => document.querySelectorAll('.tarjeta').length === 3")
        # los tres canvas dibujan algo que no es negro
        pag.wait_for_function(
            """() => [...document.querySelectorAll('canvas')].filter(c => {
              const d = c.getContext('2d').getImageData(c.width/2, c.height/2, 1, 1).data;
              return d[0] + d[1] + d[2] > 60; }).length === 3"""
        )
        # el razonamiento cambia con cada paso
        lista = tarjetas.first.locator(".razonamiento li")
        pag.wait_for_function("() => document.querySelector('.razonamiento li:nth-child(2)')")
        primero = lista.first.inner_text()
        pag.wait_for_function(
            "t => document.querySelector('.razonamiento li').textContent !== t", arg=primero
        )
        assert lista.first.inner_text() != primero
        # latencia mostrada < 1 s en las tres
        time.sleep(1.2)  # deja que el rótulo (cada 500 ms) se actualice
        latencias = [
            int(re.search(r"(\d+) ms", tarjetas.nth(i).locator(".latencia").inner_text()).group(1))
            for i in range(3)
        ]
        print("LATENCIAS_MS:", latencias)
        assert all(ms < 1000 for ms in latencias), latencias
    finally:
        parar.set()
        hilo.join(10)


# --- 3. dogfood run --motor bucle con motores.persona: claude_code ---------------------------

LOGIN = """<!doctype html><meta charset=utf-8><title>Login de prueba</title>
<h1>Acceso</h1>
<form id=f>
  <label>Email <input id=email type=email placeholder="Email"></label>
  <label>Contraseña <input id=pw type=password placeholder="Contraseña"></label>
  <button type=submit>Iniciar sesión</button>
</form>
<p id=ok hidden>Bienvenido, sesión iniciada. <a href="#">Mi cuenta</a></p>
<script>
document.getElementById('f').onsubmit = e => {
  e.preventDefault();
  if (!email.value || !pw.value) return;
  f.hidden = true; ok.hidden = false;
};
</script>
"""


def _hay_sesion_claude() -> str | None:
    """None si hay sesión; si no, el motivo para saltar."""
    if not shutil.which("claude"):
        return "no hay `claude` en el PATH"
    try:
        r = subprocess.run(
            ["claude", "-p", "di ok", "--output-format", "json"],
            check=False, capture_output=True, text=True, timeout=120, cwd="/tmp",
        )  # fmt: skip
        datos = json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        return f"`claude -p` no responde: {e}"
    return (
        None if not datos.get("is_error") else f"sin sesión de Claude Code: {datos.get('result')}"
    )


class _ObjetivoLogin:
    nombre = "login-prueba"

    def __init__(self, url: str):
        self.url = url

    def preparar(self, ref, corrida):
        return Instancia(base_url=self.url, api_url="", proyecto_compose="", commit="local")

    def destruir(self, instancia):
        pass

    def url_permitida(self, url, instancia):
        return url.startswith("file://") or url == "about:blank"

    def escenarios(self):
        return [Escenario(
            id="login", titulo="Iniciar sesión", driver="web", max_pasos=8,
            objetivo="Entra con tu email y tu contraseña en el formulario y pulsa «Iniciar sesión».",
            criterio_exito="Se ve «Bienvenido, sesión iniciada» y ya no se ve el formulario.",
        )]  # fmt: skip

    def pantalla(self, url):
        return "login"

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


def test_run_bucle_con_claude_code_se_ve_en_el_panel(tmp_path):
    motivo = _hay_sesion_claude()
    if motivo:
        pytest.skip(motivo)
    pagina = tmp_path / "login.html"
    pagina.write_text(LOGIN)
    cfg = Config(
        roles={"persona": ["m"], "juez": ["m"], "dedupe": ["m"], "redactor": ["m"]},
        repo_issues="yo/dogfood",
        motores=Motores(persona="claude_code", juez="claude_code", dedupe="claude_code",
                        redactor="claude_code"),
    )  # fmt: skip
    raiz = tmp_path / "runs"
    corrida = asyncio.run(
        correr(
            Opciones(
                objetivo_obj=_ObjetivoLogin(pagina.as_uri()),
                cfg=cfg,
                raiz=raiz,
                motor="bucle",
                personas=1,
                semilla=1,
                sin_publicar=True,
                concurrencia=1,
                memoria_gb=lambda: 99.0,
                espera_vista_s=0,
            )
        )
    )
    [fila] = [e for c in [Almacen(raiz)] for e in _ejecuciones(c, corrida.id)]
    assert fila.backend == "claude_code", fila
    assert fila.motor == "bucle"
    print("RESULTADO_RUN:", corrida.estado, fila.resultado, fila.exito, fila.motivo_juez)

    proc, base = _panel(raiz, tmp_path)
    try:
        with sync_playwright() as p:  # después de `correr`: sync_playwright deja un loop vivo
            pag = p.chromium.launch().new_page()
            pag.goto(base + "/")
            fila_html = pag.locator("tbody tr").first.inner_text()
            assert "claude_code" in fila_html and "bucle" in fila_html
            pag.locator("a:text('detalle')").first.click()
            assert "claude_code" in pag.content()
    finally:
        proc.terminate()
        proc.wait(10)


def _ejecuciones(almacen: Almacen, corrida_id: str) -> list[Ejecucion]:
    base = almacen.dir_corrida(corrida_id) / "ejecuciones"
    return [almacen.ejecucion(d.name) for d in sorted(base.iterdir()) if d.is_dir()]
