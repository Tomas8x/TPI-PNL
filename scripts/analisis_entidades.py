"""Actores de la conversación: entidades nombradas y diccionario curado (ver docs/07_entidades.md).

Uso:
    python scripts/analisis_entidades.py              # corre el NER (~10 min en CPU) y todo el análisis
    python scripts/analisis_entidades.py --reusar-ner # reusa data/processed/ent_ner_posts.jsonl

Dos mediciones complementarias:
1. NER con spaCy (es_core_news_lg, solo el componente ner) sobre los posts de los
   tres subs (texto = título + cuerpo, truncado a 2.000 caracteres). Etiquetas ORG,
   MISC, PER y LOC, normalizadas a minúsculas y con alias.
2. Diccionario curado de actores (herramientas de IA, empresas, plataformas de
   empleo y tecnologías) aplicado con expresiones regulares a posts y comentarios.

Salida:
- data/processed/ent_ner_posts.jsonl: entidades por post (caché del NER).
- reports/tablas/ent_ner_top_periodo.csv: entidades NER más frecuentes antes y después.
- reports/tablas/ent_ner_cambios.csv: entidades NER que más crecen y caen.
- reports/tablas/ent_ner_muestra.csv: 50 entidades al azar con contexto, para evaluar el NER.
- reports/tablas/ent_ner_cobertura.csv: qué parte de las menciones del diccionario reconoce el NER.
- reports/tablas/ent_dic_periodo.csv: tasa por 1.000 textos de cada actor del diccionario, antes y
  después (r/devsarg + r/empleos_AR); ent_dic_periodo_devsarg.csv, lo mismo solo para r/devsarg.
- reports/tablas/ent_dic_trimestral.csv: textos con cada actor por trimestre, subreddit y tipo.
- reports/tablas/ent_ia_trimestral.csv: tasa de mención de IA por trimestre y subreddit.
- reports/tablas/ent_ia_participacion.csv: participación de cada herramienta de IA por trimestre.
- reports/tablas/ent_dic_contextos.csv: contextos al azar de los términos ambiguos.
- reports/figures/ent_*.png

Lee el JSONL línea por línea y se queda solo con los campos que usa.
"""

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from graficos import (COLOR_SUB, ETIQUETA_SUB, SERIES, TINTA_2,  # noqa: E402
                      TINTA_TENUE, eje_fechas, guardar, marcar_corte, nueva_figura,
                      trimestre_a_fecha)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTEOS = os.path.join(ROOT, "data", "processed", "posteos.jsonl")
CACHE_NER = os.path.join(ROOT, "data", "processed", "ent_ner_posts.jsonl")
TABLAS = os.path.join(ROOT, "reports", "tablas")

SEMILLA = 42
LARGO_MAX = 2000
SUBS = ("devsarg", "empleos_AR", "taquerosprogramadores")
SUBS_AR = ("devsarg", "empleos_AR")  # los únicos con datos antes del corte
ETIQUETAS_NER = ("ORG", "MISC", "PER", "LOC")
ULTIMO_TRIMESTRE = "2026Q3"
N_CONTEXTOS = 15
MIN_TEXTOS_TRIMESTRE = 500  # trimestres con menos textos no se grafican
MIN_TEXTOS_ANTES = 20  # actores con menos menciones antes no entran en el ranking de cambios

