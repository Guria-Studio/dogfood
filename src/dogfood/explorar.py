"""Exploración de una app `web` (F13.2.T1): recorrido en anchura, mapa de funcionalidades y
escenarios propuestos como borradores del proyecto.

1. `entrar`: el agente (rol `explorador`, sonnet por defecto) entra según `acceso.modo`. La
   contraseña viaja como `<secret>DOGFOOD_PASSWORD</secret>` y se sustituye recién al escribir.
2. `recorrer`: anchura sobre el `Driver`, tocando cada elemento clicable no destructivo.
3. `armar_mapa`: un LLM cruza las pantallas con el PRD; el código corrige lo que no cuadra.

Todo texto de la app o del PRD pasa por `redactar` antes de ir al prompt.
"""

import json
import re
import secrets
import unicodedata
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from dogfood.almacen import Almacen
from dogfood.backends.base import BackendLlm
from dogfood.config import Config
from dogfood.dominio import CompatibilidadPersona, Escenario, Instancia, Persona
from dogfood.drivers.base import Accion, Driver, ElementoUI, Observacion, arbol_a_texto
from dogfood.objetivos.web import acceso
from dogfood.reporte.redactar import redactar

MODELO_POR_DEFECTO = "ag/claude-sonnet-5-5-medium"
SECRETO = f"<secret>{acceso.VARIABLE}</secret>"
DESTRUCTIVO = re.compile(
    r"borra|elimin|apag|pagar|pago|comprar|checkout|delete|remove|\bpay\b|purchase|"
    r"cancelar\s+(la\s+|mi\s+)?(cuenta|suscripci)|cancel\s+(my\s+)?(account|subscription)|"
    r"darse\s+de\s+baja|dar\s+de\s+baja|unsubscribe|cerrar\s+sesi|log\s*out|sign\s*out|salir",
    re.IGNORECASE,
)
# Lo que toca dinero, datos o la cuenta va con prioridad alta aunque el LLM no lo diga.
_SENSIBLE = re.compile(
    r"pag|precio|cobr|compr|factur|plan|suscrip|cuenta|perfil|contraseñ|password|login|registr|"
    r"export|import|dato|archivo|subir|borr|elimin|payment|billing|account|data",
    re.IGNORECASE,
)
MAX_ACCIONES_POR_PANTALLA = 20
MAX_PASOS_ENTRADA = 15


class ErrorExploracion(RuntimeError):
    pass


class PantallaVista(BaseModel):
    path: str
    url: str
    titulo: str
    acciones: list[str]
    captura: str | None = None


class CasoUso(BaseModel):
    id: str
    nombre: str
    pantallas: list[str] = []  # paths de las pantallas donde ocurre
    estado: Literal["visto", "solo_prd"]


class Funcionalidad(BaseModel):
    nombre: str
    casos: list[CasoUso]


class EscenarioPropuesto(BaseModel):
    caso: str  # id del caso de uso
    prioridad: Literal["alta", "media"] = "media"
    id: str
    titulo: str
    superficies: list[str] = []
    persona_compatible: CompatibilidadPersona = CompatibilidadPersona()
    objetivo: str
    criterio_exito: str
    max_pasos: int = 40
    carril: Literal["normal", "login_fallido"] = "normal"


class RespuestaMapa(BaseModel):
    funcionalidades: list[Funcionalidad]
    escenarios: list[EscenarioPropuesto] = []


class DecisionEntrada(BaseModel):
    razonamiento: str = ""
    accion: Accion | None = None
    confirmar_email: bool = False  # solo con acceso.confirmacion = mailpit
    terminado: bool = False  # ya está dentro de la app
    rendirse: str | None = None


def destructivo(el: ElementoUI) -> bool:
    return bool(DESTRUCTIVO.search(f"{el.texto} {el.descripcion}"))


def _clave(url: str) -> str:
    u = urlsplit(url)
    return (u.path or "/") + (f"#{u.fragment}" if u.fragment.startswith("/") else "")


def _slug(texto: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:60] or "escenario"


