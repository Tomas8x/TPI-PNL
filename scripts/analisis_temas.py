"""Temas de la conversación antes y después de ChatGPT (hipótesis A, parte de temas).

Tres análisis sobre data/processed/posteos.jsonl (ver docs/05_temas.md):

a) Diccionarios de temas (regex): proporción de textos que mencionan despidos,
   búsqueda de empleo, IA, sueldos, cambio de trabajo y junior, por trimestre,
   subreddit y tipo de texto.
b) Términos característicos por período con TF-IDF (documentos = año) y log-odds
   con prior de Dirichlet (Monroe et al., 2008) antes vs después.
c) BERTopic sobre los posts de r/devsarg y r/empleos_AR.

Uso:
    python scripts/analisis_temas.py                      # todo
    python scripts/analisis_temas.py --etapa diccionarios # solo a)
    python scripts/analisis_temas.py --etapa tfidf        # solo b)
    python scripts/analisis_temas.py --etapa bertopic     # solo c)
    python scripts/analisis_temas.py --muestra 40         # muestra para validar diccionarios
    python scripts/analisis_temas.py --etapa bertopic --reajustar  # reajustar los temas

BERTopic se ajusta una sola vez y guarda los centroides de cada tema. Las corridas
siguientes asignan cada post al centroide más cercano, así los temas y sus nombres
no cambian si el corpus cambia un poco. Con --reajustar se vuelve a ajustar y hay
que revisar los nombres de NOMBRES_BERTOPIC.

Salida:
- reports/tablas/temas_diccionario_trimestre.csv: proporción por tema, sub, tipo y trimestre.
- reports/tablas/temas_diccionario_periodo.csv: proporción antes vs después.
- reports/tablas/temas_validacion_muestra.csv: coincidencias al azar para anotar a mano.
- reports/tablas/temas_tfidf_<sub>.csv y temas_logodds_<sub>.csv: top 20 términos.
- reports/tablas/temas_bertopic_temas.csv y temas_bertopic_trimestre.csv.
- reports/figures/temas_*.png
- data/processed/temas_posts.parquet: id, tema_id, tema_nombre (BERTopic).
- data/processed/temas_embeddings.npy: embeddings de los posts (caché de BERTopic).
- reports/modelos/temas_centroides.npz: centroides de los temas de BERTopic (en git).

Lee el JSONL línea por línea y se queda solo con los campos que usa.
"""

import argparse
import json
import math
import os
import random
import re
import time
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from graficos import (COLOR_SUB, ETIQUETA_SUB, SERIES, TINTA, TINTA_2, TINTA_TENUE,
                      guardar, marcar_corte, nueva_figura, trimestre_a_fecha)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTEOS = os.path.join(ROOT, "data", "processed", "posteos.jsonl")
TABLAS = os.path.join(ROOT, "reports", "tablas")
SALIDA_POSTS = os.path.join(ROOT, "data", "processed", "temas_posts.parquet")
CACHE_EMB = os.path.join(ROOT, "data", "processed", "temas_embeddings.npy")
CENTROIDES = os.path.join(ROOT, "reports", "modelos", "temas_centroides.npz")  # versionado: fija los temas

SEMILLA = 42
SUBS = ("devsarg", "empleos_AR", "taquerosprogramadores")
SUBS_AR = ("devsarg", "empleos_AR")
CORTE_TRIM = "2022Q4"  # el trimestre que contiene el 30/11/2022
ULTIMO_TRIM = "2026Q3"

# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

SIN_TILDES = str.maketrans("áéíóúüàèìòù", "aeiouuaeiou")
RE_URL = re.compile(r"https?://\S+|www\.\S+|\[([^\]]*)\]\([^)]*\)|&amp;#x200b;|&#x200b;|&amp;|&gt;|&lt;")


def normalizar(texto):
    """Minúsculas, sin tildes (conserva la ñ) y sin URLs (deja el texto de los links)."""
    texto = (texto or "").lower().translate(SIN_TILDES)
    return RE_URL.sub(lambda m: " " + (m.group(1) or "") + " ", texto)


# ---------------------------------------------------------------------------
# a) Diccionarios
# ---------------------------------------------------------------------------

TRABAJO = r"(?:laburos?|trabajos?|empleos?|chambas?|curros?|jale)"

