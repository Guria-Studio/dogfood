"""Oráculo (FR-13, D4): compara los números de predicts con el `verdad.json` del dataset.

Por cada análisis `listo` de las cuentas de las ejecuciones trae el análisis, sus métricas y los
resultados (`recompra`, `ciclos`, `riesgo`) y el CSV de recordatorios, y los cruza con la verdad:

- **exactos** (gravedad alta): historia insuficiente sin fecha, rango `fecha_min ≤ fecha_probable
  ≤ fecha_max` y `0 ≤ p ≤ 1`, `n_compras` y `dias_desde_ultima` iguales a los de la verdad, y el
  CSV exportado igual al panel;
- **estadísticos** (gravedad media, con tolerancias de `dogfood.yaml`): ciclo por par, ciclo
  mediano por producto, MAE de backtest, precision@k contra la línea base y riesgo de abandono.

La firma de cada hallazgo es `chequeo|tipo de análisis`; el título nombra el chequeo, nunca las
cifras, para que la huella sea la misma entre corridas.
"""

import csv
import io
import json
import logging
import statistics
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

from dogfood.config import Config, Tolerancias
from dogfood.datos.defectos import defectos_que_rompen_verdad
from dogfood.datos.perfiles import PERFILES
from dogfood.dominio import (
    ContextoDeteccion,
    DatasetSintetico,
    Ejecucion,
    Evidencia,
    Gravedad,
    Hallazgo,
    Persona,
    TipoHallazgo,
)
from dogfood.objetivos.predicts.cliente import ErrorSesion

log = logging.getLogger("dogfood")

MAX_NO_RECONOCIDOS = 0.10
CICLO_PRODUCTO_ERR = 0.20
PRECISION_MARGEN = 0.05
RIESGO_PRECISION_MIN = 0.60
RIESGO_COBERTURA_MIN = 0.50
RIESGO_COMPRAS_MIN = 4
MIN_MUESTRA = 5  # por debajo, un porcentaje no dice nada: el chequeo estadístico no corre
MIN_PARES_PRODUCTO = 3
# Alteran filas sueltas (un cliente anónimo, una fecha corrida): los conteos exactos por par
# dejan de coincidir con la verdad aunque predicts esté bien.
_ALTERAN_FILAS = {"ids_vacios", "fechas_futuras"}

TITULOS = {
    "productos_no_reconocidos": "Productos no reconocidos al cruzar con la verdad",
    "historia_insuficiente": "Par con historia insuficiente recibe fecha probable",
    "rango": "Fecha probable fuera de su rango o probabilidad fuera de [0, 1]",
    "n_compras": "n_compras distinto de los días de compra reales",
    "dias_desde_ultima": "dias_desde_ultima no coincide con la última compra",
    "exportacion": "El CSV exportado no coincide con los resultados del panel",
    "ciclo_pares": "Ciclo por par lejos del ciclo real",
    "ciclo_producto": "Ciclo mediano por producto lejos del real",
    "mae_backtest": "MAE de backtest declarado no coincide con el recalculado",
    "precision_linea_base": "El modelo es peor que la línea base en precision@k",
    "riesgo_precision": "Clientes en riesgo de tienda que no abandonaron",
    "riesgo_cobertura": "Clientes que abandonaron y no aparecen en riesgo",
}


def verificar(ctx: ContextoDeteccion, tolerancias: Tolerancias | None = None) -> list[Hallazgo]:
    tol = tolerancias or _tolerancias()
    hallazgos: list[Hallazgo] = []
    vistos: set[str] = set()
    for e in ctx.ejecuciones:
        ds = ctx.datasets.get(e.dataset_id or "")
        persona = _persona(ds, e) if ds else None
        if ds is None or persona is None:
            continue
        try:
            cliente = ctx.cliente_api(persona)
        except (httpx.HTTPError, ErrorSesion) as exc:
            log.warning("oráculo: sin sesión para %s: %s", persona.id, exc)
            continue
        try:
            for analisis_id in _analisis_listos(cliente):
                if analisis_id in vistos:
                    continue
                vistos.add(analisis_id)
                hallazgos += _Comparacion(ctx, e, ds, cliente, analisis_id, tol).correr()
        except (httpx.HTTPError, ErrorSesion) as exc:
            log.warning("oráculo: falló la API para %s: %s", persona.id, exc)
        finally:
            if hasattr(cliente, "close"):
                cliente.close()
    return hallazgos


