---
id: 20261102-objetivo-web-ganchos-opcionales-por-getattr-carg
title: 'Objetivo web: ganchos opcionales por getattr, cargar_objetivo(nombre, proyecto, raiz) y tabla escenarios_proyecto'
area:
    - src/dogfood/corrida.py
    - src/dogfood/objetivos/**
    - src/dogfood/almacen.py
    - src/dogfood/proyectos.py
    - src/dogfood/explorar.py
tags:
    - objetivo-web
    - ganchos
    - migracion
source: agent
task: F13.1.T1
created: "2026-11-02"
---

- corrida.py ya no conoce predicts: busca con getattr en el objetivo `confirmar_registro(persona, instancia)` (ojo: el orden es el inverso al de `Opciones.confirmar(instancia, persona)`), `preparar_escenario(escenario, persona, instancia) -> dict` de kwargs extra del navegador, `cliente_api(instancia, persona)`, `repo() -> Path|None` y `contar_uso_ia(instancia)` (por defecto, opinion.contar_uso_ia; tests/test_corrida_cierre exige que se llame con objetivos falsos).
- `cargar_objetivo(nombre, proyecto=None, raiz=None)`: si la clase tiene `desde_proyecto`, recibe el Proyecto. Sin proyecto (como lo carga deteccion/objetivo.py por nombre), `WebObjetivo()` funciona y sus verificadores son [].
- `Proyecto.verificar_url(url)` lanza ErrorProyecto con hosts_prohibidos; la corrida lo llama después de pisar base_url con la URL del entorno y guarda el mensaje en `corrida.parametros["motivo"]`.
- Migración v7 crea `escenarios_proyecto(proyecto, id, estado borrador|aceptado|descartado, datos JSON del Escenario, creado)`. `WebObjetivo.escenarios()` lee los `aceptados` de ahí; F13.2.T1 debe escribir en esa tabla con ese esquema.
- Si subes VERSION_ESQUEMA, tests/test_contratos_f6.py tiene el número fijo (`== 7`).
