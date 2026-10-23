"""Cliente HTTP de la API de predicts (rutas de `api/src/predicts/api/*.py`, bajo `/api`)."""

from typing import Any

import httpx

from dogfood.dominio import Instancia, Persona
from dogfood.objetivos.predicts import cuentas

TIPOS_RESULTADO = ("recompra", "ciclos", "riesgo", "ofertas")


class ErrorSesion(Exception):
    """La API respondió 401: no hay sesión o expiró."""


class PredictsCliente:
    def __init__(self, api_url: str, timeout: float = 30) -> None:
        self.api_url = api_url
        # httpx.Client guarda la cookie de sesión del login y la reenvía sola
        self._http = httpx.Client(base_url=api_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def _pedir(self, metodo: str, ruta: str, **kw: Any) -> httpx.Response:
        r = self._http.request(metodo, "/api" + ruta, **kw)
        if r.status_code == 401:
            raise ErrorSesion(f"{metodo} {ruta}: 401")
        r.raise_for_status()
        return r

    def _get(self, ruta: str, **params: Any) -> Any:
        return self._pedir("GET", ruta, params=params or None).json()

    def login(self, email: str, contrasena: str) -> None:
        self._pedir("POST", "/auth/login", json={"email": email, "contrasena": contrasena})

    def yo(self) -> dict:
        return self._get("/auth/yo")

    def proyectos(self) -> list[dict]:
        return self._get("/proyectos")

    def datasets(self, proyecto_id: str) -> list[dict]:
        return self._get(f"/proyectos/{proyecto_id}/datasets")

    def mapeo(self, dataset_id: str) -> dict:
        return self._get(f"/datasets/{dataset_id}/mapeo")

    def calidad(self, dataset_id: str) -> dict:
        return self._get(f"/datasets/{dataset_id}/calidad")

    def analisis_de(self, dataset_id: str) -> list[dict]:
        return self._get(f"/datasets/{dataset_id}/analisis")

    def analisis(self, analisis_id: str) -> dict:
        """Estado, resumen y `metricas` del análisis."""
        return self._get(f"/analisis/{analisis_id}")

    def resultados(
        self, analisis_id: str, tipo: str, todas_las_paginas: bool = True, tam_pagina: int = 500
    ) -> list[dict]:
        """Filas de `tipo` (`TIPOS_RESULTADO`); con `todas_las_paginas` sigue hasta `total`."""
        filas: list[dict] = []
        pagina = 1
        while True:
            d = self._get(
                f"/analisis/{analisis_id}/resultados",
                tipo=tipo,
                pagina=pagina,
                tam_pagina=tam_pagina,
            )
            filas += d["resultados"]
            if not todas_las_paginas or not d["resultados"] or len(filas) >= d["total"]:
                return filas
            pagina += 1

    def exportar(self, analisis_id: str, tipo: str) -> bytes:
        return self._pedir(
            "GET", f"/analisis/{analisis_id}/exportar", params={"tipo": tipo}
        ).content

    def get_crudo(self, ruta: str) -> tuple[int, Any]:
        """GET sin lanzar por el estado: `(status, json | texto)`. `ruta` ya incluye `/api`."""
        r = self._http.get(ruta)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text


def cliente_para(instancia: Instancia, persona: Persona) -> PredictsCliente:
    cliente = PredictsCliente(instancia.api_url)
    cliente.login(*cuentas.credenciales(persona))
    return cliente
