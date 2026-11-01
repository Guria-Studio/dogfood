"""Orquestador de una corrida: entorno → datos → personas → asignación → ejecuciones → detectores."""

import asyncio
import logging
import secrets
import socket
import time
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dogfood import contrato, deteccion, frames
from dogfood import escenarios as esc
from dogfood.agente import bucle, navegador
from dogfood.agente.navegador import ESCRITORIO, MOVIL
from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.datos.defectos import aplicar
from dogfood.datos.generador import generar
from dogfood.deterministico import ResultadoDeterministico
from dogfood.deterministico.corredor import CorredorFlutter, a_ejecucion
from dogfood.deterministico.generador import defines
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    Escenario,
    Instancia,
    Persona,
)
from dogfood.drivers.android import Adb, DriverAndroid
from dogfood.drivers.ios import DriverIos
from dogfood.drivers.web import DriverWeb
from dogfood.eventos import BUS_NULO, BusVivo, EventoVivo
from dogfood.llm import (
    ContadorUso,
    backend_para,
    cliente_para,
    completar_json,
    indice_modelo,
)
from dogfood.nodos.cliente import ClienteNodo, a_ejecucion_ios
from dogfood.nodos.protocolo import ResultadoTrabajo, Trabajo
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.base import Objetivo
from dogfood.objetivos.predicts import cuentas
from dogfood.personas.generador import generar as generar_personas
from dogfood.reporte import consistencia, issues, opinion, slack
from dogfood.vista.servidor import iniciar_vista

log = logging.getLogger("dogfood")

FECHA_MAX = date(2026, 6, 30)
ESPERA_MEMORIA_S = 300
ESPERA_VISTA_S = 5


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
    driver: str | None = None  # web | android; pisa el del escenario
    motor: str | None = None  # browser_use | bucle
    bus: BusVivo = BUS_NULO
    vista: bool = False
    vista_puerto: int | None = None  # por defecto, cfg.vista.puerto
    espera_vista_s: float = ESPERA_VISTA_S  # deja ver el resultado final


def _clave(e: Escenario) -> str:
    d = e.datos
    return "-".join([d.perfil, str(d.clientes), *d.defectos])


def _driver(nombre: str, cfg: Config, objetivo: Objetivo, instancia: Instancia, persona: Persona):
    if nombre == "android":
        p, d = instancia.parametros, cfg.driver
        adb = Adb(p.get("serial") or d.serial, p.get("host_puerto") or d.host_puerto)
        return DriverAndroid(
            adb,
            p.get("paquete") or d.paquete,
            d.actividad,
            grabar_video=cfg.pantalla.android != "screenrecord",
            umbral_cobertura=cfg.flutter.umbral_cobertura,
        )
    if nombre == "ios":
        p = instancia.parametros
        return DriverIos(
            p["appium_url"],
            p["udid"],
            p["bundle_id"],
            umbral_cobertura=cfg.flutter.umbral_cobertura,
        )
    movil = "movil" in persona.estilo
    return DriverWeb(
        instancia.base_url,
        lambda url: objetivo.url_permitida(url, instancia),
        MOVIL if movil else ESCRITORIO,
        movil,
        flutter=bool(instancia.parametros.get("flutter")),
        umbral_cobertura=cfg.flutter.umbral_cobertura,
    )


async def _determinista_ios(
    herramienta, cfg, instancia, persona, escenario, carpeta, ejecucion_id
) -> Ejecucion:
    """Patrol / integration_test en el Mac: el trabajo viaja por SSH (sin secretos en el escenario)."""
    p = instancia.parametros
    nodo = cfg.nodos[p["nodo"]]
    proyectos = nodo.proyectos
    nombre = cfg.flutter.proyecto.name if cfg.flutter.proyecto else None
    proyecto = (
        proyectos.get(nombre) if nombre in proyectos else next(iter(proyectos.values()), None)
    )
    if proyecto is None:
        r = ResultadoTrabajo(
            id=ejecucion_id, estado="error", mensaje="falta `nodos.<nodo>.proyectos` en la config"
        )
    else:
        try:
            trabajo = Trabajo(
                id=ejecucion_id,
                tipo="patrol",  # ponytail: el nodo corre Patrol; integration_test iOS sin tipo propio
                udid=p["udid"],
                bundle_id=p["bundle_id"],
                proyecto=proyecto,
                escenario=escenario,
                dart_defines=defines(escenario.deterministico, cfg),
                timeout_s=cfg.flutter.timeout_s,
            )
            r = await ClienteNodo(p["nodo"], nodo).enviar(trabajo, carpeta)
        except Exception as exc:  # noqa: BLE001 - un nodo caído no tumba la corrida
            log.warning("el nodo falló: %s", exc)
            r = ResultadoTrabajo(id=ejecucion_id, estado="error", mensaje=str(exc))
    return a_ejecucion_ios(r, persona, escenario, ejecucion_id, carpeta)


