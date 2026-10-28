"""Cruce del tono de Reddit con el mercado laboral IT (hipótesis B).

Uso:
    .venv/Scripts/python scripts/analisis_cruce.py

Necesita data/processed/sentimiento_mensual.csv y sentimiento_trimestral.csv
(analisis_sentimiento.py) y mercado_mensual.csv y mercado_trimestral.csv
(analisis_mercado.py).

Dos series con tendencia se correlacionan aunque no tengan relación, así que
además de la correlación en niveles se calcula la correlación de las
variaciones (diferencia mes a mes, o interanual en SIPA) y con rezagos de 0 a
6 meses del mercado respecto de Reddit.

Salida:
- reports/tablas/cruce_correlaciones.csv
- reports/figures/cruce_mercado_sentimiento.png
"""

import os

import numpy as np
import pandas as pd
from scipy import stats

from graficos import (COLOR_SUB, ETIQUETA_SUB, SERIES, TINTA_2, eje_fechas,
                      marcar_corte, plt, trimestre_a_fecha)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
TABLAS = os.path.join(ROOT, "reports", "tablas")
DESDE, HASTA = "2021-03", "2026-09"  # r/devsarg tiene menos de 100 textos por mes antes
MERCADO = {
    "indeed_new": "Indeed: avisos nuevos de software (EE.UU.)",
    "hn_avisos": "Hacker News: avisos por hilo",
    "hn_pct_junior": "Hacker News: % de avisos junior",
}
REZAGOS = range(0, 7)


def cargar_mensual():
    sent = pd.read_csv(os.path.join(PROC, "sentimiento_mensual.csv"))
    sent = sent[(sent.tipo == "todos")].pivot(index="mes", columns="subreddit", values="pct_neg")
    sent.columns = [f"neg_{c}" for c in sent.columns]
    merc = pd.read_csv(os.path.join(PROC, "mercado_mensual.csv")).set_index("mes")
    df = sent.join(merc, how="inner")
    return df.loc[DESDE:HASTA]


def correlacion(x, y):
    ok = x.notna() & y.notna()
    if ok.sum() < 12:
        return np.nan, np.nan, int(ok.sum())
    r, p = stats.spearmanr(x[ok], y[ok])
    return round(r, 3), round(p, 4), int(ok.sum())


def correlaciones(df, trimestral):
    filas = []
    for sub in ["devsarg", "empleos_AR"]:
        neg = df[f"neg_{sub}"]
        for var, nombre in MERCADO.items():
            for rezago in REZAGOS:
                # rezago k: el mercado del mes t-k contra el tono del mes t
                merc = df[var].shift(rezago)
                r, p, n = correlacion(neg, merc)
                rd, pd_, nd = correlacion(neg.diff(), merc.diff())
                filas.append({"subreddit": sub, "mercado": nombre, "frecuencia": "mensual",
                              "rezago": rezago, "spearman_niveles": r, "p_niveles": p,
                              "spearman_variaciones": rd, "p_variaciones": pd_, "n": n})
        s = trimestral[trimestral.subreddit == sub].set_index("trimestre")
        r, p, n = correlacion(s.pct_neg, s.sipa_informatica)
        rd, pd_, nd = correlacion(s.pct_neg.diff(4), s.sipa_informatica.pct_change(4))
        filas.append({"subreddit": sub, "mercado": "SIPA: empleo registrado en informática (AR)",
                      "frecuencia": "trimestral", "rezago": 0, "spearman_niveles": r, "p_niveles": p,
                      "spearman_variaciones": rd, "p_variaciones": pd_, "n": n})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(os.path.join(TABLAS, "cruce_correlaciones.csv"), index=False)
    return tabla


def cargar_trimestral():
    sent = pd.read_csv(os.path.join(PROC, "sentimiento_trimestral.csv"))
    sent = sent[(sent.tipo == "todos") & (sent.n >= 300)][["subreddit", "trimestre", "pct_neg"]]
    merc = pd.read_csv(os.path.join(PROC, "mercado_trimestral.csv"))
    merc = merc[~merc.sipa_provisorio.fillna(False).astype(bool)]  # 2026-T1 está subestimado
    return sent.merge(merc, on="trimestre", how="inner").sort_values(["subreddit", "trimestre"])


def figura(df, trimestral):
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    fig.suptitle("El tono en Reddit y el mercado laboral IT", x=0.01, y=0.995, ha="left",
                 fontsize=15, fontweight="bold")
    fig.text(0.01, 0.962, "Cada panel tiene su propia escala. Fuentes: Reddit (Arctic Shift), "
             "Indeed Hiring Lab, Hacker News, OEDE/SIPA.", ha="left", fontsize=10, color=TINTA_2)
    x = pd.PeriodIndex(df.index, freq="M").to_timestamp()
    ax = axes[0]
    for sub in ["devsarg", "empleos_AR"]:
        ax.plot(x, df[f"neg_{sub}"], color=COLOR_SUB[sub], label=ETIQUETA_SUB[sub], linewidth=1.6)
    ax.set_title("% de textos negativos en Reddit", fontsize=12)
    ax.legend(loc="lower right", fontsize=9)
    paneles = [(axes[1], "indeed_new", "Indeed: avisos nuevos de software en EE.UU. (feb 2020 = 100)"),
               (axes[2], "hn_avisos", "Hacker News \"Who is hiring?\": avisos por mes")]
    for ax, col, titulo in paneles:
        ax.plot(x, df[col], color=SERIES[6], linewidth=1.6)
        ax.set_title(titulo, fontsize=12)
    ax = axes[3]
    s = trimestral[trimestral.subreddit == "devsarg"]
    ax.plot(trimestre_a_fecha(s.trimestre), s.sipa_informatica / 1000, color=SERIES[6], marker="o",
            markersize=4)
    ax.set_title("SIPA: empleo asalariado registrado en informática en Argentina (miles)", fontsize=12)
    for ax in axes:
        marcar_corte(ax, texto="ChatGPT (30/11/2022)" if ax is axes[0] else "")
        ax.set_ylim(bottom=0)
    eje_fechas(axes[-1])
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    ruta = os.path.join(ROOT, "reports", "figures", "cruce_mercado_sentimiento.png")
    fig.savefig(ruta, dpi=160)
    plt.close(fig)
    return ruta


def main():
    os.makedirs(TABLAS, exist_ok=True)
    df = cargar_mensual()
    trimestral = cargar_trimestral()
    tabla = correlaciones(df, trimestral)
    print(tabla[tabla.rezago.isin([0, 3, 6])].to_string())
    print(figura(df, trimestral))


if __name__ == "__main__":
    main()
