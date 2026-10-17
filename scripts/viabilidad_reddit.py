"""Chequeo de viabilidad de un subreddit (Arctic Shift).

Uso: python scripts/viabilidad_reddit.py [--sub NOMBRE] [--sin-descarga]

Descarga todos los posts del sub a <sub>_posts.jsonl (reanuda si el archivo
ya existe) y reporta volumen por trimestre, subconjunto junior, causas y
comentarios promedio. No hace preprocesamiento ni NLP.
"""

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://arctic-shift.photon-reddit.com/api"
SUBREDDIT = sys.argv[sys.argv.index("--sub") + 1] if "--sub" in sys.argv else "devsarg"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSONL = os.path.join(ROOT, "data", "raw", "reddit", f"{SUBREDDIT}_posts.jsonl")
OUT_PNG = os.path.join(ROOT, "reports", "figures", f"{SUBREDDIT}_junior_por_trimestre.png")
SLEEP_S = 2.0
TIMEOUT_BACKOFF_S = (30, 60)  # esperas ante "Timeout. Maybe slow down a bit"
TIMEOUT_S = 60
CUTOFF = pd.Timestamp("2022-11-30", tz="UTC")

JUNIOR = ["junior", "trainee", "primer trabajo", "primer laburo", "sin experiencia"]
CAUSES = {
    "ia": ["ia", "ai", "chatgpt", "gpt", "copilot", "cursor", "claude", "llm"],
    "layoffs": ["despidos", "layoff", "recorte"],
    "macro": ["dolar", "devaluacion", "inflacion", "crisis", "recesion", "cepo"],
    "sobreoferta": ["bootcamp", "curso", "saturado", "sobreoferta", "competencia"],
}


class ApiError(RuntimeError):
    pass


def api_get(path, params):
    """GET con reintentos acotados solo para fallas transitorias conocidas.

    429: espera lo que indica x-ratelimit-reset, una vez.
    422 "Timeout. Maybe slow down a bit": timeout por carga del server, hasta
    len(TIMEOUT_BACKOFF_S) reintentos. Cualquier otro error aborta.
    """
    timeouts = 0
    for attempt in (1, 2, 3, 4):
        try:
            r = requests.get(f"{BASE}{path}", params=params, timeout=TIMEOUT_S)
        except requests.RequestException as e:
            raise ApiError(f"Error de red en {path} {params}: {e}") from e
        if r.status_code == 429 and attempt == 1:
            wait = int(r.headers.get("x-ratelimit-reset", "60")) + 1
            print(f"  429 rate limit, espero {wait}s (x-ratelimit-reset) y reintento una vez")
            time.sleep(wait)
            continue
        if "Maybe slow down" in r.text and timeouts < len(TIMEOUT_BACKOFF_S):
            wait = TIMEOUT_BACKOFF_S[timeouts]
            timeouts += 1
            print(f"  timeout del servidor ({r.status_code}) en after={params.get('after')}, "
                  f"espero {wait}s, reintento {timeouts}/{len(TIMEOUT_BACKOFF_S)}")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise ApiError(f"HTTP {r.status_code} en {path} {params}: {r.text[:300]}")
        body = r.json()
        if body.get("error"):
            raise ApiError(f"La API devolvió error en {path} {params}: {body['error']}")
        if body.get("data") is None:
            raise ApiError(f"Respuesta sin 'data' en {path} {params}: {str(body)[:300]}")
        return body["data"]
    raise ApiError(f"Fallas persistentes (429/timeout) en {path} {params}")


def first_post():
    data = api_get("/posts/search", {"subreddit": SUBREDDIT, "sort": "asc", "limit": 1,
                                     "fields": "id,created_utc,title"})
    if not data:
        raise ApiError("sort=asc limit=1 devolvió vacío: el sub no tiene posts o el nombre está mal")
    return data[0]