# --------------------------------------------------------------------------
# Diccionario curado. Cada actor: (nombre, categoría, patrón). Los patrones se
# aplican sobre el texto en minúsculas; los de ACTORES_MAYUS, sobre el original.
# --------------------------------------------------------------------------
ACTORES = [
    # Herramientas de IA
    ("ChatGPT/OpenAI", "ia_herramienta", r"chat\s?-?gpt|\bgpt\b|\bgpt-?[345]\w*|openai|open ai"),
    ("Copilot", "ia_herramienta", r"copilot"),
    ("Claude", "ia_herramienta", r"\bclaude\b|anthropic"),
    ("Cursor", "ia_herramienta", r"\bcursor\b"),
    ("Gemini/Bard", "ia_herramienta", r"\bgemini\b|\bbard\b"),
    ("DeepSeek", "ia_herramienta", r"deep\s?seek"),
    ("Otras IA", "ia_herramienta",
     r"\bwindsurf\b|codeium|tabnine|\bdevin\b|lovable|bolt\.new|\bv0\b|perplexity|\bcodex\b"
     r"|midjourney|stable diffusion|\bgrok\b|\bmistral\b|\bqwen\b"),
    # IA como tema genérico
    ("IA/inteligencia artificial", "ia_generico", r"\bias?\b|inteligencia artificial"),
    ("LLM", "ia_generico", r"\bllms?\b|modelos? de lenguaje|\bgenai\b|ia generativa"),
    ("Vibe coding", "ia_generico", r"vibe\s?-?cod\w*"),
    # Empresas
    ("Google", "empresa", r"\bgoogle\b"),
    ("Meta/Facebook", "empresa", r"facebook|zuckerberg"),
    ("Amazon", "empresa", r"\bamazon\b"),
    ("Microsoft", "empresa", r"microsoft"),
    ("Apple", "empresa", r"\bapple\b"),
    ("Netflix", "empresa", r"netflix"),
    ("IBM", "empresa", r"\bibm\b"),
    ("Oracle", "empresa", r"\boracle\b"),
    ("Nvidia", "empresa", r"nvidia"),
    ("Twitter/X", "empresa", r"twitter"),
    ("MercadoLibre", "empresa", r"mercado\s?libre|\bmeli\b|mercado\s?pago"),
    ("Globant", "empresa", r"globant"),
    ("Accenture", "empresa", r"accenture"),
    ("Despegar", "empresa", r"despegar\.com|\bdespegar\b(?= (?:com|es|tiene|paga|busca))"),
    ("Ualá", "empresa", r"\buala\b|\bualá\b"),
    ("Naranja X", "empresa", r"naranja\s?x"),
    ("Bancos AR (Galicia, Santander, BBVA)", "empresa", r"\bgalicia\b|santander|\bbbva\b"),
    ("Tata/TCS", "empresa", r"tata consultancy|\btcs\b"),
    ("EPAM", "empresa", r"\bepam\b"),
    ("Endava", "empresa", r"endava"),
    ("GlobalLogic", "empresa", r"global\s?logic"),
    ("NTT Data/Everis", "empresa", r"ntt\s?data|\beveris\b"),
    ("Cognizant", "empresa", r"cognizant"),
    ("Big Four (Deloitte, PwC, KPMG)", "empresa", r"deloitte|\bpwc\b|\bkpmg\b"),
    ("Capgemini", "empresa", r"capgemini"),
    ("Softtek", "empresa", r"softtek"),
    ("Wizeline", "empresa", r"wizeline"),
    ("Encora/Nearsoft", "empresa", r"\bencora\b|nearsoft"),
    # Plataformas de empleo y pago
    ("LinkedIn", "plataforma", r"linked\s?in"),
    ("Upwork", "plataforma", r"upwork"),
    ("Workana", "plataforma", r"workana"),
    ("Toptal", "plataforma", r"toptal"),
    ("Deel", "plataforma", r"\bdeel\b"),
    ("Glassdoor", "plataforma", r"glassdoor"),
    ("Indeed", "plataforma", r"\bindeed\b"),
    ("Bumeran/ZonaJobs/Computrabajo", "plataforma", r"bumeran|zona\s?jobs|computrabajo|\bocc\b"),
    ("GetOnBoard", "plataforma", r"get\s?on\s?board"),
    ("Payoneer", "plataforma", r"payoneer"),
    # Tecnologías
    ("Python", "tecnologia", r"\bpython\b"),
    ("Java", "tecnologia", r"\bjava\b"),
    ("JavaScript", "tecnologia", r"javascript|\bjs\b"),
    ("TypeScript", "tecnologia", r"typescript"),
    ("React", "tecnologia", r"\breact\b"),
    ("Angular", "tecnologia", r"\bangular\b"),
    ("Node", "tecnologia", r"\bnode(?:\.?js)?\b|nodejs"),
    ("PHP", "tecnologia", r"\bphp\b"),
    (".NET/C#", "tecnologia", r"\.net\b|dotnet|(?<!\w)c#"),
    ("Go", "tecnologia", r"golang"),
    ("Rust", "tecnologia", r"\brust\b"),
    ("SQL", "tecnologia", r"\bsql\b|mysql|postgres\w*"),
    ("AWS", "tecnologia", r"\baws\b"),
    ("Azure", "tecnologia", r"\bazure\b"),
    ("Docker/Kubernetes", "tecnologia", r"docker|kubernetes|\bk8s\b"),
    ("SAP", "tecnologia", r"\bsap\b|\babap\b"),
    ("Salesforce", "tecnologia", r"salesforce"),
    ("COBOL", "tecnologia", r"\bcobol\b"),
    ("Flutter", "tecnologia", r"flutter"),
    ("Kotlin", "tecnologia", r"kotlin"),
]
# Sensibles a mayúsculas: "AI" en minúscula suele ser "ahí"; "meta" es palabra común.
ACTORES_MAYUS = [
    ("IA/inteligencia artificial", "ia_generico", r"\bAIs?\b"),
    ("Meta/Facebook", "empresa", r"\bMeta\b(?!\s*:)"),
]
CATEGORIA = {n: c for n, c, _ in ACTORES + ACTORES_MAYUS}
HERRAMIENTAS_IA = [n for n, c, _ in ACTORES if c == "ia_herramienta"]
# Términos con riesgo de falsos positivos: se guardan contextos para revisarlos.
AMBIGUOS = {"Cursor", "IA/inteligencia artificial", "Meta/Facebook", "Claude", "SAP",
            "Deel", "ChatGPT/OpenAI", "Gemini/Bard", "Rust", "React"}


