"""Pruebas del ciclo politico de la inversion municipal (obras aprobadas por mes).

Modelo: obras_dt = a_d + anio_t + mes_t + b1*campana + b2*cola + b3*inicio + e_dt
- a_d: efecto fijo de distrito; anio_t y mes_t: dummies de anio y de mes calendario.
- campana: 4 meses antes del mes de la eleccion.
- cola: del mes de la eleccion a diciembre (alcaldes salientes).
- inicio: enero a marzo del anio siguiente (alcaldes nuevos).

Medidas: obras aprobadas (viabilidad) e iniciadas (primer pago).
Salida: datos/procesados/resultados.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels import PanelOLS

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "datos" / "procesados"
ELECCIONES = {2006: 11, 2010: 10, 2014: 10, 2018: 10, 2022: 10, 2026: 10}  # anio: mes


def marcar(p):
    p = p.copy()
    p["anio"], p["mes"] = p["MES"].dt.year, p["MES"].dt.month
    me = p["anio"].map(ELECCIONES)  # mes de la eleccion si el anio es electoral
    p["campana"] = (p["mes"] >= me - 4) & (p["mes"] < me)
    p["cola"] = p["mes"] >= me
    p["inicio"] = p["anio"].sub(1).isin(ELECCIONES) & (p["mes"] <= 3)
    # Meses relativos a la eleccion mas cercana (para el estudio de eventos).
    fechas = pd.to_datetime([f"{a}-{m:02d}-01" for a, m in ELECCIONES.items()])
    dist = (p["MES"].dt.year.values[:, None] - fechas.year.values) * 12 \
        + (p["MES"].dt.month.values[:, None] - fechas.month.values)
    p["rel"] = dist[np.arange(len(p)), np.abs(dist).argmin(axis=1)]
    return p


def estimar(p, y, regs):
    X = pd.concat([p[regs].astype(float),
                   pd.get_dummies(p["anio"], prefix="a", drop_first=True, dtype=float),
                   pd.get_dummies(p["mes"], prefix="m", drop_first=True, dtype=float)], axis=1)
    idx = pd.MultiIndex.from_frame(p[["UBIGEO", "MES"]])
    X.index = idx
    m = PanelOLS(p[y].set_axis(idx), X, entity_effects=True).fit(
        cov_type="clustered", cluster_entity=True)
    media = p.loc[~p[regs].any(axis=1), y].mean()
    return {r: {"coef": m.params[r], "ee": m.std_errors[r], "p": m.pvalues[r],
                "pct": 100 * m.params[r] / media} for r in regs} | {"media_base": media,
                                                                  "n": int(m.nobs)}


if __name__ == "__main__":
    p = marcar(pd.read_parquet(PROC / "panel_distrito_mes.parquet"))
    base = ["campana", "cola", "inicio"]
    sin_lima = ~p["UBIGEO"].str[:2].isin(["15", "07"])
    res = {}
    for medida in ["aprobadas", "iniciadas"]:
        y = f"obras_{medida}"
        p[f"log_monto_{medida}"] = np.log1p(p[f"monto_{medida}"])
        res[medida] = {
            "todo": estimar(p, y, base),
            "monto": estimar(p, f"log_monto_{medida}", base),
            "sin_lima_callao": estimar(p[sin_lima], y, base),
            "desde_2015": estimar(p[p["anio"] >= 2015], y, base),
            "hasta_2014": estimar(p[p["anio"] <= 2015], y, base),
        }
        for nombre, r in res[medida].items():
            print(medida, nombre,
                  {k: f"{r[k]['pct']:+.1f}% (p={r[k]['p']:.3f})" for k in base})
    (PROC / "resultados.json").write_text(json.dumps(res, indent=1, default=float))