async def _determinista(
    herramienta, driver, cfg, instancia, persona, escenario, carpeta, ejecucion_id, bus, corrida_id
) -> Ejecucion:
    """FR-36: corre Patrol / integration_test en lugar del bucle; no usa LLM."""
    base = {
        "corrida_id": corrida_id,
        "ejecucion_id": ejecucion_id,
        "persona": persona.nombre,
        "escenario": escenario.id,
    }
    bus.publicar(EventoVivo(**base, tipo="inicio"))
    inicio = time.monotonic()
    if driver == "ios":
        e = await _determinista_ios(
            herramienta, cfg, instancia, persona, escenario, carpeta, ejecucion_id
        )
        e.duracion_s = round(time.monotonic() - inicio, 2)
        bus.publicar(EventoVivo(**base, tipo="fin", resultado=e.resultado))
        return e
    proyecto = cfg.flutter.proyecto
    if proyecto is None:
        det = carpeta / "deterministico"
        det.mkdir(parents=True, exist_ok=True)
        motivo = "falta `flutter.proyecto` en la config: no sé qué app Flutter probar"
        (det / "salida.log").write_text(motivo + "\n")
        r = ResultadoDeterministico(
            herramienta=herramienta, codigo_salida=-1, motivo="sin_proyecto", log=det / "salida.log"
        )
    else:
        p, d = instancia.parametros, cfg.driver
        adb = Adb(p.get("serial") or d.serial, p.get("host_puerto") or d.host_puerto)

        async def capturar(destino: Path) -> Path | None:
            try:
                destino.write_bytes(await adb.ejecutar("exec-out", "screencap", "-p", binario=True))
            except Exception as exc:  # noqa: BLE001 - la captura final no tumba el resultado
                log.warning("no pude capturar la pantalla final: %s", exc)
                return None
            return destino

        r = await CorredorFlutter(cfg).correr(
            escenario,
            herramienta,
            adb.destino,
            carpeta,
            proyecto=proyecto,
            capturar=capturar,
        )
    e = a_ejecucion(r, persona, escenario, ejecucion_id, driver)
    e.duracion_s = round(time.monotonic() - inicio, 2)
    bus.publicar(EventoVivo(**base, tipo="fin", resultado=e.resultado))
    return e


def _dataset(e: Escenario, semilla: int, almacen: Almacen, corrida_id: str) -> DatasetSintetico:
    d = e.datos
    ds_id = _clave(e)
    ds = generar(
        d.perfil, d.clientes, semilla, FECHA_MAX, salida=almacen.dir_dataset(corrida_id, ds_id)
    )
    ruta = aplicar(ds.ruta_csv, d.defectos, semilla) if d.defectos else ds.ruta_csv
    return ds.model_copy(update={"id": ds_id, "ruta_csv": ruta, "defectos": list(d.defectos)})


