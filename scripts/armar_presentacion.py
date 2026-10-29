"""Arma la presentación interactiva: junta los datos de los gráficos y los inserta en la plantilla.

Uso:
    .venv/Scripts/python scripts/armar_presentacion.py

Lee presentacion/plantilla.html y las salidas de los análisis (data/processed/
y reports/tablas/), y escribe presentacion/presentacion.html: un solo archivo,
sin dependencias externas, con los gráficos dibujados en SVG por el navegador.
"""

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
TABLAS = os.path.join(ROOT, "reports", "tablas")
PLANTILLA = os.path.join(ROOT, "presentacion", "plantilla.html")
SALIDA = os.path.join(ROOT, "presentacion", "presentacion.html")
SUBS = ["devsarg", "empleos_AR", "taquerosprogramadores"]
CORTE_MES = pd.Period("2022-11", "M")


def r(x, d=2):
    return None if pd.isna(x) else round(float(x), d)


def trimestre_a_mes(t):
    """'2023Q1' -> '2023-02' (mes central), para ubicar trimestres en un eje mensual."""
    p = pd.Period(t, "Q")
    return str(p.asfreq("M", "start") + 1)


def tono():
    m = pd.read_csv(os.path.join(PROC, "sentimiento_mensual.csv"))
    m = m[(m.tipo == "todos") & (m.n >= 100)]
    series = {s: [[x.mes, r(x.pct_neg, 1)] for x in m[m.subreddit == s].itertuples()] for s in SUBS}

    # Regresión segmentada de r/devsarg, igual que sent_series_segmentadas.csv.
    s = m[m.subreddit == "devsarg"]
    t = np.array([(pd.Period(x, "M") - CORTE_MES).n for x in s.mes])
    despues = (t >= 1).astype(float)
    X = np.column_stack([np.ones_like(t), t, despues, t * despues])
    c, *_ = np.linalg.lstsq(X, s.pct_neg.to_numpy(), rcond=None)
    ajuste = X @ c
    meses = list(s.mes)
    tendencia = {
        "antes": [[meses[i], r(ajuste[i], 2)] for i in range(len(meses)) if despues[i] == 0],
        "despues": [[meses[i], r(ajuste[i], 2)] for i in range(len(meses)) if despues[i] == 1],
        "pendiente_antes": r(c[1], 2),
        "pendiente_despues": r(c[1] + c[3], 2),
    }
    return {"series": series, "tendencia": tendencia}


def anual(sub):
    q = pd.read_csv(os.path.join(PROC, "sentimiento_trimestral.csv"))
    q = q[(q.tipo == "todos") & (q.subreddit == sub)].copy()
    q["anio"] = q.trimestre.str[:4]
    pesos = lambda c: (q[c] * q.n).groupby(q.anio).sum() / q.n.groupby(q.anio).sum()
    return {
        "neg": {a: r(v, 1) for a, v in pesos("pct_neg").items()},
        "enojo": {a: r(100 * v, 1) for a, v in pesos("emo_enojo").items()},
        "alegria": {a: r(100 * v, 1) for a, v in pesos("emo_alegría").items()},
        "tristeza": {a: r(100 * v, 1) for a, v in pesos("emo_tristeza").items()},
    }


def volumen():
    q = pd.read_csv(os.path.join(PROC, "sentimiento_trimestral.csv"))
    q = q[(q.tipo == "todos") & (q.subreddit == "devsarg")]
    # El % anterior al corte sale del período de cada texto (corte el 30/11/2022).
    p = pd.read_parquet(os.path.join(PROC, "sentimiento_textos.parquet"), columns=["subreddit", "periodo"])
    p = p[p.subreddit == "devsarg"]
    return {"trimestres": [[x.trimestre, int(x.n)] for x in q.itertuples()],
            "pct_antes": r(100 * (p.periodo == "antes").mean(), 1)}


def ia():
    t = pd.read_csv(os.path.join(TABLAS, "ent_ia_trimestral.csv"))
    t = t[t.textos >= 500]
    series = {s: [[trimestre_a_mes(x.trimestre), r(x.tasa_ia_cualquiera / 10, 2)]
                  for x in t[t.subreddit == s].itertuples()] for s in SUBS}
    p = pd.read_csv(os.path.join(TABLAS, "ent_ia_participacion.csv"))
    p = p[p.trimestre >= "2023Q1"]
    herramientas = {}
    for h in ["ChatGPT/OpenAI", "Claude", "Copilot", "Cursor", "Gemini/Bard"]:
        herramientas[h.split("/")[0]] = [[trimestre_a_mes(x[0]), r(x[1], 1)]
                                         for x in zip(p.trimestre, p[f"participacion_{h}"])]
    return {"series": series, "herramientas": herramientas}