DICCIONARIOS = {
    "despidos": [
        r"despid(?:o|os|e|en|an|ieron|io|iendo|iera|ieran|ida|idas|ido|idos)",
        r"despedir(?:me|te|lo|la|los|las|nos)?",
        r"layoffs?", r"lay off", r"laid off",
        r"rajad[oa]s?", r"rajar(?:on|lo|la|los|las|me|te|nos)",
        r"(?:me|te|lo|la|nos|los|las) (?:echaron|rajaron|echan|rajan|despidieron)(?! de (?:casa|mi casa|la casa|su casa))",
        r"desvincul\w+",
        r"(?:recortes?|reduccion|achique) de (?:personal|plantilla|gente|staff)",
        r"indemnizacion(?:es)?",
    ],
    "busqueda": [
        r"(?:conseguir|consigo|consigue|consiguen|conseguis|consegui|encontrar|encuentro|encontre) "
        r"(?:un |una |mi |el |algun |nuevo |otro )?" + TRABAJO,
        r"(?:buscando|busco|buscar|busque|buscas|busca) (?:un |una |mi |el |algun |nuevo |otro )?" + TRABAJO,
        r"busqueda (?:laboral|de " + TRABAJO + r")",
        r"(?:sin|no tengo|no tiene|quede sin|quedar sin|quedarme sin) " + TRABAJO,
        r"desemplead[oa]s?", r"desempleo", r"desocupad[oa]s?", r"desocupacion",
        r"postul(?:o|e|as|an|ar|arme|ando|aciones|acion|ate|ado|e a)",
        r"(?:aplique|aplicando|aplicar|aplico) (?:a|en) (?:\w+ )?(?:ofertas|busquedas|puestos|posiciones|vacantes|empresas)",
        r"no me (?:llaman|llamaron|responden|respondieron|contestan|contestaron)",
        r"ghost(?:ean|earon|eo|ing|eado|eada)",
        r"(?:mercado|cosa) (?:esta |laboral esta )?(?:dificil|complicad[oa]|saturad[oa]|muerto|jodid[oa]|brav[oa])",
    ],
    "ia": [
        r"ia", r"ias", r"inteligencias? artificial(?:es)?", r"artificial intelligence",
        r"chat ?gpt", r"gpt ?-?\d\w*", r"gpt", r"openai", r"copilot", r"llms?",
        r"claude", r"gemini", r"deepseek", r"anthropic", r"vibe ?coding", r"vibecode\w*",
        r"prompts?", r"chatbots?", r"genai", r"ai", r"codex", r"windsurf", r"agentes? de (?:ia|ai)",
    ],
    "sueldos": [
        r"sueldos?", r"sueldazos?", r"salari(?:o|os|al|ales)", r"remuneraci(?:on|ones)",
        r"paritarias?", r"aumentos? (?:de sueldo|salarial|por inflacion)", r"recibos? de sueldo",
        r"(?:brutos?|netos?)",
        r"cuanto (?:cobr|pag|gan)\w+",
        r"(?:cobr|gan)(?:o|as|a|amos|an|ar|ando|aba|e|aste) (?:en (?:dolares|usd|pesos|cripto|blanco|negro)|"
        r"bien|mal|poco|mucho|mas|menos|el doble|la mitad|unos|como|\$|u\$s|usd)",
        r"cobr(?:o|as|a|amos|an|ar|ando|aba|e|aste) \d",
        r"(?:me|te|le|nos|les) pag(?:an|aban|aria|arian|uen|a)",
        r"paga(?:n)? (?:bien|mal|poco|mucho|en dolares|en usd|en pesos)",
        r"\d+ ?(?:k|lucas|palos|mil) (?:usd|dolares|pesos|brutos?|netos?|ars|en mano|por mes|al mes|mensuales)",
        r"(?:usd|u\$s|us\$) ?\d+ ?k? (?:brutos?|netos?|por mes|al mes|mensuales)",
        r"(?:\d+|unas|mil|cien) ?lucas", r"palos (?:brutos?|netos?|en mano|por mes|al mes)",
    ],
    "cambio": [
        r"cambi(?:ar|arme|arte|o|e|ando|as|aste|amos) de (?:laburo|trabajo|empleo|empresa|chamba|jale|rubro)",
        r"(?:busc|consegu|consig|encontr)\w* (?:un |algun )?(?:otro|nuevo) (?:laburo|trabajo|empleo|lado)",
        r"(?:mi|tu|su|el) nuevo (?:laburo|trabajo|empleo)",
        r"(?:pasarme|irme|irte|cambiarme|cambiarte|saltar|moverme) a (?:otra empresa|otro (?:laburo|trabajo|lado))",
        r"renunci(?:ar|o|e|as|aste|ando|aron|arle|arme|amos)", r"(?:mi|tu|la|su) renuncia",
        r"contraofertas?", r"counter ?offer",
        r"job ?hopp\w*", r"saltar de (?:empresa|laburo|trabajo)",
        r"(?:me|te) (?:fui|voy|vas|ire) de (?:la|mi|una) empresa",
        r"dejar (?:el|mi|tu|un) (?:laburo|trabajo|empleo)",
        r"(?:me|nos) ofrecieron",
    ],
    "junior": [
        r"juniors?", r"jrs?", r"trainees?",
        r"primer (?:laburo|trabajo|empleo|chamba|jale)", r"primera experiencia( laboral)?",
        r"sin experiencia", r"pasant(?:ia|ias|e|es)", r"entry ?level",
        r"(?:recien|recen) recibid[oa]s?",
    ],
}

NOMBRE_TEMA = {
    "despidos": "Despidos",
    "busqueda": "Búsqueda de empleo",
    "ia": "IA",
    "sueldos": "Sueldos",
    "cambio": "Cambio de trabajo",
    "junior": "Junior / primer empleo",
}


def compilar(diccionarios):
    return {tema: re.compile(r"\b(?:" + "|".join(pats) + r")\b") for tema, pats in diccionarios.items()}


def leer_posteos(campos):
    """Recorre posteos.jsonl y devuelve solo los campos pedidos."""
    with open(POSTEOS, encoding="utf-8") as f:
        for linea in f:
            r = json.loads(linea)
            yield {c: r.get(c) for c in campos}


