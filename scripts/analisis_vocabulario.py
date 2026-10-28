"""Hipótesis C: ¿cambiaron los vecinos de palabras como "trabajo" o "junior"?

Entrena word2vec por separado antes y después del corte (2022-11-30) con posts
y comentarios de r/devsarg y r/empleos_AR, y compara los vecinos más cercanos
de un grupo de palabras objetivo (ver docs/06_vocabulario.md).

Para que la comparación sea justa:
- El período "después" se submuestrea al mismo número de tokens que "antes",
  estratificado por subreddit y tipo (post/comentario). Se arman N_MODELOS
  submuestras independientes.
- "Antes" se entrena N_MODELOS veces con semillas distintas.
- El cambio entre períodos se compara con el ruido de base: el solapamiento de
  vecinos entre modelos del mismo período.

Uso:
    python scripts/analisis_vocabulario.py
    python scripts/analisis_vocabulario.py --solo-figuras   # rehace figuras desde las tablas

Salida:
- reports/tablas/vocab_frecuencias.csv: frecuencia de cada palabra candidata.
- reports/tablas/vocab_pares.csv: Jaccard top-k y distancia coseno (Procrustes)
  para cada par de modelos y cada palabra.
- reports/tablas/vocab_cambio.csv: resumen por palabra (entre períodos vs. base).
- reports/tablas/vocab_vecinos.csv: top-10 vecinos estables antes y después.
- reports/tablas/vocab_corpus.csv: textos y tokens de cada corpus de entrenamiento.
- reports/figures/vocab_cambio_jaccard.png y vocab_cambio_coseno.png.

Corre en CPU. Lee el JSONL línea por línea dos veces y guarda solo tokens.
"""

import argparse
import html
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gensim.models import Word2Vec
from scipy.linalg import orthogonal_procrustes

from graficos import FIGURAS, SERIES, TINTA, TINTA_2, nueva_figura

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTEOS = os.path.join(ROOT, "data", "processed", "posteos.jsonl")
TABLAS = os.path.join(ROOT, "reports", "tablas")

SUBS = {"devsarg", "empleos_AR"}
SEMILLA = 42
N_MODELOS = 5
TOP_K = 10
UMBRAL_FRECUENCIA = 100  # ocurrencias mínimas en "antes" para analizar una palabra
WORKERS = 4

PARAMS_W2V = dict(vector_size=100, window=5, min_count=10, sg=1, negative=10,
                  sample=1e-3, epochs=15, workers=WORKERS)

# Pedidas en la consigna, más otras del tema. Solo se analizan las que pasan el umbral.
OBJETIVO = [
    "trabajo", "laburo", "junior", "empresa", "empleo", "entrevista", "sueldo",
    "ia", "programador", "remoto", "dolares",
    "senior", "trainee", "mercado", "cv", "freelance", "busqueda", "experiencia",
    "despidos", "inflacion", "aumento", "linkedin", "recruiter", "oferta", "contrato",
    "facultad", "carrera", "futuro", "python", "chatgpt",
]
# Palabras de control: no deberían cambiar de sentido por el corte.
CONTROL = ["semana", "casa", "familia", "comida", "lunes"]

URL = re.compile(r"https?://\S+|www\.\S+|\S+\.(?:com|ar|io|org|net)/\S*")
TOKEN = re.compile(r"[a-zñ0-9]+[+#]*")
TILDES = str.maketrans("áéíóúüàèìòùâêîôûäëïö", "aeiouuaeiouaeiouaeio")
# Abreviaturas frecuentes en el foro que se unifican con la palabra completa.
SINONIMOS = {"jr": "junior", "sr": "senior", "ssr": "semisenior"}


def tokenizar(texto):
    """Minúsculas, sin URLs ni entidades HTML, sin tildes (se conserva la ñ).

    Se descartan tokens de una letra y números sueltos.
    """
    texto = html.unescape(texto or "").lower()
    texto = URL.sub(" ", texto).translate(TILDES)
    tokens = []
    for t in TOKEN.findall(texto):
        if len(t) < 2 or t.isdigit():
            continue
        tokens.append(sys.intern(SINONIMOS.get(t, t)))
    return tokens


def leer(path):
    with open(path, encoding="utf-8") as f:
        for i, linea in enumerate(f):
            yield i, json.loads(linea)


# ---------------------------------------------------------------- corpus

