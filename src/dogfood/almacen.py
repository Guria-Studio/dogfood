"""Almacén de corridas: carpeta por corrida en `runs/` más el índice SQLite `runs/dogfood.db`."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from dogfood.dominio import Corrida, Ejecucion, Hallazgo, Persona, UsoLlm

VERSION_ESQUEMA = 6

# Esquema del MVP (v1); los cambios posteriores van como migraciones en MIGRACIONES.
ESQUEMA_V1 = """
CREATE TABLE corridas (
    id TEXT PRIMARY KEY, objetivo TEXT NOT NULL, ref TEXT NOT NULL, "commit" TEXT NOT NULL,
    semilla INTEGER NOT NULL, inicio TEXT NOT NULL, fin TEXT, estado TEXT NOT NULL,
    costo_usd REAL NOT NULL DEFAULT 0, n_personas INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE personas (
    id TEXT NOT NULL, corrida_id TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY (corrida_id, id)
);
CREATE TABLE ejecuciones (
    id TEXT PRIMARY KEY, corrida_id TEXT NOT NULL, persona_id TEXT NOT NULL,
    escenario_id TEXT NOT NULL, modelo TEXT NOT NULL, estado TEXT NOT NULL,
    pasos INTEGER NOT NULL, duracion_s REAL NOT NULL, exito INTEGER NOT NULL, motivo_juez TEXT NOT NULL
);
CREATE TABLE hallazgos (
    id TEXT PRIMARY KEY, corrida_id TEXT NOT NULL, ejecucion_id TEXT, tipo TEXT NOT NULL,
    gravedad TEXT NOT NULL, pantalla TEXT NOT NULL, titulo TEXT NOT NULL, huella TEXT NOT NULL,
    issue_url TEXT, nuevo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE uso_llm (
    corrida_id TEXT NOT NULL, ejecucion_id TEXT, rol TEXT NOT NULL, modelo TEXT NOT NULL,
    tokens_in INTEGER NOT NULL, tokens_out INTEGER NOT NULL, costo_usd REAL NOT NULL
);
CREATE INDEX ix_hallazgos_corrida ON hallazgos (corrida_id);
CREATE INDEX ix_ejecuciones_corrida ON ejecuciones (corrida_id);
CREATE INDEX ix_uso_corrida ON uso_llm (corrida_id);
"""

# «Cambios v0.2» del modelo de datos.
MIGRACION_V2 = """
ALTER TABLE corridas ADD COLUMN version_app TEXT;
ALTER TABLE ejecuciones ADD COLUMN driver TEXT DEFAULT 'web';
ALTER TABLE ejecuciones ADD COLUMN motor TEXT DEFAULT 'browser_use';
ALTER TABLE ejecuciones ADD COLUMN backend TEXT DEFAULT 'api';
ALTER TABLE ejecuciones ADD COLUMN resultado TEXT;
ALTER TABLE ejecuciones ADD COLUMN tokens_in INTEGER DEFAULT 0;
ALTER TABLE ejecuciones ADD COLUMN tokens_out INTEGER DEFAULT 0;
ALTER TABLE ejecuciones ADD COLUMN capturas INTEGER DEFAULT 0;
ALTER TABLE ejecuciones ADD COLUMN costo_usd REAL DEFAULT 0;
ALTER TABLE ejecuciones ADD COLUMN costo_equivalente_usd REAL DEFAULT 0;
ALTER TABLE ejecuciones ADD COLUMN video TEXT;
ALTER TABLE ejecuciones ADD COLUMN trace TEXT;
ALTER TABLE uso_llm ADD COLUMN backend TEXT DEFAULT 'api';
ALTER TABLE uso_llm ADD COLUMN costo_equivalente_usd REAL DEFAULT 0;
"""

# F11.1.T2: proyectos (un objetivo más su configuración editable, en JSON) y la corrida que los nombra.
# `predicts` se siembra una sola vez, al crear la tabla: si se borra, no vuelve.
_PREDICTS = (
    '{"slug":"predicts","nombre":"Predicts","tipo":"web","objetivo":"predicts","url":"",'
    '"acceso":{"usuario":"","secreto_ref":""},"instrucciones":"","entornos":[],'
    '"comportamiento":{"login_una_vez":false,"viewport":"escritorio","concurrencia":null},'
    '"notificaciones":{"slack":false,"issues_github":true,"repo":""},"repo_codigo":""}'
)
MIGRACION_V3 = f"""
CREATE TABLE proyectos (slug TEXT PRIMARY KEY, creado TEXT NOT NULL, datos TEXT NOT NULL);
INSERT INTO proyectos (slug, creado, datos)
    VALUES ('predicts', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), '{_PREDICTS}');
ALTER TABLE corridas ADD COLUMN proyecto TEXT;
"""

# F11.3.T2: registro de actividad de cada proyecto.
MIGRACION_V4 = """
CREATE TABLE actividad (
    id INTEGER PRIMARY KEY AUTOINCREMENT, proyecto TEXT NOT NULL, tipo TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '', autor TEXT NOT NULL DEFAULT 'panel', fecha TEXT NOT NULL
);
CREATE INDEX ix_actividad_proyecto ON actividad (proyecto, id);
"""

# F12.1.T2: diffs de comportamiento entre dos refs (el detalle completo vive en `datos`, en JSON).
MIGRACION_V5 = """
CREATE TABLE diffs (
    id TEXT PRIMARY KEY, proyecto TEXT NOT NULL, base TEXT NOT NULL, nueva TEXT NOT NULL,
    creado TEXT NOT NULL, total INTEGER NOT NULL, con_cambios INTEGER NOT NULL,
    datos TEXT NOT NULL
);
CREATE INDEX ix_diffs_proyecto ON diffs (proyecto, creado);
"""

# F11.3.T3: suites (casos de uno o varios proyectos), sus corridas y sus programaciones.
MIGRACION_V6 = """
CREATE TABLE suites (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, casos TEXT NOT NULL, creado TEXT NOT NULL
);
CREATE TABLE suite_corridas (
    suite_id INTEGER NOT NULL, inicio TEXT NOT NULL, objetivo TEXT NOT NULL, semilla INTEGER NOT NULL
);
CREATE TABLE programaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT, suite_id INTEGER NOT NULL, frecuencia TEXT NOT NULL,
    hora TEXT NOT NULL DEFAULT '', dia TEXT NOT NULL DEFAULT '', cron TEXT NOT NULL DEFAULT '',
    slack INTEGER NOT NULL DEFAULT 0, calendario TEXT NOT NULL, creado TEXT NOT NULL
);
"""

# Script que lleva la base de la versión `n - 1` a la `n`.
MIGRACIONES = {
    1: ESQUEMA_V1,
    2: MIGRACION_V2,
    3: MIGRACION_V3,
    4: MIGRACION_V4,
    5: MIGRACION_V5,
    6: MIGRACION_V6,
}

SUBCARPETAS = ("datos", "ejecuciones", "logs")


class ResumenCorrida(BaseModel):
    id: str
    objetivo: str
    ref: str
    estado: str
    inicio: datetime
    fin: datetime | None
    n_personas: int
    n_hallazgos: int
    costo_usd: float


class Almacen:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.db = self.raiz / "dogfood.db"
        with closing(self._con()) as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            for v in range(version + 1, VERSION_ESQUEMA + 1):
                # executescript hace COMMIT antes; BEGIN/COMMIT dentro deja cada paso atómico.
                con.executescript(f"BEGIN;\n{MIGRACIONES[v]}\nPRAGMA user_version = {v};\nCOMMIT;")

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        return con

    # --- rutas ---
    def dir_corrida(self, corrida_id: str) -> Path:
        return self.raiz / corrida_id

    def dir_ejecucion(self, corrida_id: str, ejecucion_id: str) -> Path:
        return self.dir_corrida(corrida_id) / "ejecuciones" / ejecucion_id

    def dir_dataset(self, corrida_id: str, dataset_id: str) -> Path:
        return self.dir_corrida(corrida_id) / "datos" / dataset_id

    # --- escritura ---
    def nueva_corrida(self, corrida: Corrida) -> Path:
        base = self.dir_corrida(corrida.id)
        for sub in SUBCARPETAS:
            (base / sub).mkdir(parents=True, exist_ok=True)
        (base / "corrida.json").write_text(corrida.model_dump_json(indent=2))
        with closing(self._con()) as con, con:
            con.execute(
                'INSERT INTO corridas (id, objetivo, ref, "commit", semilla, inicio, fin, estado,'
                " version_app, proyecto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    corrida.id,
                    corrida.objetivo,
                    corrida.ref,
                    corrida.commit,
                    corrida.semilla,
                    corrida.inicio.isoformat(),
                    corrida.fin.isoformat() if corrida.fin else None,
                    corrida.estado,
                    corrida.version_app,
                    corrida.parametros.get("proyecto"),
                ),
            )
        return base

    def guardar_personas(self, corrida_id: str, personas: list[Persona]) -> None:
        (self.dir_corrida(corrida_id) / "personas.json").write_text(
            json.dumps([p.model_dump(mode="json") for p in personas], indent=2, ensure_ascii=False)
        )
        with closing(self._con()) as con, con:
            con.execute("DELETE FROM personas WHERE corrida_id = ?", (corrida_id,))
            con.executemany(
                "INSERT INTO personas (id, corrida_id, json) VALUES (?, ?, ?)",
                [(p.id, corrida_id, p.model_dump_json()) for p in personas],
            )
            con.execute(
                "UPDATE corridas SET n_personas = ? WHERE id = ?", (len(personas), corrida_id)
            )

    def guardar_ejecucion(self, corrida_id: str, e: Ejecucion) -> None:
        d = self.dir_ejecucion(corrida_id, e.id)
        (d / "capturas").mkdir(parents=True, exist_ok=True)
        (d / "descargas").mkdir(exist_ok=True)
        actual = d / "historial.json"
        if actual.is_file():
            # navegador.py guardó ahí el historial de browser-use: se aparta antes de pisarlo
            try:
                previo = json.loads(actual.read_text())
            except ValueError:
                previo = None
            if isinstance(previo, dict) and "history" in previo:
                apartado = d / "historial-browser-use.json"
                actual.replace(apartado)
                e.ruta_historial = apartado
        actual.write_text(e.model_dump_json(indent=2))
        m = e.metricas
        for nombre, items in (("pasos", e.pasos), ("red", e.red), ("consola", e.consola)):
            (d / f"{nombre}.jsonl").write_text("".join(i.model_dump_json() + "\n" for i in items))
        with closing(self._con()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO ejecuciones (id, corrida_id, persona_id, escenario_id, modelo,"
                " estado, pasos, duracion_s, exito, motivo_juez, driver, motor, backend, resultado,"
                " tokens_in, tokens_out, capturas, costo_usd, costo_equivalente_usd, video, trace)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    e.id,
                    corrida_id,
                    e.persona_id,
                    e.escenario_id,
                    e.modelo,
                    e.estado,
                    len(e.pasos),
                    e.duracion_s,
                    int(e.exito),
                    e.motivo_juez,
                    e.driver,
                    e.motor,
                    e.backend,
                    e.resultado,
                    m.tokens_in,
                    m.tokens_out,
                    m.capturas,
                    m.costo_usd,
                    m.costo_equivalente_usd,
                    str(e.video) if e.video else None,
                    str(e.trace) if e.trace else None,
                ),
            )

    def guardar_hallazgos(self, corrida_id: str, hallazgos: list[Hallazgo]) -> list[str]:
        """Reemplaza los hallazgos de la corrida; devuelve sus ids (`<corrida>-H<n>`)."""
        ids = [f"{corrida_id}-H{n}" for n in range(1, len(hallazgos) + 1)]
        (self.dir_corrida(corrida_id) / "hallazgos.json").write_text(
            json.dumps([h.model_dump(mode="json") for h in hallazgos], indent=2, ensure_ascii=False)
        )
        with closing(self._con()) as con, con:
            con.execute("DELETE FROM hallazgos WHERE corrida_id = ?", (corrida_id,))
            con.executemany(
                "INSERT INTO hallazgos (id, corrida_id, ejecucion_id, tipo, gravedad, pantalla, titulo,"
                " huella) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        i,
                        corrida_id,
                        h.ejecucion_id,
                        h.tipo.value,
                        h.gravedad.value,
                        h.pantalla,
                        h.titulo,
                        h.huella,
                    )
                    for i, h in zip(ids, hallazgos)
                ],
            )
        return ids

    def marcar_issues(self, corrida_id: str, issues: list[tuple[str, str | None, bool]]) -> None:
        """`(hallazgo_id, issue_url, nuevo)` por hallazgo publicado."""
        with closing(self._con()) as con, con:
            con.executemany(
                "UPDATE hallazgos SET issue_url = ?, nuevo = ? WHERE id = ? AND corrida_id = ?",
                [(url, int(nuevo), hid, corrida_id) for hid, url, nuevo in issues],
            )

    def registrar_uso(self, uso: UsoLlm, corrida_id: str) -> None:
        with closing(self._con()) as con, con:
            con.execute(
                "INSERT INTO uso_llm (corrida_id, ejecucion_id, rol, modelo, tokens_in, tokens_out,"
                " costo_usd, backend, costo_equivalente_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    corrida_id,
                    uso.ejecucion_id,
                    uso.rol,
                    uso.modelo,
                    uso.tokens_in,
                    uso.tokens_out,
                    uso.costo_usd,
                    uso.backend,
                    uso.costo_equivalente_usd,
                ),
            )

    def cerrar_corrida(
        self, corrida_id: str, estado: str, costo: float, version_app: str | None = None
    ) -> None:
        with closing(self._con()) as con, con:
            con.execute(
                "UPDATE corridas SET estado = ?, costo_usd = ?, fin = ?,"
                " version_app = COALESCE(?, version_app) WHERE id = ?",
                (estado, costo, datetime.now().astimezone().isoformat(), version_app, corrida_id),
            )

    def guardar_diff(self, d: dict) -> None:
        """Guarda (o reemplaza) un diff: `id`, `proyecto`, `base`, `nueva`, `creado`, `casos`…"""
        con_cambios = sum(c["resultado"] == "cambios" for c in d["casos"])
        with closing(self._con()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO diffs (id, proyecto, base, nueva, creado, total,"
                " con_cambios, datos) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    d["id"],
                    d["proyecto"],
                    d["base"],
                    d["nueva"],
                    d["creado"],
                    len(d["casos"]),
                    con_cambios,
                    json.dumps(d, ensure_ascii=False),
                ),
            )

    def diff(self, diff_id: str) -> dict:
        with closing(self._con()) as con:
            r = con.execute("SELECT datos FROM diffs WHERE id = ?", (diff_id,)).fetchone()
        if r is None:
            raise KeyError(diff_id)
        return json.loads(r["datos"])

    def listar_diffs(self, proyecto: str) -> list[dict]:
        """Resumen (sin el detalle por caso) del más nuevo al más viejo."""
        with closing(self._con()) as con:
            filas = con.execute(
                "SELECT id, proyecto, base, nueva, creado, total, con_cambios FROM diffs"
                " WHERE proyecto = ? ORDER BY creado DESC",
                (proyecto,),
            ).fetchall()
        return [dict(f) for f in filas]

    # --- lectura ---
    def listar_corridas(self) -> list[ResumenCorrida]:
        # El costo es el de uso_llm si hay registros; si no, el fijado al cerrar la corrida.
        sql = """
            SELECT c.id, c.objetivo, c.ref, c.estado, c.inicio, c.fin, c.n_personas,
                   (SELECT COUNT(*) FROM hallazgos h WHERE h.corrida_id = c.id) AS n_hallazgos,
                   COALESCE((SELECT SUM(costo_usd) FROM uso_llm u WHERE u.corrida_id = c.id),
                            c.costo_usd) AS costo_usd
            FROM corridas c ORDER BY c.inicio DESC
        """
        with closing(self._con()) as con:
            return [ResumenCorrida(**dict(r)) for r in con.execute(sql)]

    def ejecucion(self, ejecucion_id: str) -> Ejecucion:
        with closing(self._con()) as con:
            r = con.execute(
                "SELECT corrida_id FROM ejecuciones WHERE id = ?", (ejecucion_id,)
            ).fetchone()
        if r is None:
            raise KeyError(ejecucion_id)
        ruta = self.dir_ejecucion(r["corrida_id"], ejecucion_id) / "historial.json"
        return Ejecucion.model_validate_json(ruta.read_text())

    def hallazgo(self, hallazgo_id: str) -> Hallazgo:
        with closing(self._con()) as con:
            r = con.execute(
                "SELECT corrida_id FROM hallazgos WHERE id = ?", (hallazgo_id,)
            ).fetchone()
        if r is None:
            raise KeyError(hallazgo_id)
        datos = json.loads((self.dir_corrida(r["corrida_id"]) / "hallazgos.json").read_text())
        return Hallazgo.model_validate(datos[int(hallazgo_id.rsplit("-H", 1)[1]) - 1])