def contar_diccionarios(regex, muestra=0):
    """Una pasada: textos y menciones por (sub, tipo, trimestre, tema).

    Si muestra > 0, guarda además una muestra al azar (reservorio) de
    coincidencias por tema para validar a mano.
    """
    rng = random.Random(SEMILLA)
    total = Counter()
    menciones = Counter()
    reservorio = defaultdict(list)
    vistos = Counter()
    for r in leer_posteos(("id", "tipo", "subreddit", "trimestre", "texto")):
        clave = (r["subreddit"], r["tipo"], r["trimestre"])
        total[clave] += 1
        t = normalizar(r["texto"])
        for tema, rx in regex.items():
            m = rx.search(t)
            if not m:
                continue
            menciones[clave + (tema,)] += 1
            if muestra:
                vistos[tema] += 1
                contexto = (t[max(0, m.start() - 150):m.start()] + "<<" + m.group(0) + ">>"
                            + t[m.end():m.end() + 150]).replace("\n", " ")
                fila = (tema, r["id"], r["subreddit"], r["tipo"], r["trimestre"], m.group(0), contexto)
                if len(reservorio[tema]) < muestra:
                    reservorio[tema].append(fila)
                else:
                    j = rng.randrange(vistos[tema])
                    if j < muestra:
                        reservorio[tema][j] = fila
    return total, menciones, reservorio


def tabla_trimestral(total, menciones):
    filas = []
    for (sub, tipo, trim), n in total.items():
        for tema in DICCIONARIOS:
            filas.append({"subreddit": sub, "tipo": tipo, "trimestre": trim, "tema": tema,
                          "textos": n, "menciones": menciones[(sub, tipo, trim, tema)]})
    df = pd.DataFrame(filas)
    # "todos" = posts y comentarios juntos
    todos = df.groupby(["subreddit", "trimestre", "tema"], as_index=False)[["textos", "menciones"]].sum()
    todos["tipo"] = "todos"
    df = pd.concat([df, todos], ignore_index=True)
    df["proporcion"] = df["menciones"] / df["textos"]
    df["periodo"] = np.where(df["trimestre"] < CORTE_TRIM, "antes",
                             np.where(df["trimestre"] == CORTE_TRIM, "corte", "despues"))
    return df.sort_values(["subreddit", "tipo", "tema", "trimestre"]).reset_index(drop=True)


def tabla_periodo(df):
    """Antes vs después. El trimestre del corte (2022Q4) queda afuera de los dos lados.

    Se informan dos medidas: la proporción agregada (textos con mención / textos)
    y el promedio de las proporciones trimestrales, que no deja que los
    trimestres con más volumen dominen.
    """
    d = df[df["periodo"] != "corte"]
    agr = d.groupby(["subreddit", "tipo", "tema", "periodo"]).agg(
        textos=("textos", "sum"), menciones=("menciones", "sum"),
        prom_trimestral=("proporcion", "mean"), trimestres=("trimestre", "nunique")).reset_index()
    agr["proporcion"] = agr["menciones"] / agr["textos"]
    ancho = agr.pivot_table(index=["subreddit", "tipo", "tema"], columns="periodo",
                            values=["proporcion", "prom_trimestral", "textos"]).reset_index()
    ancho.columns = ["_".join(c).strip("_") for c in ancho.columns]
    ancho["cociente"] = ancho["proporcion_despues"] / ancho["proporcion_antes"]
    # Prueba de dos proporciones (z), solo como referencia: los textos de un mismo hilo no son independientes.
    p1, p2 = ancho["proporcion_antes"], ancho["proporcion_despues"]
    n1, n2 = ancho["textos_antes"], ancho["textos_despues"]
    p = (p1 * n1 + p2 * n2) / (n1 + n2)
    ancho["z"] = (p2 - p1) / np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return ancho


def figura_diccionarios(df, tipo, nombre, titulo, subtitulo):
    """Small multiples: un panel por tema, una línea por subreddit."""
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.4), sharex=True)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=15, fontweight="bold", color=TINTA)
    fig.text(0.01, 0.915, subtitulo, ha="left", fontsize=11, color=TINTA_2)
    for i, (ax, tema) in enumerate(zip(axes.flat, DICCIONARIOS)):
        for sub in SUBS:
            d = df[(df["subreddit"] == sub) & (df["tipo"] == tipo) & (df["tema"] == tema)
                   & (df["trimestre"] <= ULTIMO_TRIM)].sort_values("trimestre")
            # Trimestres con menos de 50 textos no se grafican (r/taquerosprogramadores arranca en 2023-T3
            # con 2 posts). r/devsarg tiene entre 65 y 98 posts por trimestre en 2021: esa parte es ruidosa.
            d = d[d["textos"] >= 50]
            ax.plot(trimestre_a_fecha(d["trimestre"]), d["proporcion"] * 100,
                    color=COLOR_SUB[sub], label=ETIQUETA_SUB[sub], linewidth=1.8)
        ax.set_title(NOMBRE_TEMA[tema], fontsize=12.5)
        marcar_corte(ax, texto="ChatGPT" if i == 0 else "")
        ax.set_ylim(0, ax.get_ylim()[1] * 1.12)  # margen para la etiqueta del corte
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:g}%")
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", labelsize=9.5)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, bbox_to_anchor=(0.995, 0.955), fontsize=10.5)
    return guardar(fig, nombre)