def primera_pasada():
    """Tokeniza "antes" completo y cuenta tokens de cada texto de "después"."""
    antes, tok_antes = [], Counter()
    frec = {"antes": Counter(), "despues": Counter()}
    lineas, estratos, largos = [], [], []
    for i, d in leer(POSTEOS):
        if d["subreddit"] not in SUBS:
            continue
        tokens = tokenizar(d["texto"])
        if len(tokens) < 2:
            continue
        estrato = f"{d['subreddit']}_{d['tipo']}"
        frec[d["periodo"]].update(tokens)
        if d["periodo"] == "antes":
            antes.append(tokens)
            tok_antes[estrato] += len(tokens)
        else:
            lineas.append(i)
            estratos.append(estrato)
            largos.append(len(tokens))
    despues = pd.DataFrame({"linea": lineas, "estrato": estratos, "tokens": largos})
    return antes, tok_antes, despues, frec


def elegir_submuestras(despues, tok_antes):
    """Índices de línea de cada submuestra: textos al azar hasta igualar los tokens
    de "antes" en cada estrato (subreddit x tipo)."""
    submuestras = []
    for m in range(N_MODELOS):
        rng = np.random.default_rng(SEMILLA + m)
        elegidas = []
        for estrato, objetivo in tok_antes.items():
            grupo = despues[despues["estrato"] == estrato]
            orden = rng.permutation(len(grupo))
            acumulado = grupo["tokens"].to_numpy()[orden].cumsum()
            n = int(np.searchsorted(acumulado, objetivo)) + 1
            elegidas.extend(grupo["linea"].to_numpy()[orden[:n]].tolist())
        submuestras.append(set(elegidas))
    return submuestras


def segunda_pasada(submuestras):
    pertenece = defaultdict(list)
    for m, lineas in enumerate(submuestras):
        for i in lineas:
            pertenece[i].append(m)
    corpus = [[] for _ in submuestras]
    for i, d in leer(POSTEOS):
        if i in pertenece:
            tokens = tokenizar(d["texto"])
            for m in pertenece[i]:
                corpus[m].append(tokens)
    return corpus


# ---------------------------------------------------------------- modelos

def entrenar(textos, semilla):
    return Word2Vec(sentences=textos, seed=semilla, **PARAMS_W2V).wv


def vecinos(kv, palabra, k=TOP_K):
    if palabra not in kv.key_to_index:
        return []
    return [w for w, _ in kv.most_similar(palabra, topn=k)]


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else np.nan


def alinear(kv_a, kv_b):
    """Rota kv_b sobre kv_a (Procrustes ortogonal) con el vocabulario común."""
    comun = [w for w in kv_a.index_to_key if w in kv_b.key_to_index]
    A = kv_a.get_normed_vectors()[[kv_a.key_to_index[w] for w in comun]]
    B = kv_b.get_normed_vectors()[[kv_b.key_to_index[w] for w in comun]]
    R, _ = orthogonal_procrustes(B, A)
    return {w: j for j, w in enumerate(comun)}, A, B @ R


def comparar_pares(modelos, palabras):
    """Jaccard top-k y distancia coseno alineada para cada par de modelos."""
    filas = []
    for (na, ka), (nb, kb) in combinations(modelos.items(), 2):
        tipo = "entre" if na[0] != nb[0] else f"dentro_{'antes' if na[0] == 'A' else 'despues'}"
        indice, A, B = alinear(ka, kb)
        for p in palabras:
            cos = np.nan
            if p in indice:
                j = indice[p]
                cos = 1 - float(A[j] @ B[j] / (np.linalg.norm(A[j]) * np.linalg.norm(B[j])))
            filas.append({"palabra": p, "modelo_a": na, "modelo_b": nb, "tipo": tipo,
                          "jaccard": jaccard(vecinos(ka, p), vecinos(kb, p)),
                          "dist_coseno": cos})
    return pd.DataFrame(filas)


def resumir(pares):
    """Por palabra: media entre períodos vs. ruido de base (pares del mismo período).

    Cambio claro en Jaccard: la media entre períodos queda por debajo del mínimo de
    los pares del mismo período. En coseno, por encima del máximo.
    """
    filas = []
    for p, g in pares.groupby("palabra", sort=False):
        entre = g[g["tipo"] == "entre"]
        dentro = g[g["tipo"] != "entre"]
        fila = {"palabra": p}
        for med in ("jaccard", "dist_coseno"):
            fila[f"{med}_entre"] = entre[med].mean()
            fila[f"{med}_entre_min"] = entre[med].min()
            fila[f"{med}_entre_max"] = entre[med].max()
            fila[f"{med}_base"] = dentro[med].mean()
            fila[f"{med}_base_min"] = dentro[med].min()
            fila[f"{med}_base_max"] = dentro[med].max()
            fila[f"{med}_base_antes"] = g[g["tipo"] == "dentro_antes"][med].mean()
            fila[f"{med}_base_despues"] = g[g["tipo"] == "dentro_despues"][med].mean()
        fila["jaccard_ratio"] = fila["jaccard_entre"] / fila["jaccard_base"]
        fila["cambio_jaccard"] = bool(fila["jaccard_entre"] < fila["jaccard_base_min"])
        fila["cambio_coseno"] = bool(fila["dist_coseno_entre"] > fila["dist_coseno_base_max"])
        filas.append(fila)
    return pd.DataFrame(filas)