def load_existing():
    seen, last_ts = set(), None
    if os.path.exists(OUT_JSONL):
        with open(OUT_JSONL, encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                seen.add(p["id"])
                last_ts = p["created_utc"] if last_ts is None else max(last_ts, p["created_utc"])
    return seen, last_ts


def download(start_ts):
    seen, last_ts = load_existing()
    if last_ts is not None:
        print(f"Reanudando: {len(seen)} posts ya guardados, último {fmt(last_ts)}")
        after = last_ts
    else:
        after = start_ts - 1
    n_req = 0
    with open(OUT_JSONL, "a", encoding="utf-8") as f:
        while True:
            data = api_get("/posts/search", {"subreddit": SUBREDDIT, "sort": "asc",
                                             "limit": 100, "after": after})
            n_req += 1
            new = [p for p in data if p["id"] not in seen]
            for p in new:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
                seen.add(p["id"])
            if data:
                page_last = max(p["created_utc"] for p in data)
                if n_req % 20 == 0:
                    print(f"  {n_req} requests, {len(seen)} posts, voy por {fmt(page_last)}")
                if not new and page_last <= after:
                    raise ApiError(f"La paginación no avanza (after={after}). Corto para no loopear.")
                # after es estricto: si en el borde quedaron posts con el mismo segundo,
                # retrocedo 1s y el dedupe por id evita duplicados.
                after = page_last - 1 if new else page_last
            else:
                age_h = (time.time() - after) / 3600
                if age_h > 72:
                    raise ApiError(f"Página vacía inesperada: último post visto {fmt(after)} "
                                   f"({age_h:.0f} h atrás). Puede faltar data.")
                break
            time.sleep(SLEEP_S)
    print(f"Descarga terminada: {len(seen)} posts en {OUT_JSONL} ({n_req} requests)")


def fmt(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def kw_regex(words):
    # límite de palabra + plural opcional; "primer trabajo" tolera espacios múltiples
    alts = "|".join(r"\s+".join(map(re.escape, w.split())) for w in words)
    return re.compile(rf"\b(?:{alts})(?:s|es)?\b")


def main():
    fp = first_post()
    print(f"1. Primer post de r/{SUBREDDIT}: {fmt(fp['created_utc'])}  id={fp['id']}  \"{fp['title']}\"")

    if "--sin-descarga" in sys.argv:
        print("--sin-descarga: analizo solo lo que ya está en el JSONL (puede ser parcial)")
    else:
        try:
            download(fp["created_utc"])
        except ApiError as e:
            print(f"\nABORTO DESCARGA: {e}\nEl JSONL parcial queda guardado; volver a correr reanuda.")
            sys.exit(1)

    df = pd.read_json(OUT_JSONL, lines=True)
    df = df.drop_duplicates("id")
    df["date"] = pd.to_datetime(df["created_utc"], unit="s", utc=True)
    df["quarter"] = df["date"].dt.tz_localize(None).dt.to_period("Q")
    df["post_cutoff"] = df["date"] >= CUTOFF
    text = (df["title"].fillna("") + "\n" + df["selftext"].fillna("")).map(norm)

    df["junior"] = text.str.contains(kw_regex(JUNIOR))
    for name, words in CAUSES.items():
        df[name] = df["junior"] & text.str.contains(kw_regex(words))

    cols = ["junior", *CAUSES]
    q = df.groupby("quarter").agg(posts=("id", "size"), **{c: (c, "sum") for c in cols})
    q["%junior"] = (100 * q["junior"] / q["posts"]).round(1)

    pd.set_option("display.width", 200)
    print(f"\n2-4. Posts por trimestre (causas = dentro del subconjunto junior)")
    print(f"     Último trimestre ({q.index[-1]}) incompleto: datos hasta {df['date'].max():%Y-%m-%d}.")
    print(q.to_string())

    lbl = df["post_cutoff"].map({False: "antes 2022-11-30", True: "desde 2022-11-30"})
    tot = df.groupby(lbl).agg(posts=("id", "size"), **{c: (c, "sum") for c in cols})
    tot["%junior"] = (100 * tot["junior"] / tot["posts"]).round(1)
    tot["meses"] = df.groupby(lbl)["date"].agg(lambda d: round((d.max() - d.min()).days / 30.44, 1))
    tot["junior/mes"] = (tot["junior"] / tot["meses"]).round(1)
    tot.loc["TOTAL"] = [*df[["id"]].count(), *df[cols].sum(),
                        round(100 * df["junior"].mean(), 1), None, None]
    print("\nTotales antes / después del corte")
    print(tot.to_string())

    j = df[df["junior"]]
    age_days = (j["retrieved_on"] - j["created_utc"]) / 86400
    fresh = age_days < 2
    print("\n5. Comentarios por post (subconjunto junior)")
    print(f"   n={len(j)}  promedio={j['num_comments'].mean():.1f}  mediana={j['num_comments'].median():.0f}"
          f"  total≈{j['num_comments'].sum():,}")
    print(f"   Antes del corte: promedio={j.loc[~j['post_cutoff'], 'num_comments'].mean():.1f}  "
          f"Después: {j.loc[j['post_cutoff'], 'num_comments'].mean():.1f}")
    print(f"   Ojo: {fresh.sum()} posts junior ({100 * fresh.mean():.0f}%) se capturaron <2 días después de"
          f" publicados; su num_comments puede estar subestimado."
          f" Promedio excluyéndolos: {j.loc[~fresh, 'num_comments'].mean():.1f}")

    plot(q)


def plot(q):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = q.index.to_timestamp()
    fig, ax = plt.subplots(figsize=(11, 4.5), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.bar(x, q["junior"], width=70, color="#2a78d6", align="edge")
    ax.axvline(CUTOFF.tz_localize(None), color="#0b0b0b", lw=1.5, ls="--")
    ax.text(CUTOFF.tz_localize(None), ax.get_ylim()[1] * 0.95, "  ChatGPT (2022-11-30)",
            color="#0b0b0b", va="top", fontsize=9)
    ax.set_title(f"r/{SUBREDDIT}: posts que mencionan junior / trainee / primer trabajo, por trimestre",
                 loc="left", color="#0b0b0b", fontsize=11)
    ax.set_ylabel("posts", color="#52514e")
    ax.tick_params(colors="#52514e")
    ax.grid(axis="y", color="#e5e4e0", lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"\nGráfico guardado en {OUT_PNG}")


if __name__ == "__main__":
    main()
