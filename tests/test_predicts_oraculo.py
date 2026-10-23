import copy
import json
from datetime import date, datetime, timedelta

import pytest

from dogfood.config import Tolerancias
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    Instancia,
    Persona,
)
from dogfood.objetivos.predicts import oraculo

REF = date(2026, 6, 30)
H = 30
PRODUCTOS = {"SKU1": 30.0, "SKU2": 45.0}


def _verdad_y_resultados():
    clientes, recompra, riesgo = [], [], []
    for i in range(1, 27):
        cid = f"C{i:05d}"
        abandono = i > 21
        pares = []
        for sku, ciclo in PRODUCTOS.items():
            n = 2 if i == 21 and sku == "SKU1" else 8
            ultima = REF - timedelta(days=(120 if abandono else ciclo - 10 - i % 10))
            proxima = None if abandono else ultima + timedelta(days=round(ciclo))
            pares.append(
                {"producto_id": f"P-{sku}", "sku": sku, "ciclo_real_dias": ciclo,
                 "sigma_log": 0.2, "n_compras": n, "ultima_compra": ultima.isoformat(),
                 "proxima_compra": proxima and proxima.isoformat(), "durable": False}
            )  # fmt: skip
            dias = (REF - ultima).days
            if abandono:
                riesgo.append(
                    {"nivel": "producto", "cliente_id": cid, "producto_id": sku, "n_compras": n,
                     "ciclo": ciclo, "dias_desde_ultima": dias}
                )  # fmt: skip
            elif n >= 3:
                recompra.append(
                    {"cliente_id": cid, "producto_id": sku, "producto_nombre": sku,
                     "ciclo": ciclo, "p": 0.7, "fecha_probable": proxima.isoformat(),
                     "fecha_min": (proxima - timedelta(days=5)).isoformat(),
                     "fecha_max": (proxima + timedelta(days=5)).isoformat(),
                     "n_compras": n, "dias_desde_ultima": dias}
                )  # fmt: skip
        if abandono:
            riesgo.append({"nivel": "tienda", "cliente_id": cid, "producto_id": None})
        clientes.append(
            {"cliente_id": cid, "abandono_desde": "2026-03-01" if abandono else None,
             "pares": pares}
        )  # fmt: skip
    verdad = {
        "semilla": 1, "perfil": "prueba", "fecha_max": REF.isoformat(),
        "parametros": {"MIN_COMPRAS": 3}, "defectos": [], "clientes": clientes,
    }  # fmt: skip
    analisis = {
        "id": "a1",
        "estado": "listo",
        "tipos": ["recompra", "ciclos", "riesgo", "contactar"],
        "resumen": {"fecha_ref": REF.isoformat(), "parametros": {"min_compras": 3}},
        "metricas": {
            "horizonte": H,
            "modelo": {"mae_dias": {"media": 0.0}, "precision_at_k": {"media": 0.6}},
            "linea_base": {"precision_at_k": {"media": 0.5}},
        },
    }
    ciclos = [{"producto_id": s, "ciclo_mediano": c} for s, c in PRODUCTOS.items()]
    res = {"recompra": recompra, "ciclos": ciclos, "riesgo": riesgo}
    return verdad, analisis, res


def _csv(filas):
    lineas = ["cliente_id,producto_id,producto,fecha_sugerida,fecha_mínima"]
    lineas += [
        f"{f['cliente_id']},{f['producto_id']},{f['producto_nombre']},{f['fecha_probable']},"
        f"{f['fecha_min']}"
        for f in filas
    ]
    return ("﻿" + "\n".join(lineas) + "\n").encode()


class ClienteFalso:
    def __init__(self, analisis, res, export):
        self.a, self.res, self.export = analisis, res, export

    def proyectos(self):
        return [{"id": "p1"}]

    def datasets(self, _):
        return [{"id": "d1"}]

    def analisis_de(self, _):
        return [{"id": "a1", "estado": "listo"}, {"id": "a0", "estado": "error"}]

    def analisis(self, _):
        return self.a

    def resultados(self, _, tipo):
        return self.res[tipo]

    def exportar(self, _, tipo):
        assert tipo == "recordatorios"
        return self.export

    def close(self):
        pass


