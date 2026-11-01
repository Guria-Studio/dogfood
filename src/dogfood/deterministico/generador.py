"""Generador de tests Dart (FR-36) a partir de los pasos de un escenario."""

import math
import re

from dogfood.config import Config
from dogfood.deterministico import Herramienta
from dogfood.dominio import Escenario, PasoDeterministico, RecorridoDeterministico

_ENV = re.compile(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def _lit(s: str) -> str:
    """Literal Dart entre comillas simples; escapa `\\`, `'`, `$` y saltos de línea."""
    s = s.replace("\\", "\\\\").replace("'", "\\'").replace("$", "\\$")
    return "'" + s.replace("\n", "\\n").replace("\r", "\\r") + "'"


def _valor(v: str) -> str:
    m = _ENV.fullmatch(v)
    return f"const String.fromEnvironment({_lit(m.group(1))})" if m else _lit(v)


def _ms(p: PasoDeterministico) -> int:
    return int(p.timeout_s * 1000)


def _requerir(p: PasoDeterministico, *campos: str) -> None:
    for c in campos:
        if getattr(p, c) is None:
            raise ValueError(f"el paso {p.accion!r} necesita `{c}`")


def _it(p: PasoDeterministico) -> list[str]:
    def sel() -> str:
        if p.key is not None:
            return f"find.byKey(ValueKey({_lit(p.key)}))"
        _requerir(p, "texto")
        return f"find.text({_lit(p.texto or '')})"

    match p.accion:
        case "tocar":
            return [f"await tester.tap({sel()});", "await tester.pumpAndSettle();"]
        case "escribir":
            _requerir(p, "valor")
            return [
                f"await tester.enterText({sel()}, {_valor(p.valor or '')});",
                "await tester.pumpAndSettle();",
            ]
        case "esperar_texto":
            _requerir(p, "texto")
            f, n = f"find.text({_lit(p.texto or '')})", math.ceil(p.timeout_s * 2)
            return [
                f"for (var i = 0; i < {n} && {f}.evaluate().isEmpty; i++) {{",
                "  await tester.pump(const Duration(milliseconds: 500));",
                "}",
                f"expect({f}, findsWidgets);",
            ]
        case "ver_texto":
            _requerir(p, "texto")
            return [f"expect(find.text({_lit(p.texto or '')}), findsOneWidget);"]
        case "deslizar":
            return [
                "await tester.drag(find.byType(Scrollable).first, const Offset(0, -300));",
                "await tester.pumpAndSettle();",
            ]
        case _:  # volver
            return ["await tester.pageBack();", "await tester.pumpAndSettle();"]


def _pt(p: PasoDeterministico) -> list[str]:
    def sel() -> str:
        if p.key is not None:
            return f"$(#{p.key})"
        _requerir(p, "texto")
        return f"$({_lit(p.texto or '')})"

    match p.accion:
        case "tocar":
            return [f"await {sel()}.tap();"]
        case "escribir":
            _requerir(p, "valor")
            return [f"await {sel()}.enterText({_valor(p.valor or '')});"]
        case "esperar_texto":
            _requerir(p, "texto")
            t = f"Duration(milliseconds: {_ms(p)})"
            return [f"await $({_lit(p.texto or '')}).waitUntilVisible(timeout: {t});"]
        case "ver_texto":
            _requerir(p, "texto")
            return [f"expect($({_lit(p.texto or '')}), findsOneWidget);"]
        case "deslizar":
            return [
                "await $.tester.drag(find.byType(Scrollable).first, const Offset(0, -300));",
                "await $.pumpAndSettle();",
            ]
        case _:  # volver
            return ["await $.native.pressBack();"]


def generar_test(escenario: Escenario, herramienta: Herramienta, paquete_dart: str = "app") -> str:
    if not escenario.deterministico or not escenario.deterministico.pasos:
        raise ValueError(f"el escenario {escenario.id!r} no tiene pasos deterministas")
    pasos = escenario.deterministico.pasos
    titulo = _lit(escenario.titulo)
    app = f"import 'package:{paquete_dart}/main.dart' as app;"
    if herramienta == "integration_test":
        cabecera = [
            "import 'package:flutter/widgets.dart';",
            "import 'package:flutter_test/flutter_test.dart';",
            "import 'package:integration_test/integration_test.dart';",
            "",
            app,
            "",
            "void main() {",
            "  IntegrationTestWidgetsFlutterBinding.ensureInitialized();",
            "",
            f"  testWidgets({titulo}, (WidgetTester tester) async {{",
            "    app.main();",
            "    await tester.pumpAndSettle();",
        ]
        cuerpo = [ln for p in pasos for ln in _it(p)]
    else:
        cabecera = [
            "import 'package:flutter/widgets.dart';",
            "import 'package:flutter_test/flutter_test.dart';",
            "import 'package:patrol/patrol.dart';",
            "",
            app,
            "",
            "void main() {",
            f"  patrolTest({titulo}, ($) async {{",
            "    app.main();",
            "    await $.pumpAndSettle();",
        ]
        cuerpo = [ln for p in pasos for ln in _pt(p)]
    return "\n".join([*cabecera, *("    " + ln for ln in cuerpo), "  });", "}", ""])


def defines(recorrido: RecorridoDeterministico, cfg: Config) -> dict[str, str]:
    """`{env:NOMBRE}` de los pasos (y de `dart_defines`) → secretos de la config."""
    r: dict[str, str] = {}
    for v in (p.valor or "" for p in recorrido.pasos):
        if m := _ENV.fullmatch(v):
            r[m.group(1)] = cfg.secreto(m.group(1))
    for k, v in recorrido.dart_defines.items():
        m = _ENV.fullmatch(v)
        r[k] = cfg.secreto(m.group(1)) if m else v
    return r