def vecinos_estables(modelos_periodo, palabra, k=TOP_K, candidatos=50):
    """Top-k por similitud media entre los modelos del período.

    Devuelve también en cuántos de los top-k individuales aparece cada vecino.
    """
    cand = set()
    for kv in modelos_periodo:
        cand.update(vecinos(kv, palabra, candidatos))
    puntaje = {}
    for w in cand:
        sims = [kv.similarity(palabra, w) if w in kv.key_to_index else 0.0
                for kv in modelos_periodo]
        puntaje[w] = float(np.mean(sims))
    mejores = sorted(puntaje, key=puntaje.get, reverse=True)[:k]
    tops = [set(vecinos(kv, palabra, k)) for kv in modelos_periodo]
    return [(w, sum(w in t for t in tops)) for w in mejores]


# ---------------------------------------------------------------- figuras

def guardar_alta(fig, nombre, arriba):
    """Como graficos.guardar, pero con el margen superior en pulgadas fijas: en una
    figura alta, el 10% que reserva guardar() deja un hueco bajo el subtítulo."""
    os.makedirs(FIGURAS, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, arriba))
    ruta = os.path.join(FIGURAS, nombre)
    fig.savefig(ruta, dpi=160)
    plt.close(fig)
    return ruta


GRUPOS = (("dentro_antes", "Antes vs. antes (solo cambia la semilla)", SERIES[0], 0.22),
          ("dentro_despues", "Después vs. después (cambian semilla y textos)", SERIES[2], 0.0),
          ("entre", "Antes vs. después", SERIES[1], -0.22))


def figura_cambio(pares, resumen, col, nombre, titulo, subtitulo, etiqueta_x, mayor_es_cambio):
    marca = "cambio_jaccard" if col == "jaccard" else "cambio_coseno"
    datos = resumen.sort_values(f"{col}_entre", ascending=mayor_es_cambio).reset_index(drop=True)
    orden = {p: i for i, p in enumerate(datos["palabra"])}
    stats = pares.groupby(["palabra", "tipo"])[col].agg(["mean", "min", "max"]).reset_index()
    alto = 2.2 + 0.36 * len(datos)
    fig, ax = nueva_figura(titulo, None, ancho=10, alto=alto)
    fig.text(0.01, 1 - 0.55 / alto, subtitulo, ha="left", va="top", fontsize=11, color=TINTA_2)
    for tipo, etiqueta, color, dy in GRUPOS:
        g = stats[stats["tipo"] == tipo]
        y = g["palabra"].map(orden).to_numpy() + dy
        ax.hlines(y, g["min"], g["max"], color=color, linewidth=1.6, alpha=0.4)
        ax.plot(g["mean"], y, "o", color=color, markersize=5, label=etiqueta)
    etiquetas = [f["palabra"] + (" (control)" if f["palabra"] in CONTROL else "")
                 for _, f in datos.iterrows()]
    ax.set_yticks(np.arange(len(datos)), etiquetas)
    for tick, cambio in zip(ax.get_yticklabels(), datos[marca]):
        tick.set_color(TINTA if cambio else TINTA_2)
        if cambio:
            tick.set_fontweight("bold")
    ax.set_ylim(len(datos) - 0.5, -0.5)
    ax.grid(axis="x", color="#e1e0d9")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(etiqueta_x)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=9.5,
              handletextpad=0.3, columnspacing=1.2)
    return guardar_alta(fig, nombre, arriba=1 - 1.0 / alto)


