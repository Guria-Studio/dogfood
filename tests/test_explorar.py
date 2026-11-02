"""`dogfood explorar` (F13.2.T1) contra la app HTML de prueba (4 pantallas, una con «Eliminar cuenta»),
con un LLM falso y un driver que habla HTTP de verdad con la app."""

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urljoin

import httpx
import pytest

from dogfood import proyectos
from dogfood.backends.base import UsoBackend
from dogfood.dominio import Escenario
from dogfood.drivers.base import ElementoUI, Observacion, ResultadoAccion
from dogfood.explorar import (
    SECRETO,
    DecisionEntrada,
    RespuestaMapa,
    destructivo,
    explorar,
)
from dogfood.objetivos.web import WebObjetivo

APP = Path(__file__).parent / "fixtures" / "app_web"
CLAVE = "clave-plantada-Xy9"


class _App(BaseHTTPRequestHandler):
    posts: list[tuple[str, dict]]

    def do_GET(self):
        ruta = APP / ("index.html" if self.path == "/" else f"{self.path.strip('/')}.html")
        self.send_response(200 if ruta.is_file() else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(ruta.read_bytes() if ruta.is_file() else b"no")

    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        self.server.posts.append((self.path, dict(parse_qsl(cuerpo))))
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def app():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _App)
    s.posts = []
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s, f"http://127.0.0.1:{s.server_port}/"
    s.shutdown()


class _Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.titulo, self.texto, self.elementos, self._en = "", [], [], None
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = a.get("action", "/")
        elif tag in ("a", "button", "input"):
            self.elementos.append({"tag": tag, "a": a, "texto": "", "form": self._form})
        if tag in ("title", "a", "button"):
            self._en = tag

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        if tag == self._en:
            self._en = None

    def handle_data(self, data):
        if self._en == "title":
            self.titulo += data
            return
        if self._en in ("a", "button"):
            self.elementos[-1]["texto"] += data.strip()
        if data.strip():
            self.texto.append(data.strip())


class DriverHttp:
    """`Driver` mínimo: links, botones de formulario e inputs, sobre HTTP real."""

    nombre = "web"

    def __init__(self, url: str):
        self.url, self.http = url, httpx.Client(follow_redirects=True)
        self.valores: dict[str, str] = {}
        self.toques: list[str] = []

        class _Pagina:
            async def title(_):
                return self.doc.titulo

        self.page = _Pagina()

    async def iniciar(self, carpeta):
        self.carpeta = Path(carpeta)
        (self.carpeta / "capturas").mkdir(parents=True, exist_ok=True)
        self._cargar(self.http.get(self.url))

    def _cargar(self, r):
        self.url = str(r.url)
        self.doc = _Html()
        self.doc.feed(r.text)
        self.valores = {}
        for i, e in enumerate(self.doc.elementos, 1):
            e["id"] = f"e{i}"

    async def observar(self, n):
        captura = self.carpeta / "capturas" / f"paso-{n:03d}.png"
        captura.write_bytes(b"\x89PNG falso")
        els = []
        for e in self.doc.elementos:
            entrada = e["tag"] == "input"
            els.append(
                ElementoUI(
                    id=e["id"],
                    # como DriverWeb: el texto de un input es su `value` (también si es password)
                    texto=self.valores.get(e["id"], "") if entrada else e["texto"],
                    descripcion=e["a"].get("placeholder", ""),
                    clase=e["tag"],
                    bounds=(0, 0, 10, 10),
                    clicable=not entrada,
                    editable=entrada,
                )
            )
        return Observacion(
            pantalla=self.url,
            elementos=els,
            texto_visible="\n".join(self.doc.texto),
            captura=captura,
            ts=datetime.now(),
        )

    async def actuar(self, a):
        e = next((x for x in self.doc.elementos if x["id"] == a.elemento), None)
        if a.tipo == "navegar":
            self._cargar(self.http.get(urljoin(self.url, a.texto)))
        elif a.tipo == "escribir" and e:
            self.valores[e["id"]] = a.texto or ""
        elif a.tipo == "tocar" and e:
            self.toques.append(e["texto"])
            if e["tag"] == "a":
                self._cargar(self.http.get(urljoin(self.url, e["a"]["href"])))
            elif e["tag"] == "button" and e["form"]:
                datos = {
                    x["a"].get("name"): self.valores.get(x["id"], "")
                    for x in self.doc.elementos
                    if x["tag"] == "input" and x["form"] == e["form"]
                }
                self._cargar(self.http.post(urljoin(self.url, e["form"]), data=datos))
        return ResultadoAccion(ok=True)

    async def frame(self):
        return None

    async def evidencia(self):
        return []

    async def cerrar(self):
        self.http.close()


