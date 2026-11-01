"""Sugerencia de causa y arreglo por hallazgo (F10.2.T2).

El LLM (rol `redactor`) solo ve la evidencia ya redactada y los fragmentos del repo del objetivo que
coinciden con ella (máx. 4 archivos, 200 líneas). Nunca afirma más de lo que la evidencia muestra:
sin fragmentos del repo la confianza es `baja`, y los archivos citados salen solo de lo encontrado.
"""

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from dogfood.config import Config
from dogfood.dominio import Evidencia, Hallazgo
from dogfood.llm import completar_json
from dogfood.reporte.redactar import redactar

MAX_ARCHIVOS = 4
MAX_LINEAS = 200
_RUTA = re.compile(r"(?<![\w:/.])/[\w\-./{}]*[\w}]")
Confianza = Literal["alta", "media", "baja"]


class ArchivoProbable(BaseModel):
    ruta: str
    linea: int | None = None


class Sugerencia(BaseModel):
    causa: str
    archivos: list[ArchivoProbable] = []
    cambio: str
    confianza: Confianza = "baja"


def _tokens(h: Hallazgo, evidencia: list[Evidencia]) -> list[str]:
    textos = [
        h.pantalla,
        h.titulo,
        h.descripcion,
        h.obtenido or "",
        *(e.extracto for e in evidencia),
    ]
    vistos: dict[str, None] = {}
    for t in textos:
        for r in _RUTA.findall(t):
            if len(r) > 2 and not r.startswith(("/home", "/mnt", "/tmp")):
                vistos[r] = None
    return list(vistos)[:8]


def _buscar(repo: Path, tokens: list[str]) -> dict[str, list[tuple[int, str]]]:
    """archivo → [(línea, texto)] de las coincidencias literales; `rg` si existe, si no `grep`."""
    rg = shutil.which("rg")
    excl = ["node_modules", ".git", "dist", ".venv"]
    hallado: dict[str, list[tuple[int, str]]] = {}
    for tok in tokens:
        if rg:
            cmd = [
                rg,
                "-n",
                "-F",
                "-m",
                "3",
                "--no-heading",
                *[a for d in excl for a in ("-g", f"!{d}")],
                "--",
                tok,
                ".",
            ]
        else:
            cmd = [
                "grep",
                "-rnIF",
                "-m",
                "3",
                *[f"--exclude-dir={d}" for d in excl],
                "--",
                tok,
                ".",
            ]
        try:
            salida = subprocess.run(
                cmd, check=False, cwd=repo, capture_output=True, text=True, timeout=30
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for linea in salida.splitlines():
            partes = linea.split(":", 2)
            if len(partes) == 3 and partes[1].isdigit():
                ruta = partes[0].removeprefix("./")
                if ruta in hallado or len(hallado) < MAX_ARCHIVOS:
                    hallado.setdefault(ruta, []).append((int(partes[1]), partes[2][:200]))
    return hallado


def _fragmentos(hallado: dict[str, list[tuple[int, str]]]) -> str:
    restante, bloques = MAX_LINEAS, []
    for ruta, lineas in hallado.items():
        lineas = lineas[:restante]
        if not lineas:
            break
        restante -= len(lineas)
        bloques.append(f"### {ruta}\n" + "\n".join(f"{n}: {t}" for n, t in lineas))
    return "\n\n".join(bloques)


def _prompt(h: Hallazgo, evidencia: list[Evidencia], fragmentos: str, secretos: list[str]) -> str:
    ev = "\n".join(f"[{e.tipo}] {e.extracto}" for e in evidencia if e.extracto) or "(sin texto)"
    repo = fragmentos or "(no hay repo del objetivo: no puedes citar archivos)"
    texto = (
        "Eres un ingeniero revisando un hallazgo de pruebas. Propón la causa probable y un cambio.\n"
        "Solo afirma lo que muestran la evidencia y los fragmentos; si no alcanza, di que es una hipótesis "
        "y usa confianza «baja». Cita solo archivos de los fragmentos.\n\n"
        f"Hallazgo: {h.titulo} ({h.pantalla})\n{h.descripcion}\n"
        f"Esperado: {h.esperado or '—'}\nObtenido: {h.obtenido or '—'}\n\n"
        f"Evidencia:\n{ev}\n\nFragmentos del repo:\n{repo}\n\n"
        "Responde JSON: causa, archivos [{ruta, linea}], cambio, confianza (alta|media|baja)."
    )
    return redactar(texto, secretos)


async def sugerir(
    h: Hallazgo,
    evidencia: list[Evidencia] | None = None,
    repo_objetivo: Path | None = None,
    *,
    cfg: Config | None = None,
    secretos: list[str] | None = None,
    completar=completar_json,
) -> Sugerencia:
    evidencia = h.evidencia if evidencia is None else evidencia
    secretos = [*(secretos or []), *(cfg._secretos.values() if cfg else [])]
    hallado = {}
    if repo_objetivo and Path(repo_objetivo).is_dir():
        hallado = await asyncio.to_thread(_buscar, Path(repo_objetivo), _tokens(h, evidencia))
    s = await completar(
        "redactor", _prompt(h, evidencia, _fragmentos(hallado), secretos), Sugerencia, cfg
    )
    lineas = {r: n for r, ls in hallado.items() for n, _ in ls[:1]}
    # solo archivos realmente encontrados, con la línea de la coincidencia si el LLM no la dio
    archivos = [
        ArchivoProbable(ruta=a.ruta, linea=a.linea or lineas[a.ruta])
        for a in s.archivos
        if a.ruta in hallado
    ][:MAX_ARCHIVOS]
    confianza = s.confianza if hallado else "baja"
    causa = redactar(s.causa, secretos)
    if not hallado:
        causa = f"(hipótesis: sin acceso al código) {causa}"
    return Sugerencia(
        causa=causa, archivos=archivos, cambio=redactar(s.cambio, secretos), confianza=confianza
    )


def seccion(s: Sugerencia) -> str:
    """Texto Markdown para el cuerpo del issue (pasa por `redactar` en quien lo une)."""
    archivos = [f"- `{a.ruta}`" + (f" (línea {a.linea})" if a.linea else "") for a in s.archivos]
    return "\n\n".join(
        [
            "## Posible causa y arreglo (sugerido por dogfood, revisar)",
            f"**Confianza:** {s.confianza}",
            f"**Causa probable:** {s.causa}",
            *(["**Archivos probables:**\n" + "\n".join(archivos)] if archivos else []),
            f"**Cambio propuesto:** {s.cambio}",
        ]
    )


def guardar(carpeta: Path, sugerencias: dict[str, Sugerencia]) -> None:
    (carpeta / "sugerencias.json").write_text(
        json.dumps(
            {k: v.model_dump() for k, v in sugerencias.items()}, indent=2, ensure_ascii=False
        )
    )


def cargar(carpeta: Path) -> dict[str, Sugerencia]:
    ruta = carpeta / "sugerencias.json"
    if not ruta.is_file():
        return {}
    return {k: Sugerencia.model_validate(v) for k, v in json.loads(ruta.read_text()).items()}