def etapa_diccionarios(muestra=0):
    regex = compilar(DICCIONARIOS)
    t0 = time.time()
    total, menciones, reservorio = contar_diccionarios(regex, muestra)
    print(f"  diccionarios: {sum(total.values()):,} textos en {time.time() - t0:.0f} s")
    if muestra:
        filas = [f for tema in DICCIONARIOS for f in reservorio[tema]]
        pd.DataFrame(filas, columns=["tema", "id", "subreddit", "tipo", "trimestre", "coincidencia",
                                     "contexto"]).to_csv(
            os.path.join(TABLAS, "temas_validacion_muestra.csv"), index=False, encoding="utf-8")
        print("  muestra en reports/tablas/temas_validacion_muestra.csv")
    df = tabla_trimestral(total, menciones)
    df.to_csv(os.path.join(TABLAS, "temas_diccionario_trimestre.csv"), index=False, encoding="utf-8")
    per = tabla_periodo(df)
    per.to_csv(os.path.join(TABLAS, "temas_diccionario_periodo.csv"), index=False, encoding="utf-8")
    for tipo in ("post", "comentario"):
        print(f"\n  {tipo}: % antes -> después (sin 2022Q4)")
        for _, r in per[(per["tipo"] == tipo) & per["subreddit"].isin(SUBS_AR)].iterrows():
            print(f"    {r['subreddit']:11s} {r['tema']:9s} {100 * r['proporcion_antes']:5.2f} -> "
                  f"{100 * r['proporcion_despues']:5.2f}  x{r['cociente']:.2f}")
    figura_diccionarios(df, "post", "temas_diccionarios_posts.png",
                        "Qué temas aparecen en los posts",
                        "% de posts de cada trimestre que mencionan el tema (diccionarios de palabras)")
    figura_diccionarios(df, "comentario", "temas_diccionarios_comentarios.png",
                        "Qué temas aparecen en los comentarios",
                        "% de comentarios de cada trimestre que mencionan el tema (diccionarios de palabras)")


# ---------------------------------------------------------------------------
# b) TF-IDF y log-odds
# ---------------------------------------------------------------------------

RE_TOKEN = re.compile(r"[a-zñ]{2,}")
RE_RISA = re.compile(r"^(?:j[aeiou]){2,}j?$|^(?:a?j+a+)+$|^x+d+$")
RUIDO = {"http", "https", "www", "com", "gt", "lt", "amp", "x200b", "nbsp", "jpg", "png", "gif",
         "preview", "redd", "reddit", "imgur", "webp", "format", "auto", "width", "height",
         "removed", "deleted", "edit", "edito", "xd", "q", "xq", "pq", "tmb", "tb", "ok", "si", "re",
         "che", "bueno", "igual", "cosa", "cosas", "gente", "ser", "va", "hace", "ver", "tenes", "sos",
         "podes", "queres", "sabes", "hacer", "tener", "decir", "creo", "hay",
         "the", "to", "and", "of", "in", "is", "it", "you", "for", "that", "on", "with", "this", "be",
         "are", "my", "if", "or", "at", "as", "an", "so", "what", "have", "not", "but", "do", "can",
         "your", "we", "was", "they", "from", "will", "just", "me", "no"}


def stopwords_es():
    """Stopwords de spaCy (español), normalizadas igual que los textos, más ruido de Reddit."""
    from spacy.lang.es.stop_words import STOP_WORDS
    return {normalizar(w).strip() for w in STOP_WORDS} | RUIDO


def periodo_trim(trimestre):
    if trimestre < CORTE_TRIM:
        return "antes"
    return "corte" if trimestre == CORTE_TRIM else "despues"


def contar_tokens(stop):
    """Frecuencia de documento de cada palabra por (subreddit, trimestre).

    Cada texto (post o comentario) cuenta una vez por palabra, así un bloque de
    código o un texto que repite una palabra cien veces no domina el conteo.
    """
    cuentas = defaultdict(Counter)
    n_textos = Counter()
    for r in leer_posteos(("subreddit", "trimestre", "texto")):
        if r["subreddit"] not in SUBS_AR or r["trimestre"] > ULTIMO_TRIM:
            continue
        toks = {w for w in RE_TOKEN.findall(normalizar(r["texto"]))
                if w not in stop and not RE_RISA.match(w)}
        clave = (r["subreddit"], r["trimestre"])
        cuentas[clave].update(toks)
        n_textos[clave] += 1
    return cuentas, n_textos


def tfidf(cuentas, n_textos, sub, presencia=5, min_textos=30, top=20):
    """TF-IDF con un documento por trimestre, agregado por período y por año.

    tf = proporción de textos del trimestre que usan la palabra.
    idf = log(N / df), con N = trimestres y df = trimestres donde la palabra
    aparece en al menos `presencia` textos. Una palabra presente en todos los
    trimestres tiene idf 0: TF-IDF destaca lo que se concentra en el tiempo.
    El puntaje de un período (o año) es el promedio de sus trimestres.
    """
    trims = sorted(t for s, t in cuentas if s == sub)
    vocab = sorted({w for t in trims for w, c in cuentas[(sub, t)].items() if c >= presencia})
    idx = {w: i for i, w in enumerate(vocab)}
    tf = np.zeros((len(trims), len(vocab)), dtype=np.float32)
    df_textos = np.zeros_like(tf)
    for i, t in enumerate(trims):
        for w, c in cuentas[(sub, t)].items():
            j = idx.get(w)
            if j is not None:
                df_textos[i, j] = c
                tf[i, j] = c / n_textos[(sub, t)]
    presente = (df_textos >= presencia).sum(axis=0)
    idf = np.log(len(trims) / np.maximum(presente, 1))
    puntaje = tf * idf
    grupos = {}
    for i, t in enumerate(trims):
        p = periodo_trim(t)
        if p != "corte":
            grupos.setdefault(("periodo", p), []).append(i)
        grupos.setdefault(("anio", t[:4]), []).append(i)
    filas = []
    for (nivel, doc), filas_idx in grupos.items():
        media = puntaje[filas_idx].mean(axis=0)
        textos = df_textos[filas_idx].sum(axis=0)
        media[textos < min_textos] = 0
        for rango, j in enumerate(np.argsort(-media)[:top], 1):
            filas.append({"subreddit": sub, "nivel": nivel, "documento": doc, "rango": rango,
                          "termino": vocab[j], "tfidf": round(float(media[j]), 5),
                          "idf": round(float(idf[j]), 3), "textos": int(textos[j]),
                          "pct_textos": round(100 * float(tf[filas_idx, j].mean()), 3)})
    return pd.DataFrame(filas)


