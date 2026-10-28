"""Lado "mercado" de la hipótesis B: demanda de software y composición de los avisos.

Uso:
    .venv/Scripts/python scripts/analisis_mercado.py

Entrada (data/processed/): avisos_hn.jsonl, indeed_software_mensual.csv y
sipa_informatica_trimestral.csv (ver docs/03_consolidacion.md).

Mide en cada aviso de Hacker News "Who is hiring?" si menciona puestos junior,
senior, IA o trabajo remoto, con diccionarios de expresiones regulares en
inglés. La IA se separa en tres medidas: cualquier mención, IA en el
encabezado (la empresa o el puesto son de IA) y uso de herramientas de IA para
programar.

Validación: saca 30 coincidencias al azar de cada diccionario (semilla fija) a
reports/tablas/mercado_validacion_muestras.csv. Las etiquetas manuales están en
reports/tablas/mercado_validacion_etiquetas.csv (diccionario, id, correcto); si
existen, calcula la precisión de cada diccionario.

Salida:
- data/processed/mercado_mensual.csv: Indeed y medidas de HN por mes.
- data/processed/mercado_trimestral.csv: SIPA y agregados trimestrales.
- reports/tablas/mercado_*.csv: resúmenes anuales, por período y validación.
- reports/figures/mercado_*.png: figuras.
"""

import os
import re
import time

import numpy as np
import pandas as pd

from graficos import (CORTE, SERIES, TINTA_2, TINTA_TENUE, eje_fechas, etiqueta_final, guardar,
                      marcar_corte, nueva_figura, trimestre_a_fecha)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
TABLAS = os.path.join(ROOT, "reports", "tablas")

SEMILLA = 42
N_MUESTRA = 30
DESDE = "2019-01"            # período principal
MES_BASE = "2022-11"         # base común de los índices (mes del corte)
TRIM_BASE = "2022Q4"
MIN_AVISOS_HILO = 50       # menos que esto es un hilo mal capturado (solo 2011-12)

# Diccionarios. Junior, senior y remoto no distinguen mayúsculas; los de IA sí,
# para que "AI" o "ML" no coincidan con palabras de otros idiomas o dominios.
DICCIONARIOS = {
    "junior": re.compile(
        r"\b(junior|jr\.?(?= )|entry[- ]level|new[- ]grads?|recent (college )?grad(uate)?s?"
        r"|graduate (roles?|positions?|program(me)?s?|engineers?|developers?)"
        r"|interns?|(?<!micro-)internships?)\b", re.I),
    "senior": re.compile(
        r"\b(senior|sr\.?(?= )|staff (\w+ )?(engineer|developer|scientist|swe)s?"
        r"|principal (\w+ )?(engineer|developer|scientist|architect)s?"
        r"|(tech|technical|team|engineering) leads?|lead (\w+ )?(engineer|developer|scientist|swe)s?)\b", re.I),
    "ia": re.compile(
        r"(\bAI\b|\bA\.I\.|\bML\b|\bLLMs?\b|\bGenAI\b|\bNLP\b|[Aa]rtificial [Ii]ntelligence"
        r"|[Mm]achine[- ][Ll]earning|[Dd]eep[- ][Ll]earning|[Ll]arge [Ll]anguage [Mm]odels?"
        r"|[Gg]enerative AI|ChatGPT|\bGPT-?\d|OpenAI|[Nn]eural [Nn]et|[Cc]omputer [Vv]ision)"),
    "ia_herramientas": re.compile(
        r"(\bGitHub Copilot\b|\bCursor (IDE|AI|editor)\b"
        r"|\bCursor\b(?=[^.\n]{0,30}\b(Copilot|Claude|Windsurf|Codex)\b)|\bClaude Code\b|\bWindsurf\b"
        r"|\bAI[- ](assisted|augmented) (coding|development|engineering|programming)"
        r"|\bAI[- ]native (engineering |development )?workflows?|\b(?<!building )AI (coding|developer|dev) tool(s|ing)?\b"
        r"|\b(use|using|uses|leverag\w*|comfortable with|experience with|experience using|fluency with"
        r"|fluent with|proficient with|proficiency with) (modern )?(AI|LLM)s? (coding |development )?(tools|assistants)\b"
        r"|\bagentic coding\b|\bvibe[- ]cod)"),
    "remoto": re.compile(
        r"(?<!\bno )(?<!\bnot )(?<!\bnon-)(?<!\bnon )\b(remote|remotely|work from home|wfh|fully distributed)\b"
        r"(?![:\s-]*(no\b|not (possible|available|an option|offered)))", re.I),
}
# "ia_encabezado" usa el diccionario "ia" sobre la primera línea del aviso.
LARGO_ENCABEZADO = 250

