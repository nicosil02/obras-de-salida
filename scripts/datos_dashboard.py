"""Prepara los datos del dashboard (docs/datos.json y docs/distritos.geojson).

Requiere haber corrido procesar_datos.py y analizar_datos.py.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import analizar_datos as A

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "datos" / "procesados"
ORIG = RAIZ / "datos" / "originales"
DOCS = RAIZ / "docs"


def costos():
    """Costo de cada inversion, por codigo unico y por codigo SNIP antiguo."""
    c = ["CODIGO_UNICO", "CODIGO_SNIP", "MONTO_VIABLE", "COSTO_ACTUALIZADO"]
    inv = pd.concat(pd.read_csv(ORIG / f, dtype=str, usecols=lambda x: x in c)
                    for f in ["DETALLE_INVERSIONES.csv", "CIERRE_INVERSIONES.csv"])
    inv["costo"] = pd.to_numeric(inv["COSTO_ACTUALIZADO"], errors="coerce") \
        .fillna(pd.to_numeric(inv["MONTO_VIABLE"], errors="coerce"))
    costo = pd.concat([inv.set_index("CODIGO_UNICO")["costo"],
                       inv.dropna(subset=["CODIGO_SNIP"]).set_index("CODIGO_SNIP")["costo"]])
    return costo[~costo.index.duplicated()]


def inconclusas(p):
    """Obras inconclusas (pagado < 80% del costo) vivas en cada enero de transicion o placebo."""
    primer = p.groupby("obra")["t"].min()
    ejecutora = p.sort_values("t").drop_duplicates("SEC_EJEC", keep="last") \
        .set_index("SEC_EJEC")["UBIGEO"]
    d = pd.concat([A.cohorte(p, a, primer, ejecutora).assign(transicion=a in A.TRANSICIONES)
                   for a in A.TRANSICIONES + A.PLACEBOS])
    d["costo"] = d["obra"].str.split("-").str[1].map(costos())
    d = d[(d["costo"] > 0) & (d["pagado_previo"] < 0.8 * d["costo"])].copy()
    # Las municipalidades con ubigeo "00" (todo el departamento o provincia) van a la capital.
    d["UBIGEO"] = d["UBIGEO"].where(d["UBIGEO"].str[-2:] != "00", d["UBIGEO"].str[:4] + "01")
    d["dep"] = d["UBIGEO"].str[:2]
    return d


def cambio_partido(d):
    el = pd.read_parquet(PROC / "elecciones_distritales.parquet")
    el["anio"] = el["anio"] + 1  # la eleccion de 2010 define la transicion de enero 2011
    d = d[d["transicion"]].merge(el[["UBIGEO", "anio", "cambio_partido"]], how="left",
                                 on=["UBIGEO", "anio"])
    t = d.dropna(subset=["cambio_partido"]).groupby(["anio", "cambio_partido"])["abandonada"].mean()
    return [{"anio": int(a), "cambio": bool(c), "abandono": round(100 * v, 1)}
            for (a, c), v in t.items()]


def main():
    p = A.pagos()
    d = inconclusas(p)
    # Abandono por departamento ("PE" = todo el pais) y por anio (transiciones y placebos).
    abandono = []
    for dep, g in [("PE", d)] + list(d.groupby("dep")):
        for anio, h in g.groupby("anio"):
            abandono.append({"dep": dep, "anio": int(anio), "transicion": anio in A.TRANSICIONES,
                             "n": len(h), "abandonadas": int(h["abandonada"].sum()),
                             "pct": round(100 * h["abandonada"].mean(), 1)})
    # Mapa: % de obras inconclusas abandonadas por distrito en cada transicion.
    t = d[d["transicion"]].groupby(["UBIGEO", "anio"])["abandonada"].agg(["mean", "size"])
    mapa = {}
    for (u, a), r in t.iterrows():
        mapa.setdefault(u, {})[str(a)] = [round(100 * r["mean"]), int(r["size"])]

    # Gasto mensual en obras por departamento (S/ millones), con el ubigeo de la municipalidad.
    m = A.panel_ejecucion()
    ub = p.sort_values("t").drop_duplicates("SEC_EJEC", keep="last").set_index("SEC_EJEC")["UBIGEO"]
    m["dep"] = m["SEC_EJEC"].map(ub).str[:2]
    serie = {}
    for dep, g in [("PE", m)] + list(m.groupby("dep")):
        s = g.groupby("t")[["gasto", "obras", "nuevas"]].sum()
        serie[dep] = {"gasto": (s["gasto"] / 1e6).round(1).tolist(),
                      "obras": s["obras"].astype(int).tolist(),
                      "nuevas": s["nuevas"].astype(int).tolist()}
    # El panel empieza en 2008 (anio siguiente a la entrada al SIAF); todas las series
    # comparten el mismo eje de meses.
    meses = sorted(m["t"].unique())
    for dep in serie:
        if len(serie[dep]["gasto"]) != len(meses):
            raise ValueError(f"serie incompleta: {dep}")

    geo = json.loads((ORIG / "peru_distrital_simple.geojson").read_text(encoding="utf-8"))
    deps = {f["properties"]["IDDPTO"]: f["properties"]["NOMBDEP"].title() for f in geo["features"]}
    datos = {
        "meses": [f"{t // 12}-{t % 12 + 1:02d}" for t in meses],
        "serie": serie,
        "departamentos": dict(sorted(deps.items(), key=lambda x: x[1])),
        "abandono": abandono,
        "partido": cambio_partido(d),
        "regresion": json.loads((PROC / "resultados_ejecucion.json").read_text()),
        "mapa": mapa,
        "paralizadas": int((pd.read_excel(ORIG / "obras_paralizadas_jun2026.xlsx")
                            .filter(like="NIVEL").iloc[:, 0].astype(str)
                            .str.contains("LOCAL|^GL$")).sum()),
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, default=float),
                                     encoding="utf-8")
    # Geojson liviano: solo ubigeo, nombres y coordenadas con 3 decimales (~100 m).
    for f in geo["features"]:
        pr = f["properties"]
        f["properties"] = {"u": pr["IDDIST"], "n": pr["NOMBDIST"].title(),
                           "p": pr["NOMBPROV"].title(), "d": pr["IDDPTO"]}
        redondear = lambda c: [redondear(x) for x in c] if isinstance(c[0], list) \
            else [round(c[0], 3), round(c[1], 3)]
        if f["geometry"]:  # algunos distritos vienen sin geometria
            f["geometry"]["coordinates"] = redondear(f["geometry"]["coordinates"])
    geo.pop("crs", None)
    (DOCS / "distritos.geojson").write_text(json.dumps(geo, separators=(",", ":")),
                                            encoding="utf-8")
    nac = [a for a in abandono if a["dep"] == "PE"]
    print(json.dumps(nac), datos["partido"], datos["paralizadas"], len(mapa))


if __name__ == "__main__":
    main()
