"""Orquestador de una corrida: entorno → datos → personas → asignación → ejecuciones → detectores."""

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dogfood import deteccion
from dogfood import escenarios as esc
from dogfood.agente import navegador
from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.datos.defectos import aplicar
from dogfood.datos.generador import generar
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    Escenario,
    Instancia,
    Persona,
)
from dogfood.llm import ContadorUso, cliente_para, completar_json, indice_modelo
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.base import Objetivo
from dogfood.objetivos.predicts import cuentas
from dogfood.personas.generador import generar as generar_personas
from dogfood.reporte import issues, opinion, slack

log = logging.getLogger("dogfood")

FECHA_MAX = date(2026, 6, 30)
ESPERA_MEMORIA_S = 300


def memoria_disponible_gb() -> float:
    for linea in Path("/proc/meminfo").read_text().splitlines():
        if linea.startswith("MemAvailable:"):
            return int(linea.split()[1]) / 1024**2
    return float("inf")  # ponytail: sin MemAvailable (no Linux) no se frena


class ErrorMemoria(Exception):
    pass


@dataclass
class Opciones:
    objetivo: str = "predicts"
    ref: str = "main"
    personas: int = 1
    escenarios: list[str] | None = None
    semilla: int | None = None
    repeat: int = 1
    mantener_entorno: bool = False
    sin_publicar: bool = False
    tope_usd: float | None = None
    raiz: Path = field(default_factory=lambda: Path("runs"))
    # Inyectables (tests): por defecto salen de la config y del registro de objetivos.
    cfg: Config | None = None
    objetivo_obj: Objetivo | None = None
    llm: Any = None
    juez: Any = None
    concurrencia: int | None = None  # por defecto, la de la config
    idiomas: dict[str, float] | None = None
    # Inyectables de la espera de memoria y del registro (tests).
    memoria_gb: Callable[[], float] = memoria_disponible_gb
    reloj: Callable[[], float] = time.monotonic
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep
    confirmar: Callable[[Instancia, Persona], str | None] | None = None


def _clave(e: Escenario) -> str:
    d = e.datos
    return "-".join([d.perfil, str(d.clientes), *d.defectos])


def _dataset(e: Escenario, semilla: int, almacen: Almacen, corrida_id: str) -> DatasetSintetico:
    d = e.datos
    ds_id = _clave(e)
    ds = generar(
        d.perfil, d.clientes, semilla, FECHA_MAX, salida=almacen.dir_dataset(corrida_id, ds_id)
    )
    ruta = aplicar(ds.ruta_csv, d.defectos, semilla) if d.defectos else ds.ruta_csv
    return ds.model_copy(update={"id": ds_id, "ruta_csv": ruta, "defectos": list(d.defectos)})