def figuras(pares, resumen):
    figura_cambio(
        pares, resumen, "jaccard", "vocab_cambio_jaccard.png",
        "¿Cambiaron los vecinos de cada palabra después de ChatGPT?",
        f"Solapamiento (Jaccard) de los {TOP_K} vecinos más cercanos entre pares de modelos word2vec. "
        "Punto: media; línea: mínimo a máximo.\n"
        "En negrita, las palabras donde antes vs. después "
        "queda debajo de todos los pares del mismo período.",
        f"Jaccard de los top-{TOP_K} vecinos (1 = mismos vecinos)", mayor_es_cambio=False)
    figura_cambio(
        pares, resumen, "dist_coseno", "vocab_cambio_coseno.png",
        "Desplazamiento de cada palabra tras alinear los modelos (Procrustes)",
        "Distancia coseno entre los vectores de la palabra en dos modelos. "
        "Punto: media; línea: mínimo a máximo.\n"
        "En negrita, las palabras donde antes vs. después "
        "supera a todos los pares del mismo período.",
        "Distancia coseno (0 = misma posición)", mayor_es_cambio=True)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-figuras", action="store_true")
    args = parser.parse_args()
    os.makedirs(TABLAS, exist_ok=True)
    if args.solo_figuras:
        figuras(pd.read_csv(os.path.join(TABLAS, "vocab_pares.csv")),
                pd.read_csv(os.path.join(TABLAS, "vocab_cambio.csv")))
        return

    t0 = time.time()
    antes, tok_antes, despues, frec = primera_pasada()
    print(f"antes: {len(antes):,} textos, {sum(tok_antes.values()):,} tokens; "
          f"después: {len(despues):,} textos, {despues['tokens'].sum():,} tokens "
          f"({time.time() - t0:.0f} s)")

    submuestras = elegir_submuestras(despues, tok_antes)
    corpus_despues = segunda_pasada(submuestras)
    del despues
    filas = [{"corpus": "antes", "textos": len(antes), "tokens": sum(map(len, antes))}]
    for m, c in enumerate(corpus_despues):
        filas.append({"corpus": f"despues_sub{m + 1}", "textos": len(c),
                      "tokens": sum(map(len, c))})
    pd.DataFrame(filas).to_csv(os.path.join(TABLAS, "vocab_corpus.csv"), index=False)
    print(pd.DataFrame(filas).to_string(index=False))
    print(f"solapamiento de textos entre submuestras 1 y 2: "
          f"{len(submuestras[0] & submuestras[1]):,} ({time.time() - t0:.0f} s)")

    # Frecuencias: corpus completo y submuestras.
    frec_sub = Counter()
    for c in corpus_despues:
        for tokens in c:
            frec_sub.update(tokens)
    total_a, total_d = sum(frec["antes"].values()), sum(frec["despues"].values())
    candidatas = OBJETIVO + CONTROL
    tabla_frec = pd.DataFrame([{
        "palabra": p,
        "grupo": "control" if p in CONTROL else "objetivo",
        "frec_antes": frec["antes"][p],
        "frec_despues_total": frec["despues"][p],
        "frec_despues_submuestra_media": frec_sub[p] / N_MODELOS,
        "por_millon_antes": frec["antes"][p] / total_a * 1e6,
        "por_millon_despues": frec["despues"][p] / total_d * 1e6,
        "analizada": frec["antes"][p] >= UMBRAL_FRECUENCIA,
    } for p in candidatas])
    tabla_frec.to_csv(os.path.join(TABLAS, "vocab_frecuencias.csv"), index=False,
                      float_format="%.1f")
    print(tabla_frec.to_string(index=False))
    palabras = tabla_frec.loc[tabla_frec["analizada"], "palabra"].tolist()
    del frec, frec_sub

    modelos = {}
    for m in range(N_MODELOS):
        t = time.time()
        modelos[f"A{m + 1}"] = entrenar(antes, SEMILLA + m)
        modelos[f"D{m + 1}"] = entrenar(corpus_despues[m], SEMILLA + m)
        print(f"modelos {m + 1}/{N_MODELOS}: vocab antes {len(modelos[f'A{m + 1}']):,}, "
              f"después {len(modelos[f'D{m + 1}']):,} ({time.time() - t:.0f} s)")
    del antes, corpus_despues

    pares = comparar_pares(modelos, palabras)
    pares.to_csv(os.path.join(TABLAS, "vocab_pares.csv"), index=False, float_format="%.4f")
    resumen = resumir(pares)
    resumen.to_csv(os.path.join(TABLAS, "vocab_cambio.csv"), index=False, float_format="%.4f")
    print(resumen[["palabra", "jaccard_base_antes", "jaccard_base_despues", "jaccard_entre",
                   "jaccard_ratio", "cambio_jaccard", "dist_coseno_base", "dist_coseno_entre",
                   "cambio_coseno"]].round(3).to_string(index=False))

    filas = []
    modelos_a = [modelos[f"A{m + 1}"] for m in range(N_MODELOS)]
    modelos_d = [modelos[f"D{m + 1}"] for m in range(N_MODELOS)]
    for p in palabras:
        va, vd = vecinos_estables(modelos_a, p), vecinos_estables(modelos_d, p)
        for r in range(TOP_K):
            filas.append({"palabra": p, "rango": r + 1,
                          "antes": va[r][0], "antes_en_modelos": va[r][1],
                          "despues": vd[r][0], "despues_en_modelos": vd[r][1]})
    pd.DataFrame(filas).to_csv(os.path.join(TABLAS, "vocab_vecinos.csv"), index=False)

    figuras(pares, resumen)
    print(f"listo en {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
