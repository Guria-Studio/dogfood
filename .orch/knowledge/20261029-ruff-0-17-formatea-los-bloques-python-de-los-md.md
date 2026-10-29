---
id: 20261029-ruff-0-17-formatea-los-bloques-python-de-los-md
title: 'ruff 0.17 formatea los bloques ```python de los .md: CI cae por docs'
area:
    - docs/**
    - specs/**
tags:
    - ruff
    - ci
    - markdown
source: agent
task: F6.1.T1
created: "2026-10-29"
---

CI corre `uv run ruff format --check .` y ruff 0.17 también revisa los bloques de código Python dentro de los Markdown (docs/, specs/). Un comentario alineado a mano en docs/arch/001 rompió el CI aunque todo el código y los tests estaban bien. Antes de terminar corre `uv run ruff format .` (no solo sobre src/) y comitea lo que cambie en los .md.
