"""Suites (casos de uno o varios proyectos) y sus programaciones con timers de `systemd --user`."""

import json
import re
import secrets
import shlex
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from dogfood import proyectos
from dogfood.almacen import Almacen

_DIAS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_CAMPO_CRON = re.compile(r"^[0-9*/,\-]+$")
_PERDIDA = timedelta(hours=6)  # sin corrida registrada pasado este tiempo: se da por bloqueada


def _con(raiz: Path):
    return closing(Almacen(raiz)._con())


# --- suites ---


def crear(raiz: Path, nombre: str, casos: list[dict]) -> dict:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("la suite necesita un nombre")
    if not casos:
        raise ValueError("elige al menos un caso")
    limpios = []
    for c in casos:
        slug, caso = str(c.get("proyecto", "")), str(c.get("caso", ""))
        if proyectos.obtener(slug, raiz) is None or not caso:
            raise ValueError(f"caso inválido: {slug}/{caso}")
        limpios.append({"proyecto": slug, "caso": caso})
    with _con(raiz) as con, con:
        cur = con.execute(
            "INSERT INTO suites (nombre, casos, creado) VALUES (?, ?, ?)",
            (nombre, json.dumps(limpios), datetime.now(UTC).isoformat()),
        )
    return obtener(raiz, cur.lastrowid)  # type: ignore[arg-type]


def _casos(fila) -> list[dict]:
    return json.loads(fila["casos"])


def estado_ultima(raiz: Path, suite_id: int) -> tuple[str | None, str | None]:
    """(estado, inicio) de la última corrida de la suite: paso, advertencia, fallo, bloqueado o corriendo."""
    with _con(raiz) as con:
        ini = con.execute(
            "SELECT MAX(inicio) FROM suite_corridas WHERE suite_id = ?", (suite_id,)
        ).fetchone()[0]
        if ini is None:
            return None, None
        lanzadas = con.execute(
            "SELECT objetivo, semilla FROM suite_corridas WHERE suite_id = ? AND inicio = ?",
            (suite_id, ini),
        ).fetchall()
        p = f = b = 0
        en_curso = False
        for objetivo, semilla in lanzadas:
            c = con.execute(
                "SELECT id, fin FROM corridas WHERE semilla = ? AND objetivo = ?",
                (semilla, objetivo),
            ).fetchone()
            if c is None:
                en_curso |= datetime.now(UTC) - datetime.fromisoformat(ini) < _PERDIDA
                b += 1
                continue
            en_curso |= c["fin"] is None
            for e in con.execute(
                "SELECT estado, exito, resultado FROM ejecuciones WHERE corrida_id = ?", (c["id"],)
            ):
                if e["resultado"] == "aprobado" or (e["resultado"] is None and e["exito"] == 1):
                    p += 1
                elif e["resultado"] == "no_concluyente" or e["estado"] == "rendido":
                    b += 1
                else:
                    f += 1
    if en_curso:
        return "corriendo", ini
    if f == 0 and b == 0 and p:
        return "paso", ini
    if p == 0:
        return ("fallo" if f else "bloqueado"), ini
    return "advertencia", ini  # resultados mixtos


def obtener(raiz: Path, suite_id: int) -> dict | None:
    with _con(raiz) as con:
        fila = con.execute("SELECT * FROM suites WHERE id = ?", (suite_id,)).fetchone()
    if fila is None:
        return None
    estado, ini = estado_ultima(raiz, suite_id)
    casos = _casos(fila)
    return {
        "id": fila["id"], "nombre": fila["nombre"], "casos": casos, "n_casos": len(casos),
        "ultima_ejecucion": ini, "estado": estado,
    }  # fmt: skip


def listar(raiz: Path) -> list[dict]:
    with _con(raiz) as con:
        ids = [r[0] for r in con.execute("SELECT id FROM suites ORDER BY id")]
    return [obtener(raiz, i) for i in ids]  # type: ignore[misc]


def borrar(raiz: Path, suite_id: int) -> bool:
    with _con(raiz) as con, con:
        con.execute("DELETE FROM programaciones WHERE suite_id = ?", (suite_id,))
        con.execute("DELETE FROM suite_corridas WHERE suite_id = ?", (suite_id,))
        return con.execute("DELETE FROM suites WHERE id = ?", (suite_id,)).rowcount > 0


def planear(raiz: Path, suite: dict) -> list[dict]:
    """Una corrida por proyecto: {objetivo, escenarios, semilla}; el caso es `escenario[:persona]`."""
    por: dict[str, list[str]] = {}
    for c in suite["casos"]:
        p = proyectos.obtener(c["proyecto"], raiz)
        if p is None:
            continue
        esc = c["caso"].split(":")[0]
        if esc not in por.setdefault(p.objetivo, []):
            por[p.objetivo].append(esc)
    return [
        {"objetivo": o, "escenarios": e, "semilla": secrets.randbelow(2**31)}
        for o, e in por.items()
    ]