ETIQUETAS = {
    "junior": "Junior, entry level, new grad o pasantía",
    "senior": "Senior, staff, principal o lead",
    "ia": "Menciona IA o machine learning",
    "ia_encabezado": "Empresa o puesto de IA (encabezado)",
    "ia_herramientas": "Pide o usa herramientas de IA para programar",
    "remoto": "Remoto",
}


def encabezado(texto):
    return texto.split("\n", 1)[0][:LARGO_ENCABEZADO]


def marcar_avisos(avisos):
    """Agrega una columna booleana por diccionario."""
    for nombre, patron in DICCIONARIOS.items():
        avisos[nombre] = avisos["texto"].map(lambda t, p=patron: p.search(t) is not None)
    enc = avisos["texto"].map(encabezado)
    avisos["ia_encabezado"] = enc.map(lambda t: DICCIONARIOS["ia"].search(t) is not None)
    return avisos


def fragmento(texto, patron, margen=110):
    m = patron.search(texto)
    ini, fin = max(0, m.start() - margen), min(len(texto), m.end() + margen)
    return texto[ini:fin].replace("\n", " / ")


def muestras_validacion(avisos):
    """30 coincidencias al azar de cada diccionario, desde 2019."""
    rng = np.random.default_rng(SEMILLA)
    base = avisos[avisos["mes"] >= DESDE]
    filas = []
    for nombre in ETIQUETAS:
        positivos = base[base[nombre]]
        idx = rng.choice(len(positivos), size=min(N_MUESTRA, len(positivos)), replace=False)
        for _, a in positivos.iloc[np.sort(idx)].iterrows():
            if nombre == "ia_encabezado":
                frag = fragmento(encabezado(a["texto"]), DICCIONARIOS["ia"])
            else:
                frag = fragmento(a["texto"], DICCIONARIOS[nombre])
            filas.append({"diccionario": nombre, "id": a["id"], "mes": a["mes"], "fragmento": frag})
    muestras = pd.DataFrame(filas)
    muestras.to_csv(os.path.join(TABLAS, "mercado_validacion_muestras.csv"), index=False, encoding="utf-8")
    return muestras


def precision(muestras):
    ruta = os.path.join(TABLAS, "mercado_validacion_etiquetas.csv")
    if not os.path.exists(ruta):
        print("Sin etiquetas manuales: no se calcula la precisión.")
        return None
    etiquetas = pd.read_csv(ruta)
    unidas = muestras.merge(etiquetas, on=["diccionario", "id"], how="left")
    faltan = unidas["correcto"].isna().sum()
    if faltan:
        print(f"Atención: {faltan} muestras sin etiqueta (cambió la muestra o el diccionario).")
    tabla = (unidas.dropna(subset=["correcto"]).groupby("diccionario", sort=False)["correcto"]
             .agg(etiquetadas="size", correctas="sum").reset_index())
    tabla["precision"] = (tabla["correctas"] / tabla["etiquetadas"]).round(2)
    tabla.to_csv(os.path.join(TABLAS, "mercado_validacion.csv"), index=False)
    return tabla