def log_odds(cuentas, sub, a0=1000, min_cuenta=30, top=20):
    """Log-odds con prior de Dirichlet informativo (Monroe, Colaresi y Quinn, 2008).

    Compara antes (2021-T1 a 2022-T3) con después (2023-T1 a 2026-T3); 2022-T4
    queda afuera. Las cuentas son frecuencias de documento. El prior es la
    frecuencia de cada palabra en todo el subreddit, escalada a a0 pseudo-cuentas.
    z > 0: característica de "después"; z < 0: de "antes".
    """
    antes, despues = Counter(), Counter()
    for (s, t), c in cuentas.items():
        p = periodo_trim(t)
        if s == sub and p != "corte":
            (antes if p == "antes" else despues).update(c)
    fondo = antes + despues
    n_fondo = sum(fondo.values())
    n_a, n_d = sum(antes.values()), sum(despues.values())
    filas = []
    for w, f in fondo.items():
        if f < min_cuenta:
            continue
        alfa = a0 * f / n_fondo
        ya, yd = antes[w], despues[w]
        delta = (math.log((yd + alfa) / (n_d + a0 - yd - alfa))
                 - math.log((ya + alfa) / (n_a + a0 - ya - alfa)))
        var = 1 / (yd + alfa) + 1 / (ya + alfa)
        filas.append((w, delta / math.sqrt(var), ya, yd, 1e4 * ya / n_a, 1e4 * yd / n_d))
    df = pd.DataFrame(filas, columns=["termino", "z", "frec_antes", "frec_despues",
                                      "por10k_antes", "por10k_despues"])
    df["subreddit"] = sub
    sel = pd.concat([df.nlargest(top, "z").assign(lado="despues"),
                     df.nsmallest(top, "z").assign(lado="antes")])
    return sel.round(3)


def figura_log_odds(lo, sub, nombre):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.6), sharex=True)
    fig.suptitle(f"Palabras características de cada período en {ETIQUETA_SUB[sub]}", x=0.01, ha="left",
                 fontsize=15, fontweight="bold", color=TINTA)
    fig.text(0.01, 0.915, "Log-odds con prior de Dirichlet (Monroe et al.) sobre posts y comentarios, sin 2022-T4. "
             "Top 15 por z-score", ha="left", fontsize=11, color=TINTA_2)
    for ax, lado, titulo in ((axes[0], "antes", "Más típicas de antes (2021 a 2022-T3)"),
                             (axes[1], "despues", "Más típicas de después (2023 a 2026-T3)")):
        d = lo[(lo["subreddit"] == sub) & (lo["lado"] == lado)].copy()
        d["za"] = d["z"].abs()
        d = d.nlargest(15, "za").iloc[::-1]
        ax.set_axisbelow(True)
        ax.barh(d["termino"], d["za"], color=COLOR_SUB[sub], height=0.7)
        ax.set_title(titulo, fontsize=12.5)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.tick_params(axis="y", labelsize=11, labelcolor=TINTA)
        ax.set_xlabel("|z|")
    return guardar(fig, nombre)


def etapa_tfidf():
    t0 = time.time()
    stop = stopwords_es()
    cuentas, n_textos = contar_tokens(stop)
    print(f"  tokens contados en {time.time() - t0:.0f} s")
    los = []
    for sub in SUBS_AR:
        tf = tfidf(cuentas, n_textos, sub)
        tf.to_csv(os.path.join(TABLAS, f"temas_tfidf_{sub}.csv"), index=False, encoding="utf-8")
        ancho = tf.pivot_table(index="rango", columns="documento", values="termino", aggfunc="first")
        print(f"\n  TF-IDF {sub}\n{ancho.to_string()}")
        lo = log_odds(cuentas, sub)
        lo.to_csv(os.path.join(TABLAS, f"temas_logodds_{sub}.csv"), index=False, encoding="utf-8")
        los.append(lo)
        print(f"\n  log-odds {sub} antes: {', '.join(lo[lo['lado'] == 'antes']['termino'])}")
        print(f"  log-odds {sub} después: {', '.join(lo[lo['lado'] == 'despues']['termino'])}")
    lo = pd.concat(los)
    for sub in SUBS_AR:
        figura_log_odds(lo, sub, f"temas_logodds_{sub}.png")


# ---------------------------------------------------------------------------
# c) BERTopic
# ---------------------------------------------------------------------------

MODELO_EMB = "paraphrase-multilingual-MiniLM-L12-v2"
N_TEMAS = 30

