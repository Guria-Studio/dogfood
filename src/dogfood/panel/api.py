"""API JSON del panel: los mismos datos que arman las plantillas, tipados para el frontend."""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dogfood import proyectos
from dogfood.config import Config
from dogfood.dominio import EventoConsola, EventoRed, Gravedad, TipoHallazgo
from dogfood.drivers import adb_red
from dogfood.drivers.android import AdbError
from dogfood.panel import consultas, detalle, issue


class Opcion(BaseModel):
    valor: str
    etiqueta: str


class ResumenYComparacion(BaseModel):
    resumen: consultas.ResumenCorridaPanel
    comparacion: list[consultas.FilaComparacion]


class PasoVista(BaseModel):
    n: int
    url: str
    pantalla: str
    accion: str
    captura: str | None
    razonamiento: str
    paso_contrato: str
    esperado: str
    observado: str
    consola: list[EventoConsola]
    red: list[EventoRed]


class FriccionVista(BaseModel):
    texto: str
    severidad: Gravedad
    pantalla: str
    cita: str
    captura: str | None


class PersonaVista(BaseModel):  # sin email ni contraseña
    id: str
    nombre: str
    empresa: str
    rubro: str
    idioma: str
    destreza: int
    paciencia: int
    intencion: str
    estilo: list[str]


class CorridaVista(BaseModel):
    id: str
    objetivo: str
    ref: str
    commit: str
    version: str
    inicio: datetime
    estado: str


class EjecucionVista(BaseModel):
    id: str
    persona_id: str
    escenario_id: str
    modelo: str
    estado: str
    driver: str
    motor: str
    backend: str
    resultado: str
    duracion_s: float
    motivo_juez: str
    notas: list[str]


class DetalleEjecucion(BaseModel):
    ejecucion: EjecucionVista
    corrida: CorridaVista
    persona: PersonaVista
    pasos: list[PasoVista]
    consola: list[EventoConsola]
    red: list[EventoRed]
    fricciones: dict[str, list[FriccionVista]]
    video: str | None
    trace: str | None
    logcat: str


class FilaCorrida(BaseModel):
    id: str
    estado: str
    entorno: str  # el ref de la corrida
    pasaron: int
    total: int
    costo_usd: float
    duracion_s: float | None
    inicio: str


class Dispositivo(BaseModel):
    id: str
    nombre: str
    plataforma: str
    estado: str
    permitido: bool
    motivo: str


class IssueCreado(BaseModel):
    url: str | None
    accion: str
    aviso: str


class ErrorApi(BaseModel):
    codigo: str
    detalle: str


def _detalle(d: dict) -> DetalleEjecucion:
    e, c, p = d["e"], d["corrida"], d["persona"]
    return DetalleEjecucion(
        ejecucion=EjecucionVista(**e.model_dump(include=set(EjecucionVista.model_fields) - {"resultado"}),
                                 resultado=d["resultado"]),
        corrida=CorridaVista(**c.model_dump(include={"id", "objetivo", "ref", "commit", "inicio", "estado"}),
                             version=c.version_app or c.commit),
        persona=PersonaVista(**p.model_dump(include=set(PersonaVista.model_fields))),
        pasos=[
            PasoVista(**v["p"].model_dump(include=set(PasoVista.model_fields) - {"captura", "consola", "red"}),
                      captura=v["captura"], consola=v["consola"], red=v["red"])
            for v in d["pasos"]
        ],
        consola=d["consola"],
        red=d["red"],
        fricciones={
            pantalla: [
                FriccionVista(**x["f"].model_dump(include={"texto", "severidad", "pantalla", "cita"}),
                              captura=x["captura"])
                for x in fs
            ]
            for pantalla, fs in d["fricciones"].items()
        },
        video=d["video"],
        trace=d["trace"],
        logcat=d["logcat"],
    )  # fmt: skip


def _tarjetas(cfg: Config | None) -> list[Dispositivo]:
    try:
        androides = adb_red.listar()
    except (AdbError, OSError):  # sin adb o servidor caído: solo los nodos
        androides = []
    lista = [
        Dispositivo(
            id=d.serial,
            nombre=d.modelo or d.serial,
            plataforma="android",
            estado=d.estado,
            permitido=d.permitido,
            motivo=d.motivo,
        )
        for d in androides
    ]
    for nombre, nodo in (cfg.nodos if cfg else {}).items():
        lista.append(
            Dispositivo(
                id=f"ios-{nombre}",
                nombre=f"{nombre} ({nodo.usuario}@{nodo.host})",
                plataforma="ios",
                estado="configurado",
                permitido=True,
                motivo="",
            )
        )
    return lista