async def correr(op: Opciones) -> Corrida:
    cfg = op.cfg or Config.cargar()
    objetivo = op.objetivo_obj or cargar_objetivo(op.objetivo)
    almacen = Almacen(op.raiz)
    semilla = op.semilla if op.semilla is not None else secrets.randbelow(2**31)
    inicio = datetime.now().astimezone()
    corrida = Corrida(
        id=f"{inicio:%Y%m%d-%H%M%S}-{semilla}-{secrets.token_hex(2)}",
        objetivo=objetivo.nombre,
        ref=op.ref,
        commit="",
        semilla=semilla,
        inicio=inicio,
        estado="en_curso",
    )
    almacen.nueva_corrida(corrida)
    contador = ContadorUso(cfg)
    instancia: Instancia | None = None
    estado = "ok"
    avisos: list[str] = []
    try:
        instancia = objetivo.preparar(op.ref, corrida)
        corrida.commit = instancia.commit

        todos = objetivo.escenarios()
        if op.escenarios:
            todos = [e for e in todos if e.id in op.escenarios]
        datasets = {
            ds.id: ds
            for ds in (_dataset(e, semilla, almacen, corrida.id) for e in todos if e.datos)
        }

        personas = generar_personas(op.personas, semilla, op.idiomas)
        almacen.guardar_personas(corrida.id, personas)
        pares = esc.asignar(personas, todos, semilla) * op.repeat

        def llm_de(n: int):
            return op.llm or cliente_para("persona", indice_modelo("persona", n, semilla, cfg), cfg)

        async def juez(prompt, esquema):
            return await completar_json("juez", prompt, esquema, cfg, contador)

        confirmar = op.confirmar or (
            cuentas.confirmar_registro if objetivo.nombre == "predicts" else None
        )
        sem = asyncio.Semaphore(op.concurrencia or cfg.concurrencia)
        resultados: dict[int, Ejecucion] = {}

        async def esperar_memoria() -> None:
            desde = op.reloj()
            while op.memoria_gb() < cfg.memoria_libre_min_gb:
                if op.reloj() - desde >= ESPERA_MEMORIA_S:
                    raise ErrorMemoria
                await op.dormir(5)

        async def una(n: int, persona: Persona, escenario: Escenario) -> None:
            if op.tope_usd is not None and sum(u.costo_usd for u in contador.usos) >= op.tope_usd:
                corrida.parametros["motivo"] = "tope_usd"
                return
            await esperar_memoria()
            ds = datasets[_clave(escenario)] if escenario.datos else None
            extra = {}
            if objetivo.nombre == "predicts" and escenario.id == "recuperar-contrasena":
                extra["herramientas_extra"] = cuentas.herramientas_extra(instancia, persona)
            e = await navegador.ejecutar(
                persona,
                escenario,
                instancia,
                ds,
                almacen.dir_ejecucion(corrida.id, f"{corrida.id}-E{n}"),
                llm_de(n),
                op.juez or juez,
                objetivo=objetivo,
                contador=contador,
                **extra,
            )
            if escenario.carril == "login_fallido":
                esperados = [r for r in e.red if r.estado == 429 and "/auth/login" in r.url]
                if esperados:
                    e.red = [r for r in e.red if r not in esperados]
                    e.notas.append(f"429 esperado en /auth/login ({len(esperados)})")
            if confirmar:
                try:
                    e.empresa_id = await asyncio.to_thread(confirmar, instancia, persona)
                except Exception:
                    log.exception("no pude confirmar el registro de %s", persona.id)
            almacen.guardar_ejecucion(corrida.id, e)
            resultados[n] = e

        async def con_cupo(*args) -> None:
            async with sem:
                await una(*args)

        numeradas = [(n, p, e) for n, (p, e) in enumerate(pares, 1)]
        normales = [t for t in numeradas if t[2].carril != "login_fallido"]
        tareas = [asyncio.ensure_future(con_cupo(*t)) for t in normales]
        try:
            await asyncio.gather(*tareas)
            for t in numeradas:  # al final y de a una: el rate limit del login es global
                if t[2].carril == "login_fallido":
                    await una(*t)
        except BaseException:
            for t in tareas:
                t.cancel()
            await asyncio.gather(*tareas, return_exceptions=True)
            raise
        ejecuciones = [resultados[n] for n in sorted(resultados)]
        if op.tope_usd is not None and len(ejecuciones) < len(numeradas):
            log.warning("tope de %s USD alcanzado; corto la corrida", op.tope_usd)

        logs = objetivo.logs(instancia, corrida.inicio)
        for servicio, texto in logs.items():
            (almacen.dir_corrida(corrida.id) / "logs" / f"{servicio}.log").write_text(texto)

        from dogfood.objetivos.predicts.cliente import PredictsCliente  # ponytail: solo predicts

        ctx = ContextoDeteccion(
            corrida=corrida,
            instancia=instancia,
            ejecuciones=ejecuciones,
            datasets=datasets,
            cliente_api=lambda _persona: PredictsCliente(instancia.api_url),
            logs=logs,
        )
        hallazgos = deteccion.ejecutar_detectores(ctx)
        almacen.guardar_hallazgos(corrida.id, hallazgos)

        # Cierre: cada paso falla por separado. contar_uso_ia consulta el Postgres de la
        # instancia, así que va antes de destruirla (D12).
        @contextmanager
        def paso(nombre: str):
            try:
                yield
            except Exception:
                log.exception("falló %s en la corrida %s", nombre, corrida.id)
                avisos.append(nombre)

        uso_ia = None
        with paso("contar_uso_ia"):
            uso_ia = opinion.contar_uso_ia(instancia)
        secretos = [p.contrasena for p in personas]
        publicados: list[issues.ResultadoIssue] = []
        with paso("publicar"):
            publicados = issues.publicar(
                hallazgos,
                corrida,
                cfg,
                publicar=not op.sin_publicar,
                almacen=almacen,
                secretos=secretos,
            )
        costo = sum(u.costo_usd for u in contador.usos)
        ruta_reporte = None
        with paso("opinion"):
            ruta_reporte, _ = await opinion.generar(
                corrida,
                ejecuciones,
                hallazgos,
                personas,
                destino=almacen.dir_corrida(corrida.id),
                cfg=cfg,
                costo_dogfood_usd=costo,
                uso_ia=uso_ia,
                usos=contador.usos,
                issues={r.huella: r.issue_url for r in publicados if r.issue_url},
                bloqueados={r.huella for r in publicados if r.accion == "bloqueado_por_redaccion"},
            )
        with paso("slack"):
            slack.avisar(
                corrida,
                slack.Resumen(
                    personas=len(personas),
                    exitos=sum(1 for e in ejecuciones if e.exito),
                    hallazgos=hallazgos,
                    issues=publicados,
                    ruta_reporte=str(ruta_reporte or almacen.dir_corrida(corrida.id)),
                    costo_usd=costo,
                    duracion_s=(datetime.now().astimezone() - inicio).total_seconds(),
                ),
                cfg,
                secretos=secretos,
            )
        if ruta_reporte:
            print(f"Reporte: {ruta_reporte}")
        for r in publicados:
            if r.issue_url:
                print(f"Issue: {r.issue_url}")
    except ErrorMemoria:
        log.error("memoria libre bajo el mínimo por %s s; aborto la corrida", ESPERA_MEMORIA_S)
        corrida.parametros["motivo"] = "memoria"
        estado = "error"
    except Exception:
        log.exception("la corrida %s falló", corrida.id)
        estado = "error"
    finally:
        for uso in contador.usos:
            almacen.registrar_uso(uso, corrida.id)
        if not op.mantener_entorno:
            # Si preparar falló no hay Instancia: destruir igual, con el proyecto por convención.
            try:
                objetivo.destruir(
                    instancia
                    or Instancia(
                        base_url="",
                        api_url="",
                        proyecto_compose=f"dogfood-{objetivo.nombre}",
                        commit="",
                    )
                )
            except Exception:
                log.exception("no pude destruir el entorno de %s", corrida.id)
        if estado == "ok" and avisos:
            estado = "ok_con_avisos"
            corrida.parametros["avisos"] = avisos
        corrida.estado = estado
        corrida.fin = datetime.now().astimezone()
        almacen.cerrar_corrida(corrida.id, estado, sum(u.costo_usd for u in contador.usos))
        (almacen.dir_corrida(corrida.id) / "corrida.json").write_text(
            corrida.model_dump_json(indent=2)
        )
    return corrida
