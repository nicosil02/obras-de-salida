"""Limpia las inversiones municipales del MEF y arma el panel distrito x mes.

Salidas (datos/procesados/):
- obras_municipales.parquet: una fila por inversion municipal, con fecha de viabilidad,
  monto, tipo de obra y coordenadas.
- panel_distrito_mes.parquet: obras aprobadas y monto por distrito y mes (2006-2026).
"""
import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIG = RAIZ / "datos" / "originales"
PROC = RAIZ / "datos" / "procesados"

COLS = ["NIVEL", "CODIGO_UNICO", "NOMBRE_INVERSION", "SEC_EJEC", "FECHA_REGISTRO",
        "FECHA_VIABILIDAD", "MONTO_VIABLE", "FUNCION", "DES_TIPOLOGIA", "TIPO_INVERSION",
        "UBIGEO", "DEPARTAMENTO", "PROVINCIA", "DISTRITO", "LATITUD", "LONGITUD",
        "PRIMER_DEVENGADO"]

# Obras "visibles" (cemento que se ve) frente a servicios basicos. Se clasifica por el
# nombre de la inversion; el orden importa: la primera coincidencia gana.
TIPOS = [
    ("Agua y saneamiento", r"AGUA POTABLE|SANEAMIENTO|ALCANTARILLADO|DESAG"),
    ("Pistas y veredas", r"PISTA|VEREDA|PAVIMENT|CALLE|JIRON|JR\.|AVENIDA|AV\."),
    ("Plazas y parques", r"PLAZA|PARQUE|ALAMEDA|MALECON|AREAS? VERDES?"),
    ("Deporte", r"LOSA|ESTADIO|COLISEO|DEPORTIV|POLIDEPORTIVO|CANCHA|GRASS"),
    ("Caminos y puentes", r"CAMINO VECINAL|TROCHA|CARRETERA|PUENTE|VIAL"),
    ("Educacion", r"EDUCATIV|INICIAL|PRIMARIA|SECUNDARIA|I\.E\.|COLEGIO"),
    ("Salud", r"SALUD|HOSPITAL|POSTA"),
    ("Riego y agro", r"RIEGO|CANAL|AGRICOL|PECUARI|GANAD"),
]


def obras():
    cols = lambda c: c in COLS
    df = pd.concat([pd.read_csv(ORIG / f, dtype=str, usecols=cols)
                    for f in ["DETALLE_INVERSIONES.csv", "CIERRE_INVERSIONES.csv"]])
    df = df[df["NIVEL"] == "GL"].drop_duplicates("CODIGO_UNICO")
    df["FECHA_VIABILIDAD"] = pd.to_datetime(df["FECHA_VIABILIDAD"], errors="coerce")
    # Mes del primer pago (AAAAMM): cuando la obra empieza a ejecutarse de verdad.
    df["FECHA_INICIO"] = pd.to_datetime(df["PRIMER_DEVENGADO"].str[:6], format="%Y%m",
                                        errors="coerce")
    df["MONTO_VIABLE"] = pd.to_numeric(df["MONTO_VIABLE"], errors="coerce")
    df["LATITUD"] = pd.to_numeric(df["LATITUD"], errors="coerce")
    df["LONGITUD"] = pd.to_numeric(df["LONGITUD"], errors="coerce")
    # Coordenadas fuera del Peru (errores de registro) se dejan vacias.
    fuera = ~df["LATITUD"].between(-18.5, 0.1) | ~df["LONGITUD"].between(-81.5, -68.5)
    df.loc[fuera, ["LATITUD", "LONGITUD"]] = None
    df["TIPO_OBRA"] = "Otros"
    nombre = df["NOMBRE_INVERSION"].fillna("").str.upper()
    for tipo, patron in reversed(TIPOS):
        df.loc[nombre.str.contains(patron, regex=True), "TIPO_OBRA"] = tipo
    return df.drop(columns=["NIVEL", "PRIMER_DEVENGADO"])


