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


def estimar(p, y, regs, ent="UBIGEO"):
    X = pd.concat([p[regs].astype(float),
                   pd.get_dummies(p["anio"], prefix="a", drop_first=True, dtype=float),
                   pd.get_dummies(p["mes"], prefix="m", drop_first=True, dtype=float)], axis=1)
    idx = pd.MultiIndex.from_frame(p[[ent, "MES"]])
    X.index = idx
    m = PanelOLS(p[y].set_axis(idx), X, entity_effects=True).fit(
        cov_type="clustered", cluster_entity=True)
    media = p.loc[~p[regs].any(axis=1), y].mean()
    return {r: {"coef": m.params[r], "ee": m.std_errors[r], "p": m.pvalues[r],
                "pct": 100 * m.params[r] / media} for r in regs} | {"media_base": media,
                                                                  "n": int(m.nobs)}


TRANSICIONES = [2011, 2015, 2019, 2023]  # enero en que asume el alcalde nuevo
PLACEBOS = [2009, 2013, 2017, 2021]      # enero a mitad de gestion, sin cambio de alcalde


def deflactor():
    """Factor para pasar soles de cada mes t a soles de 2022 (IPC de Lima del BCRP, serie PN38705PM)."""
    ipc = pd.read_csv(RAIZ / "datos" / "originales" / "ipc_lima.csv")
    t = ipc["mes"].str[:4].astype(int) * 12 + ipc["mes"].str[5:].astype(int) - 1
    ipc = ipc.set_index(t)["ipc"]
    return ipc[(ipc.index // 12) == 2022].mean() / ipc


def pagos():
    """Pagos mensuales por obra 2007-2026 (solo pagos positivos), con indice de mes t."""
    p = pd.concat(pd.read_parquet(f) for f in sorted((PROC / "gasto").glob("pagos_obra_*.parquet")))
    p = p[p["DEVENGADO"] > 0].copy()
    p["t"] = p["ANO_EJE"].astype(int) * 12 + p["MES"].astype(int) - 1
    p["obra"] = p["SEC_EJEC"] + "-" + p["PROYECTO"]
    return p


def cohorte(p, anio, primer_pago, ejecutora):
    """Obras vivas al 1 de enero de `anio` y si quedan abandonadas despues.

    - viva: recibio algun pago en los 6 meses previos.
    - tardia: su primer pago fue en los 12 meses previos (la empezo el alcalde que se va,
      si es transicion).
    - abandonada: no recibe ningun pago en los 24 meses siguientes.
    """
    T = anio * 12
    vivas = p.loc[p["t"].between(T - 6, T - 1), "obra"].unique()
    despues = set(p.loc[p["t"].between(T, T + 23), "obra"])
    acum = p[p["t"] < T].groupby("obra")["DEVENGADO"].sum()
    d = pd.DataFrame({"obra": vivas})
    d["anio"] = anio
    d["tardia"] = (primer_pago.reindex(vivas) >= T - 12).values
    d["abandonada"] = ~d["obra"].isin(despues)
    d["pagado_previo"] = acum.reindex(vivas).values
    d["SEC_EJEC"] = d["obra"].str.split("-").str[0]
    d["UBIGEO"] = d["SEC_EJEC"].map(ejecutora)
    return d


def abandono():
    from linearmodels.iv.absorbing import AbsorbingLS
    p = pagos()
    primer = p.groupby("obra")["t"].min()
    ejecutora = p.sort_values("t").drop_duplicates("SEC_EJEC", keep="last") \
        .set_index("SEC_EJEC")["UBIGEO"]
    d = pd.concat([cohorte(p, a, primer, ejecutora).assign(transicion=a in TRANSICIONES)
                   for a in TRANSICIONES + PLACEBOS])
    # Las obras que empezaron antes de 2007 no tienen primer pago observado: son "antiguas".
    d["tardia"] = d["tardia"].astype(int)
    d["transicion"] = d["transicion"].astype(int)
    d["abandonada"] = d["abandonada"].astype(int)
    tabla = d.groupby(["transicion", "tardia"])["abandonada"].agg(["mean", "size"])
    print(tabla.round(3))
    # Diferencias en diferencias: abandono ~ tardia + tardia x transicion, con efectos fijos
    # de anio (absorben "transicion") y de municipalidad; errores agrupados por municipalidad.
    d["tardia_x_transicion"] = d["tardia"] * d["transicion"]
    X = d[["tardia", "tardia_x_transicion"]].astype(float).assign(const=1.0)
    ef = pd.DataFrame({"anio": pd.Categorical(d["anio"]),
                       "muni": pd.Categorical(d["SEC_EJEC"])}, index=d.index)
    d = d.reset_index(drop=True)
    m = AbsorbingLS(d["abandonada"].astype(float), X.reset_index(drop=True),
                    absorb=ef.reset_index(drop=True)).fit(
        cov_type="clustered", clusters=pd.Categorical(d["SEC_EJEC"]).codes)
    print(m.params.round(4).to_dict(), m.pvalues.round(4).to_dict(), "n =", m.nobs)
    return d, m


def panel_ejecucion():
    """Municipalidad x mes 2007-2026: gasto pagado en obras (soles de 2022), obras con pagos y obras que
    reciben su primer pago; mas las transferencias del anio (canon, FONCOMUN...)."""
    p = pagos()
    p["nueva"] = p["t"] == p.groupby("obra")["t"].transform("min")
    m = p.groupby(["SEC_EJEC", "t"]).agg(gasto=("DEVENGADO", "sum"), obras=("obra", "nunique"),
                                         nuevas=("nueva", "sum"))
    idx = pd.MultiIndex.from_product([m.index.levels[0], range(2007 * 12, 2026 * 12 + 9)],
                                     names=["SEC_EJEC", "t"])
    m = m.reindex(idx, fill_value=0).reset_index()
    m["MES"] = pd.to_datetime(dict(year=m["t"] // 12, month=m["t"] % 12 + 1, day=1))
    m["gasto"] = m["gasto"] * m["t"].map(deflactor())  # soles de 2022
    tr = pd.concat(pd.read_parquet(f) for f in (PROC / "transferencias").glob("*.parquet"))
    tr = tr.groupby([tr["SEC_EJEC"], tr["ANO_PRC"].astype(int)])["MONTO"].sum()
    m["log_transf"] = np.log1p(tr.reindex(pd.MultiIndex.from_arrays(
        [m["SEC_EJEC"], m["t"] // 12])).fillna(0).values)
    # Entre 2007 y 2009 las municipalidades entran al SIAF de a pocas: cada una cuenta desde
    # el anio siguiente al de su primer gasto registrado (de cualquier tipo).
    g = pd.concat(pd.read_parquet(f, columns=["ANO_EJE", "SEC_EJEC", "DEVENGADO"])
                  for f in (PROC / "gasto").glob("gasto_municipal_*.parquet"))
    entrada = g[g["DEVENGADO"] > 0].groupby("SEC_EJEC")["ANO_EJE"].min().astype(int)
    m = m[m["t"] // 12 > m["SEC_EJEC"].map(entrada)].copy()
    # Gasto como indice: 100 = gasto mensual promedio de esa municipalidad.
    m["indice_gasto"] = 100 * m["gasto"] / m.groupby("SEC_EJEC")["gasto"].transform("mean")
    return m


def ejecucion():
    """Se ejecuta mas obra al final de la gestion? Dos pruebas, antes y despues de la
    prohibicion de reelegirse (2015).

    1. Anio de gestion: y = municipalidad + mes calendario + gestion + tendencia + transferencias
       + anio2 + anio3 + anio4 (base: primer anio del alcalde).
    2. Meses de la eleccion: y = municipalidad + anio + mes + campana + cola + inicio. La cola
       (octubre-diciembre del anio electoral) se compara con los mismos meses de otros anios.
    """
    m = marcar(panel_ejecucion())
    m["gestion"] = (m["anio"] - 2007) // 4
    m["anio_gestion"] = (m["anio"] - 2007) % 4 + 1
    m["con_reeleccion"] = m["gestion"] <= 1  # 2007-2010 y 2011-2014
    res = {}
    for y in ["indice_gasto", "obras", "nuevas"]:
        for etapa, sub in [("con_reeleccion", m[m["con_reeleccion"]]),
                           ("sin_reeleccion", m[~m["con_reeleccion"]])]:
            X = pd.concat([pd.get_dummies(sub["anio_gestion"], prefix="anio", dtype=float)
                           .drop(columns="anio_1"),
                           pd.get_dummies(sub["gestion"], prefix="g", drop_first=True, dtype=float),
                           pd.get_dummies(sub["mes"], prefix="m", drop_first=True, dtype=float),
                           (sub["t"] / 12).rename("tendencia"), sub["log_transf"]], axis=1)
            idx = pd.MultiIndex.from_frame(sub[["SEC_EJEC", "MES"]])
            r = PanelOLS(sub[y].set_axis(idx), X.set_axis(idx), entity_effects=True).fit(
                cov_type="clustered", cluster_entity=True)
            base = sub.loc[sub["anio_gestion"] == 1, y].mean()
            pct = lambda b: 100 * b / base
            res[f"{y}|{etapa}|anio_gestion"] = {
                k: {"pct": pct(r.params[k]), "ic": 1.96 * pct(r.std_errors[k]), "p": r.pvalues[k]}
                for k in ["anio_2", "anio_3", "anio_4"]}
            # Prueba 2: dentro del anio (efectos fijos de anio).
            e = estimar(sub, y, ["campana", "cola", "inicio"], ent="SEC_EJEC")
            res[f"{y}|{etapa}|eleccion"] = {k: {"pct": e[k]["pct"], "p": e[k]["p"],
                                                "ic": 1.96 * 100 * e[k]["ee"] / e["media_base"]}
                                            for k in ["campana", "cola", "inicio"]}
    for k, v in res.items():
        print(k, {c: f"{d['pct']:+.1f}% (p={d['p']:.3f})" for c, d in v.items()}, flush=True)
    (PROC / "resultados_ejecucion.json").write_text(json.dumps(res, indent=1, default=float))
    return res


if __name__ == "__main__":
    ejecucion()
    abandono()
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