# Una regex por actor: con una sola alternación gigante el motor de re prueba
# todas las ramas en cada posición y tarda ~3,5 veces más.
RE_ACTORES = [(nombre, re.compile(patron), False) for nombre, _, patron in ACTORES]
RE_ACTORES += [(nombre, re.compile(patron), True) for nombre, _, patron in ACTORES_MAYUS]


def buscar_actores(texto):
    """Lista de (actor, inicio, fin) en el texto."""
    minus = texto.lower()
    encontrados = []
    for nombre, regex, mayus in RE_ACTORES:
        for m in regex.finditer(texto if mayus else minus):
            encontrados.append((nombre, m.start(), m.end()))
    return encontrados


# --------------------------------------------------------------------------
# Normalización de entidades NER
# --------------------------------------------------------------------------
ALIAS_NER = {
    "chat gpt": "chatgpt", "chat-gpt": "chatgpt", "gpt": "chatgpt", "openai": "chatgpt",
    "mercado libre": "mercadolibre", "meli": "mercadolibre", "mercado pago": "mercadolibre",
    "mercadopago": "mercadolibre",
    "github copilot": "copilot",
    "facebook": "meta", "linked in": "linkedin",
    "eeuu": "estados unidos", "ee.uu.": "estados unidos", "usa": "estados unidos",
    "us": "estados unidos", "yanquilandia": "estados unidos",
    "bs as": "buenos aires", "bsas": "buenos aires", "caba": "buenos aires",
    "capital federal": "buenos aires",
    "arg": "argentina", "argentino": "argentina",
    "méxico": "mexico", "cdmx": "mexico", "ciudad de mexico": "mexico", "ciudad de méxico": "mexico",
    "españa": "españa", "js": "javascript", "node.js": "node", "nodejs": "node",
    "ia": "ia", "ai": "ia", "inteligencia artificial": "ia",
}
# Palabras de saludo o relleno que el modelo marca como entidad (casi siempre MISC).
RUIDO_NER = {
    "hola", "buenas", "buenos", "saludos", "gracias", "holis", "hola gente", "buenas gente",
    "buen dia", "buen día", "buenas tardes", "buenas noches", "hola a todos", "gente",
    "edit", "pd", "ps", "tldr", "tl;dr", "les", "me", "uds", "che", "espero", "tengo",
    "alguien", "algun", "algún", "alguno", "duda", "consulta", "ayuda", "hola!", "nada",
    "jajaja", "jaja", "xd", "ok", "bueno", "sr", "jr", "ssr", "senior", "junior",
}


