import pytest


@pytest.fixture(autouse=True)
def _ayuda_sin_color(monkeypatch: pytest.MonkeyPatch) -> None:
    # El runner de CI fuerza color: Rich parte las opciones con códigos ANSI y los tests que
    # buscan "--opcion" en la ayuda fallan. Se apaga el color y se fija el ancho para todos.
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("_TYPER_FORCE_DISABLE_TERMINAL", "1")