def _tolerancias() -> Tolerancias:
    try:
        return Config.cargar().tolerancias
    except (OSError, ValueError, AttributeError):
        return Tolerancias()


def _persona(ds: DatasetSintetico, e: Ejecucion) -> Persona | None:
    # `runs/<corrida>/datos/<dataset>/verdad.json` → `runs/<corrida>/personas.json` (almacen.py)
    ruta = Path(ds.ruta_verdad).parents[2] / "personas.json"
    if not ruta.exists():
        return None
    return next(
        (
            Persona.model_validate(p)
            for p in json.loads(ruta.read_text())
            if p["id"] == e.persona_id
        ),
        None,
    )


def _analisis_listos(cliente) -> list[str]:
    # ponytail: una persona = un dataset; si una cuenta sube varios datasets distintos, todos sus
    # análisis se comparan con el de la ejecución. Cruzar por nombre de archivo si hace falta.
    return [
        a["id"]
        for p in cliente.proyectos()
        for d in cliente.datasets(p["id"])
        for a in cliente.analisis_de(d["id"])
        if a.get("estado") == "listo"
    ]


def _norm(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto))
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def _fecha(v) -> date | None:
    return date.fromisoformat(str(v)[:10]) if v not in (None, "") else None


def _media(metricas: dict, metodo: str, campo: str) -> float | None:
    return ((metricas.get(metodo) or {}).get(campo) or {}).get("media")