class Explorador:
    """Una sesión de exploración: el driver, el LLM y lo que no puede llegar al prompt."""

    def __init__(self, driver: Driver, backend: BackendLlm, secretos: list[str]):
        self.driver, self.backend = driver, backend
        self.secretos = [s for s in secretos if s]
        self.n = 0
        self.costo_usd = 0.0
        self.tokens = [0, 0]
        self.obs: Observacion | None = None

    def limpio(self, texto: str) -> str:
        return redactar(texto, self.secretos)

    async def preguntar[T: BaseModel](self, prompt: str, esquema: type[T]) -> T:
        # última barrera: un secreto en el prompt es un bug, no se manda
        if any(s in prompt for s in self.secretos):
            raise ErrorExploracion("un secreto llegó al prompt del explorador; no se envía")
        salida, uso, _ = await self.backend.completar_json(prompt, esquema)
        self.costo_usd += uso.costo_usd
        self.tokens[0] += uso.tokens_in
        self.tokens[1] += uso.tokens_out
        return salida

    async def observar(self) -> Observacion:
        self.n += 1
        self.obs = await self.driver.observar(self.n)
        return self.obs

    async def ir(self, url: str) -> Observacion:
        await self.driver.actuar(Accion(tipo="navegar", texto=url))
        return await self.observar()

    async def tocar(self, el: ElementoUI) -> None:
        if destructivo(el):  # nunca, ni aunque lo pida el LLM
            raise ErrorExploracion(f"acción destructiva bloqueada: {el.texto!r}")
        await self.driver.actuar(Accion(tipo="tocar", elemento=el.id))

    async def titulo(self, obs: Observacion) -> str:
        page = getattr(self.driver, "page", None)  # DriverWeb expone la página de Playwright
        if page is not None:
            try:
                if t := (await page.title()).strip():
                    return self.limpio(t)
            except Exception:  # noqa: BLE001, S110 - sin título, se usa el texto
                pass
        return self.limpio(obs.texto_visible.strip().split("\n", 1)[0][:80])

    # --- 1. entrada ---
    async def entrar(self, proyecto, persona: Persona) -> None:
        a = proyecto.acceso
        if a.modo == "sin_login":
            return
        sensibles = acceso.datos_sensibles(proyecto)
        cuenta = f"Email: {persona.email}\nContraseña: {persona.contrasena}"
        if sensibles:
            cuenta += f"\n(escribe la contraseña literalmente como {SECRETO}: se sustituye sola)"
        historial: list[str] = []
        obs = self.obs or await self.observar()
        for _ in range(MAX_PASOS_ENTRADA):
            prompt = (
                "Eres el explorador de dogfood. Antes de recorrer la app tienes que entrar.\n"
                f"{persona.instrucciones}\n{cuenta}\n"
                "Nunca toques nada que borre, elimine, pague o cancele la cuenta.\n"
                "Devuelve una `accion` (tocar/escribir/tecla/navegar/esperar) o `terminado` si ya "
                "estás dentro; `rendirse` con el motivo si no puedes entrar"
                + (", o `confirmar_email` si la app pide confirmar el email" if a.confirmacion == "mailpit" else "")
                + ".\n"
                f"Pantalla: {self.limpio(obs.pantalla)}\n"
                f"Elementos:\n{self.limpio(arbol_a_texto(obs.elementos))}\n"
                f"Texto visible:\n{self.limpio(obs.texto_visible[:2000])}\n"
                f"Pasos previos:\n" + "\n".join(historial[-8:])
            )  # fmt: skip
            d = await self.preguntar(prompt, DecisionEntrada)
            if d.rendirse:
                raise ErrorExploracion(f"no pude entrar: {self.limpio(d.rendirse)}")
            if d.terminado:
                return
            if d.confirmar_email and a.confirmacion == "mailpit":
                link = acceso.link_de_confirmacion(a.mailpit_url, persona.email)
                if link:
                    await self.driver.actuar(Accion(tipo="navegar", texto=link))
                historial.append("confirmar_email: " + ("ok" if link else "no llegó el correo"))
            elif d.accion:
                ac = d.accion
                el = next((e for e in obs.elementos if e.id == ac.elemento), None)
                if ac.tipo == "tocar" and el is not None and destructivo(el):
                    historial.append(f"BLOQUEADO: {el.texto!r} es destructivo")
                    continue
                if ac.texto and SECRETO in ac.texto:
                    ac = ac.model_copy(
                        update={
                            "texto": ac.texto.replace(SECRETO, sensibles.get(acceso.VARIABLE, ""))
                        }
                    )
                r = await self.driver.actuar(ac)
                historial.append(
                    self.limpio(f"{d.accion.model_dump_json(exclude_none=True)} → "
                                f"{'ok' if r.ok else r.error}")
                )  # fmt: skip
            obs = await self.observar()
        raise ErrorExploracion(f"no pude entrar en {MAX_PASOS_ENTRADA} pasos")

    # --- 2. recorrido en anchura ---
    async def recorrer(self, max_paginas: int, permitida) -> list[PantallaVista]:
        # ponytail: anchura por URL; un botón que cambia la pantalla sin cambiar la URL (SPA con
        # estado) no abre pantalla nueva. Si hace falta, clave por título + elementos.
        inicio = (self.obs or await self.observar()).pantalla
        vistas: dict[str, PantallaVista] = {}
        cola, en_cola = deque([inicio]), {_clave(inicio)}
        while cola and len(vistas) < max_paginas:
            url = cola.popleft()
            obs = self.obs if self.obs and self.obs.pantalla == url else await self.ir(url)
            clave = _clave(obs.pantalla)
            if clave in vistas or not permitida(obs.pantalla):
                continue
            vistas[clave] = PantallaVista(
                path=clave,
                url=self.limpio(obs.pantalla),
                titulo=await self.titulo(obs),
                acciones=[
                    self.limpio(e.texto or e.descripcion)
                    for e in obs.elementos
                    if (e.clicable or e.editable) and (e.texto or e.descripcion)
                ],
                captura=str(obs.captura) if obs.captura else None,
            )
            candidatos = [(e.clase, e.texto, e.descripcion) for e in obs.elementos
                          if e.clicable and not destructivo(e)][:MAX_ACCIONES_POR_PANTALLA]  # fmt: skip
            for firma in candidatos:
                if self.obs.pantalla != obs.pantalla:
                    await self.ir(url)
                # los ids cambian al recargar: se busca el mismo elemento por su firma
                el = next(
                    (e for e in self.obs.elementos if (e.clase, e.texto, e.descripcion) == firma),
                    None,
                )
                if el is None:
                    continue
                await self.tocar(el)
                destino = (await self.observar()).pantalla
                k = _clave(destino)
                if permitida(destino) and k not in vistas and k not in en_cola:
                    cola.append(destino)
                    en_cola.add(k)
        return list(vistas.values())

    # --- 3. mapa y escenarios ---
    async def armar_mapa(
        self, pantallas: list[PantallaVista], prd: str
    ) -> tuple[list[Funcionalidad], list[tuple[dict, str]]]:
        resumen = "\n".join(
            f"- {p.path} «{p.titulo}»: {', '.join(p.acciones) or 'sin acciones'}" for p in pantallas
        )
        prompt = (
            "Eres el explorador de dogfood. Arma el mapa de funcionalidades de una app web.\n"
            "Cada funcionalidad tiene casos de uso con las pantallas (paths) donde ocurren. Marca "
            "cada caso `visto` si lo encontraste en las pantallas exploradas, o `solo_prd` si está "
            "en el PRD y no aparece (posible brecha).\n"
            "Para cada caso visto propone un escenario de prueba para un usuario real: `id` en "
            "kebab-case, `titulo`, `superficies` (nombres cortos de pantallas), "
            "`persona_compatible`, `objetivo` (qué intenta hacer, en lenguaje de usuario), "
            "`criterio_exito` (qué debe verse al final), `max_pasos` y `carril` (normal), con "
            "`caso` = id del caso y `prioridad` alta si toca dinero, datos o la cuenta.\n"
            "Ningún escenario borra, elimina, paga ni cancela la cuenta.\n\n"
            f"Pantallas exploradas:\n{resumen or '(ninguna)'}\n\n"
            f"PRD:\n{self.limpio(prd)[:20000] if prd.strip() else '(no hay PRD)'}\n"
        )
        r = await self.preguntar(prompt, RespuestaMapa)
        return corregir(r, {p.path for p in pantallas})