def panel(df):
    # Dos medidas por distrito y mes: obras aprobadas (viabilidad) y obras iniciadas
    # (primer pago), cada una con su monto viable.
    partes = []
    for fecha, sufijo in [("FECHA_VIABILIDAD", "aprobadas"), ("FECHA_INICIO", "iniciadas")]:
        d = df.assign(MES=df[fecha].dt.to_period("M").dt.to_timestamp())
        partes.append(d.groupby(["UBIGEO", "MES"]).agg(
            **{f"obras_{sufijo}": ("CODIGO_UNICO", "size"),
               f"monto_{sufijo}": ("MONTO_VIABLE", "sum")}))
    p = pd.concat(partes, axis=1)
    # Completar con ceros los meses sin obras para cada distrito.
    meses = pd.date_range("2006-01-01", "2026-09-01", freq="MS")
    idx = pd.MultiIndex.from_product([df["UBIGEO"].dropna().unique(), meses],
                                     names=["UBIGEO", "MES"])
    return p.reindex(idx, fill_value=0).fillna(0).reset_index()


def clave(*cols):
    # Departamento|provincia|distrito sin tildes ni signos, para cruzar fuentes por nombre.
    s = cols[0].astype(str)
    for c in cols[1:]:
        s = s + "|" + c.astype(str)
    return (s.str.normalize("NFD").str.encode("ascii", "ignore").str.decode("ascii")
            .str.upper().str.replace(r"[^A-Z|]", "", regex=True))


def onpe(anio, nivel):
    """Ganador de cada eleccion municipal segun los resultados oficiales por mesa de la ONPE."""
    c = ["DEPARTAMENTO", "PROVINCIA", "DISTRITO", "AGRUPACION_POLITICA", "VOTOS_OBTENIDOS"]
    f = ORIG / "elecciones" / "onpe" / f"ERM{anio}_Municipal_{nivel}.csv"
    try:
        e = pd.read_csv(f, sep=";", dtype=str, usecols=c, encoding="utf-8-sig")
    except UnicodeDecodeError:  # 2014 y 2018 vienen en latin-1
        e = pd.read_csv(f, sep=";", dtype=str, usecols=c, encoding="cp1252")
    # Mesas no contabilizadas traen texto en VOTOS_OBTENIDOS: cuentan como 0.
    e["VOTOS_OBTENIDOS"] = pd.to_numeric(e["VOTOS_OBTENIDOS"], errors="coerce").fillna(0)
    e = e[e["AGRUPACION_POLITICA"].notna()]
    # La eleccion provincial se vota en toda la provincia: se agrega por provincia.
    lugar = ["DEPARTAMENTO", "PROVINCIA"] + (["DISTRITO"] if nivel == "Distrital" else [])
    v = e.groupby(lugar + ["AGRUPACION_POLITICA"], as_index=False)["VOTOS_OBTENIDOS"].sum()
    v["pct"] = v["VOTOS_OBTENIDOS"] / v.groupby(lugar)["VOTOS_OBTENIDOS"].transform("sum")
    v = v.sort_values("pct", ascending=False)
    top = v.groupby(lugar).agg(
        ganador=("AGRUPACION_POLITICA", "first"), pct_ganador=("pct", "first"),
        segundo=("pct", lambda s: s.iloc[1] if len(s) > 1 else 0.0),
        n_partidos=("pct", "size")).reset_index()
    top["margen"] = top["pct_ganador"] - top["segundo"]
    top["anio"] = anio
    return top