PRD = f"""# Tienda
- Ver el catálogo de productos.
- Escribir al soporte desde Contacto.
- Exportar las compras a PDF.
Credencial de staging: {CLAVE}
"""

MAPA = {
    "funcionalidades": [
        {
            "nombre": "Catálogo",
            "casos": [
                {"id": "ver-catalogo", "nombre": "Ver productos", "pantallas": ["/productos"],
                 "estado": "visto"},
                # el LLM dice «visto» sin una pantalla real: el código lo corrige
                {"id": "exportar-pdf", "nombre": "Exportar compras a PDF",
                 "pantallas": ["/exportar"], "estado": "visto"},
            ],
        },
        {
            "nombre": "Soporte",
            "casos": [
                {"id": "contactar", "nombre": "Escribir al soporte", "pantallas": ["/contacto"],
                 "estado": "visto"},
            ],
        },
    ],
    "escenarios": [
        {"caso": "ver-catalogo", "id": "Ver catálogo", "titulo": "Ver el catálogo",
         "superficies": ["productos"], "objetivo": "Mira qué productos hay y sus precios",
         "criterio_exito": "Ves al menos dos productos con precio", "max_pasos": 20},
        {"caso": "contactar", "prioridad": "media", "id": "contactar-soporte",
         "titulo": "Escribir al soporte", "superficies": ["contacto"],
         "objetivo": "Manda un mensaje al soporte", "criterio_exito": "El mensaje se envía"},
        {"caso": "exportar-pdf", "id": "exportar", "titulo": "Exportar", "objetivo": "o",
         "criterio_exito": "c"},  # caso solo_prd: no da escenario
        {"caso": "contactar", "id": "malo", "titulo": "Malo", "objetivo": "o",
         "criterio_exito": "c", "max_pasos": 0},  # no valida contra Escenario
    ],
}  # fmt: skip


class LlmFalso:
    nombre, modelo = "api", "falso"

    def __init__(self, entrada=()):
        self.prompts: list[str] = []
        self.entrada = list(entrada)

    async def completar_json(self, prompt, esquema, *, imagenes=(), sesion=None):
        self.prompts.append(prompt)
        uso = UsoBackend(tokens_in=100, tokens_out=10, costo_usd=0.01)
        if esquema is DecisionEntrada:
            return DecisionEntrada.model_validate(self.entrada.pop(0)), uso, None
        assert esquema is RespuestaMapa
        return RespuestaMapa.model_validate(MAPA), uso, None


def _proyecto(tmp_path, url, **kw):
    return proyectos.crear(
        {"slug": "tienda", "nombre": "Tienda", "objetivo": "web", "url": url,
         "acceso": {"modo": "sin_login"}, "prd": PRD} | kw,
        tmp_path,
    )  # fmt: skip


async def test_recorre_las_4_pantallas_sin_eliminar_la_cuenta(tmp_path, app):
    servidor, url = app
    driver, llm = DriverHttp(url), LlmFalso()
    r = await explorar(_proyecto(tmp_path, url), raiz=tmp_path, driver=driver, backend=llm)
    assert {p["path"] for p in r["pantallas"]} == {"/", "/productos", "/perfil", "/contacto"}
    perfil = next(p for p in r["pantallas"] if p["path"] == "/perfil")
    assert perfil["titulo"] == "Perfil" and "Eliminar cuenta" in perfil["acciones"]
    assert Path(perfil["captura"]).is_file()
    assert "Eliminar cuenta" not in driver.toques
    assert all(path != "/eliminar-cuenta" for path, _ in servidor.posts)
    carpeta = tmp_path / r["id"]
    assert r["id"].startswith("exploracion-tienda-") and (carpeta / "mapa.json").is_file()
    assert json.loads((carpeta / "mapa.json").read_text())["costo_usd"] == pytest.approx(0.01)


