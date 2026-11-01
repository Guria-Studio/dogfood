---
id: 20261101-contratos-f8-d-nde-viven-plataforma-resultadodet
title: 'Contratos F8: dónde viven Plataforma, ResultadoDeterministico, FuenteFrames, Nodo y cómo se validan hosts'
area:
    - src/dogfood/dominio.py
    - src/dogfood/config.py
    - src/dogfood/frames/**
    - src/dogfood/nodos/**
    - src/dogfood/deterministico/**
    - src/dogfood/objetivos/**
    - src/dogfood/deteccion/flutter.py
    - src/dogfood/drivers/android.py
tags:
    - contratos
    - f8
    - config
source: agent
task: F8.1.T1
created: "2026-11-01"
---

- `Plataforma` está en `dogfood.dominio`; `Escenario.motor` es None por defecto (None = lo decide la corrida).
- `ResultadoDeterministico.resultado()` (en `dogfood/deterministico/__init__.py`): algún test en `fallo` → fallo (aunque haya timeout); aprobado solo con código 0, ≥1 test, todos ok y `motivo` vacío; lo demás no_concluyente. `Resultado` se importa de `dogfood.contrato`.
- `dogfood.frames.base`: `FuenteFrames`, `FuenteDeDriver(driver, intervalo_s=None)` (nombre "driver"; 0,2 s web, 1 s resto), `validar_url_local` (reusa `dogfood.web.validar_host`; acepta todo 127.0.0.0/8, localhost, ::1 y 100.64/10).
- config: `Nodo.host` y `FlutterWeb.host` se validan con `field_validator("host")(validar_host)` → un host malo da `pydantic.ValidationError` en `Config.cargar`. `Nodo.dir_trabajo` es `str` sin expandir (es ruta del Mac); `flutter.copia_trabajo` es `Path` con `expanduser`.
- `DriverAndroid(..., grabar_video=False)` no lanza screenrecord; con eso `evidencia()` no hace `pull` (lista de segmentos vacía).
- Los stubs `objetivos/ios` y `objetivos/flutter_web` lanzan NotImplementedError en `preparar`/`destruir`; `deteccion/flutter.detectar` devuelve [] y ya está en DETECTORES.