def elecciones():
    """Ganador de cada eleccion municipal (2006-2022) con su partido y margen.

    Fuente: resultados oficiales por mesa de la ONPE. La ONPE usa el ubigeo de RENIEC, asi que
    se pasa al ubigeo INEI cruzando por nombre de departamento, provincia y distrito."""
    # Nombre -> ubigeo INEI: mapa de distritos y, para nombres antiguos o distritos nuevos,
    # las inversiones del MEF.
    geo = json.loads((ORIG / "distritos_inei.geojson").read_text(encoding="utf-8"))
    g = pd.DataFrame([f["properties"] for f in geo["features"]])
    g = g.rename(columns={"NOMBDEP": "d", "NOMBPROV": "p", "NOMBDIST": "n", "IDDIST": "u"})
    mef = pd.read_csv(ORIG / "DETALLE_INVERSIONES.csv", dtype=str,
                      usecols=["DEPARTAMENTO", "PROVINCIA", "DISTRITO", "UBIGEO"]).dropna()
    a_inei = pd.concat([pd.DataFrame({"clave": clave(g["d"], g["p"], g["n"]), "UBIGEO": g["u"]}),
                        pd.DataFrame({"clave": clave(mef["DEPARTAMENTO"], mef["PROVINCIA"], mef["DISTRITO"]),
                                      "UBIGEO": mef["UBIGEO"]})])         .drop_duplicates("clave").set_index("clave")["UBIGEO"]
    # Provincia -> capital (ubigeo PPPP01): la gobierna la municipalidad provincial.
    a_prov = (a_inei.str[:4] + "01").groupby(a_inei.index.str.rsplit("|", n=1).str[0]).first()

    dist, prov = [], []
    for anio in [2006, 2010, 2014, 2018, 2022]:
        d = onpe(anio, "Distrital")
        d["UBIGEO"] = clave(d["DEPARTAMENTO"], d["PROVINCIA"], d["DISTRITO"]).map(a_inei)
        p = onpe(anio, "Provincial")
        p["UBIGEO"] = clave(p["DEPARTAMENTO"], p["PROVINCIA"]).map(a_prov)
        print(f"{anio}: sin ubigeo distrital {d['UBIGEO'].isna().mean():.1%}, provincial {p['UBIGEO'].isna().mean():.1%}")
        dist.append(d); prov.append(p)
    cols = ["UBIGEO", "anio", "nivel", "ganador", "pct_ganador", "margen", "n_partidos"]
    el = pd.concat([pd.concat(dist).assign(nivel="distrital"), pd.concat(prov).assign(nivel="provincial")])
    el = el.dropna(subset=["UBIGEO"]).reindex(columns=cols).sort_values(["UBIGEO", "anio"])
    el = el.drop_duplicates(["UBIGEO", "anio", "nivel"])
    # Cambio de partido respecto de la eleccion anterior en el mismo distrito.
    # Se compara sin tildes ni signos: la ONPE escribe el mismo partido con y sin tildes.
    nom = clave(el["ganador"])
    previo = nom.groupby([el["UBIGEO"], el["nivel"]]).shift()
    el["cambio_partido"] = (nom != previo).where(previo.notna())
    return el


