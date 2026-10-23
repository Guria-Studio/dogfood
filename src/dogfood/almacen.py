"""Almacén de corridas: carpeta por corrida en `runs/` más el índice SQLite `runs/dogfood.db`."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from dogfood.dominio import Corrida, Ejecucion, Hallazgo, Persona, UsoLlm

VERSION_ESQUEMA = 1

# Esquema completo del MVP: las fases siguientes no lo cambian.
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
            if con.execute("PRAGMA user_version").fetchone()[0] < VERSION_ESQUEMA:
                con.executescript(ESQUEMA_V1)
                con.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")
                con.commit()

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
                'INSERT INTO corridas (id, objetivo, ref, "commit", semilla, inicio, fin, estado)'
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    corrida.id,
                    corrida.objetivo,
                    corrida.ref,
                    corrida.commit,
                    corrida.semilla,
                    corrida.inicio.isoformat(),
                    corrida.fin.isoformat() if corrida.fin else None,
                    corrida.estado,
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
        (d / "historial.json").write_text(e.model_dump_json(indent=2))
        for nombre, items in (("pasos", e.pasos), ("red", e.red), ("consola", e.consola)):
            (d / f"{nombre}.jsonl").write_text("".join(i.model_dump_json() + "\n" for i in items))
        with closing(self._con()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO ejecuciones (id, corrida_id, persona_id, escenario_id, modelo,"
                " estado, pasos, duracion_s, exito, motivo_juez) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

    def registrar_uso(self, uso: UsoLlm, corrida_id: str) -> None:
        with closing(self._con()) as con, con:
            con.execute(
                "INSERT INTO uso_llm (corrida_id, ejecucion_id, rol, modelo, tokens_in, tokens_out,"
                " costo_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    corrida_id,
                    uso.ejecucion_id,
                    uso.rol,
                    uso.modelo,
                    uso.tokens_in,
                    uso.tokens_out,
                    uso.costo_usd,
                ),
            )

    def cerrar_corrida(self, corrida_id: str, estado: str, costo: float) -> None:
        with closing(self._con()) as con, con:
            con.execute(
                "UPDATE corridas SET estado = ?, costo_usd = ?, fin = ? WHERE id = ?",
                (estado, costo, datetime.now().astimezone().isoformat(), corrida_id),
            )

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