def corregir(
    r: RespuestaMapa, paths: set[str]
) -> tuple[list[Funcionalidad], list[tuple[dict, str]]]:
    """Lo que el LLM dice se contrasta con lo explorado: `visto` exige una pantalla real; solo los
    casos vistos dan escenario; cada escenario valida contra `Escenario`."""
    vistos: dict[str, list[str]] = {}
    for f in r.funcionalidades:
        for c in f.casos:
            c.pantallas = [p for p in c.pantallas if p in paths]
            if c.estado == "visto" and not c.pantallas:
                c.estado = "solo_prd"
            if c.estado == "visto":
                vistos[c.id] = c.pantallas
    propuestos: list[tuple[dict, str]] = []
    ids: set[str] = set()
    for p in r.escenarios:
        if p.caso not in vistos:
            continue
        texto = " ".join([p.titulo, p.objetivo, *p.superficies])
        if DESTRUCTIVO.search(texto):
            continue
        base = _slug(p.id or p.titulo)
        id_ = base
        for n in range(2, 100):
            if id_ not in ids:
                break
            id_ = f"{base}-{n}"
        datos = p.model_dump(exclude={"caso", "prioridad"}) | {"id": id_}
        try:
            esc = Escenario.model_validate(datos)
        except ValidationError:
            continue
        ids.add(id_)
        prioridad = "alta" if p.prioridad == "alta" or _SENSIBLE.search(texto) else "media"
        propuestos.append((esc.model_dump(mode="json", exclude_none=True), prioridad))
    return r.funcionalidades, propuestos