def hn_mensual(avisos):
    cols = list(ETIQUETAS)
    g = avisos.groupby("mes")
    mensual = g[cols].mean().mul(100).round(2).add_prefix("hn_pct_")
    mensual.insert(0, "hn_avisos", g.size())
    return mensual


def leer_indeed():
    indeed = pd.read_csv(os.path.join(PROC, "indeed_software_mensual.csv"))
    indeed = indeed.rename(columns={"new postings": "indeed_new", "total postings": "indeed_total"})
    return indeed.set_index("mes")


def leer_sipa():
    sipa = pd.read_csv(os.path.join(PROC, "sipa_informatica_trimestral.csv")).set_index("trimestre")
    sipa = sipa.rename(columns={"informatica": "sipa_informatica", "total": "sipa_total",
                                "prop_informatica": "sipa_prop_informatica"})
    for col in ("sipa_informatica", "sipa_total"):
        sipa[f"{col}_idx"] = (sipa[col] / sipa.loc[TRIM_BASE, col] * 100).round(2)
    sipa["sipa_provisorio"] = sipa.index == sipa.index.max()  # la fuente lo marca subestimado
    return sipa


def armar_mensual(hn, indeed):
    mensual = hn.join(indeed, how="outer")
    meses = pd.period_range(mensual.index.min(), mensual.index.max(), freq="M").strftime("%Y-%m")
    mensual = mensual.reindex(meses)
    mensual.index.name = "mes"
    orden = ["indeed_new", "indeed_total", "hn_avisos", "hn_pct_junior", "hn_pct_senior", "hn_pct_ia",
             "hn_pct_ia_encabezado", "hn_pct_ia_herramientas", "hn_pct_remoto"]
    return mensual[orden]


def armar_trimestral(avisos, indeed, sipa):
    avisos = avisos.assign(trimestre=pd.PeriodIndex(avisos["mes"], freq="M").asfreq("Q").astype(str))
    g = avisos.groupby("trimestre")
    hn = g[list(ETIQUETAS)].mean().mul(100).round(2).add_prefix("hn_pct_")
    hn.insert(0, "hn_avisos_mes", (g.size() / g["mes"].nunique()).round(1))
    hn.insert(1, "hn_meses", g["mes"].nunique())
    ind = indeed.assign(trimestre=pd.PeriodIndex(indeed.index, freq="M").asfreq("Q").astype(str))
    ind = ind.groupby("trimestre").agg(indeed_new=("indeed_new", "mean"), indeed_total=("indeed_total", "mean"),
                                       indeed_meses=("indeed_new", "size")).round(2)
    trimestral = sipa.join(hn, how="outer").join(ind, how="outer")
    trimestral = trimestral[trimestral.index >= hn.index.min()]
    trimestral.index.name = "trimestre"
    return trimestral


def resumen_anual(mensual):
    m = mensual.copy()
    m["anio"] = m.index.str[:4]
    pct = [c for c in m.columns if c.startswith("hn_pct_")]
    # porcentajes anuales ponderados por cantidad de avisos
    ponderados = m[pct].mul(m["hn_avisos"], axis=0).groupby(m["anio"]).sum().div(
        m.groupby("anio")["hn_avisos"].sum(), axis=0).round(1)
    anual = pd.concat([m.groupby("anio")[["indeed_new", "indeed_total"]].mean().round(1),
                       m.groupby("anio")["hn_avisos"].agg(hn_avisos_mes="mean", hn_hilos="size").round(0),
                       ponderados], axis=1)
    anual.to_csv(os.path.join(TABLAS, "mercado_anual.csv"))
    return anual