def registrar_api(app: FastAPI, raiz: Path, cfg: Config | None = None) -> None:
    raiz = Path(raiz)

    @app.get("/api/ejecuciones", response_model=list[consultas.FilaEjecucion])
    def api_ejecuciones(
        recorrido: str = "",
        resultado: str = "",
        version: str = "",
        persona: str = "",
        driver: str = "",
        motor: str = "",
    ):
        filtros = dict(  # noqa: C408
            recorrido=recorrido,
            resultado=resultado,
            version=version,
            persona=persona,
            driver=driver,
            motor=motor,
        )
        return consultas.ejecuciones(raiz, filtros)

    @app.get("/api/filtros", response_model=dict[str, list[Opcion]])
    def api_filtros():
        return {
            k: [Opcion(valor=v, etiqueta=e) for v, e in ops]
            for k, ops in consultas.opciones_filtro(raiz).items()
        }

    @app.get("/api/etiquetas", response_model=dict[str, str])
    def api_etiquetas():
        return consultas.ETIQUETAS

    @app.get("/api/proyectos/{slug}/corridas", response_model=list[FilaCorrida])
    def api_corridas_proyecto(slug: str, q: str = ""):
        p = proyectos.obtener(slug, raiz)
        if p is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")
        with closing(sqlite3.connect(raiz / "dogfood.db")) as con:
            con.row_factory = sqlite3.Row
            ids = con.execute(
                "SELECT id FROM corridas WHERE proyecto = ? OR (proyecto IS NULL AND objetivo = ?)"
                " ORDER BY inicio DESC",
                (p.slug, p.objetivo),
            ).fetchall()
        filas = []
        for (cid,) in ids:
            r = consultas.corrida(raiz, cid)
            if r is None:
                continue
            seg = (
                (datetime.fromisoformat(r.fin) - datetime.fromisoformat(r.inicio)).total_seconds()
                if r.fin
                else None
            )
            filas.append(
                FilaCorrida(
                    id=r.id, estado=r.estado, entorno=r.ref,
                    pasaron=r.por_resultado.get("aprobado", 0), total=r.ejecuciones,
                    costo_usd=r.costo_usd, duracion_s=seg or None, inicio=r.inicio,
                )
            )  # fmt: skip
        n = q.strip().lower()
        return [f for f in filas if not n or n in f"{f.id} {f.estado} {f.entorno}".lower()]

    @app.get("/api/corridas/{corrida_id}", response_model=ResumenYComparacion)
    def api_corrida(corrida_id: str):
        resumen = consultas.corrida(raiz, corrida_id)
        if resumen is None:
            raise HTTPException(404, f"corrida {corrida_id!r} no existe")
        return ResumenYComparacion(
            resumen=resumen, comparacion=consultas.comparacion_motores(raiz, corrida_id)
        )

    @app.get("/api/recorridos", response_model=list[consultas.Recorrido])
    def api_recorridos(objetivo: str = "predicts"):
        return consultas.recorridos(raiz, objetivo)

    @app.get("/api/ejecuciones/{ejecucion_id}", response_model=DetalleEjecucion)
    def api_ejecucion(ejecucion_id: str):
        return _detalle(detalle.datos_ejecucion(raiz, ejecucion_id))

    @app.post(
        "/api/ejecuciones/{ejecucion_id}/issue",
        response_model=IssueCreado,
        responses={403: {"model": ErrorApi}, 502: {"model": ErrorApi}},
    )
    def api_issue(
        request: Request,
        ejecucion_id: str,
        tipo: TipoHallazgo = TipoHallazgo.tecnico,
        gravedad: Gravedad = Gravedad.media,
        x_dogfood: str | None = Header(default=None),
    ):
        if x_dogfood != "1":  # un formulario de otro sitio no puede poner este header
            return JSONResponse(
                {"codigo": "falta_header", "detalle": "falta el header X-Dogfood: 1"}, 403
            )
        e, corrida, persona, carpeta = detalle._cargar(raiz, ejecucion_id)
        conf = getattr(request.app.state, "cfg", None) or cfg or Config.cargar()
        try:
            r = issue.publicar_issue(e, persona, corrida, conf, carpeta, tipo, gravedad)
        except Exception as exc:  # noqa: BLE001 - gh sin sesión, sin repo, sin red
            return JSONResponse(
                {"codigo": "publicar_fallo", "detalle": f"no se pudo publicar: {exc}"}, 502
            )
        return IssueCreado(url=r.issue_url, accion=r.accion, aviso=r.aviso)

    @app.get("/api/dispositivos", response_model=list[Dispositivo])
    def api_dispositivos():
        return _tarjetas(cfg)