def normalizar(texto):
    t = " ".join(texto.lower().split())
    t = t.strip(" .,;:!?¡¿\"'()[]{}*_-#>")
    return ALIAS_NER.get(t, t)


def entidad_valida(norm):
    """Descarta saludos, números y spans largos (el NER marca frases enteras como MISC)."""
    if len(norm) < 2 or norm in RUIDO_NER:
        return False
    if len(norm.split()) > 3:
        return False
    if not re.search(r"[a-zñ]", norm):
        return False
    return True


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------
def leer_textos(solo_posts=False):
    """Recorre posteos.jsonl devolviendo solo los campos necesarios."""
    with open(POSTEOS, encoding="utf-8") as f:
        for linea in f:
            d = json.loads(linea)
            if solo_posts and d["tipo"] != "post":
                continue
            yield d["id"], d["tipo"], d["subreddit"], d["trimestre"], d["periodo"], d["texto"] or ""


# --------------------------------------------------------------------------
# 1. NER
# --------------------------------------------------------------------------
def correr_ner():
    import spacy

    nlp = spacy.load("es_core_news_lg",
                     exclude=["tok2vec", "morphologizer", "parser", "attribute_ruler",
                              "lemmatizer", "senter"])
    print(f"Componentes: {nlp.pipe_names}")
    metas = []
    textos = []
    for id_, _, sub, trim, per, texto in leer_textos(solo_posts=True):
        metas.append((id_, sub, trim, per))
        textos.append(texto[:LARGO_MAX])
    print(f"{len(textos):,} posts para NER")
    t0 = time.time()
    with open(CACHE_NER, "w", encoding="utf-8") as out:
        for i, doc in enumerate(nlp.pipe(textos, batch_size=128, n_process=4)):
            id_, sub, trim, per = metas[i]
            ents = [[e.text, e.label_, e.start_char, e.end_char] for e in doc.ents
                    if e.label_ in ETIQUETAS_NER]
            out.write(json.dumps({"id": id_, "subreddit": sub, "trimestre": trim,
                                  "periodo": per, "ents": ents}, ensure_ascii=False) + "\n")
            if (i + 1) % 10000 == 0:
                print(f"  {i + 1:,} posts, {time.time() - t0:.0f} s", flush=True)
    print(f"NER: {time.time() - t0:.0f} s")


def leer_cache():
    with open(CACHE_NER, encoding="utf-8") as f:
        for linea in f:
            yield json.loads(linea)


def log2_razon(antes, n_antes, despues, n_despues):
    """log2 de la razón de tasas, con 0,5 sumado a cada conteo para no dividir por cero."""
    return math.log2(((despues + 0.5) / n_despues) / ((antes + 0.5) / n_antes))


def analizar_ner():
    """Frecuencia de documentos por entidad normalizada, antes y después (subs argentinos)."""
    docs = Counter()          # (periodo) -> posts
    df = defaultdict(Counter)  # periodo -> entidad -> posts que la mencionan
    etiqueta = defaultdict(Counter)
    total_ents = 0
    validas = 0
    for r in leer_cache():
        if r["subreddit"] not in SUBS_AR:
            continue
        per = r["periodo"]
        docs[per] += 1
        vistas = set()
        for texto, lab, _, _ in r["ents"]:
            total_ents += 1
            n = normalizar(texto)
            if not entidad_valida(n):
                continue
            validas += 1
            etiqueta[n][lab] += 1
            vistas.add(n)
        for n in vistas:
            df[per][n] += 1
    print(f"NER (subs AR): {total_ents:,} entidades, {validas:,} válidas tras filtrar ruido")

    filas = []
    for n in set(df["antes"]) | set(df["despues"]):
        a, d = df["antes"][n], df["despues"][n]
        filas.append({
            "entidad": n,
            "etiqueta": etiqueta[n].most_common(1)[0][0],
            "posts_antes": a,
            "posts_despues": d,
            "tasa_antes": 1000 * a / docs["antes"],
            "tasa_despues": 1000 * d / docs["despues"],
            "log2_cambio": log2_razon(a, docs["antes"], d, docs["despues"]),
        })
    tabla = pd.DataFrame(filas)

    top = []
    for per in ("antes", "despues"):
        t = tabla.sort_values(f"tasa_{per}", ascending=False).head(30).copy()
        t.insert(0, "periodo", per)
        t.insert(1, "rango", range(1, len(t) + 1))
        top.append(t)
    top = pd.concat(top)
    top.to_csv(os.path.join(TABLAS, "ent_ner_top_periodo.csv"), index=False, float_format="%.2f")

    # Cambios: al menos 30 posts en total para no rankear rarezas.
    base = tabla[(tabla.posts_antes + tabla.posts_despues) >= 30]
    crecen = base.sort_values("log2_cambio", ascending=False).head(25).assign(sentido="crece")
    caen = base.sort_values("log2_cambio").head(25).assign(sentido="cae")
    cambios = pd.concat([crecen, caen])
    cambios.to_csv(os.path.join(TABLAS, "ent_ner_cambios.csv"), index=False, float_format="%.2f")
    return top, cambios, docs


