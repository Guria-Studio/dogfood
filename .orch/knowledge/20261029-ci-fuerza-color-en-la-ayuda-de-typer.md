---
id: 20261029-ci-fuerza-color-en-la-ayuda-de-typer
title: 'El CI fuerza color: la ayuda de Typer sale con códigos ANSI'
area:
    - tests/**
    - src/dogfood/comandos/**
tags:
    - ci
    - typer
    - tests
source: agent
task: F6.7.T1
created: "2026-10-29"
---

En el runner de CI Rich colorea `--help` y parte las opciones con códigos ANSI, así que `"--opcion" in r.output` pasa en local y falla en CI. `tests/conftest.py` apaga el color para todos los tests (NO_COLOR, TERM=dumb, COLUMNS=200); igual, en un test de ayuda invoca con `env={"NO_COLOR": "1", "COLUMNS": "200"}` y quita los ANSI con `re.sub(r"\x1b\[[0-9;]*m", "", salida)`. Pruébalo con `FORCE_COLOR=1 uv run pytest`.
