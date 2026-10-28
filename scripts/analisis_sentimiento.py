"""Tono de la conversación antes y después del corte (hipótesis A, parte de tono).

Uso:
    .venv/Scripts/python scripts/analisis_sentimiento.py

Necesita data/processed/sentimiento/ (scripts/sentimiento.py).

Medidas por texto: etiqueta de mayor probabilidad (NEG, NEU, POS), polaridad
(P(POS) - P(NEG), entre -1 y 1) y probabilidad de cada emoción.

Salida:
- data/processed/sentimiento_textos.parquet: metadatos + sentimiento por texto.
- data/processed/sentimiento_mensual.csv y sentimiento_trimestral.csv: promedios
  por subreddit y tipo, para el cruce con el mercado.
- reports/tablas/sent_antes_despues.csv: comparación por período con IC 95%
  por bootstrap de hilos (los comentarios de un mismo post no son independientes).
- reports/tablas/sent_diferencia_en_diferencias.csv: r/devsarg contra r/empleos_AR.
- reports/tablas/sent_series_segmentadas.csv: cambio de nivel y de pendiente en el corte.
- reports/tablas/sent_muestra_validacion.csv: muestra para revisar el modelo a mano.
- reports/figures/sent_*.png
"""

import glob
import json
import os

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from graficos import (COLOR_SUB, CORTE, ETIQUETA_SUB, TINTA_2, eje_fechas, guardar,
                      marcar_corte, nueva_figura, plt, trimestre_a_fecha)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
TABLAS = os.path.join(ROOT, "reports", "tablas")
SUBS = ["devsarg", "empleos_AR", "taquerosprogramadores"]
SUBS_AR = ["devsarg", "empleos_AR"]
EMOCIONES = {"sadness": "tristeza", "anger": "enojo", "fear": "miedo", "joy": "alegría"}
SEMILLA = 2022
N_BOOT = 500


