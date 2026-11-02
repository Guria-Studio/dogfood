"""Proyectos: un objetivo de `objetivos/` más su configuración editable, en la base del almacén.

El valor de un secreto nunca se guarda aquí: solo su referencia (el nombre de la variable en
`~/.config/dogfood/secretos/<slug>.env`).
"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from dogfood.almacen import Almacen
from dogfood.objetivos import OBJETIVOS

RAIZ = Path("runs")


class ErrorProyecto(ValueError):
    pass


class Acceso(BaseModel):
    usuario: str = ""
    secreto_ref: str = ""
    # Objetivo `web` (F13): cómo entra la persona. `registro` es lo que hacía siempre.
    modo: Literal["registro", "usuario_prueba", "sin_login"] = "registro"
    confirmacion: Literal["no", "mailpit", "manual"] = "no"  # solo en modo `registro`
    mailpit_url: str = ""  # API de Mailpit si `confirmacion: mailpit`


class Entorno(BaseModel):
    nombre: str
    url: str
    predeterminado: bool = False
    tipo: Literal["local", "staging"] = "local"  # nunca producción


class Comportamiento(BaseModel):
    login_una_vez: bool = False
    viewport: Literal["escritorio", "movil"] = "escritorio"
    concurrencia: int | None = Field(default=None, ge=1, le=20)  # None: la de la config


class Notificaciones(BaseModel):
    slack: bool = False
    issues_github: bool = True
    repo: str = ""  # dueño/repo donde se abren los issues
    etiqueta: str = ""  # etiqueta de los issues publicados
    comentar_pr: bool = False  # `dogfood ci` comenta el resultado en el PR


class Proyecto(BaseModel):
    # Los campos desconocidos (p. ej. un valor de secreto) se descartan, no se guardan.
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    nombre: str = Field(min_length=1)
    tipo: Literal["web", "android", "ios", "flutter_web"] = "web"
    objetivo: str
    url: str = ""
    acceso: Acceso = Acceso()
    instrucciones: str = ""
    entornos: list[Entorno] = []
    comportamiento: Comportamiento = Comportamiento()
    notificaciones: Notificaciones = Notificaciones()
    repo_codigo: str = ""  # dueño/repo del código, para las sugerencias de arreglo
    diff_activo: bool = False  # `dogfood ci` corre también `dogfood diff` contra la rama base
    diff_bloquea: bool = False  # un 4xx/5xx nuevo en el diff hace fallar el check
    # Objetivo `web`: cómo levantar la app (p. ej. `docker compose -f … up -d`) y cómo saber que
    # está sana (una URL o un path; vacío = la raíz).
    levantar: str = ""
    bajar: str = ""
    salud: str = ""
    origenes_extra: list[str] = []  # orígenes que el navegador puede tocar además del de la URL
    hosts_prohibidos: list[str] = []  # la corrida no arranca si la URL cae en uno (producción)
    creado: datetime | None = None

    @field_validator("objetivo")
    @classmethod
    def _objetivo(cls, v: str) -> str:
        if v not in OBJETIVOS:
            raise ValueError(
                f"objetivo desconocido: {v!r}. Válidos: {', '.join(sorted(OBJETIVOS))}"
            )
        return v

    @field_validator("entornos")
    @classmethod
    def _un_predeterminado(cls, v: list[Entorno]) -> list[Entorno]:
        if sum(e.predeterminado for e in v) > 1:
            raise ValueError("solo un entorno puede ser el predeterminado")
        return v

    def verificar_url(self, url: str) -> None:
        """Frena con ErrorProyecto si el host de `url` es (o cuelga de) un host prohibido."""
        host = (urlsplit(url).hostname or "").lower()
        for prohibido in self.hosts_prohibidos:
            p = prohibido.strip().lower()
            if p and (host == p or host.endswith("." + p)):
                raise ErrorProyecto(
                    f"la URL {url} cae en hosts_prohibidos ({p}) del proyecto {self.slug!r}: "
                    "dogfood nunca corre contra producción"
                )

    def entorno(self, nombre: str | None = None) -> Entorno | None:
        for e in self.entornos:
            if e.nombre == nombre if nombre else e.predeterminado:
                return e
        if nombre:
            raise ErrorProyecto(f"el proyecto {self.slug!r} no tiene el entorno {nombre!r}")
        return None


def _con(raiz: Path) -> sqlite3.Connection:
    return Almacen(raiz)._con()  # crea o migra la base; siembra `predicts` la primera vez


def _leer(slug: str, datos: str, creado: str) -> Proyecto:
    return Proyecto.model_validate_json(datos).model_copy(
        update={"creado": datetime.fromisoformat(creado)}
    )


def listar(raiz: Path = RAIZ) -> list[Proyecto]:
    with closing(_con(raiz)) as con:
        return [
            _leer(*r)
            for r in con.execute("SELECT slug, datos, creado FROM proyectos ORDER BY slug")
        ]


def obtener(slug: str, raiz: Path = RAIZ) -> Proyecto | None:
    with closing(_con(raiz)) as con:
        r = con.execute(
            "SELECT slug, datos, creado FROM proyectos WHERE slug = ?", (slug,)
        ).fetchone()
    return _leer(*r) if r else None


def crear(datos: dict, raiz: Path = RAIZ) -> Proyecto:
    p = Proyecto.model_validate(datos | {"creado": None})
    with closing(_con(raiz)) as con, con:
        try:
            con.execute(
                "INSERT INTO proyectos (slug, creado, datos) VALUES (?, ?, ?)",
                (
                    p.slug,
                    datetime.now(UTC).isoformat(),
                    p.model_dump_json(exclude={"creado"}),
                ),
            )
        except sqlite3.IntegrityError:
            raise ErrorProyecto(f"el proyecto {p.slug!r} ya existe") from None
    return obtener(p.slug, raiz)


def actualizar(slug: str, cambios: dict, raiz: Path = RAIZ) -> Proyecto | None:
    actual = obtener(slug, raiz)
    if actual is None:
        return None
    nuevo = actual.model_dump(mode="json", exclude={"creado"})
    for k, v in cambios.items():
        if k in ("slug", "creado"):
            continue  # el slug es la identidad
        # ponytail: los grupos (acceso, comportamiento…) se mezclan campo a campo; las listas se reemplazan
        nuevo[k] = nuevo[k] | v if isinstance(v, dict) and isinstance(nuevo.get(k), dict) else v
    p = Proyecto.model_validate(nuevo)
    with closing(_con(raiz)) as con, con:
        con.execute(
            "UPDATE proyectos SET datos = ? WHERE slug = ?",
            (p.model_dump_json(exclude={"creado"}), slug),
        )
    return obtener(slug, raiz)


def borrar(slug: str, raiz: Path = RAIZ) -> bool:
    with closing(_con(raiz)) as con, con:
        return con.execute("DELETE FROM proyectos WHERE slug = ?", (slug,)).rowcount > 0


def ultimos_resultados(p: Proyecto, raiz: Path = RAIZ) -> dict:
    """Pasaron, fallaron y última actividad de la corrida más reciente del proyecto."""
    with closing(_con(raiz)) as con:
        c = con.execute(
            "SELECT id, COALESCE(fin, inicio) AS actividad FROM corridas"
            " WHERE proyecto = ? OR (proyecto IS NULL AND objetivo = ?)"
            " ORDER BY inicio DESC LIMIT 1",
            (p.slug, p.objetivo),
        ).fetchone()
        if c is None:
            return {"corrida_id": None, "pasaron": 0, "fallaron": 0, "ultima_actividad": None}
        pasaron, total = con.execute(
            "SELECT COALESCE(SUM(COALESCE(resultado = 'aprobado', exito = 1)), 0), COUNT(*)"
            " FROM ejecuciones WHERE corrida_id = ?",
            (c["id"],),
        ).fetchone()
    return {
        "corrida_id": c["id"],
        "pasaron": pasaron,
        "fallaron": total - pasaron,
        "ultima_actividad": c["actividad"],
    }