@pytest.fixture
def correr(tmp_path):
    def _correr(verdad, analisis, res, export=None):
        carpeta = tmp_path / "c1" / "datos" / "ds1"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "verdad.json").write_text(json.dumps(verdad))
        persona = Persona(
            id="per1", nombre="Ana", email="a@x.io", contrasena="x", empresa="E", rubro="r",
            idioma="es", destreza=3, paciencia=3, intencion="analisis_completo", semilla=1,
        )  # fmt: skip
        (tmp_path / "c1" / "personas.json").write_text(json.dumps([persona.model_dump()]))
        ds = DatasetSintetico(
            id="ds1", perfil="prueba", ruta_csv=carpeta / "ventas.csv",
            ruta_verdad=carpeta / "verdad.json", n_clientes=26, n_filas=1, semilla=1,
        )  # fmt: skip
        cliente = ClienteFalso(analisis, res, export or _csv(res["recompra"]))
        ctx = ContextoDeteccion(
            corrida=Corrida(
                id="c1",
                objetivo="predicts",
                ref="main",
                commit="abc",
                semilla=7,
                inicio=datetime(2026, 7, 1),
                estado="corriendo",
            ),
            instancia=Instancia(
                base_url="http://w", api_url="http://a", proyecto_compose="x", commit="abc"
            ),
            ejecuciones=[
                Ejecucion(
                    id="e1",
                    persona_id="per1",
                    escenario_id="s",
                    dataset_id="ds1",
                    modelo="m",
                    estado="ok",
                )
            ],
            datasets={"ds1": ds},
            cliente_api=lambda p: cliente,
            logs={},
        )
        return oraculo.verificar(ctx, Tolerancias())

    return _correr


def _titulos(hallazgos):
    return {h.titulo for h in hallazgos}


def test_resultados_coincidentes_no_dan_hallazgos(correr):
    assert correr(*_verdad_y_resultados()) == []


def _ciclo_desplazado(factor):
    verdad, analisis, res = _verdad_y_resultados()
    for f in res["recompra"]:
        f["ciclo"] *= factor
    return verdad, analisis, res


def test_ciclo_desplazado_40_da_hallazgo_de_ciclo(correr):
    hs = correr(*_ciclo_desplazado(1.4))
    assert _titulos(hs) == {oraculo.TITULOS["ciclo_pares"] + " (recompra)"}
    assert hs[0].tipo == "logica" and "0%" in hs[0].obtenido


def test_par_con_2_compras_y_fecha_da_hallazgo_exacto(correr):
    verdad, analisis, res = _verdad_y_resultados()
    fila = copy.deepcopy(res["recompra"][0])
    fila.update(cliente_id="C00021", producto_id="SKU1", n_compras=2)
    par = verdad["clientes"][20]["pares"][0]
    fila["dias_desde_ultima"] = (REF - date.fromisoformat(par["ultima_compra"])).days
    res["recompra"].append(fila)
    hs = correr(verdad, analisis, res)
    assert _titulos(hs) == {oraculo.TITULOS["historia_insuficiente"] + " (recompra)"}
    assert hs[0].gravedad == "alta" and "C00021" in hs[0].descripcion


def test_export_con_una_fila_de_menos(correr):
    verdad, analisis, res = _verdad_y_resultados()
    hs = correr(verdad, analisis, res, export=_csv(res["recompra"][1:]))
    assert _titulos(hs) == {oraculo.TITULOS["exportacion"] + " (recompra)"}
    assert hs[0].pantalla == "exportar"


def _mae_inflado(dias):
    verdad, analisis, res = _verdad_y_resultados()
    analisis["metricas"]["modelo"]["mae_dias"]["media"] = dias
    return verdad, analisis, res


def test_mae_declarado_inflado_da_hallazgo_de_backtest(correr):
    hs = correr(*_mae_inflado(3.0))
    assert _titulos(hs) == {oraculo.TITULOS["mae_backtest"] + " (recompra)"}


def test_dataset_vacio_no_se_compara(correr):
    verdad, analisis, res = _ciclo_desplazado(1.4)
    verdad["defectos"] = ["vacio"]
    analisis["metricas"]["modelo"]["mae_dias"]["media"] = 9.0
    for f in res["riesgo"]:
        f["n_compras"] = 99
    assert correr(verdad, analisis, res) == []


def test_huellas_no_dependen_de_los_numeros(correr):
    a, b = correr(*_ciclo_desplazado(1.4)), correr(*_ciclo_desplazado(1.8))
    assert [h.huella for h in a] == [h.huella for h in b]
    assert a[0].titulo == b[0].titulo
    assert a[0].obtenido != b[0].obtenido or a[0].descripcion != b[0].descripcion
    c, d = correr(*_mae_inflado(3.0)), correr(*_mae_inflado(7.5))
    assert c[0].huella == d[0].huella and c[0].descripcion != d[0].descripcion
