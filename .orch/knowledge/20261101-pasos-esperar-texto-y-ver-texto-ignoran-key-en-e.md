---
id: 20261101-pasos-esperar-texto-y-ver-texto-ignoran-key-en-e
title: Pasos esperar_texto y ver_texto ignoran key en el generador determinista
area:
    - src/dogfood/deterministico/**
    - src/dogfood/config.py
    - docs/ops/flutter.md
tags:
    - flutter
    - deterministico
    - secretos
    - docs
source: agent
task: F8.9.T1
created: "2026-11-01"
---

En src/dogfood/deterministico/generador.py, las acciones esperar_texto y ver_texto solo usan `texto` (find.text / $('...')); el campo `key` se ignora en esas dos acciones aunque el paso lo traiga. tocar y escribir sí usan `key` primero (ValueKey / $(#key)). Además, la función secreto() de config.py elige el archivo de secretos por prefijo (solo ROUTER_ y SLACK_ tienen el suyo); cualquier otra variable que falte, como DOGFOOD_APP_EMAIL, produce el mensaje «falta X en ~/.config/dogfood/predicts.env» aunque la variable deba ir en flutter.env. Documentado en docs/ops/flutter.md; un arreglo en código sería que esperar_texto use key y que secreto() reconozca DOGFOOD_APP_ → flutter.env.