async def _arrancar_vista(cfg: Config, puerto: int | None) -> tuple[BusVivo, asyncio.Task | None]:
    """La vista nunca hace fallar la corrida: si no arranca, sigue con BUS_NULO."""
    host, puerto = cfg.vista.host, puerto or cfg.vista.puerto
    try:
        with socket.socket() as s:  # uvicorn hace sys.exit si el puerto está ocupado
            s.bind((host, puerto))
        bus = BusVivo()
        tarea = await iniciar_vista(bus, host, puerto)
        for _ in range(100):  # espera a que escuche
            try:
                _, w = await asyncio.open_connection(host, puerto)
                w.close()
                break
            except OSError:
                await asyncio.sleep(0.05)
    except (OSError, ValueError) as exc:
        log.warning("no pude abrir la vista en %s:%s (%s); sigo sin vista", host, puerto, exc)
        return BUS_NULO, None
    log.info("vista en vivo: http://%s:%s/", host, puerto)
    return bus, tarea


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
    bus = op.bus
    tarea_vista: asyncio.Task | None = None
    try:
        if op.vista:
            bus, tarea_vista = await _arrancar_vista(cfg, op.vista_puerto)
        instancia = objetivo.preparar(op.ref, corrida)
        corrida.commit = instancia.commit
        instancia.parametros.setdefault("umbral_cobertura", cfg.flutter.umbral_cobertura)
        corrida.version_app = instancia.parametros.get("version_app") or instancia.commit

        todos = objetivo.escenarios()
        if op.escenarios:
            todos = [e for e in todos if e.id in op.escenarios]
        datasets = {
            ds.id: ds
            for ds in (_dataset(e, semilla, almacen, corrida.id) for e in todos if e.datos)
        }

        personas = generar_personas(op.personas, semilla, op.idiomas)
        almacen.guardar_personas(corrida.id, personas)
        base = esc.asignar(personas, todos, semilla)
        # cada repetición necesita su propia cuenta: el email lleva el sufijo +r<k>
        pares = [
            (
                p.model_copy(update={"email": p.email.replace("@", f"+r{k}@", 1)})
                if op.repeat > 1
                else p,
                e,
            )
            for k in range(1, op.repeat + 1)
            for p, e in base
        ]

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
            carpeta = almacen.dir_ejecucion(corrida.id, f"{corrida.id}-E{n}")
            driver = op.driver or escenario.driver
            motor = op.motor or escenario.motor
            por_bucle = driver in ("android", "ios") or op.motor == "bucle"
            if not por_bucle and cfg.motores["persona"] == "claude_code":
                log.info(
                    "motores.persona=claude_code: browser-use necesita un cliente de chat por "
                    "API, uso el bucle propio con el driver web"
                )
                por_bucle = True
            if motor in ("patrol", "integration_test") and escenario.deterministico:
                e = await _determinista(
                    motor, driver, cfg, instancia, persona, escenario, carpeta,
                    f"{corrida.id}-E{n}", bus, corrida.id,
                )  # fmt: skip
            elif por_bucle:
                indice = indice_modelo("persona", n, semilla, cfg)
                drv = _driver(driver, cfg, objetivo, instancia, persona)
                e = await bucle.ejecutar(
                    persona,
                    escenario,
                    drv,
                    backend_para("persona", cfg, indice),
                    backend_para("juez", cfg),
                    carpeta,
                    cfg=cfg,
                    bus=bus,
                    corrida_id=corrida.id,
                    objetivo=objetivo,
                    fuente_frames=(
                        frames.crear_fuente(cfg, drv, instancia.parametros) if bus.activo else None
                    ),
                )
                m = e.metricas
                uso = contador.registrar(
                    "persona",
                    e.modelo,
                    m.tokens_in,
                    m.tokens_out,
                    e.id,
                    backend=e.backend,
                    costo_equivalente_usd=m.costo_equivalente_usd,
                )
                uso.costo_usd = m.costo_usd  # lo cobrado de verdad: 0 con el plan Max
            else:
                if bus.activo:  # sin vista no se pasa nada: los navegadores falsos no lo esperan
                    extra |= {"bus": bus, "corrida_id": corrida.id}
                e = await navegador.ejecutar(
                    persona,
                    escenario,
                    instancia,
                    ds,
                    carpeta,
                    llm_de(n),
                    op.juez or juez,
                    objetivo=objetivo,
                    contador=contador,
                    **extra,
                )
            if e.motor not in ("patrol", "integration_test"):  # el determinista ya trae el suyo
                e.resultado = contrato.resultado(e)
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
        if op.repeat > 1:
            consistencia.marcar_inestables(hallazgos, ejecuciones)
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
        if tarea_vista:
            await asyncio.sleep(op.espera_vista_s)
            tarea_vista.cancel()
            await asyncio.gather(tarea_vista, return_exceptions=True)
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
        almacen.cerrar_corrida(
            corrida.id, estado, sum(u.costo_usd for u in contador.usos), corrida.version_app
        )
        (almacen.dir_corrida(corrida.id) / "corrida.json").write_text(
            corrida.model_dump_json(indent=2)
        )
    return corrida