def resumen_periodos(avisos, mensual, sipa):
    """Antes y después del corte, desde 2019, más los extremos de cada serie."""
    a = avisos[avisos["mes"] >= DESDE]
    filas = []
    for periodo, sub in a.groupby("periodo"):
        fila = {"medida": "hn", "periodo": periodo, "avisos": len(sub), "meses": sub["mes"].nunique(),
                "avisos_por_mes": round(len(sub) / sub["mes"].nunique(), 1)}
        fila.update({f"pct_{k}": round(sub[k].mean() * 100, 1) for k in ETIQUETAS})
        fila.update({f"{k}_por_mes": round(sub[k].sum() / sub["mes"].nunique(), 1) for k in ("junior", "senior", "ia")})
        filas.append(fila)
    tabla = pd.DataFrame(filas)
    tabla.to_csv(os.path.join(TABLAS, "mercado_hn_antes_despues.csv"), index=False)

    ind = mensual["indeed_new"].dropna()
    hn3 = mensual["hn_avisos"].rolling(3, center=True).mean().dropna()
    hn3 = hn3[hn3.index >= DESDE]
    sipa_ok = sipa[~sipa["sipa_provisorio"]]
    sipa_ok = sipa_ok[sipa_ok.index >= "2019Q1"]
    extremos = pd.DataFrame([
        {"serie": "Indeed new postings (base feb-2020=100)", "pico": ind.idxmax(), "valor_pico": ind.max(),
         "valor_corte": ind.loc[MES_BASE], "ultimo": ind.index[-1], "valor_ultimo": ind.iloc[-1],
         "minimo": ind.idxmin(), "valor_minimo": ind.min()},
        {"serie": "HN avisos por hilo (media móvil 3 meses)", "pico": hn3.idxmax(), "valor_pico": round(hn3.max(), 1),
         "valor_corte": round(hn3.loc[MES_BASE], 1), "ultimo": hn3.index[-1], "valor_ultimo": round(hn3.iloc[-1], 1),
         "minimo": hn3.idxmin(), "valor_minimo": round(hn3.min(), 1)},
        {"serie": "SIPA informática (asalariados)", "pico": sipa_ok["sipa_informatica"].idxmax(),
         "valor_pico": sipa_ok["sipa_informatica"].max(), "valor_corte": sipa_ok.loc[TRIM_BASE, "sipa_informatica"],
         "ultimo": sipa_ok.index[-1], "valor_ultimo": sipa_ok["sipa_informatica"].iloc[-1],
         "minimo": sipa_ok["sipa_informatica"].idxmin(), "valor_minimo": sipa_ok["sipa_informatica"].min()},
    ])
    extremos.to_csv(os.path.join(TABLAS, "mercado_extremos.csv"), index=False)
    return tabla, extremos


# ---------------------------------------------------------------- figuras


def a_fecha(meses):
    return pd.PeriodIndex(meses, freq="M").to_timestamp() + pd.Timedelta(days=14)


def fig_demanda(mensual, sipa):
    """Las tres medidas de demanda, índice base noviembre de 2022 = 100."""
    m = mensual[mensual.index >= DESDE]
    ind = m["indeed_new"].dropna()
    hn3 = m["hn_avisos"].rolling(3, center=True).mean()
    s = sipa[(sipa.index >= "2019Q1")]
    fig, ax = nueva_figura("Los avisos de software caían desde 2022; el empleo informático argentino no",
                           "Índice, noviembre de 2022 (4.º trimestre en SIPA) = 100")
    series = [
        (a_fecha(ind.index), ind / ind.loc[MES_BASE] * 100, SERIES[0], "Indeed EE.UU., avisos nuevos de software"),
        (a_fecha(hn3.index), hn3 / hn3.loc[MES_BASE] * 100, SERIES[1], "Hacker News, avisos por hilo (media de 3 meses)"),
    ]
    for x, y, color, etiqueta in series:
        ax.plot(x, y, color=color, label=etiqueta)
    fechas_s = trimestre_a_fecha(s.index)
    ok = ~s["sipa_provisorio"].values
    ax.plot(fechas_s[ok], s["sipa_informatica_idx"][ok], color=SERIES[2], marker="o", markersize=4,
            label="SIPA Argentina, asalariados en informática")
    ax.plot(fechas_s[-2:], s["sipa_informatica_idx"].iloc[-2:], color=SERIES[2], linestyle=(0, (2, 2)))
    ax.axhline(100, color=TINTA_TENUE, linewidth=0.8, zorder=0)
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylim(0, None)
    ax.set_ylabel("Índice (nov-2022 = 100)")
    ax.legend(loc="lower left", fontsize=10)
    return guardar(fig, "mercado_demanda.png")