def muestra_ner(n=50):
    """Entidades al azar (todas las etiquetas, los tres subs) con su contexto."""
    rng = random.Random(SEMILLA)
    todas = []
    for r in leer_cache():
        for texto, lab, ini, fin in r["ents"]:
            todas.append((r["id"], texto, lab, ini, fin))
    elegidas = rng.sample(todas, n)
    ids = {e[0] for e in elegidas}
    textos = {id_: t[:LARGO_MAX] for id_, _, _, _, _, t in leer_textos(solo_posts=True) if id_ in ids}
    filas = []
    for id_, texto, lab, ini, fin in elegidas:
        t = textos[id_]
        contexto = (t[max(0, ini - 60):ini] + "[[" + t[ini:fin] + "]]" + t[fin:fin + 60])
        filas.append({"id": id_, "entidad": texto, "etiqueta": lab,
                      "contexto": " ".join(contexto.split())})
    pd.DataFrame(filas).to_csv(os.path.join(TABLAS, "ent_ner_muestra.csv"), index=False)
    print(f"Muestra de {n} entidades sobre {len(todas):,} en total")
    return len(todas)


def cobertura_ner():
    """De las menciones del diccionario en los posts, cuántas reconoce el NER como entidad."""
    ents_por_post = {r["id"]: r["ents"] for r in leer_cache()}
    menciones = Counter()
    cubiertas = Counter()
    etiquetas = defaultdict(Counter)
    for id_, _, _, _, _, texto in leer_textos(solo_posts=True):
        texto = texto[:LARGO_MAX]
        ents = ents_por_post.get(id_, [])
        for actor, ini, fin in buscar_actores(texto):
            menciones[actor] += 1
            lab = next((e[1] for e in ents if e[2] <= ini and fin <= e[3]), None)
            if lab:
                cubiertas[actor] += 1
                etiquetas[actor][lab] += 1
            else:
                etiquetas[actor]["ninguna"] += 1
    filas = []
    for actor, m in menciones.items():
        fila = {"actor": actor, "categoria": CATEGORIA[actor], "menciones": m,
                "reconocidas_ner": cubiertas[actor], "pct_reconocidas": 100 * cubiertas[actor] / m}
        for lab in ETIQUETAS_NER + ("ninguna",):
            fila[f"n_{lab}"] = etiquetas[actor][lab]
        filas.append(fila)
    tabla = pd.DataFrame(filas).sort_values("menciones", ascending=False)
    tabla.to_csv(os.path.join(TABLAS, "ent_ner_cobertura.csv"), index=False, float_format="%.1f")
    por_cat = tabla.groupby("categoria")[["menciones", "reconocidas_ner"]].sum()
    por_cat["pct"] = 100 * por_cat.reconocidas_ner / por_cat.menciones
    print("Cobertura del NER sobre el diccionario:\n", por_cat.round(1))
    return tabla, por_cat


# --------------------------------------------------------------------------
# 2. Diccionario sobre posts y comentarios
# --------------------------------------------------------------------------
def clave_muestra(id_, actor):
    """Clave pseudoaleatoria y reproducible para muestrear contextos (bottom-k)."""
    return hashlib.md5(f"{SEMILLA}|{id_}|{actor}".encode("utf-8")).hexdigest()


