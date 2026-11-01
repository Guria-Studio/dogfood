"""Pantallas Flutter sin Semantics o sin ids estables -> hallazgos `accesibilidad` (FR-35)."""

from dogfood.dominio import ContextoDeteccion, Evidencia, Gravedad, Hallazgo, TipoHallazgo
from dogfood.flutter.semantica import cobertura_xml


def detectar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    umbral = ctx.instancia.parametros.get("umbral_cobertura", 0.6)
    vistas: set[str] = set()  # pantalla ya reportada en la corrida
    hallazgos: list[Hallazgo] = []
    for e in ctx.ejecuciones:
        for p in e.pasos:
            if p.url in vistas:
                continue
            cob = p.cobertura
            if cob is None:
                if e.driver not in ("android", "ios") or p.arbol is None or not p.arbol.is_file():
                    continue
                xml = p.arbol.read_text(errors="replace")
                if not xml.lstrip().startswith("<"):
                    continue
                cob = cobertura_xml(xml, umbral=umbral)
            if not cob.flutter:
                continue
            numeros = (
                f"{cob.interactivos} interactivos, {cob.etiquetados} etiquetados, "
                f"{cob.con_id} con id"
            )
            if cob.ciega:
                gravedad, firma = Gravedad.media, "ciega"
                titulo = f"pantalla sin Semantics: {p.url}"
                desc = (
                    f"La pantalla Flutter no expone Semantics ({numeros}, "
                    f"{cob.nodos} nodos). Envuelve los widgets con "
                    "`Semantics(label: ..., identifier: ...)` y dales una `Key`."
                )
            elif cob.interactivos and cob.ratio_id < 0.5:
                gravedad, firma = Gravedad.baja, "sin_ids"
                titulo = f"sin ids estables para tests: {p.url}"
                desc = (
                    f"La pantalla tiene etiquetas pero pocos ids ({numeros}). Agrega "
                    "`Semantics(identifier: ...)` o una `Key` a los controles."
                )
            else:
                vistas.add(p.url)
                continue
            vistas.add(p.url)
            h = Hallazgo(
                tipo=TipoHallazgo.accesibilidad,
                gravedad=gravedad,
                pantalla=p.url,
                titulo=titulo,
                descripcion=desc,
                evidencia=([Evidencia(tipo="captura", ruta=p.captura)] if p.captura else [])
                + ([Evidencia(tipo="texto", ruta=p.arbol)] if p.arbol else []),
                ejecucion_id=e.id,
                semilla=ctx.corrida.semilla,
                commit=ctx.instancia.commit,
            )
            h.huella = h.calcular_huella(firma)
            hallazgos.append(h)
    return hallazgos