# Nombres puestos a mano después de leer las palabras y los posts de cada tema.
# tema_id -> (palabra que tiene que estar entre las 10 del tema, nombre).
# La palabra es un control: si otra corrida da temas distintos, el script avisa
# y usa las palabras clave como nombre en lugar de un nombre equivocado.
NOMBRES_BERTOPIC = {
    0: ("carrera", "Carrera, estudios y dudas laborales"),
    1: ("entrevista", "Entrevistas, CV y selección"),
    2: ("argentina", "Trabajar desde Argentina o afuera"),
    3: ("sueldo", "Sueldo, horario y condiciones"),
    4: ("carlos", "Posts cortos, humor y off-topic"),
    5: ("remoto", "Remoto, freelance, asistente virtual"),
    6: ("ia", "IA y automatización"),
    7: ("datos", "Datos (data science, SQL)"),
    8: ("ingles", "Inglés: clases y traducción"),
    9: ("videos", "Edición de video y contenido"),
    10: ("python", "Aprender a programar"),
    11: ("notebook", "Hardware: notebooks y PC"),
    12: ("web", "Páginas web y hosting"),
    13: ("marketing", "Marketing y ventas"),
    14: ("videojuegos", "Desarrollo de videojuegos"),
    15: ("diseño", "Diseño gráfico y UX"),
    16: ("ciberseguridad", "Ciberseguridad, redes y DevOps"),
    17: ("banco", "Cobrar en dólares (bancos, Payoneer)"),
    18: ("app", "Desarrollo de apps"),
    19: ("utm", "Links, imágenes y memes"),
    20: ("java", "Java y backend"),
    21: ("whatsapp", "Bots y chatbots de WhatsApp"),
    22: ("bootcamp", "Bootcamps (MeLi, Accenture)"),
    23: ("cocina", "Gastronomía y comida rápida"),
    24: ("moto", "Delivery y apps de viaje"),
    25: ("cursos", "Cursos, matemática y facultad"),
    26: ("steve", "Memes internos de r/devsarg"),
    27: ("javascript", "Frontend (JavaScript, HTML, CSS)"),
    28: ("senior", "Seniority y edad"),
    29: ("mercado", "Mercado saturado y economía"),
}


def leer_posts_ar():
    filas = [r for r in leer_posteos(("id", "tipo", "subreddit", "trimestre", "texto"))
             if r["tipo"] == "post" and r["subreddit"] in SUBS_AR]
    return pd.DataFrame(filas).drop(columns="tipo")


def calcular_embeddings(textos, ids):
    """Embeddings en GPU, con caché en disco (el orden se controla con los ids)."""
    ids_cache = CACHE_EMB.replace(".npy", "_ids.txt")
    if os.path.exists(CACHE_EMB) and os.path.exists(ids_cache):
        with open(ids_cache, encoding="utf-8") as f:
            if f.read().split("\n") == list(ids):
                print("  embeddings desde caché")
                return np.load(CACHE_EMB)
    import torch
    from sentence_transformers import SentenceTransformer
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = SentenceTransformer(MODELO_EMB, device=dispositivo)
    if dispositivo == "cuda":
        modelo.half()
    t0 = time.time()
    emb = modelo.encode([t[:2000] for t in textos], batch_size=64, show_progress_bar=False,
                        convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
    print(f"  embeddings: {emb.shape} en {time.time() - t0:.0f} s ({dispositivo})")
    np.save(CACHE_EMB, emb)
    with open(ids_cache, "w", encoding="utf-8") as f:
        f.write("\n".join(ids))
    del modelo
    if dispositivo == "cuda":
        torch.cuda.empty_cache()
    return emb


def ajustar_bertopic(docs, emb):
    """Ajusta BERTopic y devuelve los centroides de cada tema en el espacio de embeddings."""
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from hdbscan import HDBSCAN
    from umap import UMAP
    umap = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine",
                random_state=SEMILLA, low_memory=True)
    hdb = HDBSCAN(min_cluster_size=150, min_samples=20, metric="euclidean",
                  cluster_selection_method="eom", prediction_data=True)
    modelo = BERTopic(umap_model=umap, hdbscan_model=hdb, vectorizer_model=vectorizador_temas(),
                      ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
                      top_n_words=10, calculate_probabilities=False, verbose=False,
                      language="multilingual")  # con "english" borra la ñ antes del c-TF-IDF
    t0 = time.time()
    temas, _ = modelo.fit_transform(docs, embeddings=emb)
    temas = np.array(temas)
    n_ini = len(set(temas)) - (1 if -1 in temas else 0)
    atipicos_ini = float(np.mean(temas == -1))
    print(f"  BERTopic: {n_ini} temas iniciales, {atipicos_ini:.1%} atípicos, {time.time() - t0:.0f} s")
    modelo.reduce_topics(docs, nr_topics=N_TEMAS + 1)  # +1 por el tema -1 de atípicos
    temas = np.array(modelo.topics_)
    ids = np.array(sorted(t for t in set(temas) if t >= 0))
    centroides = np.stack([emb[temas == t].mean(axis=0) for t in ids])
    centroides /= np.linalg.norm(centroides, axis=1, keepdims=True)
    return ids, centroides, {"temas_iniciales": n_ini, "atipicos_iniciales": atipicos_ini}


def asignar_centroides(emb, ids, centroides):
    """Tema del centroide más cercano (coseno); -1 si la similitud no llega al umbral.

    La asignación de cada post depende solo de su embedding y de los centroides
    guardados, no del resto del corpus.
    """
    sim = emb @ centroides.T
    mejor = sim.argmax(axis=1)
    sim_max = sim[np.arange(len(emb)), mejor]
    return np.where(sim_max >= UMBRAL_CENTROIDE, ids[mejor], -1), sim_max


def vectorizador_temas():
    from sklearn.feature_extraction.text import CountVectorizer
    # Se aplica a un documento por tema (c-TF-IDF): min_df cuenta temas, no posts.
    return CountVectorizer(stop_words=sorted(stopwords_es()), min_df=2, ngram_range=(1, 2),
                           token_pattern=r"(?u)\b[a-zñ][a-zñ0-9]+\b")


