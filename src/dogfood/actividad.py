"""Registro de actividad de un proyecto (tabla `actividad`): quién hizo qué y cuándo."""

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from dogfood.almacen import Almacen

TIPOS = (
    "corrida_lanzada",
    "corrida_terminada",
    "corrida_cancelada",
    "issue_publicado",
    "ajuste_cambiado",
    "proyecto_creado",
)


def registrar(
    raiz: Path, proyecto: str, tipo: str, detalle: str = "", autor: str = "panel"
) -> None:
    with closing(Almacen(raiz)._con()) as con, con:
        con.execute(
            "INSERT INTO actividad (proyecto, tipo, detalle, autor, fecha) VALUES (?, ?, ?, ?, ?)",
            (proyecto, tipo, detalle, autor, datetime.now(UTC).isoformat()),
        )


def listar(raiz: Path, proyecto: str, limite: int = 200) -> list[dict]:
    with closing(Almacen(raiz)._con()) as con:
        filas = con.execute(
            "SELECT id, tipo, detalle, autor, fecha FROM actividad WHERE proyecto = ?"
            " ORDER BY id DESC LIMIT ?",
            (proyecto, limite),
        )
        return [dict(f) for f in filas]
