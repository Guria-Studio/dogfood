"""Objetivo `web` genérico: cualquier app web, configurada entera desde su `Proyecto` (F13).

Sin oráculo: solo corren los detectores genéricos (técnicos, fricción) y la opinión.
"""

import json
import logging
import os
import re
import sqlite3
import subprocess
import time
from collections.abc import Callable
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia

log = logging.getLogger(__name__)

EXPLORACION_LIBRE = Escenario(
    id="exploracion-libre",
    titulo="Exploración libre",
    objetivo="Recorre la app como un usuario nuevo y usa su función principal",
    criterio_exito="La persona entiende para qué sirve la app y logra usar su función principal",
)

# Segmentos que no nombran una pantalla: ids numéricos, uuids, hashes.
_ID = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f-]{27,}|[0-9a-f]{16,})$", re.IGNORECASE)


def _origen(url: str) -> tuple[str, str]:
    u = urlsplit(url if "//" in url else f"//{url}")
    return u.scheme, (u.netloc or "").lower()


def _sh(cmd: str) -> list[str]:
    return ["sh", "-c", cmd]


class WebObjetivo:
    nombre = "web"

    def __init__(
        self,
        proyecto=None,
        *,
        raiz: Path = Path("runs"),
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        timeout_salud_s: float = 120,
    ):
        self.proyecto = proyecto
        self.raiz = Path(raiz)
        self.runner = runner
        self.timeout_salud_s = timeout_salud_s

    @classmethod
    def desde_proyecto(cls, p, **kw) -> "WebObjetivo":
        return cls(p, **kw)

    def _url(self) -> str:
        p = self.proyecto
        e = p.entorno() if p else None
        return (e.url if e else "") or (p.url if p else "")

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        p = self.proyecto
        if p is None:
            raise ValueError("el objetivo web necesita un proyecto (`--target <slug>`)")
        url = self._url()
        if not url:
            raise ValueError(f"el proyecto {p.slug!r} no tiene URL")
        p.verificar_url(url)  # antes de levantar nada
        if p.levantar:
            self.runner(_sh(p.levantar), check=True)
        self._esperar_salud(urljoin(url, p.salud) if p.salud else url)
        return Instancia(
            base_url=url,
            api_url=url,
            proyecto_compose=os.environ.get("COMPOSE_PROJECT_NAME", f"dogfood-{p.slug}"),
            commit=ref,
        )

    def _esperar_salud(self, url: str) -> None:
        limite = time.monotonic() + self.timeout_salud_s
        ultimo = "sin respuesta"
        while True:
            try:
                r = httpx.get(url, timeout=10, follow_redirects=False)
                if r.status_code < 400:
                    return
                ultimo = f"HTTP {r.status_code}"
            except httpx.HTTPError as exc:
                ultimo = f"{type(exc).__name__}: {exc}"
            if time.monotonic() >= limite:
                raise TimeoutError(
                    f"{url} no respondió 2xx/3xx en {self.timeout_salud_s:g} s ({ultimo})"
                )
            time.sleep(1)

    def destruir(self, instancia: Instancia) -> None:
        if self.proyecto and self.proyecto.bajar:
            self.runner(_sh(self.proyecto.bajar), check=False)

    def url_permitida(self, url: str, instancia: Instancia) -> bool:
        if url.startswith(("about:", "data:", "blob:")):
            return True
        esquema, host = _origen(url)
        if (esquema, host) == _origen(instancia.base_url):
            return True
        for extra in self.proyecto.origenes_extra if self.proyecto else []:
            e_esquema, e_host = _origen(extra)
            if host == e_host and (not e_esquema or e_esquema == esquema):
                return True
        return False

    def escenarios(self) -> list[Escenario]:
        aceptados = []
        if self.proyecto:
            db = self.raiz / "dogfood.db"
            try:
                with closing(sqlite3.connect(db)) as con:
                    filas = con.execute(
                        "SELECT datos FROM escenarios_proyecto"
                        " WHERE proyecto = ? AND estado = 'aceptado' ORDER BY creado, id",
                        (self.proyecto.slug,),
                    ).fetchall()
                aceptados = [Escenario.model_validate(json.loads(d)) for (d,) in filas]
            except sqlite3.OperationalError:  # base sin migrar
                pass
        return aceptados or [EXPLORACION_LIBRE]

    def pantalla(self, url: str, titulo: str = "") -> str:
        u = urlsplit(url)
        segmentos = [s for s in u.path.split("/") if s and not _ID.match(s)]
        if not segmentos and u.fragment.startswith("/"):  # rutas por hash (#/ajustes)
            segmentos = [s for s in u.fragment.split("?")[0].split("/") if s and not _ID.match(s)]
        return segmentos[0] if segmentos else (titulo.strip() or "inicio")

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]:
        return []  # sin oráculo: los genéricos corren igual en `deteccion`

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        p = self.proyecto
        if not (p and "compose" in p.levantar and " up" in p.levantar):
            return {}
        # ponytail: los logs salen del mismo comando de compose cambiando `up …` por `logs`;
        # un `levantar` que no sea compose no da logs.
        base = p.levantar.rsplit(" up", 1)[0]
        r = self.runner(
            _sh(f"{base} logs --no-color --since {desde.isoformat()}"),
            capture_output=True,
            text=True,
            check=False,
        )
        return {"app": r.stdout or ""}

    def contar_uso_ia(self, instancia: Instancia) -> None:
        return None  # no hay base conocida que contar