def temas():
    c = pd.read_csv(os.path.join(TABLAS, "temas_bertopic_cambio.csv"))
    elegidos = ["Aprender a programar", "Frontend (JavaScript, HTML, CSS)", "Java y backend",
                "Sueldo, horario y condiciones", "IA y automatización", "Entrevistas, CV y selección",
                "Mercado saturado y economía"]
    c = c.set_index("tema_nombre").loc[elegidos]
    nombres = {"Frontend (JavaScript, HTML, CSS)": "Frontend (JS, HTML, CSS)",
               "Sueldo, horario y condiciones": "Sueldo y condiciones"}
    return [{"tema": nombres.get(n, n), "antes": r(100 * x.antes_devsarg, 1), "despues": r(100 * x.despues_devsarg, 1)}
            for n, x in c.iterrows()]


def vocab():
    v = pd.read_csv(os.path.join(TABLAS, "vocab_vecinos.csv"))
    c = pd.read_csv(os.path.join(TABLAS, "vocab_cambio.csv")).set_index("palabra")
    salida = {}
    for p in ["ia", "remoto", "mercado", "trabajo", "junior", "empresa"]:
        x = v[v.palabra == p].sort_values("rango").head(8)
        salida[p] = {"antes": list(x.antes), "despues": list(x.despues),
                     "entre": r(c.loc[p, "jaccard_entre"]), "base": r(c.loc[p, "jaccard_base_despues"]),
                     "cambia": bool(c.loc[p, "cambio_jaccard"])}
    return salida


def mercado():
    m = pd.read_csv(os.path.join(PROC, "mercado_mensual.csv"))
    m = m[(m.mes >= "2019-01") & (m.mes <= "2026-10")].set_index("mes")
    hn = m.hn_avisos.rolling(3, center=True, min_periods=2).mean()
    q = pd.read_csv(os.path.join(PROC, "mercado_trimestral.csv"))
    q = q[(q.trimestre >= "2019Q1") & q.sipa_informatica.notna() & ~q.sipa_provisorio.fillna(False).astype(bool)]
    base_sipa = q.set_index("trimestre").loc["2022Q4", "sipa_informatica"]
    return {
        "indeed": [[k, r(100 * v / m.loc["2022-11", "indeed_new"], 1)] for k, v in m.indeed_new.dropna().items()],
        "hn": [[k, r(100 * v / hn.loc["2022-11"], 1)] for k, v in hn.dropna().items()],
        "sipa": [[trimestre_a_mes(t), r(100 * v / base_sipa, 1)] for t, v in zip(q.trimestre, q.sipa_informatica)],
    }


def correlaciones():
    t = pd.read_csv(os.path.join(TABLAS, "cruce_correlaciones.csv"))
    f = t[(t.subreddit == "devsarg") & (t.rezago == 0) & t.mercado.str.startswith("Indeed")].iloc[0]
    return {"niveles": r(f.spearman_niveles), "variaciones": r(f.spearman_variaciones)}


def eventos():
    e = pd.read_csv(os.path.join(ROOT, "docs", "eventos.csv"))
    return [{"fecha": x.fecha, "tipo": x.tipo, "texto": x.corto} for x in e.itertuples()]


def main():
    consolidacion = json.load(open(os.path.join(PROC, "consolidacion.json"), encoding="utf-8"))
    total = sum(v["finales"] for k, v in consolidacion.items() if isinstance(v, dict) and k != "hn_avisos")
    datos = {
        "total_textos": total,
        "avisos_hn": consolidacion["hn_avisos"]["finales"],
        "volumen": volumen(),
        "tono": tono(),
        "anual": {s: anual(s) for s in SUBS},
        "ia": ia(),
        "temas": temas(),
        "vocab": vocab(),
        "mercado": mercado(),
        "correlaciones": correlaciones(),
        "eventos": eventos(),
    }
    with open(PLANTILLA, encoding="utf-8") as f:
        html = f.read()
    marca = "/*__DATOS__*/null"
    assert marca in html, "falta la marca de datos en la plantilla"
    html = html.replace(marca, json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{SALIDA}: {os.path.getsize(SALIDA) / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
