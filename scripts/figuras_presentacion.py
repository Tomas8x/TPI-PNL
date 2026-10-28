"""Figuras para la presentación: sin título (lo pone la diapositiva) y con letra grande.

Uso:
    .venv/Scripts/python scripts/figuras_presentacion.py

Necesita las salidas de analisis_sentimiento.py, analisis_entidades.py y
analisis_mercado.py.

Salida: reports/figures/pres_*.png, en proporción 8,4 x 5 para el espacio de
figura de presentacion/presentacion.html.
"""

import os

import numpy as np
import pandas as pd

from graficos import (COLOR_SUB, CORTE, ETIQUETA_SUB, FIGURAS, SERIES, SUPERFICIE, TINTA, TINTA_2,
                      eje_fechas, plt, trimestre_a_fecha)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
TABLAS = os.path.join(ROOT, "reports", "tablas")
SUBS = ["devsarg", "empleos_AR", "taquerosprogramadores"]
TAMANO = (8.4, 5.0)

plt.rcParams.update({"font.size": 15, "legend.fontsize": 14, "xtick.labelsize": 14, "ytick.labelsize": 14,
                     "axes.labelsize": 14, "lines.linewidth": 2.6})


def guardar(fig, nombre):
    fig.tight_layout()
    ruta = os.path.join(FIGURAS, nombre)
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return ruta


def marcar_corte(ax, alto=1.0):
    """Línea del corte con la etiqueta "ChatGPT"; alto es la posición vertical de la etiqueta (0 a 1)."""
    ax.axvline(CORTE, color=TINTA_2, linewidth=1.4, linestyle=(0, (4, 3)), zorder=1)
    ax.annotate("ChatGPT", xy=(CORTE, alto), xycoords=("data", "axes fraction"), xytext=(5, -2),
                textcoords="offset points", ha="left", va="top", fontsize=14, color=TINTA_2)


def leyenda(ax, **kwargs):
    """Leyenda con fondo de superficie, para que la línea del corte no la cruce."""
    ax.legend(frameon=True, facecolor=SUPERFICIE, edgecolor="none", framealpha=1, **kwargs)


def etiqueta_y(ax, texto):
    """Unidad arriba del eje y, horizontal, en lugar de un rótulo girado."""
    ax.annotate(texto, xy=(0, 1), xycoords="axes fraction", xytext=(-4, 12), textcoords="offset points",
                ha="left", va="bottom", fontsize=13, color=TINTA_2)


def tono_mensual():
    """% de textos negativos por mes, con las rectas de la regresión segmentada de r/devsarg."""
    m = pd.read_csv(os.path.join(PROC, "sentimiento_mensual.csv"))
    m = m[(m.tipo == "todos") & (m.n >= 100)]
    fig, ax = plt.subplots(figsize=TAMANO)
    lineas = {}
    for sub in ["empleos_AR", "devsarg"]:
        s = m[m.subreddit == sub]
        x = pd.PeriodIndex(s.mes, freq="M").to_timestamp()
        lineas[sub], = ax.plot(x, s.pct_neg, color=COLOR_SUB[sub], label=ETIQUETA_SUB[sub],
                               linewidth=1.8 if sub == "empleos_AR" else 2.6,
                               alpha=0.75 if sub == "empleos_AR" else 1)

    # Mismo modelo que sent_series_segmentadas.csv: noviembre de 2022 cuenta como "antes".
    s = m[m.subreddit == "devsarg"].copy()
    p = pd.PeriodIndex(s.mes, freq="M")
    t = np.array([(x - pd.Period(CORTE, "M")).n for x in p])
    despues = (t >= 1).astype(float)
    X = np.column_stack([np.ones_like(t), t, despues, t * despues])
    coef, *_ = np.linalg.lstsq(X, s.pct_neg.to_numpy(), rcond=None)
    ajuste = X @ coef
    x = p.to_timestamp()
    for tramo in [despues == 0, despues == 1]:
        lineas["ajuste"], = ax.plot(x[tramo], ajuste[tramo], color=TINTA, linewidth=2, linestyle=(0, (5, 3)),
                                    label="Tendencia de r/devsarg")
    def coma(v):
        return f"{v:+.2f}".replace(".", ",")
    ax.annotate(f"Antes: {coma(coef[1])} por mes", xy=(pd.Timestamp("2021-01-15"), 40.5),
                fontsize=15, color=TINTA, fontweight="bold")
    ax.annotate(f"Después: {coma(coef[1] + coef[3])} por mes", xy=(pd.Timestamp("2024-09-01"), 25),
                fontsize=15, color=TINTA, fontweight="bold")

    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylim(0, 45)
    etiqueta_y(ax, "% de textos negativos")
    leyenda(ax, loc="lower right", handles=[lineas["devsarg"], lineas["empleos_AR"], lineas["ajuste"]])
    return guardar(fig, "pres_tono_mensual.png")