class _Comparacion:
    def __init__(self, ctx, ejecucion, ds, cliente, analisis_id, tol: Tolerancias):
        self.ctx, self.e, self.tol = ctx, ejecucion, tol
        self.cliente, self.analisis_id = cliente, analisis_id
        self.verdad = json.loads(Path(ds.ruta_verdad).read_text("utf-8"))
        self.hallazgos: list[Hallazgo] = []

    # --- hallazgos ---
    def _hallazgo(self, chequeo, tipo, gravedad, descripcion, esperado=None, obtenido=None,
                  pantalla="resultados", extracto=""):  # fmt: skip
        h = Hallazgo(
            tipo=TipoHallazgo.logica,
            gravedad=gravedad,
            pantalla=pantalla,
            titulo=f"{TITULOS[chequeo]} ({tipo})",
            descripcion=f"Análisis {self.analisis_id}: {descripcion}",
            evidencia=[Evidencia(tipo="texto", extracto=extracto)] if extracto else [],
            esperado=esperado,
            obtenido=obtenido,
            ejecucion_id=self.e.id,
            semilla=self.ctx.corrida.semilla,
            commit=self.ctx.instancia.commit,
        )
        h.huella = h.calcular_huella(f"{chequeo}|{tipo}")
        self.hallazgos.append(h)

    def _exacto(self, chequeo, tipo, violaciones: list[tuple[dict, str, str]], total: int,
                pantalla="resultados"):  # fmt: skip
        if not violaciones:
            return
        fila, esperado, obtenido = violaciones[0]
        par = f"cliente {fila.get('cliente_id')}, producto {fila.get('producto_id')}"
        self._hallazgo(
            chequeo, tipo, Gravedad.alta,
            f"{len(violaciones)} de {total} filas violan el chequeo; ejemplo: {par}.",
            esperado, obtenido, pantalla, extracto=json.dumps(fila, default=str)[:1000],
        )  # fmt: skip

    # --- correspondencia ---
    def _indice_productos(self) -> dict[str, str]:
        """clave normalizada (SKU, EAN, nombre, id) → `producto_id` de la verdad."""
        indice: dict[str, str] = {}
        perfil = PERFILES.get(self.verdad.get("perfil", ""))
        for p in perfil.productos if perfil else ():
            for clave in (p.sku, p.ean, p.ean.lstrip("0"), p.nombre_pt, p.nombre_es, p.id):
                indice[_norm(clave)] = p.id
        for c in self.verdad["clientes"]:
            for par in c["pares"]:
                for clave in (par.get("sku"), par["producto_id"]):
                    if clave:
                        indice.setdefault(_norm(clave), par["producto_id"])
        return indice

    def _producto(self, fila: dict) -> str | None:
        for clave in (fila.get("producto_id"), fila.get("producto_nombre")):
            if clave and (pid := self.indice.get(_norm(clave))):
                return pid
        return None

    def _par(self, fila: dict) -> dict | None:
        pid = self._producto(fila)
        return self.pares.get((fila.get("cliente_id"), pid)) if pid else None

    # --- flujo ---
    def correr(self) -> list[Hallazgo]:
        a = self.cliente.analisis(self.analisis_id)
        tipos = [t for t in ("recompra", "ciclos", "riesgo") if t in (a.get("tipos") or [])]
        res = {t: self.cliente.resultados(self.analisis_id, t) for t in tipos}
        resumen, metricas = a.get("resumen") or {}, a.get("metricas") or {}

        # Chequeos internos: no dependen de la verdad, corren siempre.
        if "recompra" in res:
            self._rango(res["recompra"])
            self._exportacion(res["recompra"])

        defectos = set(self.verdad.get("defectos") or [])
        if defectos & set(defectos_que_rompen_verdad()):
            return self.hallazgos

        self.indice = self._indice_productos()
        self.clientes = {c["cliente_id"]: c for c in self.verdad["clientes"]}
        self.pares = {
            (c["cliente_id"], p["producto_id"]): p
            for c in self.verdad["clientes"]
            for p in c["pares"]
        }
        self._no_reconocidos(res)

        params = resumen.get("parametros") or {}
        min_compras = (
            params.get("min_compras")
            or self.ctx.instancia.parametros.get("MIN_COMPRAS")
            or self.verdad["parametros"]["MIN_COMPRAS"]
        )
        fecha_ref = _fecha(resumen.get("fecha_ref"))
        conteos_fiables = not (
            defectos & _ALTERAN_FILAS or params.get("desde") or params.get("hasta")
        )

        if "recompra" in res:
            filas = res["recompra"]
            self._historia_insuficiente(filas, int(min_compras))
            self._ciclo_pares(filas)
            self._mae(filas, metricas, fecha_ref)
            if not defectos:
                self._precision(metricas)
        for t in ("recompra", "riesgo"):
            filas = [f for f in res.get(t, []) if f.get("producto_id") is not None]
            if conteos_fiables and filas:
                self._n_compras(t, filas)
                if fecha_ref:
                    self._dias_desde_ultima(t, filas, fecha_ref)
        if "ciclos" in res:
            self._ciclo_producto(res["ciclos"])
        if "riesgo" in res:
            self._riesgo(res["riesgo"])
        return self.hallazgos

    def _no_reconocidos(self, res: dict[str, list[dict]]) -> None:
        productos = {
            f["producto_id"]: f
            for filas in res.values()
            for f in filas
            if f.get("producto_id") is not None
        }
        if not productos:
            return
        fuera = [pid for pid, f in productos.items() if self._producto(f) is None]
        grupos = sum(str(pid).startswith("grupo:") for pid in productos)
        if len(fuera) / len(productos) > MAX_NO_RECONOCIDOS:
            self._hallazgo(
                "productos_no_reconocidos", "analisis", Gravedad.media,
                f"{len(fuera)} de {len(productos)} productos de predicts no se pudieron unir con "
                f"la verdad por SKU, EAN o nombre ({grupos} son grupos); no se comparan.",
                f"≤ {MAX_NO_RECONOCIDOS:.0%} sin reconocer", f"{len(fuera) / len(productos):.0%}",
                extracto=", ".join(map(str, fuera[:20])),
            )  # fmt: skip

    # --- exactos ---
    def _historia_insuficiente(self, filas: list[dict], min_compras: int) -> None:
        malas = []
        for f in filas:
            par = self._par(f)
            if par and par["n_compras"] < min_compras and f.get("fecha_probable"):
                malas.append((f, f"sin fecha ({par['n_compras']} < {min_compras} compras)",
                              str(f["fecha_probable"])))  # fmt: skip
        self._exacto("historia_insuficiente", "recompra", malas, len(filas))

    def _rango(self, filas: list[dict]) -> None:
        malas = []
        for f in filas:
            fp, fmin, fmax = (
                _fecha(f.get(k)) for k in ("fecha_probable", "fecha_min", "fecha_max")
            )
            p = f.get("p")
            if fp and not (fmin and fmax and fmin <= fp <= fmax):
                malas.append(
                    (f, "fecha_min ≤ fecha_probable ≤ fecha_max", f"{fmin} / {fp} / {fmax}")
                )
            elif p is not None and not 0 <= p <= 1:
                malas.append((f, "0 ≤ p ≤ 1", str(p)))
        self._exacto("rango", "recompra", malas, len(filas))

    def _n_compras(self, tipo: str, filas: list[dict]) -> None:
        malas = [
            (f, str(par["n_compras"]), str(f.get("n_compras")))
            for f in filas
            if (par := self._par(f)) and f.get("n_compras") is not None
            and int(f["n_compras"]) != par["n_compras"]
        ]  # fmt: skip
        self._exacto("n_compras", tipo, malas, len(filas))

    def _dias_desde_ultima(self, tipo: str, filas: list[dict], fecha_ref: date) -> None:
        malas = []
        for f in filas:
            par = self._par(f)
            if not par or f.get("dias_desde_ultima") is None:
                continue
            esperado = max((fecha_ref - date.fromisoformat(par["ultima_compra"])).days, 0)
            if int(f["dias_desde_ultima"]) != esperado:
                malas.append((f, f"{esperado} (última {par['ultima_compra']}, ref {fecha_ref})",
                              str(f["dias_desde_ultima"])))  # fmt: skip
        self._exacto("dias_desde_ultima", tipo, malas, len(filas))

    def _exportacion(self, filas: list[dict]) -> None:
        try:
            crudo = self.cliente.exportar(self.analisis_id, "recordatorios")
        except httpx.HTTPStatusError as exc:
            log.warning("oráculo: no se pudo exportar %s: %s", self.analisis_id, exc)
            return
        _, *export = list(csv.reader(io.StringIO(crudo.decode("utf-8-sig"))))
        # El export solo trae los clientes con `contactar = sí`, pero de esos, todas sus filas.
        csv_por_cliente: dict[str, set] = defaultdict(set)
        for r in export:
            if len(r) >= 4:
                csv_por_cliente[r[0]].add((r[1], str(_fecha(r[3]))))
        panel_por_cliente: dict[str, set] = defaultdict(set)
        for f in filas:
            clave = (str(f.get("producto_id")), str(_fecha(f.get("fecha_probable"))))
            panel_por_cliente[str(f.get("cliente_id"))].add(clave)
        malas = []
        for cid, en_csv in csv_por_cliente.items():
            en_panel = panel_por_cliente.get(cid, set())
            if en_csv != en_panel:
                ejemplo = min(en_csv ^ en_panel)
                malas.append((
                    {"cliente_id": cid, "producto_id": ejemplo[0], "fecha_probable": ejemplo[1]},
                    f"{len(en_panel)} filas como en resultados(recompra)",
                    f"{len(en_csv)} filas en el CSV",
                ))  # fmt: skip
        self._exacto("exportacion", "recompra", malas, len(csv_por_cliente), "exportar")

    # --- estadísticos ---
    def _estadistico(self, chequeo, tipo, descripcion, esperado, obtenido, extracto=""):
        self._hallazgo(chequeo, tipo, Gravedad.media, descripcion, esperado, obtenido,
                       extracto=extracto)  # fmt: skip

    def _ciclo_pares(self, filas: list[dict]) -> None:
        errores = []
        for f in filas:
            par = self._par(f)
            real = par and par.get("ciclo_real_dias")
            if real and par["n_compras"] >= self.tol.compras_min_par and f.get("ciclo") is not None:
                errores.append(abs(float(f["ciclo"]) - real) / real)
        if len(errores) < MIN_MUESTRA:
            return
        ok = sum(e <= self.tol.ciclo_relativo_max for e in errores) / len(errores)
        if ok < self.tol.pares_ok_min:
            self._estadistico(
                "ciclo_pares", "recompra",
                f"de {len(errores)} pares con {self.tol.compras_min_par}+ compras, solo {ok:.0%} "
                f"tienen el ciclo a ±{self.tol.ciclo_relativo_max:.0%} del real "
                f"(error mediano {statistics.median(errores):.0%}).",
                f"≥ {self.tol.pares_ok_min:.0%} de los pares", f"{ok:.0%}",
            )  # fmt: skip

    def _ciclo_producto(self, filas: list[dict]) -> None:
        reales: dict[str, list[float]] = defaultdict(list)
        for (_, pid), par in self.pares.items():
            if par.get("ciclo_real_dias"):
                reales[pid].append(par["ciclo_real_dias"])
        malos, n = [], 0
        for f in filas:
            pid = self._producto(f)
            if not pid or len(reales[pid]) < MIN_PARES_PRODUCTO or f.get("ciclo_mediano") is None:
                continue
            n += 1
            real = statistics.median(reales[pid])
            if abs(float(f["ciclo_mediano"]) - real) / real > CICLO_PRODUCTO_ERR:
                malos.append(f"{f['producto_id']}: {float(f['ciclo_mediano']):.1f} vs {real:.1f}")
        if malos:
            self._estadistico(
                "ciclo_producto", "ciclos",
                f"{len(malos)} de {n} productos tienen el ciclo mediano a más de "
                f"±{CICLO_PRODUCTO_ERR:.0%} de la mediana real.",
                f"a ±{CICLO_PRODUCTO_ERR:.0%} de la mediana real", malos[0],
                extracto="; ".join(malos[:20]),
            )  # fmt: skip

    def _mae(self, filas: list[dict], metricas: dict, fecha_ref: date | None) -> None:
        declarado = _media(metricas, "modelo", "mae_dias")
        horizonte = metricas.get("horizonte")
        if declarado is None or not horizonte or not fecha_ref:
            return
        # ponytail: el backtest de predicts mide ventanas pasadas con compras reales; dogfood no
        # ve sus predicciones de entonces y mide la predicción actual contra `proxima_compra`
        # de la verdad, solo en los pares cuya próxima compra cae en `(fecha_ref, +horizonte]`.
        errores = []
        for f in filas:
            par, fp = self._par(f), _fecha(f.get("fecha_probable"))
            proxima = _fecha(par.get("proxima_compra")) if par else None
            if fp and proxima and 0 < (proxima - fecha_ref).days <= horizonte:
                errores.append(abs((fp - proxima).days))
        if len(errores) < MIN_MUESTRA:
            return
        mae = sum(errores) / len(errores)
        if abs(mae - declarado) > self.tol.mae_dias_delta:
            self._estadistico(
                "mae_backtest", "recompra",
                f"predicts declara mae_dias={declarado:.2f}; dogfood recalcula {mae:.2f} sobre "
                f"{len(errores)} pares con compra real en los próximos {horizonte} días.",
                f"{mae:.2f} ± {self.tol.mae_dias_delta}", f"{declarado:.2f}",
            )  # fmt: skip

    def _precision(self, metricas: dict) -> None:
        modelo = _media(metricas, "modelo", "precision_at_k")
        base = _media(metricas, "linea_base", "precision_at_k")
        if modelo is not None and base is not None and modelo < base - PRECISION_MARGEN:
            self._estadistico(
                "precision_linea_base", "recompra",
                f"precision@k del modelo {modelo:.3f} contra {base:.3f} de la línea base, en "
                "datos sin defectos.",
                f"≥ {base - PRECISION_MARGEN:.3f}", f"{modelo:.3f}",
            )  # fmt: skip

    def _riesgo(self, filas: list[dict]) -> None:
        # predicts no tiene «nivel alto»: el nivel más fuerte es `tienda` (dejó de comprar todo).
        alto = {f["cliente_id"] for f in filas if f.get("nivel") == "tienda"} & set(self.clientes)
        if len(alto) >= MIN_MUESTRA:
            abandonaron = sum(bool(self.clientes[c].get("abandono_desde")) for c in alto)
            ratio = abandonaron / len(alto)
            if ratio < RIESGO_PRECISION_MIN:
                self._estadistico(
                    "riesgo_precision", "riesgo",
                    f"de {len(alto)} clientes en riesgo de tienda, {abandonaron} abandonaron.",
                    f"≥ {RIESGO_PRECISION_MIN:.0%}", f"{ratio:.0%}",
                )  # fmt: skip
        en_riesgo = {f["cliente_id"] for f in filas}
        abandonos = [
            cid
            for cid, c in self.clientes.items()
            if c.get("abandono_desde")
            and sum(p["n_compras"] for p in c["pares"] if not p.get("durable"))
            >= RIESGO_COMPRAS_MIN
        ]
        if len(abandonos) >= MIN_MUESTRA:
            vistos = sum(c in en_riesgo for c in abandonos)
            ratio = vistos / len(abandonos)
            if ratio < RIESGO_COBERTURA_MIN:
                faltan = [c for c in abandonos if c not in en_riesgo]
                self._estadistico(
                    "riesgo_cobertura", "riesgo",
                    f"de {len(abandonos)} clientes que abandonaron con {RIESGO_COMPRAS_MIN}+ "
                    f"compras, solo {vistos} aparecen en riesgo.",
                    f"≥ {RIESGO_COBERTURA_MIN:.0%}", f"{ratio:.0%}",
                    extracto=", ".join(faltan[:20]),
                )  # fmt: skip
