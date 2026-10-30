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


def elecciones():
    """Ganador de cada eleccion distrital (2006-2022) con su partido y margen.

    2010-2018: resultados por distrito con ubigeo INEI. 2022: resultados ONPE por mesa,
    con ubigeo RENIEC (se pasa a INEI cruzando por nombre). 2006: autoridades de Infogob,
    sin ubigeo (tambien por nombre)."""
    E = ORIG / "elecciones"
    filas = []
    for anio in [2010, 2014, 2018]:
        d = pd.read_stata(E / f"elecciones{anio}distb.dta")
        d.columns = [c.replace("Organizacin_Poltica", "OrganizaciónPolítica") for c in d.columns]
        d = d[d["Votos_porc"].notna()]  # solo organizaciones (no blancos ni nulos)
        g = d.sort_values("Votos", ascending=False).drop_duplicates("Ubigeo")
        filas.append(pd.DataFrame({
            "UBIGEO": g["Ubigeo"].astype(str).str.zfill(6), "anio": anio,
            "ganador": g["OrganizaciónPolítica"], "pct_ganador": g["Votos_ganador_porc"],
            "margen": g["margvictoria"], "n_partidos": g["N_Partidos"],
            "clave": clave(g.iloc[:, list(g.columns).index("Provincia") - 1],
                           g["Provincia"], g["Distrito"])}))
    base = pd.concat(filas)
    # Nombre -> ubigeo INEI: de las elecciones y, para distritos creados despues de 2018,
    # de las inversiones del MEF.
    mef = pd.read_csv(ORIG / "DETALLE_INVERSIONES.csv", dtype=str,
                      usecols=["DEPARTAMENTO", "PROVINCIA", "DISTRITO", "UBIGEO"]).dropna()
    mef["clave"] = clave(mef["DEPARTAMENTO"], mef["PROVINCIA"], mef["DISTRITO"])
    a_inei = pd.concat([base[["clave", "UBIGEO"]], mef[["clave", "UBIGEO"]]]) \
        .drop_duplicates("clave").set_index("clave")["UBIGEO"]

    e = pd.read_csv(E / "ERM2022_Municipal_Distrital.csv", sep=";", encoding="utf-8-sig",
                    dtype={"UBIGEO": str}, usecols=["UBIGEO", "DEPARTAMENTO", "PROVINCIA",
                                                    "DISTRITO", "AGRUPACION_POLITICA",
                                                    "VOTOS_OBTENIDOS"], low_memory=False)
    # Mesas no contabilizadas traen texto en VOTOS_OBTENIDOS: cuentan como 0.
    e["VOTOS_OBTENIDOS"] = pd.to_numeric(e["VOTOS_OBTENIDOS"], errors="coerce").fillna(0)
    e = e[e["AGRUPACION_POLITICA"].notna()]
    v = e.groupby(["DEPARTAMENTO", "PROVINCIA", "DISTRITO", "AGRUPACION_POLITICA"],
                  as_index=False)["VOTOS_OBTENIDOS"].sum()
    v["pct"] = v["VOTOS_OBTENIDOS"] / v.groupby(["DEPARTAMENTO", "PROVINCIA", "DISTRITO"])[
        "VOTOS_OBTENIDOS"].transform("sum")
    v = v.sort_values("pct", ascending=False)
    top = v.groupby(["DEPARTAMENTO", "PROVINCIA", "DISTRITO"]).agg(
        ganador=("AGRUPACION_POLITICA", "first"), pct_ganador=("pct", "first"),
        segundo=("pct", lambda s: s.iloc[1] if len(s) > 1 else 0.0),
        n_partidos=("pct", "size")).reset_index()
    top["clave"] = clave(top["DEPARTAMENTO"], top["PROVINCIA"], top["DISTRITO"])
    top["UBIGEO"] = top["clave"].map(a_inei)
    top["margen"] = top["pct_ganador"] - top["segundo"]
    top["anio"] = 2022

    i = pd.read_excel(E / "ERM2006_Autoridades_Distrital.xlsx")
    i.columns = ["region", "provincia", "distrito", "cargo"] + list(i.columns[4:])
    i = i[i["cargo"].str.contains("ALCALDE", na=False)]
    org = [c for c in i.columns if "Organizaci" in c and "Tipo" not in c][0]
    pct = [c for c in i.columns if c.startswith("%")][0]
    i = pd.DataFrame({"clave": clave(i["region"], i["provincia"], i["distrito"]),
                      "ganador": i[org], "pct_ganador": i[pct], "anio": 2006})
    i["UBIGEO"] = i["clave"].map(a_inei)

    # Capitales de provincia: las gobierna la municipalidad provincial (ubigeo PPPP01).
    # Ganadores 2014-2022 de los archivos de Infogob procesados por el proyecto vigia-peru.
    prov = []
    for anio in [2014, 2018, 2022]:
        j = json.loads((E / f"autoridades-{anio}-vigia.json").read_text(encoding="utf-8"))
        prov += [{"UBIGEO": r["u"] + "01", "anio": anio, "ganador": j["orgs"][r["o"]]["n"].upper(),
                  "pct_ganador": r["p"], "nivel": "provincial"} for r in j["provincial"]]
    cols = ["UBIGEO", "anio", "nivel", "ganador", "pct_ganador", "margen", "n_partidos"]
    el = pd.concat([i, base, top]).assign(nivel="distrital")
    el = pd.concat([el, pd.DataFrame(prov)])
    sin = el["UBIGEO"].isna().groupby(el["anio"]).mean()
    print("sin ubigeo por anio:", sin.round(3).to_dict())
    el = el.dropna(subset=["UBIGEO"]).reindex(columns=cols).sort_values(["UBIGEO", "anio"])
    # Cambio de partido respecto de la eleccion anterior en el mismo distrito.
    previo = el.groupby("UBIGEO")["ganador"].shift()
    el["cambio_partido"] = (el["ganador"].str.strip() != previo.str.strip()).where(previo.notna())
    return el


if __name__ == "__main__":
    PROC.mkdir(parents=True, exist_ok=True)
    el = elecciones()
    el.to_parquet(PROC / "elecciones_distritales.parquet", index=False)
    print(el.groupby("anio").agg(n=("UBIGEO", "size"), cambio=("cambio_partido", "mean")).round(3))
    o = obras()
    o.to_parquet(PROC / "obras_municipales.parquet", index=False)
    p = panel(o)
    p.to_parquet(PROC / "panel_distrito_mes.parquet", index=False)
    print(f"obras: {len(o):,} | distritos: {p['UBIGEO'].nunique():,} | panel: {len(p):,}")
    print(o["TIPO_OBRA"].value_counts(normalize=True).round(3).to_string())