def cargar():
    campos = ["id", "tipo", "subreddit", "created_utc", "trimestre", "periodo", "post_id"]
    filas = []
    with open(os.path.join(PROC, "posteos.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            filas.append([d[c] for c in campos])
    meta = pd.DataFrame(filas, columns=campos)
    sent = pd.concat([pd.read_parquet(p) for p in
                      sorted(glob.glob(os.path.join(PROC, "sentimiento", "bloque_*.parquet")))])
    sent = sent.drop_duplicates("id")
    df = meta.merge(sent, on="id", how="left", validate="one_to_one")
    assert df.sent_neg.notna().all(), "hay textos sin sentimiento: correr scripts/sentimiento.py"
    df["mes"] = pd.to_datetime(df.created_utc, unit="s").dt.strftime("%Y-%m")
    df["polaridad"] = df.sent_pos - df.sent_neg
    clases = df[["sent_neg", "sent_neu", "sent_pos"]].to_numpy().argmax(axis=1)
    df["etiqueta"] = np.array(["NEG", "NEU", "POS"])[clases]
    df["neg"] = (df.etiqueta == "NEG").astype(float)
    df["pos"] = (df.etiqueta == "POS").astype(float)
    for col in ["subreddit", "tipo", "periodo", "trimestre", "mes"]:
        df[col] = df[col].astype("category")
    return df


def agregar(df, por):
    columnas = {"n": ("id", "size"), "pct_neg": ("neg", "mean"), "pct_pos": ("pos", "mean"),
                "polaridad": ("polaridad", "mean")}
    columnas.update({f"emo_{v}": (f"emo_{k}", "mean") for k, v in EMOCIONES.items()})
    g = df.groupby(por, observed=True).agg(**columnas).reset_index()
    for c in ["pct_neg", "pct_pos"]:
        g[c] = (100 * g[c]).round(2)
    return g.round(4)


def bootstrap_hilos(sub, rng):
    """Media por período con IC 95%, remuestreando hilos (post + sus comentarios).

    Bootstrap de Poisson: cada hilo recibe un peso ~ Poisson(1) en cada réplica.
    """
    hilos = sub.groupby("post_id", observed=True).agg(
        n=("neg", "size"), neg=("neg", "sum"), pol=("polaridad", "sum"))
    pesos = rng.poisson(1.0, size=(N_BOOT, len(hilos)))
    n = pesos @ hilos.n.to_numpy()
    reps_neg = 100 * (pesos @ hilos.neg.to_numpy()) / n
    reps_pol = (pesos @ hilos.pol.to_numpy()) / n
    return {
        "n_textos": int(hilos.n.sum()), "n_hilos": len(hilos),
        "pct_neg": round(100 * hilos.neg.sum() / hilos.n.sum(), 2),
        "pct_neg_ic": tuple(np.percentile(reps_neg, [2.5, 97.5]).round(2)),
        "polaridad": round(hilos.pol.sum() / hilos.n.sum(), 4),
        "polaridad_ic": tuple(np.percentile(reps_pol, [2.5, 97.5]).round(4)),
        "reps_neg": reps_neg,
    }


def antes_despues(df):
    rng = np.random.default_rng(SEMILLA)
    filas, reps = [], {}
    for sub in SUBS_AR:
        for tipo in ["post", "comentario", "todos"]:
            parte = df[df.subreddit == sub] if tipo == "todos" else df[(df.subreddit == sub) & (df.tipo == tipo)]
            for periodo in ["antes", "despues"]:
                r = bootstrap_hilos(parte[parte.periodo == periodo], rng)
                reps[(sub, tipo, periodo)] = r.pop("reps_neg")
                filas.append({"subreddit": sub, "tipo": tipo, "periodo": periodo, **r})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(os.path.join(TABLAS, "sent_antes_despues.csv"), index=False)

    # Diferencia en diferencias: cambio de r/devsarg menos cambio de r/empleos_AR.
    did = []
    for tipo in ["post", "comentario", "todos"]:
        cambio = {s: reps[(s, tipo, "despues")] - reps[(s, tipo, "antes")] for s in SUBS_AR}
        dd = cambio["devsarg"] - cambio["empleos_AR"]
        punto = {s: tabla.query("subreddit == @s and tipo == @tipo").set_index("periodo").pct_neg
                 for s in SUBS_AR}
        did.append({
            "tipo": tipo,
            "cambio_devsarg_pp": round(punto["devsarg"]["despues"] - punto["devsarg"]["antes"], 2),
            "cambio_devsarg_ic": tuple(np.percentile(cambio["devsarg"], [2.5, 97.5]).round(2)),
            "cambio_empleos_pp": round(punto["empleos_AR"]["despues"] - punto["empleos_AR"]["antes"], 2),
            "cambio_empleos_ic": tuple(np.percentile(cambio["empleos_AR"], [2.5, 97.5]).round(2)),
            "dif_en_dif_pp": round((punto["devsarg"]["despues"] - punto["devsarg"]["antes"])
                                   - (punto["empleos_AR"]["despues"] - punto["empleos_AR"]["antes"]), 2),
            "dif_en_dif_ic": tuple(np.percentile(dd, [2.5, 97.5]).round(2)),
        })
    did = pd.DataFrame(did)
    did.to_csv(os.path.join(TABLAS, "sent_diferencia_en_diferencias.csv"), index=False)
    return tabla, did


def series_segmentadas(mensual):
    """Regresión segmentada sobre el % de textos negativos por mes (todos los textos).

    pct_neg ~ t + despues + t_despues, con errores HAC (Newey-West, 6 rezagos)
    porque los meses consecutivos están autocorrelacionados. Cada mes pesa igual.
    t = 0 es noviembre de 2022, que cuenta como "antes": el 97% de sus textos es
    anterior al 30/11. "despues" empieza en diciembre de 2022.
    """
    corte_mes = pd.Period(CORTE, "M")
    filas = []
    for sub in SUBS_AR:
        s = mensual[(mensual.subreddit == sub)].copy()
        s = s[s.n >= 100]  # meses con muy pocos textos al principio de r/devsarg
        p = pd.PeriodIndex(s.mes, freq="M")
        s["t"] = [(x - corte_mes).n for x in p]
        s["despues"] = (s.t >= 1).astype(int)
        s["t_despues"] = s.t * s.despues
        m = smf.ols("pct_neg ~ t + despues + t_despues", data=s).fit(
            cov_type="HAC", cov_kwds={"maxlags": 6})
        for termino, nombre in [("t", "pendiente antes (pp/mes)"), ("despues", "salto en el corte (pp)"),
                                ("t_despues", "cambio de pendiente (pp/mes)")]:
            ic = m.conf_int().loc[termino]
            filas.append({"subreddit": sub, "termino": nombre, "estimacion": round(m.params[termino], 3),
                          "ic_inf": round(ic[0], 3), "ic_sup": round(ic[1], 3),
                          "p_valor": round(m.pvalues[termino], 4), "meses": len(s)})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(os.path.join(TABLAS, "sent_series_segmentadas.csv"), index=False)
    return tabla


def muestra_validacion(df):
    """60 textos al azar de r/devsarg (20 por etiqueta) con su texto, para revisar a mano."""
    rng = np.random.default_rng(SEMILLA)
    ids = []
    for etiqueta in ["NEG", "NEU", "POS"]:
        cand = df[(df.subreddit == "devsarg") & (df.etiqueta == etiqueta)].id.to_numpy()
        ids += list(rng.choice(cand, 20, replace=False))
    elegidos = set(ids)
    textos = {}
    with open(os.path.join(PROC, "posteos.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in elegidos:
                textos[d["id"]] = d["texto"][:500]
    m = df[df.id.isin(elegidos)][["id", "tipo", "periodo", "etiqueta", "sent_neg", "sent_neu", "sent_pos"]].copy()
    m["texto"] = m.id.map(textos)
    m["etiqueta_manual"] = ""
    m.sort_values("etiqueta").to_csv(os.path.join(TABLAS, "sent_muestra_validacion.csv"), index=False)


def figura_negatividad(trimestral):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    fig.suptitle("Proporción de textos negativos por trimestre", x=0.01, ha="left",
                 fontsize=15, fontweight="bold")
    fig.text(0.01, 0.905, "Clasificador RoBERTuito (pysentimiento). Trimestres con al menos 60 posts "
             "o 200 comentarios.", ha="left", fontsize=11, color=TINTA_2)
    minimo = {"post": 60, "comentario": 200}
    tope = 0
    for ax, tipo, titulo in [(axes[0], "post", "Posts"), (axes[1], "comentario", "Comentarios")]:
        for sub in SUBS:
            s = trimestral[(trimestral.subreddit == sub) & (trimestral.tipo == tipo)
                           & (trimestral.n >= minimo[tipo])]
            ax.plot(trimestre_a_fecha(s.trimestre), s.pct_neg, color=COLOR_SUB[sub], label=ETIQUETA_SUB[sub])
            tope = max(tope, s.pct_neg.max())
        ax.set_title(titulo, fontsize=12)
        marcar_corte(ax)
        eje_fechas(ax)
    axes[0].set_ylim(0, tope * 1.12)
    axes[0].set_ylabel("% de textos negativos")
    axes[1].legend(loc="lower right")
    return guardar(fig, "sent_negatividad_trimestral.png")


def figura_emociones(trimestral):
    fig, axes = plt.subplots(1, 4, figsize=(14, 4.2), sharey=False)
    fig.suptitle("Emociones por trimestre (probabilidad media, todos los textos)", x=0.01, ha="left",
                 fontsize=15, fontweight="bold")
    for ax, (_, nombre) in zip(axes, EMOCIONES.items()):
        for sub in SUBS:
            s = trimestral[(trimestral.subreddit == sub) & (trimestral.n >= 200)]
            ax.plot(trimestre_a_fecha(s.trimestre), 100 * s[f"emo_{nombre}"], color=COLOR_SUB[sub],
                    label=ETIQUETA_SUB[sub])
        ax.set_title(nombre.capitalize(), fontsize=12)
        marcar_corte(ax, texto="ChatGPT")
        eje_fechas(ax, 2)
        ax.set_ylim(bottom=0)
    axes[0].set_ylabel("probabilidad media (%)")
    manejadores, etiquetas = axes[0].get_legend_handles_labels()
    fig.legend(manejadores, etiquetas, loc="upper right", ncol=3, bbox_to_anchor=(0.99, 0.99))
    return guardar(fig, "sent_emociones_trimestral.png")


def figura_mensual(mensual):
    fig, ax = nueva_figura("r/devsarg y r/empleos_AR: % de textos negativos por mes",
                           "Posts y comentarios juntos. Meses con al menos 100 textos.")
    for sub in SUBS_AR:
        s = mensual[(mensual.subreddit == sub) & (mensual.n >= 100)]
        ax.plot(pd.PeriodIndex(s.mes, freq="M").to_timestamp(), s.pct_neg, color=COLOR_SUB[sub],
                label=ETIQUETA_SUB[sub], linewidth=1.6)
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylabel("% de textos negativos")
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right")
    return guardar(fig, "sent_negatividad_mensual.png")


def main():
    os.makedirs(TABLAS, exist_ok=True)
    df = cargar()
    cols = ["id", "tipo", "subreddit", "trimestre", "mes", "periodo", "post_id", "etiqueta",
            "polaridad", "sent_neg", "sent_neu", "sent_pos"] + [c for c in df.columns if c.startswith("emo_")]
    df[cols].to_parquet(os.path.join(PROC, "sentimiento_textos.parquet"), index=False)

    trimestral = pd.concat([agregar(df, ["subreddit", "tipo", "trimestre"]),
                            agregar(df, ["subreddit", "trimestre"]).assign(tipo="todos")])
    mensual = agregar(df, ["subreddit", "mes"])
    trimestral.to_csv(os.path.join(PROC, "sentimiento_trimestral.csv"), index=False)
    pd.concat([agregar(df, ["subreddit", "tipo", "mes"]), mensual.assign(tipo="todos")]).to_csv(
        os.path.join(PROC, "sentimiento_mensual.csv"), index=False)

    print(agregar(df, ["subreddit", "tipo", "periodo"]).to_string())
    tabla, did = antes_despues(df)
    print(tabla.to_string())
    print(did.to_string())
    print(series_segmentadas(mensual).to_string())
    muestra_validacion(df)
    for ruta in [figura_negatividad(trimestral), figura_emociones(trimestral[trimestral.tipo == "todos"]),
                 figura_mensual(mensual)]:
        print(ruta)


if __name__ == "__main__":
    main()