def contar_bloque(lineas):
    """Procesa un bloque de líneas del JSONL (corre en un proceso aparte)."""
    totales = Counter()
    con = Counter()
    ia_alguna = Counter()
    contextos = defaultdict(list)
    for linea in lineas:
        d = json.loads(linea)
        texto = d["texto"] or ""
        clave = (d["subreddit"], d["tipo"], d["trimestre"], d["periodo"])
        totales[clave] += 1
        actores = set()
        for actor, ini, fin in buscar_actores(texto):
            if actor in actores:
                continue
            actores.add(actor)
            if actor in AMBIGUOS:
                ctx = " ".join((texto[max(0, ini - 70):ini] + "[[" + texto[ini:fin] + "]]"
                                + texto[fin:fin + 70]).split())
                contextos[(actor, d["periodo"])].append((clave_muestra(d["id"], actor), d["id"], ctx))
        for actor in actores:
            con[clave + (actor,)] += 1
        cats = {CATEGORIA[a] for a in actores}
        if "ia_herramienta" in cats:
            ia_alguna[clave + ("herramienta",)] += 1
        if cats & {"ia_herramienta", "ia_generico"}:
            ia_alguna[clave + ("cualquiera",)] += 1
    # Solo se devuelven los 15 contextos de menor clave por actor y período.
    contextos = {k: sorted(v)[:N_CONTEXTOS] for k, v in contextos.items()}
    return totales, con, ia_alguna, contextos


def bloques(tamanio=20000):
    with open(POSTEOS, encoding="utf-8") as f:
        bloque = []
        for linea in f:
            bloque.append(linea)
            if len(bloque) == tamanio:
                yield bloque
                bloque = []
        if bloque:
            yield bloque


def contar_diccionario(procesos=4):
    """Cuenta textos que mencionan cada actor, por subreddit, tipo y trimestre."""
    totales = Counter()   # (sub, tipo, trim, periodo) -> textos
    con = Counter()       # (sub, tipo, trim, periodo, actor) -> textos con el actor
    ia_alguna = Counter()  # (sub, tipo, trim, periodo, clase) -> textos
    contextos = defaultdict(list)  # (actor, periodo) -> muestra de contextos
    t0 = time.time()
    with Pool(procesos) as pool:
        for i, (t, c, ia, ctx) in enumerate(pool.imap(contar_bloque, bloques()), start=1):
            totales.update(t)
            con.update(c)
            ia_alguna.update(ia)
            for k, v in ctx.items():
                contextos[k] = sorted(contextos[k] + v)[:N_CONTEXTOS]
            if i % 20 == 0:
                print(f"  {sum(totales.values()):,} textos, {time.time() - t0:.0f} s", flush=True)
    print(f"Diccionario: {sum(totales.values()):,} textos en {time.time() - t0:.0f} s", flush=True)

    filas = [{"subreddit": s, "tipo": t, "trimestre": q, "periodo": p, "textos": n}
             for (s, t, q, p), n in totales.items()]
    tot = pd.DataFrame(filas)
    filas = [{"subreddit": s, "tipo": t, "trimestre": q, "periodo": p, "actor": a,
              "categoria": CATEGORIA[a], "textos_con_actor": n}
             for (s, t, q, p, a), n in con.items()]
    dic = pd.DataFrame(filas)
    filas = [{"subreddit": s, "tipo": t, "trimestre": q, "periodo": p, "clase": c, "textos": n}
             for (s, t, q, p, c), n in ia_alguna.items()]
    ia = pd.DataFrame(filas)

    filas = []
    for (actor, per), lista in sorted(contextos.items()):
        for _, id_, ctx in lista:
            filas.append({"actor": actor, "periodo": per, "id": id_, "contexto": ctx})
    pd.DataFrame(filas).to_csv(os.path.join(TABLAS, "ent_dic_contextos.csv"), index=False)
    return tot, dic, ia


