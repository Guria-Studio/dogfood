---
id: 20261101-predicts-api-url-es-el-proxy-del-web-las-rutas-d
title: 'predicts: api_url es el proxy del web (las rutas de la API van sin /api) y ContextoDeteccion no trae objetivo'
area:
    - src/dogfood/objetivos/predicts/**
    - src/dogfood/deteccion/**
    - src/dogfood/corrida.py
tags:
    - predicts
    - api_url
    - deteccion
    - proxy
source: agent
task: F10.1.T3
created: "2026-11-01"
---

- La API de predicts sirve sus rutas en la raíz (`/auth/login`, `/proyectos`…); el nginx del web hace proxy de `/api/*` → API. PredictsCliente, cuentas.confirmar_registro y aislamiento siempre anteponen `/api`, así que `Instancia.api_url` tiene que ser el origen del web (18080), no el puerto directo de la API (18100): con 18100 todo daba 404 en silencio (empresa_id quedaba None y el oráculo no revisaba ningún número).
- El OpenAPI de la API lista rutas sin `/api`: aislamiento le antepone `/api` antes de probarlas por el proxy.
- `ContextoDeteccion` no tiene atributo `objetivo`: `deteccion/objetivo.py` lo carga con `cargar_objetivo(ctx.corrida.objetivo)`. Los tests que hacen `ctx.objetivo = ...` lo inyectan a mano; eso escondía el AttributeError de producción.
- `cliente_api` recibe una `Persona` y en la corrida devuelve un cliente con sesión (`cliente_para`).
- Las personas de una corrida real están en `runs/<id>/personas.json`, no en `corrida.parametros`; `reglas._personas` las busca ahí.
- Fixture de una corrida real: `tests/fixtures/corrida-10/` (historial.json por ejecución, personas con contraseñas redactadas).