def fig_indeed(mensual):
    m = mensual["indeed_new"].dropna()
    t = mensual["indeed_total"].dropna()
    fig, ax = nueva_figura("Avisos de software en Indeed (EE.UU.)", "Índice, 1 de febrero de 2020 = 100")
    ax.plot(a_fecha(m.index), m, color=SERIES[0], label="Avisos nuevos")
    ax.plot(a_fecha(t.index), t, color=SERIES[1], label="Avisos activos (total)")
    ax.axhline(100, color=TINTA_TENUE, linewidth=0.8, zorder=0)
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylim(0, None)
    ax.set_ylabel("Índice (feb-2020 = 100)")
    ax.legend(loc="upper right", fontsize=10)
    return guardar(fig, "mercado_indeed.png")


def fig_sipa(sipa):
    s = sipa[sipa.index >= "2012Q1"]
    x = trimestre_a_fecha(s.index)
    fig, ax = nueva_figura("Empleo registrado en informática en Argentina (SIPA)",
                           "Asalariados privados, índice 4.º trimestre de 2022 = 100. "
                           "El último trimestre está subestimado según la fuente (línea punteada)")
    ok = ~s["sipa_provisorio"].values
    for col, color, etiqueta in [("sipa_informatica_idx", SERIES[0], "Informática (rama 72)"),
                                 ("sipa_total_idx", SERIES[1], "Total sector privado")]:
        ax.plot(x[ok], s[col][ok], color=color, label=etiqueta)
        ax.plot(x[-2:], s[col].iloc[-2:], color=color, linestyle=(0, (2, 2)))
    ax.axhline(100, color=TINTA_TENUE, linewidth=0.8, zorder=0)
    ax.set_ylim(55, 114)
    x_dev = pd.Timestamp("2023-12-13")
    ax.axvline(x_dev, color=TINTA_TENUE, linewidth=1, linestyle=(0, (1, 2)), zorder=1)
    ax.annotate("Devaluación (12/2023)", xy=(x_dev, 0.08), xycoords=("data", "axes fraction"), xytext=(4, 0),
                textcoords="offset points", fontsize=10, color=TINTA_2)
    marcar_corte(ax, "ChatGPT")
    eje_fechas(ax, 2)
    ax.set_ylabel("Índice (2022-T4 = 100)")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.9), fontsize=10)
    return guardar(fig, "mercado_sipa.png")


def fig_hn_avisos(mensual):
    m = mensual["hn_avisos"].where(mensual["hn_avisos"] >= MIN_AVISOS_HILO)  # 2011-12: hilo con 1 aviso
    fig, ax = nueva_figura("Avisos por hilo de Hacker News \"Who is hiring?\"",
                           "Avisos (comentarios de primer nivel) por hilo mensual, 2011 a 2026")
    x = a_fecha(m.index)
    ax.plot(x, m, color=SERIES[0], linewidth=1, alpha=0.35, label="Por hilo")
    ax.plot(x, m.rolling(6, center=True, min_periods=4).mean(), color=SERIES[0], label="Media móvil de 6 meses")
    marcar_corte(ax)
    eje_fechas(ax, 2)
    ax.set_ylim(0, None)
    ax.set_ylabel("Avisos")
    ax.legend(loc="lower left", fontsize=10)
    return guardar(fig, "mercado_hn_avisos.png")