def registrar_lanzadas(raiz: Path, suite_id: int, plan: list[dict]) -> None:
    ini = datetime.now(UTC).isoformat()
    with _con(raiz) as con, con:
        con.executemany(
            "INSERT INTO suite_corridas (suite_id, inicio, objetivo, semilla) VALUES (?, ?, ?, ?)",
            [(suite_id, ini, g["objetivo"], g["semilla"]) for g in plan],
        )


# --- programaciones ---


def cron_a_calendario(expr: str) -> str:
    campos = expr.split()
    if len(campos) != 5 or not all(_CAMPO_CRON.match(c) for c in campos):
        raise ValueError("la expresión cron debe tener 5 campos: minuto hora día mes día-semana")
    m, h, dom, mes, dow = (c.replace("-", "..") for c in campos)
    dow = re.sub(r"\d", lambda x: _DIAS[int(x.group()) % 7], dow)
    return f"{'' if dow == '*' else dow + ' '}*-{mes}-{dom} {h}:{m}:00"


def calendario(frecuencia: str, hora: str = "", dia: str = "", cron: str = "") -> str:
    if frecuencia == "hora":
        return "hourly"
    if frecuencia == "cron":
        return cron_a_calendario(cron)
    if frecuencia not in ("dia", "semana"):
        raise ValueError("la frecuencia es hora, dia, semana o cron")
    if not _HORA.match(hora):
        raise ValueError("la hora debe ser HH:MM")
    if frecuencia == "dia":
        return f"*-*-* {hora}:00"
    if dia not in _DIAS:
        raise ValueError(f"el día debe ser uno de {', '.join(_DIAS)}")
    return f"{dia} *-*-* {hora}:00"


class Programador(Protocol):
    def crear(self, id: int, calendario: str, comando: list[str], cwd: Path) -> None: ...
    def borrar(self, id: int) -> None: ...


class ProgramadorSystemd:
    """Un par `.service`/`.timer` en `~/.config/systemd/user` por programación."""

    def __init__(self, carpeta: Path | None = None):
        self.carpeta = carpeta or Path.home() / ".config" / "systemd" / "user"

    def _ctl(self, *args: str) -> None:
        subprocess.run(["systemctl", "--user", *args], check=False, capture_output=True)

    def crear(self, id: int, calendario: str, comando: list[str], cwd: Path) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        n = f"dogfood-prog-{id}"
        (self.carpeta / f"{n}.service").write_text(
            f"[Unit]\nDescription=dogfood: programación {id}\n\n[Service]\nType=oneshot\n"
            f"WorkingDirectory={cwd}\nExecStart={shlex.join(comando)}\n"
        )
        (self.carpeta / f"{n}.timer").write_text(
            f"[Unit]\nDescription=dogfood: programación {id}\n\n[Timer]\n"
            f"OnCalendar={calendario}\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n"
        )
        self._ctl("daemon-reload")
        self._ctl("enable", "--now", f"{n}.timer")

    def borrar(self, id: int) -> None:
        n = f"dogfood-prog-{id}"
        self._ctl("disable", "--now", f"{n}.timer")
        for ext in ("timer", "service"):
            (self.carpeta / f"{n}.{ext}").unlink(missing_ok=True)
        self._ctl("daemon-reload")


def comando_suite(raiz: Path, suite_id: int, slack: bool) -> list[str]:
    cmd = [
        sys.executable,
        "-c",
        "from dogfood.cli import main; main()",
        "suite",
        "run",
        str(suite_id),
    ]
    cmd += ["--runs", str(Path(raiz).resolve())]
    return cmd + (["--slack"] if slack else [])


def crear_programacion(raiz: Path, programador: Programador, suite_id: int, datos: dict) -> dict:
    if obtener(raiz, suite_id) is None:
        raise ValueError(f"la suite {suite_id} no existe")
    cal = calendario(*(str(datos.get(k, "")) for k in ("frecuencia", "hora", "dia", "cron")))
    slack = bool(datos.get("slack"))
    with _con(raiz) as con, con:
        cur = con.execute(
            "INSERT INTO programaciones (suite_id, frecuencia, hora, dia, cron, slack, calendario, creado)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (suite_id, datos["frecuencia"], datos.get("hora", ""), datos.get("dia", ""),
             datos.get("cron", ""), int(slack), cal, datetime.now(UTC).isoformat()),
        )  # fmt: skip
    id = cur.lastrowid
    programador.crear(id, cal, comando_suite(raiz, suite_id, slack), Path(raiz).resolve().parent)  # type: ignore[arg-type]
    return listar_programaciones(raiz, id)[0]


def listar_programaciones(raiz: Path, id: int | None = None) -> list[dict]:
    with _con(raiz) as con:
        filas = con.execute(
            "SELECT p.*, s.nombre AS suite FROM programaciones p JOIN suites s ON s.id = p.suite_id"
            + (" WHERE p.id = ?" if id else "")
            + " ORDER BY p.id",
            (id,) if id else (),
        )
        return [dict(f) | {"slack": bool(f["slack"])} for f in filas]


def borrar_programacion(raiz: Path, programador: Programador, id: int) -> bool:
    with _con(raiz) as con, con:
        hubo = con.execute("DELETE FROM programaciones WHERE id = ?", (id,)).rowcount > 0
    if hubo:
        programador.borrar(id)
    return hubo
