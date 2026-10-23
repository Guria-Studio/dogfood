"""Orquestador de una corrida: entorno → datos → personas → asignación → ejecuciones → detectores."""

import logging
import secrets
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
    Idioma,
    Instancia,
    Intencion,
    Persona,
)
from dogfood.llm import ContadorUso, cliente_para, completar_json
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.base import Objetivo

log = logging.getLogger("dogfood")

FECHA_MAX = date(2026, 6, 30)


@dataclass
class Opciones:
    objetivo: str = "predicts"
    ref: str = "main"
    personas: int = 1
    escenarios: list[str] | None = None
    semilla: int | None = None
    repeat: int = 1
    mantener_entorno: bool = False
    sin_publicar: bool = False  # ponytail: se acepta; la publicación llega en F4
    tope_usd: float | None = None
    raiz: Path = field(default_factory=lambda: Path("runs"))
    # Inyectables (tests): por defecto salen de la config y del registro de objetivos.
    cfg: Config | None = None
    objetivo_obj: Objetivo | None = None
    llm: Any = None
    juez: Any = None


def persona_por_defecto(semilla: int, i: int) -> Persona:
    """Persona fija y válida. ponytail: F2.4.T1 la reemplaza por el generador."""
    return Persona(
        id=f"P{i + 1}",
        nombre=f"Persona {i + 1}",
        email=f"persona{i + 1}-{semilla}@dogfood.test",
        contrasena=f"Dogfood-{semilla}-{i + 1}!",
        empresa=f"Empresa {i + 1}",
        rubro="farmacia",
        idioma=Idioma.pt_BR,
        destreza=5,
        paciencia=5,
        intencion=Intencion.analisis_completo,
        semilla=semilla + i,
    )


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

        personas = [persona_por_defecto(semilla, i) for i in range(op.personas)]
        almacen.guardar_personas(corrida.id, personas)
        pares = esc.asignar(personas, todos, semilla) * op.repeat

        llm = op.llm or cliente_para("persona", cfg=cfg)

        async def juez(prompt, esquema):
            return await completar_json("juez", prompt, esquema, cfg, contador)

        ejecuciones: list[Ejecucion] = []
        for n, (persona, escenario) in enumerate(pares, 1):  # ponytail: serie hasta F2.4
            ds = datasets[_clave(escenario)] if escenario.datos else None
            e = await navegador.ejecutar(
                persona,
                escenario,
                instancia,
                ds,
                almacen.dir_ejecucion(corrida.id, f"{corrida.id}-E{n}"),
                llm,
                op.juez or juez,
                objetivo=objetivo,
                contador=contador,
            )
            almacen.guardar_ejecucion(corrida.id, e)
            ejecuciones.append(e)
            if op.tope_usd is not None and sum(u.costo_usd for u in contador.usos) >= op.tope_usd:
                log.warning("tope de %s USD alcanzado; corto la corrida", op.tope_usd)
                break

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
        almacen.guardar_hallazgos(corrida.id, deteccion.ejecutar_detectores(ctx))
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
        corrida.estado = estado
        corrida.fin = datetime.now().astimezone()
        almacen.cerrar_corrida(corrida.id, estado, sum(u.costo_usd for u in contador.usos))
        (almacen.dir_corrida(corrida.id) / "corrida.json").write_text(
            corrida.model_dump_json(indent=2)
        )
    return corrida
