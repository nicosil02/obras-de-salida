"""Prepara los datos del dashboard (docs/datos.json, docs/mapa.json y docs/distritos.geojson).

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


def inversiones():
    """Costo, nombre y coordenadas de cada inversion, por codigo unico y por codigo SNIP."""
    c = ["CODIGO_UNICO", "CODIGO_SNIP", "NOMBRE_INVERSION", "MONTO_VIABLE", "COSTO_ACTUALIZADO",
         "LATITUD", "LONGITUD"]
    inv = pd.concat(pd.read_csv(ORIG / f, dtype=str, usecols=lambda x: x in c)
                    for f in ["DETALLE_INVERSIONES.csv", "CIERRE_INVERSIONES.csv"])
    inv["costo"] = pd.to_numeric(inv["COSTO_ACTUALIZADO"], errors="coerce")         .fillna(pd.to_numeric(inv["MONTO_VIABLE"], errors="coerce"))
    for k in ["LATITUD", "LONGITUD"]:
        inv[k] = pd.to_numeric(inv[k], errors="coerce")
    fuera = ~inv["LATITUD"].between(-18.5, 0.1) | ~inv["LONGITUD"].between(-81.5, -68.5)
    inv.loc[fuera, ["LATITUD", "LONGITUD"]] = np.nan
    cols = ["costo", "NOMBRE_INVERSION", "LATITUD", "LONGITUD"]
    inv = pd.concat([inv.set_index("CODIGO_UNICO")[cols],
                     inv.dropna(subset=["CODIGO_SNIP"]).set_index("CODIGO_SNIP")[cols]])
    return inv[~inv.index.duplicated()]


def centroides():
    """Centro aproximado de cada distrito (promedio de los vertices del poligono)."""
    geo = json.loads((ORIG / "distritos_inei.geojson").read_text(encoding="utf-8"))
    cen = {}
    for f in geo["features"]:
        g = f["geometry"]
        if not g:  # algunos distritos vienen sin geometria
            continue
        anillo = g["coordinates"][0] if g["type"] == "Polygon" else             max((pol[0] for pol in g["coordinates"]), key=len)
        pr = f["properties"]
        cen[pr["IDDIST"]] = [*np.mean(anillo, axis=0), f"{pr['NOMBDIST'].title()} ({pr['NOMBPROV'].title()})"]
    cen = pd.DataFrame(cen, index=["lon", "lat", "nombre"]).T
    return cen.astype({"lon": float, "lat": float})


# Tipos de obra: funcion del gasto en adquisicion de activos no financieros (inversion).
TIPOS = {"TRANSPORTE": "tr", "SANEAMIENTO": "sa", "EDUCACION": "ed", "CULTURA Y DEPORTE": "cu",
         "AGROPECUARIA": "ag", "VIVIENDA Y DESARROLLO URBANO": "vi", "ORDEN PUBLICO Y SEGURIDAD": "se", "SALUD": "sl"}


def por_tipo(anios):
    """Gasto de inversion por distrito, tipo y anio (millones). Antes de 2009 no hay generica."""
    g = pd.concat(pd.read_parquet(PROC / "gasto" / f"gasto_municipal_{a}.parquet",
                                  columns=["ANO_EJE", "UBIGEO", "FUNCION_NOMBRE", "GENERICA_NOMBRE", "DEVENGADO"])
                  for a in anios)
    g = g[(g["GENERICA_NOMBRE"] == "ADQUISICION DE ACTIVOS NO FINANCIEROS") & g["FUNCION_NOMBRE"].isin(TIPOS)]
    g["UBIGEO"] = g["UBIGEO"].where(g["UBIGEO"].str[-2:] != "00", g["UBIGEO"].str[:4] + "01").replace(RECODIFICA)
    return g.groupby(["UBIGEO", g["FUNCION_NOMBRE"].map(TIPOS), g["ANO_EJE"].astype(int)])["DEVENGADO"].sum() / 1e6


# En 2014 se creo la provincia de Putumayo y el INEI recodifico dos distritos de Maynas.
RECODIFICA = {"160109": "160801", "160114": "160803"}


def mapa3d(m, d, inv, cen):
    """Columnas por distrito y anio (gasto y obras con pagos) y puntos de obras abandonadas."""
    m = m.assign(anio=m["t"] // 12)
    # Obras distintas con pagos en el anio (no la suma de los meses).
    p = A.pagos()
    p["UBIGEO"] = p["UBIGEO"].where(p["UBIGEO"].str[-2:] != "00", p["UBIGEO"].str[:4] + "01").replace(RECODIFICA)
    p = p[p["t"] // 12 >= 2007]
    obras = p.groupby(["UBIGEO", p["t"] // 12])["obra"].nunique()
    gasto = p.groupby(["UBIGEO", p["t"] // 12])["DEVENGADO"].sum() / 1e6
    anios = list(range(2007, 2027))
    # 2007 esta incompleto: solo cuentan las municipalidades que ya reportaban en enero.
    g7 = pd.read_parquet(PROC / "gasto" / "gasto_municipal_2007.parquet")
    u7 = g7.loc[(g7["MES"].astype(int) == 1) & (g7["DEVENGADO"] > 0), "UBIGEO"]
    enero07 = set(u7.where(u7.str[-2:] != "00", u7.str[:4] + "01").replace(RECODIFICA))
    # Distritos creados despues del mapa del INEI: entran en los totales aunque no se dibujen.
    nom = pd.read_csv(ORIG / "DETALLE_INVERSIONES.csv", dtype=str, usecols=["UBIGEO", "PROVINCIA", "DISTRITO"])         .dropna().drop_duplicates("UBIGEO").set_index("UBIGEO")
    tipo = por_tipo(anios)
    col = []
    for u in sorted(set(obras.index.get_level_values(0))):
        if u in cen.index:
            n, x, y = cen.at[u, "nombre"], round(cen.at[u, "lon"], 3), round(cen.at[u, "lat"], 3)
        elif u in nom.index:
            n, x, y = f"{nom.at[u, 'DISTRITO'].title()} ({nom.at[u, 'PROVINCIA'].title()})", None, None
        else:
            continue
        col.append({"u": u, "n": n, "x": x, "y": y,
                    "g": [round(float(gasto.get((u, a), 0)), 2) for a in anios],
                    "o": [int(obras.get((u, a), 0)) for a in anios], "e7": int(u in enero07),
                    "f": {t: [round(float(tipo.get((u, t, a), 0)), 2) for a in anios]
                          for t in TIPOS.values() if (u, t) in tipo.index.droplevel(2)}})
    # Obras inconclusas abandonadas en cada cambio de alcalde, con sus coordenadas; las que
    # no tienen coordenadas van al centro de su distrito con un desplazamiento aleatorio.
    ab = d[d["transicion"] & d["abandonada"].astype(bool)].copy()
    cod = ab["obra"].str.split("-").str[1]
    ab = ab.join(inv[["NOMBRE_INVERSION", "LATITUD", "LONGITUD"]], on=cod.rename("cod"))
    rng = np.random.default_rng(0)
    sin = ab["LATITUD"].isna() & ab["UBIGEO"].isin(cen.index)
    ab.loc[sin, "LATITUD"] = ab.loc[sin, "UBIGEO"].map(cen["lat"]) + rng.normal(0, 0.02, sin.sum())
    ab.loc[sin, "LONGITUD"] = ab.loc[sin, "UBIGEO"].map(cen["lon"]) + rng.normal(0, 0.02, sin.sum())
    ab = ab.dropna(subset=["LATITUD"])
    puntos = [{"a": int(r.anio), "d": str(r.UBIGEO)[:2], "x": round(r.LONGITUD, 4), "y": round(r.LATITUD, 4),
               "n": str(r.NOMBRE_INVERSION)[:90].capitalize() if isinstance(r.NOMBRE_INVERSION, str) else "Obra sin nombre",
               "c": round(r.costo / 1e6, 2), "p": round(r.pagado_previo / r.costo * 100)}
              for r in ab.itertuples()]
    print(f"mapa: {len(col)} distritos ({sum(c['x'] is None for c in col)} sin poligono), {len(puntos)} obras abandonadas ({sin.mean():.0%} sin coordenadas)")
    return {"anios": anios, "columnas": col, "abandonadas": puntos}


def inconclusas(p):
    """Obras inconclusas (pagado < 80% del costo) vivas en cada enero de transicion o placebo."""
    primer = p.groupby("obra")["t"].min()
    ejecutora = p.sort_values("t").drop_duplicates("SEC_EJEC", keep="last") \
        .set_index("SEC_EJEC")["UBIGEO"]
    d = pd.concat([A.cohorte(p, a, primer, ejecutora).assign(transicion=a in A.TRANSICIONES)
                   for a in A.TRANSICIONES + A.PLACEBOS])
    d["costo"] = d["obra"].str.split("-").str[1].map(inversiones()["costo"])
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


def relaciones(d):
    """Abandono segun la relacion del alcalde que entra con la gestion que sale (2019 y 2023)."""
    r = pd.read_parquet(PROC / "relaciones_alcaldes.parquet")
    r["anio"] = r["anio"] + 1  # la eleccion de 2018 define la transicion de enero 2019
    m = d[d["transicion"]].merge(r, on=["UBIGEO", "anio"], how="inner")
    m["grupo"] = np.select([m["mismo_partido"], m["fue_regidor"], m["fue_alcalde"]],
                           ["mismo", "regidor", "exalcalde"], "ruptura")
    t = m.groupby("grupo").agg(obras=("abandonada", "size"), munis=("UBIGEO", "nunique"),
                               abandono=("abandonada", "mean"))
    return [{"grupo": g, "obras": int(x.obras), "munis": int(x.munis), "abandono": round(100 * x.abandono, 1)}
            for g, x in t.iterrows()]


POB = {r["UBIGEO"]: r["POBTOTAL"] or 0 for r in __import__("shapefile").Reader(
    str(ORIG / "limites" / "DISTRITOS_inei.shp"), encoding="utf-8").records()}


def distritos():
    """Geojson liviano para el mapa: ubigeo, nombres y coordenadas con 3 decimales (~100 m)."""
    geo = json.loads((ORIG / "distritos_inei.geojson").read_text(encoding="utf-8"))
    redondear = lambda c: [redondear(x) for x in c] if isinstance(c[0], list)         else [round(c[0], 3), round(c[1], 3)]
    geo["features"] = [f for f in geo["features"] if f["geometry"]]  # algunos vienen sin geometria
    for f in geo["features"]:
        pr = f["properties"]
        f["properties"] = {"u": pr["IDDIST"], "n": pr["NOMBDIST"].title(), "p": pr["NOMBPROV"].title(),
                           "h": int(POB.get(pr["IDDIST"], 0))}  # poblacion INEI, para desempatar en el buscador
        f["geometry"]["coordinates"] = redondear(f["geometry"]["coordinates"])
    geo.pop("crs", None)
    (DOCS / "distritos.geojson").write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    # Un mapa detallado (~30 m) por provincia, que el dashboard carga al elegirla.
    import shapefile  # pyshp
    from shapely.geometry import mapping, shape
    prov = {}
    for sr in shapefile.Reader(str(ORIG / "limites" / "DISTRITOS_inei.shp"), encoding="utf-8").iterShapeRecords():
        u = sr.record["UBIGEO"]
        g = mapping(shape(sr.shape.__geo_interface__).simplify(0.0003, preserve_topology=True))
        prov.setdefault(u[:4], []).append({"type": "Feature", "geometry": {"type": g["type"], "coordinates": redondear4(g["coordinates"])},
                                            "properties": {"u": u, "n": sr.record["NOMBDIST"].title(), "p": sr.record["NOMBPROV"].title()}})
    # Contorno del país sin huecos (lagos): fondo del mapa.
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    pais = unary_union([shape(sh.__geo_interface__).buffer(0.002) for sh in
                        shapefile.Reader(str(ORIG / "limites" / "DISTRITOS_inei.shp")).iterShapes()])
    partes = pais.geoms if pais.geom_type == "MultiPolygon" else [pais]
    pais = unary_union([Polygon(q.exterior) for q in partes if q.area > 1e-4]).simplify(0.003)
    (DOCS / "pais.json").write_text(json.dumps({"type": "Feature", "properties": {},
                                                "geometry": {"type": pais.geom_type, "coordinates": redondear4(mapping(pais)["coordinates"])}},
                                               separators=(",", ":")), encoding="utf-8")
    (DOCS / "prov").mkdir(exist_ok=True)
    for k, v in prov.items():
        (DOCS / "prov" / f"{k}.json").write_text(json.dumps({"type": "FeatureCollection", "features": v}, separators=(",", ":")),
                                                 encoding="utf-8")


def redondear4(c):
    return [redondear4(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 4), round(c[1], 4)]


MESES_C = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"]
VISIBLES = "AGUA|ALCANTARILL|DESAG|EDUCATIV|COLEGIO|SALUD|PISTA|VEREDA|VIAL|PUENTE|RIEGO|ESTADIO|LOSA|MERCADO"


def ejemplos(p, inv, cen):
    """Una obra real por departamento y eleccion: empezo en el anio electoral, se pago entre 25% y
    75% de su costo y no volvio a recibir pagos desde que entro el nuevo alcalde."""
    g = p.groupby(["obra", "PROYECTO", "UBIGEO"]).agg(ini=("t", "min"), fin=("t", "max"),
                                                       pag=("DEVENGADO", "sum")).reset_index()
    g = g.join(inv, on="PROYECTO")
    g["av"] = g["pag"] / g["costo"]
    g["UBIGEO"] = g["UBIGEO"].where(g["UBIGEO"].str[-2:] != "00", g["UBIGEO"].str[:4] + "01")
    g = g[g["av"].between(0.25, 0.75) & g["costo"].between(1e6, 40e6)
          & g["NOMBRE_INVERSION"].str.upper().str.contains(VISIBLES, na=False) & g["UBIGEO"].isin(cen.index)
          & ~g["NOMBRE_INVERSION"].str.contains("\ufffd", na=True)]  # nombres con tildes rotas en origen
    res = {}
    for E in [2010, 2014, 2018, 2022]:
        e = g[(g["ini"] // 12 == E) & (g["ini"] % 12 < 10) & (g["fin"] // 12 == E)]
        for dep, h in [("PE", e)] + list(e.groupby(e["UBIGEO"].str[:2])):
            r = h.sort_values("costo").iloc[-1]
            res.setdefault(dep, {})[str(E)] = {
                "n": r["NOMBRE_INVERSION"].capitalize()[:140], "lugar": cen.at[r["UBIGEO"], "nombre"],
                "costo": round(r["costo"] / 1e6, 1), "pct": round(100 * r["av"]),
                "ini": f"{MESES_C[r['ini'] % 12]} {E}", "fin": f"{MESES_C[r['fin'] % 12]} {E}"}
    return res


def main():
    p = A.pagos()
    d = inconclusas(p)
    # Abandono por departamento y provincia ("PE" = todo el pais) y por anio (transiciones y placebos).
    abandono = []
    for dep, g in [("PE", d)] + list(d.groupby("dep")) + list(d.groupby(d["UBIGEO"].str[:4])):
        for anio, h in g.groupby("anio"):
            abandono.append({"dep": dep, "anio": int(anio), "transicion": anio in A.TRANSICIONES,
                             "n": len(h), "abandonadas": int(h["abandonada"].sum()),
                             "pct": round(100 * h["abandonada"].mean(), 1)})
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

    geo = json.loads((ORIG / "distritos_inei.geojson").read_text(encoding="utf-8"))
    deps = {f["properties"]["IDDPTO"]: f["properties"]["NOMBDEP"].title() for f in geo["features"]}
    provs = {f["properties"]["IDPROV"]: f["properties"]["NOMBPROV"].title() for f in geo["features"]}
    datos = {
        "meses": [f"{t // 12}-{t % 12 + 1:02d}" for t in meses],
        "serie": serie,
        "departamentos": dict(sorted(deps.items(), key=lambda x: x[1])),
        "provincias": dict(sorted(provs.items(), key=lambda x: x[1])),
        "abandono": abandono,
        "partido": cambio_partido(d),
        "relaciones": relaciones(d),
        "ejemplos": ejemplos(p, inversiones(), centroides()),
        "regresion": json.loads((PROC / "resultados_ejecucion.json").read_text()),
        "paralizadas": int((pd.read_excel(ORIG / "obras_paralizadas_jun2026.xlsx")
                            .filter(like="NIVEL").iloc[:, 0].astype(str)
                            .str.contains("LOCAL|^GL$")).sum()),
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, default=float),
                                     encoding="utf-8")
    (DOCS / "mapa.json").write_text(json.dumps(mapa3d(m, d, inversiones(), centroides()),
                                               ensure_ascii=False, separators=(",", ":")),
                                    encoding="utf-8")


if __name__ == "__main__":
    distritos()
    main()