def relaciones():
    """Quien entra en cada municipalidad y su relacion con la gestion que sale (2018 y 2022).

    Fuente: autoridades electas del JNE (datos abiertos), que identifica a cada persona por su
    DNI. Para cada alcalde electo en E se mira la gestion elegida en E-4 en la misma
    municipalidad: si su partido es el mismo, si fue regidor (de la lista del alcalde saliente
    o de otra) y si ya habia sido alcalde."""
    a = pd.read_excel(ORIG / "elecciones" / "jne" / "Autoridades_Electas_20251113.xls")
    a = a[a["PROCESOELECTORAL"].str.match(r"ELECCIONES REGIONALES Y MUNICIPALES (2014|2018|2022)$")
          & a["CARGO"].str.contains("ALCALDE|REGIDOR")].copy()
    a["dni"] = a["DOCUMENTOIDENTIDAD"].astype(str).str.zfill(8)
    a["nivel"] = a["CARGO"].str.split().str[-1].str.lower()
    a["alcalde"] = a["CARGO"].str.startswith("ALCALDE")
    a["partido"] = clave(a["ORGANIZACIONPOLITICA"])
    # Ubigeo INEI por nombre (como en elecciones); la provincial gobierna la capital PPPP01.
    geo = json.loads((ORIG / "distritos_inei.geojson").read_text(encoding="utf-8"))
    g = pd.DataFrame([f["properties"] for f in geo["features"]])
    a_inei = pd.Series(g["IDDIST"].values, index=clave(g["NOMBDEP"], g["NOMBPROV"], g["NOMBDIST"]))
    a_prov = (a_inei.str[:4] + "01").groupby(a_inei.index.str.rsplit("|", n=1).str[0]).first()
    a["UBIGEO"] = clave(a["REGION"], a["PROVINCIA"], a["DISTRITO"]).map(a_inei)
    prov = a["nivel"] == "provincial"
    a.loc[prov, "UBIGEO"] = clave(a.loc[prov, "REGION"], a.loc[prov, "PROVINCIA"]).map(a_prov)
    print(f"autoridades sin ubigeo: {a['UBIGEO'].isna().mean():.1%}")
    a = a.dropna(subset=["UBIGEO"])
    # Un alcalde por municipalidad y eleccion: el proclamado primero (no sus reemplazos).
    alc = (a[a["alcalde"]].sort_values("FEINICIOVIGENCIA")
           .drop_duplicates(["UBIGEO", "nivel", "ANIOELECCION"]))
    filas = []
    for E in [2018, 2022]:
        nuevo, sale = alc[alc["ANIOELECCION"] == E], alc[alc["ANIOELECCION"] == E - 4]
        reg = a[(a["ANIOELECCION"] == E - 4) & ~a["alcalde"]]
        antes = set(zip(alc.loc[alc["ANIOELECCION"] < E, "UBIGEO"], alc.loc[alc["ANIOELECCION"] < E, "dni"]))
        m = nuevo.merge(sale[["UBIGEO", "nivel", "partido", "dni"]], on=["UBIGEO", "nivel"],
                        how="inner", suffixes=("", "_sale"))
        m = m.merge(reg[["UBIGEO", "nivel", "dni", "partido"]].rename(columns={"partido": "partido_reg"}),
                    on=["UBIGEO", "nivel", "dni"], how="left")
        filas.append(pd.DataFrame({
            "UBIGEO": m["UBIGEO"], "anio": E, "nivel": m["nivel"],
            "mismo_partido": m["partido"] == m["partido_sale"],
            "fue_regidor": m["partido_reg"].notna(),
            "regidor_del_saliente": m["partido_reg"] == m["partido_sale"],
            "fue_alcalde": [(u, d) in antes for u, d in zip(m["UBIGEO"], m["dni"])]}))
    r = pd.concat(filas).drop_duplicates(["UBIGEO", "anio", "nivel"])
    print(r.groupby("anio")[["mismo_partido", "fue_regidor", "regidor_del_saliente", "fue_alcalde"]].mean().round(3))
    return r


if __name__ == "__main__":
    PROC.mkdir(parents=True, exist_ok=True)
    el = elecciones()
    el.to_parquet(PROC / "elecciones_distritales.parquet", index=False)
    relaciones().to_parquet(PROC / "relaciones_alcaldes.parquet", index=False)
    print(el.groupby("anio").agg(n=("UBIGEO", "size"), cambio=("cambio_partido", "mean")).round(3))
    o = obras()
    o.to_parquet(PROC / "obras_municipales.parquet", index=False)
    p = panel(o)
    p.to_parquet(PROC / "panel_distrito_mes.parquet", index=False)
    print(f"obras: {len(o):,} | distritos: {p['UBIGEO'].nunique():,} | panel: {len(p):,}")
    print(o["TIPO_OBRA"].value_counts(normalize=True).round(3).to_string())
