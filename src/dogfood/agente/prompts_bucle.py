"""Prompt por paso del bucle propio (FR-27): persona, tarea, contrato, historial y árbol."""

from dogfood.agente import prompts
from dogfood.dominio import ContratoRecorrido, Escenario, Persona

_ACCIONES = """\
Acciones posibles (`accion.tipo`):
- `tocar`: `elemento` (id del árbol) o `x`/`y`.
- `escribir`: `texto` en `elemento` (un campo editable).
- `deslizar`: de `x`/`y` a `x2`/`y2`.
- `tecla`: `texto` con la tecla (p. ej. "Enter", "BACK").
- `navegar`: `texto` con la URL. `abrir_app` / `cerrar_app`: `texto` con el paquete.
- `volver`. `esperar`: `ms` milisegundos."""


def _contrato(c: ContratoRecorrido | None) -> str:
    if not c:
        return "(sin contrato: persigue el objetivo)"
    acciones = "\n".join(f"{i}. {a}" for i, a in enumerate(c.acciones, 1)) or "(libres)"
    return (
        f"Estado inicial: {c.estado_inicial or '(no indicado)'}\n"
        f"Acciones:\n{acciones}\n"
        f"Resultado esperado: {c.resultado_esperado or '(no indicado)'}"
    )


def paso(
    persona: Persona,
    escenario: Escenario,
    *,
    n: int,
    pantalla: str,
    arbol: str,
    texto_visible: str,
    historial: list[str],
    con_captura: bool,
    ciega: bool = False,
    tamano: tuple[int, int] | None = None,
) -> str:
    hist = "\n".join(historial) or "(ninguna todavía)"
    captura = "\nTe adjunto una captura de la pantalla." if con_captura else ""
    if ciega:
        medida = f" La captura original mide {tamano[0]}x{tamano[1]} px: escala" if tamano else ""
        captura += (
            "\nPantalla ciega: la app no expone Semantics en esta pantalla, así que los "
            "elementos listados pueden faltar. Guíate por la captura y usa acciones por "
            "coordenadas `x`/`y`." + (medida + " las coordenadas a ese tamaño." if medida else "")
        )
    return f"""{prompts.sistema(persona)}
<tarea>
{prompts.tarea(escenario, persona, None)}
</tarea>

<contrato>
{_contrato(escenario.contrato)}
</contrato>

<historial>
Tus últimas acciones y lo que pasó:
{hist}
</historial>

<pantalla paso="{n}" nombre="{pantalla}">
Elementos (id, clase, texto, centro x,y, marcas):
{arbol or "(el árbol está vacío)"}

Texto visible:
{texto_visible[:2000] or "(ninguno)"}{captura}
</pantalla>

{_ACCIONES}

Responde solo con el JSON pedido:
- `razonamiento`: una o dos frases, lo que piensas como esta persona.
- `paso_contrato`: qué paso del contrato persigues ahora.
- `accion`: la próxima acción, o null si terminaste o te rindes.
- `esperado`: qué debería pasar después de la acción.
- `friccion`: si algo te confundió o molestó, qué fue y la cita de la pantalla; si no, null.
- `pedir_captura`: true si el árbol no te alcanza para entender la pantalla siguiente.
- `terminado`: true si ya cumpliste el objetivo.
- `rendirse`: el motivo, si una persona como tú dejaría la app aquí; si no, null."""
