from collections.abc import Callable
from datetime import datetime
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia
from dogfood.objetivos.predicts import aislamiento, entorno, oraculo, pantallas, reglas


class PredictsObjetivo:
    nombre = "predicts"

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        return entorno.preparar(ref, corrida)

    def destruir(self, instancia: Instancia) -> None:
        entorno.destruir(instancia)

    def url_permitida(self, url: str, instancia: Instancia) -> bool:
        return entorno.url_permitida(url, instancia)

    def escenarios(self) -> list[Escenario]:
        if find_spec("dogfood.escenarios") is None:  # lo trae F1.3.T1
            return []
        return import_module("dogfood.escenarios").cargar(Path(__file__).parent / "escenarios")

    def pantalla(self, url: str) -> str:
        return pantallas.pantalla(url)

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]:
        return [oraculo.verificar, aislamiento.verificar, reglas.verificar]

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        return entorno.logs(instancia, desde)

    def rutas_esperadas(self) -> list[dict]:
        """Respuestas de red que no son hallazgo (`esperada`) o que son una carrera (`carrera`)."""
        return [
            # la sesión se consulta al abrir la app: sin login es un 401 normal
            {"ruta": "/api/auth/yo", "estados": [401], "antes_de_login": True},
            {"ruta": "/api/auth/login", "estados": [401, 429], "carril": "login_fallido"},
            {
                "tipo": "carrera",
                "ruta": "/api/datasets/{id}/calidad",
                "estados": [404],
                "tras": ("POST", "/api/proyectos/{id}/datasets"),
                "hipotesis": "carrera entre la subida y el cálculo de calidad",
            },
        ]