def palabras_temas(docs, temas, top=10):
    """c-TF-IDF (el de BERTopic) sobre la asignación final: las palabras de cada tema."""
    from bertopic.vectorizers import ClassTfidfTransformer
    ids = sorted(t for t in set(temas) if t >= 0)
    por_tema = [" ".join(d for d, t in zip(docs, temas) if t == i) for i in ids]
    vec = vectorizador_temas()
    X = vec.fit_transform(por_tema)
    ctfidf = ClassTfidfTransformer(reduce_frequent_words=True).fit_transform(X).toarray()
    vocab = vec.get_feature_names_out()
    return {i: [vocab[j] for j in np.argsort(-ctfidf[k])[:top]] for k, i in enumerate(ids)}


UMBRAL_CENTROIDE = 0.4


def nombrar_temas(palabras):
    nombres = {-1: "Sin tema (atípicos)", -2: "Sin texto (borrado)"}
    avisos = []
    for t, pal in palabras.items():
        t = int(t)
        if t in NOMBRES_BERTOPIC:
            control, nombre = NOMBRES_BERTOPIC[t]
            if control in pal:
                nombres[t] = nombre
                continue
            avisos.append(t)
        nombres[t] = f"Tema {t}: {' / '.join(pal[:4])}"
    if avisos:
        print(f"  AVISO: los temas {avisos} no coinciden con los nombres guardados; se usan palabras clave")
    return nombres


def figura_bertopic_cambio(cambio, nombre):
    """Puntos antes y después por tema (proporción de posts), ordenados por el cambio."""
    d = cambio[cambio["tema_id"] >= 0].sort_values("diferencia")
    fig, ax = nueva_figura("Temas de los posts antes y después del corte (BERTopic)",
                           "% de posts en cada tema, promedio de r/devsarg y r/empleos_AR, sin 2022-T4",
                           ancho=11, alto=9.5)
    y = np.arange(len(d))
    ax.hlines(y, d["antes"] * 100, d["despues"] * 100, color=TINTA_TENUE, linewidth=1.4, zorder=1)
    ax.scatter(d["antes"] * 100, y, color=TINTA_TENUE, s=36, zorder=2, label="Antes (2021-T1 a 2022-T3)")
    ax.scatter(d["despues"] * 100, y, color=SERIES[0], s=36, zorder=3, label="Después (2023-T1 a 2026-T3)")
    ax.set_yticks(y, d["tema_nombre"], fontsize=10, color=TINTA)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:g}%")
    ax.legend(loc="lower right", fontsize=10)
    return guardar(fig, nombre)