def test_destructivo():
    def el(t):
        return ElementoUI(id="e", texto=t, bounds=(0, 0, 1, 1), clicable=True)

    for t in ("Eliminar cuenta", "Borrar", "Pagar ahora", "Cancelar cuenta", "Delete", "Salir"):
        assert destructivo(el(t)), t
    for t in ("Productos", "Enviar", "Cancelar", "Guardar"):
        assert not destructivo(el(t)), t


async def test_mapa_solo_prd_y_borradores_validos(tmp_path, app):
    _, url = app
    p = _proyecto(tmp_path, url)
    r = await explorar(p, raiz=tmp_path, driver=DriverHttp(url), backend=LlmFalso())
    casos = {c["id"]: c for f in r["funcionalidades"] for c in f["casos"]}
    assert (
        casos["exportar-pdf"]["estado"] == "solo_prd" and casos["exportar-pdf"]["pantallas"] == []
    )
    assert casos["ver-catalogo"]["estado"] == "visto"

    with closing(sqlite3.connect(tmp_path / "dogfood.db")) as con:
        filas = con.execute(
            "SELECT id, estado, prioridad, datos FROM escenarios_proyecto WHERE proyecto = 'tienda'"
        ).fetchall()
        assert con.execute("SELECT costo_usd FROM exploraciones").fetchone()[0] > 0
    assert {f[0] for f in filas} == {"ver-catalogo", "contactar-soporte"}
    assert {f[1] for f in filas} == {"borrador"}
    for _, _, _, datos in filas:
        Escenario.model_validate(json.loads(datos))
    assert WebObjetivo.desde_proyecto(p, raiz=tmp_path).escenarios()[0].id == "exploracion-libre"


async def test_reexplorar_no_pisa_lo_aceptado(tmp_path, app):
    _, url = app
    p = _proyecto(tmp_path, url)
    await explorar(p, raiz=tmp_path, driver=DriverHttp(url), backend=LlmFalso())
    with closing(sqlite3.connect(tmp_path / "dogfood.db")) as con, con:
        con.execute("UPDATE escenarios_proyecto SET estado = 'aceptado' WHERE id = 'ver-catalogo'")
    await explorar(p, raiz=tmp_path, driver=DriverHttp(url), backend=LlmFalso())
    assert [e.id for e in WebObjetivo.desde_proyecto(p, raiz=tmp_path).escenarios()] == [
        "ver-catalogo"
    ]


async def test_secreto_plantado_no_llega_al_prompt(tmp_path, app, monkeypatch):
    servidor, url = app
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg" / "secretos").mkdir(parents=True)
    (tmp_path / "cfg" / "secretos" / "tienda.env").write_text(f"DOGFOOD_PASSWORD={CLAVE}\n")
    p = _proyecto(
        tmp_path, url, acceso={"modo": "usuario_prueba", "usuario": "qa@dogfood.example.com"}
    )
    llm = LlmFalso(
        entrada=[
            {"accion": {"tipo": "escribir", "elemento": "e4", "texto": "qa@dogfood.example.com"}},
            {"accion": {"tipo": "escribir", "elemento": "e5", "texto": SECRETO}},
            {"accion": {"tipo": "tocar", "elemento": "e6"}},
            {"terminado": True},
        ]
    )
    driver = DriverHttp(url)
    r = await explorar(p, raiz=tmp_path, driver=driver, backend=llm)
    # la contraseña real llegó a la app…
    assert ("/entrar", {"email": "qa@dogfood.example.com", "clave": CLAVE}) in servidor.posts
    # …pero ni al LLM (aunque el input la mostró en el árbol y el PRD la traía) ni al mapa
    assert len(llm.prompts) == 5 and SECRETO in llm.prompts[0]
    assert not any(CLAVE in pr for pr in llm.prompts)
    assert CLAVE not in (tmp_path / r["id"] / "mapa.json").read_text()


async def test_host_prohibido_frena_antes_de_abrir(tmp_path):
    p = _proyecto(tmp_path, "https://app.prod.example/", hosts_prohibidos=["prod.example"])
    driver = DriverHttp("https://app.prod.example/")
    with pytest.raises(proyectos.ErrorProyecto, match="hosts_prohibidos"):
        await explorar(p, raiz=tmp_path, driver=driver, backend=LlmFalso())
    assert not hasattr(driver, "doc")
