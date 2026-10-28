"""Estilo común de los gráficos del TPI (matplotlib, PNG para las diapositivas).

Uso:
    from graficos import COLOR_SUB, ETIQUETA_SUB, nueva_figura, marcar_corte, guardar

Colores fijos por entidad: cada subreddit tiene siempre el mismo color, en el
orden de la paleta categórica validada (azul, naranja, aqua). Polaridad:
negativo en rojo y positivo en azul, con gris en el medio.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURAS = os.path.join(ROOT, "reports", "figures")

CORTE = pd.Timestamp("2022-11-30")

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_TENUE = "#898781"
GRILLA = "#e1e0d9"
EJE = "#c3c2b7"

# Paleta categórica en orden fijo (no cambiar el orden: es lo que la hace
# distinguible con daltonismo).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COLOR_SUB = {
    "devsarg": SERIES[0],
    "empleos_AR": SERIES[1],
    "taquerosprogramadores": SERIES[2],
}
ETIQUETA_SUB = {
    "devsarg": "r/devsarg",
    "empleos_AR": "r/empleos_AR",
    "taquerosprogramadores": "r/taquerosprogramadores",
}
NEGATIVO = "#e34948"
POSITIVO = "#2a78d6"
NEUTRO = "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE,
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 11,
    "text.color": TINTA,
    "axes.labelcolor": TINTA_2,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.edgecolor": EJE,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": GRILLA,
    "grid.linewidth": 0.8,
    "xtick.color": TINTA_TENUE,
    "ytick.color": TINTA_TENUE,
    "xtick.labelcolor": TINTA_2,
    "ytick.labelcolor": TINTA_2,
    "lines.linewidth": 2,
    "legend.frameon": False,
    "legend.labelcolor": TINTA_2,
})


def nueva_figura(titulo, subtitulo=None, ancho=11, alto=4.8, **kwargs):
    """Figura con título a la izquierda y subtítulo en tinta secundaria."""
    fig, ax = plt.subplots(figsize=(ancho, alto), **kwargs)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=15, fontweight="bold", color=TINTA)
    if subtitulo:
        fig.text(0.01, 0.905, subtitulo, ha="left", fontsize=11, color=TINTA_2)
    return fig, ax


def marcar_corte(ax, texto="ChatGPT (30/11/2022)", x=CORTE):
    """Línea vertical punteada en el corte, con etiqueta arriba.

    Si el eje x es de trimestres como Period, pasar x con la posición numérica.
    """
    ax.axvline(x, color=TINTA_2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
    ax.annotate(texto, xy=(x, 1), xycoords=("data", "axes fraction"), xytext=(4, -2),
                textcoords="offset points", ha="left", va="top", fontsize=10, color=TINTA_2)


def eje_fechas(ax, cada_anios=1):
    ax.xaxis.set_major_locator(mdates.YearLocator(cada_anios))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def trimestre_a_fecha(trimestres):
    """'2023Q1' -> Timestamp del punto medio del trimestre, para graficar."""
    p = pd.PeriodIndex(trimestres, freq="Q")
    return p.start_time + (p.end_time - p.start_time) / 2


def etiqueta_final(ax, x, y, texto, color=TINTA_2):
    """Etiqueta directa al final de una serie."""
    ax.annotate(texto, xy=(x, y), xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=10, color=color)


def guardar(fig, nombre):
    os.makedirs(FIGURAS, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    ruta = os.path.join(FIGURAS, nombre)
    fig.savefig(ruta, dpi=160)
    plt.close(fig)
    return ruta