def figura_bertopic_series(trim, cambio, nombre, n=6):
    """Small multiples con los temas que más suben y más bajan."""
    d = cambio[cambio["tema_id"] >= 0]
    elegidos = (list(d.nlargest(n // 2, "diferencia")["tema_id"])
                + list(d.nsmallest(n // 2, "diferencia")["tema_id"]))
    fig, axes = plt.subplots(2, n // 2, figsize=(13, 7.2), sharex=True)
    fig.suptitle("Los temas que más subieron (arriba) y más bajaron (abajo)", x=0.01, ha="left",
                 fontsize=15, fontweight="bold", color=TINTA)
    fig.text(0.01, 0.915, "% de posts de cada trimestre asignados al tema (BERTopic)",
             ha="left", fontsize=11, color=TINTA_2)
    nombres = cambio.set_index("tema_id")["tema_nombre"]
    for i, (ax, t) in enumerate(zip(axes.flat, elegidos)):
        for sub in SUBS_AR:
            s = trim[(trim["tema_id"] == t) & (trim["subreddit"] == sub)
                     & (trim["trimestre"] <= ULTIMO_TRIM)].sort_values("trimestre")
            ax.plot(trimestre_a_fecha(s["trimestre"]), s["proporcion"] * 100, color=COLOR_SUB[sub],
                    label=ETIQUETA_SUB[sub], linewidth=1.8)
        ax.set_title(nombres[t], fontsize=11.5)
        marcar_corte(ax, texto="ChatGPT" if i == 0 else "")
        ax.set_ylim(0, ax.get_ylim()[1] * 1.12)  # margen para la etiqueta del corte
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:g}%")
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", labelsize=9.5)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, bbox_to_anchor=(0.995, 0.955), fontsize=10.5)
    return guardar(fig, nombre)


def etapa_bertopic(reajustar=False):
    t0 = time.time()
    posts = leer_posts_ar()
    print(f"  {len(posts):,} posts de r/devsarg y r/empleos_AR")
    emb = calcular_embeddings(posts["texto"].fillna("").tolist(), posts["id"].tolist())
    docs = [normalizar(t).strip() for t in posts["texto"].fillna("")]
    # Posts cuyo título y cuerpo se borraron: no tienen contenido para asignarles tema.
    con_texto = np.array([d not in ("[deleted by user]", "[removed]", "[deleted]", "") for d in docs])
    print(f"  {np.sum(~con_texto):,} posts sin texto quedan como tema -2")
    docs_t, emb_t = [d for d, k in zip(docs, con_texto) if k], emb[con_texto]

    # Ajuste: solo la primera vez o con --reajustar. Si no, se reusan los centroides
    # guardados para que los temas (y sus nombres) no cambien con cambios chicos del corpus.
    if reajustar or not os.path.exists(CENTROIDES):
        ids, centroides, info = ajustar_bertopic(docs_t, emb_t)
        np.savez(CENTROIDES, ids=ids, centroides=centroides, info=json.dumps(info))
        print(f"  centroides guardados en {os.path.relpath(CENTROIDES, ROOT)}")
    else:
        guardado = np.load(CENTROIDES)
        ids, centroides = guardado["ids"], guardado["centroides"]
        info = json.loads(str(guardado["info"]))
        print(f"  centroides desde {os.path.relpath(CENTROIDES, ROOT)} (--reajustar para volver a ajustar)")
    temas_t, sim_t = asignar_centroides(emb_t, ids, centroides)
    print(f"  {len(ids)} temas, {np.mean(temas_t == -1):.1%} atípicos (similitud < {UMBRAL_CENTROIDE})")
    palabras = palabras_temas(docs_t, temas_t)
    nombres = nombrar_temas(palabras)
    posts["tema_id"] = -2
    posts.loc[con_texto, "tema_id"] = temas_t
    posts["similitud"] = np.nan
    posts.loc[con_texto, "similitud"] = sim_t
    temas = posts["tema_id"].to_numpy()
    posts["tema_nombre"] = posts["tema_id"].map(nombres)

    # Descripción de cada tema: palabras, tamaño y posts representativos.
    filas = []
    for t in sorted(set(temas)):
        sel = posts[posts["tema_id"] == t]
        # Posts representativos: los 3 más cercanos al centroide.
        rep = sel.nlargest(3, "similitud")["texto"].fillna("").tolist() if t >= 0 else []
        filas.append({"tema_id": t, "tema_nombre": nombres[t], "posts": len(sel),
                      "pct_devsarg": round(100 * (sel["subreddit"] == "devsarg").mean(), 1),
                      "palabras": ", ".join(palabras.get(t, [])),
                      "ejemplos": " ||| ".join(r[:160].replace("\n", " ") for r in rep[:3])})
    pd.DataFrame(filas).to_csv(os.path.join(TABLAS, "temas_bertopic_temas.csv"), index=False,
                               encoding="utf-8")

    # Proporción de posts de cada tema por trimestre y subreddit (con ceros explícitos).
    conteo = posts.groupby(["subreddit", "trimestre", "tema_id"]).size()
    completo = pd.MultiIndex.from_product([SUBS_AR, sorted(posts["trimestre"].unique()), sorted(set(temas))],
                                          names=["subreddit", "trimestre", "tema_id"])
    trim = conteo.reindex(completo, fill_value=0).rename("posts").reset_index()
    trim["total"] = trim.groupby(["subreddit", "trimestre"])["posts"].transform("sum")
    trim = trim[trim["total"] > 0].copy()
    trim["proporcion"] = trim["posts"] / trim["total"]
    trim["tema_nombre"] = trim["tema_id"].map(nombres)
    trim["periodo"] = np.where(trim["trimestre"] < CORTE_TRIM, "antes",
                               np.where(trim["trimestre"] == CORTE_TRIM, "corte", "despues"))
    trim.to_csv(os.path.join(TABLAS, "temas_bertopic_trimestre.csv"), index=False, encoding="utf-8")

    # Antes vs después: promedio de las proporciones trimestrales, y después
    # promedio de los dos subs (cada trimestre y cada sub pesan igual).
    t2 = trim[(trim["periodo"] != "corte") & (trim["trimestre"] <= ULTIMO_TRIM)]
    por_sub = t2.groupby(["tema_id", "subreddit", "periodo"])["proporcion"].mean().unstack("periodo")
    cambio = por_sub.groupby("tema_id").mean().reset_index()
    for sub in SUBS_AR:
        ps = por_sub.xs(sub, level="subreddit")
        cambio[f"antes_{sub}"] = cambio["tema_id"].map(ps["antes"])
        cambio[f"despues_{sub}"] = cambio["tema_id"].map(ps["despues"])
    cambio["diferencia"] = cambio["despues"] - cambio["antes"]
    cambio["cociente"] = cambio["despues"] / cambio["antes"]
    cambio["tema_nombre"] = cambio["tema_id"].map(nombres)
    cambio = cambio.sort_values("diferencia", ascending=False)
    cambio.round(4).to_csv(os.path.join(TABLAS, "temas_bertopic_cambio.csv"), index=False, encoding="utf-8")
    print(cambio[["tema_id", "tema_nombre", "antes", "despues", "cociente"]].round(3).to_string(index=False))

    posts[["id", "tema_id", "tema_nombre"]].to_parquet(SALIDA_POSTS, index=False)
    with open(os.path.join(TABLAS, "temas_bertopic_info.json"), "w", encoding="utf-8") as f:
        json.dump({**info, "posts": len(posts), "atipicos_finales": float(np.mean(temas == -1))}, f, indent=1)
    figura_bertopic_cambio(cambio, "temas_bertopic_cambio.png")
    figura_bertopic_series(trim, cambio, "temas_bertopic_series.png")
    print(f"  BERTopic total: {time.time() - t0:.0f} s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", choices=("diccionarios", "tfidf", "bertopic", "todo"), default="todo")
    ap.add_argument("--muestra", type=int, default=0, help="tamaño de la muestra de validación por tema")
    ap.add_argument("--reajustar", action="store_true",
                    help="volver a ajustar BERTopic en lugar de usar los centroides guardados")
    args = ap.parse_args()
    os.makedirs(TABLAS, exist_ok=True)
    random.seed(SEMILLA)
    np.random.seed(SEMILLA)
    t0 = time.time()
    if args.etapa in ("diccionarios", "todo"):
        print("a) Diccionarios")
        etapa_diccionarios(args.muestra)
    if args.etapa in ("tfidf", "todo"):
        print("b) TF-IDF y log-odds")
        etapa_tfidf()
    if args.etapa in ("bertopic", "todo"):
        print("c) BERTopic")
        etapa_bertopic(args.reajustar)
    print(f"Listo en {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
