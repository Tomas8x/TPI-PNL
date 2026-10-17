"""Chequeo de viabilidad de un subreddit (Arctic Shift).

Uso: python scripts/viabilidad_reddit.py [--sub NOMBRE] [--sin-descarga]

Descarga todos los posts del sub a data/raw/reddit/<sub>_posts.jsonl (reanuda
si el archivo ya existe) y reporta volumen por trimestre, subconjunto junior, causas y
comentarios promedio. No hace preprocesamiento ni NLP.
"""

import os
import re
import sys
import unicodedata

import pandas as pd

from arctic_shift import ApiError, api_get, download, fmt

SUBREDDIT = sys.argv[sys.argv.index("--sub") + 1] if "--sub" in sys.argv else "devsarg"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSONL = os.path.join(ROOT, "data", "raw", "reddit", f"{SUBREDDIT}_posts.jsonl")
OUT_PNG = os.path.join(ROOT, "reports", "figures", f"{SUBREDDIT}_junior_por_trimestre.png")
CUTOFF = pd.Timestamp("2022-11-30", tz="UTC")

JUNIOR = ["junior", "trainee", "primer trabajo", "primer laburo", "sin experiencia"]
CAUSES = {
    "ia": ["ia", "ai", "chatgpt", "gpt", "copilot", "cursor", "claude", "llm"],
    "layoffs": ["despidos", "layoff", "recorte"],
    "macro": ["dolar", "devaluacion", "inflacion", "crisis", "recesion", "cepo"],
    "sobreoferta": ["bootcamp", "curso", "saturado", "sobreoferta", "competencia"],
}


def first_post():
    data = api_get("/posts/search", {"subreddit": SUBREDDIT, "sort": "asc", "limit": 1,
                                     "fields": "id,created_utc,title"})
    if not data:
        raise ApiError("sort=asc limit=1 devolvió vacío: el sub no tiene posts o el nombre está mal")
    return data[0]


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
            download("posts", SUBREDDIT, OUT_JSONL)
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
    print("\n2-4. Posts por trimestre (causas = dentro del subconjunto junior)")
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