def persona_exploradora(proyecto) -> Persona:
    p = Persona(
        id="explorador",
        nombre="Explorador",
        email=f"explorador-{proyecto.slug}-{secrets.token_hex(3)}@dogfood.example.com",
        contrasena=f"Dg-{secrets.token_urlsafe(9)}",
        empresa="",
        rubro="",
        idioma="es",
        destreza=4,
        paciencia=5,
        intencion="explorar",
        semilla=0,
        instrucciones=proyecto.instrucciones,
    )
    acceso.aplicar(proyecto, p)
    return p


def backend_explorador(cfg: Config, contador=None) -> BackendLlm:
    from dogfood.backends.api import BackendApi

    modelo = (cfg.roles.get("explorador") or [MODELO_POR_DEFECTO])[0]
    return BackendApi(modelo, cfg, contador, rol="explorador")


async def explorar(
    proyecto,
    *,
    raiz: Path = Path("runs"),
    cfg: Config | None = None,
    max_paginas: int = 25,
    prd: str | None = None,
    driver: Driver | None = None,
    backend: BackendLlm | None = None,
) -> dict:
    """Explora, guarda `runs/exploracion-<slug>-<fecha>/mapa.json` y los borradores; devuelve el
    registro de la exploración. `driver` y `backend` se inyectan en los tests."""
    raiz = Path(raiz)
    acceso.validar(proyecto)  # secreto faltante: error claro antes de abrir nada
    creado = datetime.now().astimezone()
    id_ = f"exploracion-{proyecto.slug}-{creado:%Y%m%d-%H%M%S}"
    carpeta = raiz / id_
    carpeta.mkdir(parents=True, exist_ok=True)
    secretos = list(acceso.datos_sensibles(proyecto).values())
    if cfg is not None:
        secretos += list(cfg._secretos.values())
    if backend is None:
        from dogfood.llm import ContadorUso

        backend = backend_explorador(cfg or Config.cargar(), ContadorUso(cfg or Config.cargar()))

    from dogfood.objetivos.web import WebObjetivo

    objetivo = WebObjetivo.desde_proyecto(proyecto, raiz=raiz)
    preparada = driver is None
    if preparada:
        from dogfood.agente.navegador import ESCRITORIO
        from dogfood.drivers.web import DriverWeb

        instancia = objetivo.preparar("main", None)  # hosts prohibidos, levantar y salud
        driver = DriverWeb(
            instancia.base_url, lambda u: objetivo.url_permitida(u, instancia), ESCRITORIO
        )
    else:
        proyecto.verificar_url(objetivo._url())
        instancia = Instancia(base_url=objetivo._url(), api_url="", proyecto_compose="", commit="")

    def permitida(url: str) -> bool:
        return objetivo.url_permitida(url, instancia)

    ex = Explorador(driver, backend, secretos)
    await driver.iniciar(carpeta)
    try:
        await ex.entrar(proyecto, persona_exploradora(proyecto))
        pantallas = await ex.recorrer(max_paginas, permitida)
    finally:
        await driver.cerrar()
        if preparada:
            objetivo.destruir(instancia)
    funcionalidades, propuestos = await ex.armar_mapa(
        pantallas, proyecto.prd if prd is None else prd
    )
    registro = {
        "id": id_,
        "proyecto": proyecto.slug,
        "creado": creado.isoformat(),
        "modelo": backend.modelo,
        "costo_usd": round(ex.costo_usd, 6),
        "tokens_in": ex.tokens[0],
        "tokens_out": ex.tokens[1],
        "pantallas": [p.model_dump() for p in pantallas],
        "funcionalidades": [f.model_dump() for f in funcionalidades],
        "escenarios": [e["id"] for e, _ in propuestos],
    }
    (carpeta / "mapa.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False))
    alm = Almacen(raiz)
    alm.guardar_exploracion(registro)
    alm.guardar_borradores(proyecto.slug, propuestos)
    return registro