def tono_trimestral():
    q = pd.read_csv(os.path.join(PROC, "sentimiento_trimestral.csv"))
    q = q[(q.tipo == "todos") & (q.n >= 300)]
    fig, ax = plt.subplots(figsize=TAMANO)
    for sub in SUBS:
        s = q[q.subreddit == sub]
        ax.plot(trimestre_a_fecha(s.trimestre), s.pct_neg, color=COLOR_SUB[sub], label=ETIQUETA_SUB[sub])
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylim(0, 45)
    etiqueta_y(ax, "% de textos negativos, por trimestre")
    leyenda(ax, loc="lower right")
    return guardar(fig, "pres_tono_tres_subs.png")


def ia_por_sub():
    t = pd.read_csv(os.path.join(TABLAS, "ent_ia_trimestral.csv"))
    t = t[t.textos >= 500]
    fig, ax = plt.subplots(figsize=TAMANO)
    for sub in SUBS:
        s = t[t.subreddit == sub]
        ax.plot(trimestre_a_fecha(s.trimestre), s.tasa_ia_cualquiera / 10, color=COLOR_SUB[sub],
                label=ETIQUETA_SUB[sub])
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylim(bottom=0)
    etiqueta_y(ax, "% de textos que mencionan la IA, por trimestre")
    leyenda(ax, loc="center left", bbox_to_anchor=(0.0, 0.66), fontsize=13)
    return guardar(fig, "pres_ia_por_sub.png")


def mercado():
    """Avisos de Indeed y Hacker News y empleo SIPA, con base noviembre de 2022 = 100."""
    m = pd.read_csv(os.path.join(PROC, "mercado_mensual.csv"))
    m = m[(m.mes >= "2019-01") & (m.mes <= "2026-10")].set_index("mes")
    q = pd.read_csv(os.path.join(PROC, "mercado_trimestral.csv"))
    q = q[(q.trimestre >= "2019Q1") & (q.sipa_informatica.notna())]
    q = q[~q.sipa_provisorio.fillna(False).astype(bool)]
    fig, ax = plt.subplots(figsize=TAMANO)
    x = pd.PeriodIndex(m.index, freq="M").to_timestamp()
    indeed = 100 * m.indeed_new / m.loc["2022-11", "indeed_new"]
    hn = m.hn_avisos.rolling(3, center=True, min_periods=2).mean()
    hn = 100 * hn / hn.loc["2022-11"]
    sipa = 100 * q.sipa_informatica / q.set_index("trimestre").loc["2022Q4", "sipa_informatica"]
    series = [(x, indeed, SERIES[6], "Indeed: avisos de software (EE.UU.)"),
              (x, hn, SERIES[3], "Hacker News: avisos (media de 3 meses)"),
              (trimestre_a_fecha(q.trimestre), sipa, SERIES[5], "SIPA: empleo informático (Argentina)")]
    for xs, ys, color, nombre in series:
        ax.plot(xs, ys, color=color, label=nombre)
    ax.axhline(100, color=TINTA_2, linewidth=0.8)
    marcar_corte(ax, alto=0.1)
    eje_fechas(ax)
    ax.set_ylim(0, 200)
    etiqueta_y(ax, "índice, noviembre de 2022 = 100")
    ax.set_xlim(pd.Timestamp("2018-11-01"), pd.Timestamp("2026-12-31"))
    leyenda(ax, loc="upper right", fontsize=13)
    return guardar(fig, "pres_mercado.png")


def main():
    for f in [tono_mensual, tono_trimestral, ia_por_sub, mercado]:
        print(f())


if __name__ == "__main__":
    main()