def fig_composicion(mensual):
    """Junior, senior e IA como % de los avisos, en paneles con escala propia."""
    import matplotlib.pyplot as plt
    m = mensual.rolling(3, center=True).mean()  # la media móvil se calcula antes de recortar
    m = m[m.index >= DESDE]
    x = a_fecha(m.index)
    paneles = [
        ("Junior, entry level o pasantía", [("hn_pct_junior", SERIES[0], None)]),
        ("Senior, staff o lead", [("hn_pct_senior", SERIES[0], None)]),
        ("IA", [("hn_pct_ia", SERIES[0], "Cualquier mención"),
                ("hn_pct_ia_encabezado", SERIES[1], "Empresa o puesto de IA"),
                ("hn_pct_ia_herramientas", SERIES[2], "Usa herramientas de IA")]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharex=True)
    fig.suptitle("Qué piden los avisos de Hacker News", x=0.01, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.01, 0.905, "% de avisos de cada hilo que mencionan el término, media móvil de 3 meses. "
             "Cada panel tiene su propia escala", ha="left", fontsize=11, color=TINTA_2)
    for ax, (titulo, cols) in zip(axes, paneles):
        for col, color, etiqueta in cols:
            ax.plot(x, m[col], color=color, label=etiqueta)
        ax.set_title(titulo, fontsize=12)
        ax.set_ylim(0, None)
        ax.axvline(CORTE, color=TINTA_2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
        eje_fechas(ax, 2)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        if len(cols) > 1:
            ax.legend(loc="upper left", fontsize=9)
    axes[0].annotate("ChatGPT", xy=(CORTE, 0.02), xycoords=("data", "axes fraction"), xytext=(4, 0),
                     textcoords="offset points", fontsize=10, color=TINTA_2)
    return guardar(fig, "mercado_hn_composicion.png")


def fig_remoto(mensual):
    m = mensual
    x = a_fecha(m.index)
    fig, ax = nueva_figura("Avisos de Hacker News que ofrecen trabajo remoto",
                           "% de avisos de cada hilo, media móvil de 3 meses, 2011 a 2026")
    y = m["hn_pct_remoto"].rolling(3, center=True).mean()
    ax.plot(x, y, color=SERIES[0])
    pandemia = pd.Timestamp("2020-03-11")
    ax.axvline(pandemia, color=TINTA_TENUE, linewidth=1, linestyle=(0, (1, 2)), zorder=1)
    ax.annotate("Pandemia (03/2020)", xy=(pandemia, 0.08), xycoords=("data", "axes fraction"), xytext=(-4, 0),
                textcoords="offset points", ha="right", fontsize=10, color=TINTA_2)
    marcar_corte(ax)
    eje_fechas(ax, 2)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    etiqueta_final(ax, x[-2], y.iloc[-2], f"{y.iloc[-2]:.0f}%")
    return guardar(fig, "mercado_hn_remoto.png")


def main():
    t0 = time.time()
    os.makedirs(TABLAS, exist_ok=True)
    avisos = pd.read_json(os.path.join(PROC, "avisos_hn.jsonl"), lines=True)
    avisos = marcar_avisos(avisos)
    print(f"{len(avisos)} avisos marcados en {time.time() - t0:.0f} s")

    muestras = muestras_validacion(avisos)
    prec = precision(muestras)
    if prec is not None:
        print(prec.to_string(index=False))

    indeed = leer_indeed()
    sipa = leer_sipa()
    mensual = armar_mensual(hn_mensual(avisos), indeed)
    trimestral = armar_trimestral(avisos, indeed, sipa)
    mensual.to_csv(os.path.join(PROC, "mercado_mensual.csv"))
    trimestral.to_csv(os.path.join(PROC, "mercado_trimestral.csv"))

    anual = resumen_anual(mensual)
    tabla, extremos = resumen_periodos(avisos, mensual, sipa)
    print(anual.to_string())
    print(tabla.to_string(index=False))
    print(extremos.to_string(index=False))

    for f in (fig_demanda(mensual, sipa), fig_indeed(mensual), fig_sipa(sipa), fig_hn_avisos(mensual),
              fig_composicion(mensual), fig_remoto(mensual)):
        print("Figura:", f)
    print(f"Listo en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