def tabla_dic_periodo(tot, dic, subs=SUBS_AR, nombre="ent_dic_periodo.csv"):
    """Tasa por 1.000 textos (posts + comentarios) de cada actor antes y después."""
    t = tot[tot.subreddit.isin(subs)].groupby("periodo").textos.sum()
    d = (dic[dic.subreddit.isin(subs)]
         .groupby(["actor", "categoria", "periodo"]).textos_con_actor.sum()
         .unstack("periodo", fill_value=0).reset_index())
    for per in ("antes", "despues"):
        if per not in d:
            d[per] = 0
    d = d.rename(columns={"antes": "textos_antes", "despues": "textos_despues"})
    d["tasa_antes"] = 1000 * d.textos_antes / t["antes"]
    d["tasa_despues"] = 1000 * d.textos_despues / t["despues"]
    d["razon"] = d.tasa_despues / d.tasa_antes.where(d.tasa_antes > 0)
    d["log2_cambio"] = [log2_razon(a, t["antes"], b, t["despues"])
                        for a, b in zip(d.textos_antes, d.textos_despues)]
    d = d.sort_values(["categoria", "tasa_despues"], ascending=[True, False])
    d.to_csv(os.path.join(TABLAS, nombre), index=False, float_format="%.3f")
    print(f"Textos {', '.join(subs)}: antes {t['antes']:,}, después {t['despues']:,}")
    return d, t


def tabla_ia_trimestral(tot, ia):
    """Tasa por 1.000 textos (posts + comentarios) que mencionan IA, por trimestre y sub."""
    t = tot.groupby(["subreddit", "trimestre"]).textos.sum().rename("textos")
    filas = []
    for clase in ("cualquiera", "herramienta"):
        c = ia[ia.clase == clase].groupby(["subreddit", "trimestre"]).textos.sum()
        filas.append(c.rename(f"textos_ia_{clase}"))
    tabla = pd.concat([t] + filas, axis=1).fillna(0).reset_index()
    for clase in ("cualquiera", "herramienta"):
        tabla[f"tasa_ia_{clase}"] = 1000 * tabla[f"textos_ia_{clase}"] / tabla.textos
    tabla = tabla[tabla.trimestre <= ULTIMO_TRIMESTRE].sort_values(["subreddit", "trimestre"])
    tabla.to_csv(os.path.join(TABLAS, "ent_ia_trimestral.csv"), index=False, float_format="%.2f")
    return tabla


def tabla_participacion(tot, dic):
    """Tasa por 1.000 textos de cada herramienta de IA por trimestre (tres subs juntos)
    y su participación sobre el total de menciones de herramientas."""
    t = tot.groupby("trimestre").textos.sum()
    h = (dic[dic.categoria == "ia_herramienta"]
         .groupby(["trimestre", "actor"]).textos_con_actor.sum()
         .unstack("actor", fill_value=0))
    h = h.reindex(t.index, fill_value=0)
    h = h[h.index <= ULTIMO_TRIMESTRE]
    tasa = h.div(t[h.index], axis=0) * 1000
    part = h.div(h.sum(axis=1).where(h.sum(axis=1) > 0), axis=0) * 100
    salida = pd.concat({"textos": h, "tasa": tasa, "participacion": part}, axis=1)
    salida.columns = [f"{a}_{b}" for a, b in salida.columns]
    salida.insert(0, "textos_trimestre", t[h.index])
    salida.reset_index().to_csv(os.path.join(TABLAS, "ent_ia_participacion.csv"),
                                index=False, float_format="%.3f")
    return tasa, part, h


def guardar_trimestral(tot, dic):
    d = dic.merge(tot, on=["subreddit", "tipo", "trimestre", "periodo"])
    d["tasa_1000"] = 1000 * d.textos_con_actor / d.textos
    d = d.sort_values(["categoria", "actor", "subreddit", "tipo", "trimestre"])
    d.to_csv(os.path.join(TABLAS, "ent_dic_trimestral.csv"), index=False, float_format="%.3f")


# --------------------------------------------------------------------------
# Figuras
# --------------------------------------------------------------------------
def fig_ia_por_sub(tabla):
    fig, ax = nueva_figura(
        "Cuántos textos mencionan la IA",
        "Posts y comentarios que nombran IA, LLM o una herramienta (ChatGPT, Copilot, etc.), "
        "por cada 1.000 textos del trimestre")
    for sub in SUBS:
        s = tabla[(tabla.subreddit == sub) & (tabla.textos >= MIN_TEXTOS_TRIMESTRE)]
        x = trimestre_a_fecha(s.trimestre)
        ax.plot(x, s.tasa_ia_cualquiera, color=COLOR_SUB[sub], label=ETIQUETA_SUB[sub])
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylabel("textos por cada 1.000")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.92))
    return guardar(fig, "ent_ia_por_subreddit.png")


