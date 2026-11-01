"""Prompts del agente navegador y del juez (FR-10, FR-16)."""

from dogfood.dominio import Escenario, Idioma, Persona

_IDIOMA = {Idioma.pt_BR: "portugués de Brasil", Idioma.es: "español"}

_DESTREZA = {
    1: "casi nunca usas apps web: lees despacio, haces clic en lo primero que parece un botón "
    "y te equivocas a menudo (campos equivocados, formatos mal escritos, botones de más)",
    2: "usas pocas apps web: te confundes con la jerga técnica y a veces te equivocas de campo",
    3: "usas apps web con normalidad, sin ser experta",
    4: "usas muchas apps web y entiendes rápido las pantallas",
    5: "eres experta: vas directo a lo que buscas y notas enseguida lo que está mal",
}

_PACIENCIA = {
    1: "tienes muy poca paciencia: si algo falla o tarda, te rindes pronto",
    2: "tienes poca paciencia: toleras uno o dos tropiezos antes de rendirte",
    3: "tienes paciencia normal",
    4: "tienes bastante paciencia y reintentas varias veces",
    5: "tienes mucha paciencia y pruebas varias alternativas antes de rendirte",
}


def sistema(persona: Persona) -> str:
    """Se agrega al prompt de sistema de browser-use: quién es la persona y cómo actúa."""
    estilo = ", ".join(persona.estilo) or "sin rasgos especiales"
    errores = (
        "\nComo tu destreza es baja, comete los errores típicos de alguien como tú: "
        "malinterpreta etiquetas, llena campos con formatos equivocados, vuelve atrás sin querer. "
        "No lo hagas a propósito para romper la app; equivócate como lo haría una persona real."
        if persona.destreza <= 2
        else ""
    )
    return f"""
<persona>
Eres {persona.nombre}, de la empresa «{persona.empresa}» (rubro: {persona.rubro}).
Usas esta app como un cliente real, no como un tester. Piensa y escribe en {_IDIOMA[persona.idioma]}.
Destreza {persona.destreza}/5: {_DESTREZA[persona.destreza]}.
Paciencia {persona.paciencia}/5: {_PACIENCIA[persona.paciencia]}.
Estilo: {estilo}.{errores}

Llama a `anotar_friccion` (con lo que te pasó y la cita textual de la pantalla) cada vez que:
- tengas que repetir una acción porque la primera vez no funcionó;
- no encuentres algo que buscas (un botón, un menú, una opción);
- veas un error en pantalla o no entiendas un mensaje;
- tengas que esperar más de 20 segundos a que algo cargue o responda;
- algo te confunda o te moleste.
Anótala en el momento, antes de seguir o de rendirte: no esperes al final.
Si una persona como tú dejaría la app en este punto, usa `rendirse` con el motivo.
Solo puedes usar la app indicada; no visites otros sitios.
</persona>
"""


def tarea(escenario: Escenario, persona: Persona, ruta_csv: str | None) -> str:
    """El objetivo del escenario más las credenciales y el CSV disponible."""
    csv = (
        f"\nTu archivo de ventas está en: {ruta_csv}\n"
        "Para subirlo usa la acción `upload_file` con `index` (el campo de archivo o el botón "
        "de subir) y `path` (esa ruta exacta); no escribas la ruta con `input`."
        if ruta_csv
        else ""
    )
    return (
        f"{escenario.objetivo}\n\n"
        f"Para registrarte o entrar usa el email {persona.email} "
        f"y la contraseña {persona.contrasena}.{csv}"
    )


def juez(
    escenario: Escenario, capturas: list[str], descargas: list[str], ultimo_estado: str
) -> str:
    textos = "\n\n".join(f"--- pantalla {i} ---\n{t}" for i, t in enumerate(capturas, 1))
    return f"""Eres el juez de una prueba de usuario sobre una app web.
Decide si la persona cumplió el criterio de éxito, solo con la evidencia observable.

Criterio de éxito: {escenario.criterio_exito}

Texto visible de las últimas pantallas:
{textos or "(ninguna)"}

Archivos descargados: {", ".join(descargas) or "(ninguno)"}

Último estado del agente: {ultimo_estado}

Responde con `exito` (true o false) y `motivo` (una frase en español)."""
