"""Genera un `runs/` de prueba para el e2e del panel: 1 corrida, 3 ejecuciones (una con 3 pasos)."""

import sys
from datetime import datetime
from pathlib import Path

from dogfood.almacen import Almacen
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    Evidencia,
    Hallazgo,
    MetricasEjecucion,
    Paso,
    Persona,
)
from dogfood.plan import CasoPrueba, PlanPruebas
from dogfood.reporte import sugerencia

# PNG de 1x1: basta para que la captura cargue.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082"
)


def _persona(id: str, nombre: str) -> Persona:
    return Persona(
        id=id, nombre=nombre, email=f"{id}@x.com", contrasena="pw", empresa="E", rubro="r",
        idioma="es", destreza=3, paciencia=3, intencion="explorar", semilla=1,
    )  # fmt: skip


def _ejecucion(a: Almacen, id: str, persona: str, esc: str, res: str, n_pasos: int) -> Ejecucion:
    d = a.dir_ejecucion("c1", id)
    pasos = []
    for n in range(1, n_pasos + 1):
        cap = d / "capturas" / f"{n}.png"
        cap.parent.mkdir(parents=True, exist_ok=True)
        cap.write_bytes(_PNG)
        pasos.append(
            Paso(
                n=n, url="http://app/login", pantalla="/login", accion=f"clic {n}", captura=cap,
                ts=datetime(2026, 1, 1), razonamiento=f"porque {n}", paso_contrato=f"contrato {n}",
                esperado=f"ver panel {n}", observado=f"observado {n}",
            )
        )  # fmt: skip
    return Ejecucion(
        id=id, persona_id=persona, escenario_id=esc, modelo="m", estado="ok", driver="web",
        motor="bucle", backend="api", resultado=res, exito=res == "aprobado", duracion_s=12,
        pasos=pasos,
        metricas=MetricasEjecucion(tokens_in=100, tokens_out=50, capturas=n_pasos, costo_usd=0.1),
    )  # fmt: skip


def preparar(raiz: Path) -> None:
    a = Almacen(raiz)
    a.nueva_corrida(
        Corrida(id="c1", objetivo="predicts", ref="main", commit="abc1234", semilla=1,
                inicio=datetime(2026, 1, 1), estado="completa", version_app="v1.0",
                parametros={"proyecto": "predicts"})
    )  # fmt: skip
    a.guardar_personas("c1", [_persona("p1", "Ana"), _persona("p2", "Bob")])
    for id, persona, esc, res, n in (
        ("e1", "p1", "demo", "aprobado", 1),
        ("e2", "p2", "login-fallido", "fallo", 3),
        ("e3", "p1", "login-fallido", "fallo", 1),
    ):
        a.guardar_ejecucion("c1", _ejecucion(a, id, persona, esc, res, n))
    _plan_y_hallazgos(a, raiz)


def _caso(esc: str, pid: str, nombre: str, prioridad: str, ejecuciones: list[str]) -> CasoPrueba:
    return CasoPrueba(
        id=f"{esc}:{pid}", titulo=f"{nombre} hace {esc}", escenario_id=esc, persona_id=pid,
        persona_nombre=nombre, objetivo=f"Lograr {esc}", criterio_exito="ve el resultado",
        prioridad=prioridad, superficies=[], ejecuciones=ejecuciones,
    )  # fmt: skip


def _plan_y_hallazgos(a: Almacen, raiz: Path) -> None:
    """Plan de 3 casos (1 pasa, 2 fallan) con un hallazgo y su sugerencia de arreglo."""
    plan = PlanPruebas(
        objetivo="predicts", semilla=1,
        casos=[
            _caso("demo", "p1", "Ana", "alta", ["e1"]),
            _caso("login-fallido", "p2", "Bob", "alta", ["e2"]),
            _caso("login-fallido", "p1", "Ana", "media", ["e3"]),
        ],
    )  # fmt: skip
    (raiz / "c1" / "plan.json").write_text(plan.model_dump_json())
    a.guardar_hallazgos("c1", [
        Hallazgo(
            tipo="logica", gravedad="alta", pantalla="/login", titulo="El login no avisa del error",
            descripcion="Muestra una pantalla en blanco", ejecucion_id="e2", semilla=1,
            commit="abc1234", esperado="Mensaje de error", obtenido="Pantalla en blanco",
            evidencia=[Evidencia(tipo="log", extracto="POST /login 500")],
        )
    ])  # fmt: skip
    sugerencia.guardar(raiz / "c1", {"c1-H1": sugerencia.Sugerencia(
        causa="El formulario ignora el 500 del servidor", cambio="Mostrar el mensaje de error",
        archivos=[sugerencia.ArchivoProbable(ruta="app/login.tsx", linea=42)],
    )})  # fmt: skip


if __name__ == "__main__":
    preparar(Path(sys.argv[1]))