def fig_herramientas(tasa):
    orden = ["ChatGPT/OpenAI", "Copilot", "Claude", "Cursor", "Gemini/Bard", "DeepSeek"]
    colores = dict(zip(orden, SERIES[:6]))
    fig, ax = nueva_figura(
        "Qué herramientas de IA se nombran",
        "Textos que mencionan cada herramienta por cada 1.000 textos del trimestre "
        "(tres subreddits juntos)")
    x = trimestre_a_fecha(tasa.index)
    for actor in orden:
        if actor in tasa:
            ax.plot(x, tasa[actor], color=colores[actor], label=actor)
    marcar_corte(ax)
    eje_fechas(ax)
    ax.set_ylabel("textos por cada 1.000")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.92), ncol=2)
    return guardar(fig, "ent_ia_herramientas.png")


def fig_cambios_dic(d):
    """Barras horizontales: log2 del cambio de tasa, empresas y plataformas."""
    base = d[d.categoria.isin(["empresa", "plataforma", "tecnologia"])
             & (d.textos_antes >= MIN_TEXTOS_ANTES)].copy()
    base = base.sort_values("log2_cambio")
    sel = pd.concat([base.head(10), base.tail(10)]).drop_duplicates("actor")
    fig, ax = nueva_figura(
        "Empresas, plataformas y tecnologías: qué sube y qué baja",
        "Tasa de mención después del corte / antes, r/devsarg, posts y comentarios. "
        "Al lado de cada barra, textos por cada 1.000 (antes → después)",
        alto=7)
    y = range(len(sel))
    ax.barh(y, sel.log2_cambio, color=TINTA_TENUE, height=0.65)
    ax.set_yticks(list(y))
    ax.set_yticklabels(sel.actor)
    ax.axvline(0, color=TINTA_TENUE, linewidth=1)
    ticks = [-3, -2, -1, 0, 1, 2, 3]
    ax.set_xticks(ticks)
    ax.set_xticklabels(["÷8", "÷4", "÷2", "igual", "×2", "×4", "×8"])
    ax.grid(axis="x", color="#e1e0d9")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("tasa después / tasa antes (escala logarítmica)")
    for yi, (v, a, b) in enumerate(zip(sel.log2_cambio, sel.tasa_antes, sel.tasa_despues)):
        texto = f"{a:.1f} → {b:.1f}"
        ax.annotate(texto, xy=(v, yi), xytext=(5 if v > 0 else -5, 0), textcoords="offset points",
                    ha="left" if v > 0 else "right", va="center", fontsize=9, color=TINTA_2)
    lim = max(abs(sel.log2_cambio).max() + 1.2, 3.2)
    ax.set_xlim(-lim, lim)
    return guardar(fig, "ent_cambios_actores.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reusar-ner", action="store_true",
                        help="no correr spaCy si ya existe data/processed/ent_ner_posts.jsonl")
    args = parser.parse_args()
    os.makedirs(TABLAS, exist_ok=True)
    t0 = time.time()

    if not (args.reusar_ner and os.path.exists(CACHE_NER)):
        correr_ner()
    analizar_ner()
    muestra_ner()
    cobertura_ner()

    tot, dic, ia = contar_diccionario()
    guardar_trimestral(tot, dic)
    tabla_dic_periodo(tot, dic)
    d_devsarg, _ = tabla_dic_periodo(tot, dic, subs=("devsarg",), nombre="ent_dic_periodo_devsarg.csv")
    tabla_ia = tabla_ia_trimestral(tot, ia)
    tasa, _, _ = tabla_participacion(tot, dic)

    for ruta in (fig_ia_por_sub(tabla_ia), fig_herramientas(tasa), fig_cambios_dic(d_devsarg)):
        print(f"Figura: {ruta}")
    print(f"Total: {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
