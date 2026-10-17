"""Descarga posts o comentarios completos de uno o más subreddits (Arctic Shift).

Uso:
    python scripts/descargar_reddit.py devsarg empleos_AR taquerosprogramadores
    python scripts/descargar_reddit.py devsarg --comentarios

Salida: data/raw/reddit/<sub>_posts.jsonl o <sub>_comments.jsonl, un objeto
por línea tal como lo devuelve la API. Los posts se guardan con todos sus
campos. Los comentarios, con un subconjunto (COMMENT_FIELDS), porque son
~900k solo en r/devsarg y el resto de los campos no se usa.

Cada corrida agrega una línea a data/raw/reddit/descargas.jsonl con el
resumen (totales, requests, duración), que se pasa a docs/02_scraping.md.
"""

import json
import os
import sys
from datetime import datetime, timezone

from arctic_shift import ApiError, download

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "reddit")
COMMENT_FIELDS = ("id,created_utc,author,author_flair_text,body,link_id,parent_id,"
                  "score,subreddit,retrieved_on")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    comments = "--comentarios" in sys.argv
    if not args:
        sys.exit(__doc__)
    kind = "comments" if comments else "posts"
    failed = False
    for sub in args:
        out = os.path.join(RAW, f"{sub}_{kind}.jsonl")
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            summary = download(kind, sub, out, fields=COMMENT_FIELDS if comments else None)
            summary["estado"] = "completa"
        except ApiError as e:
            print(f"\nABORTO r/{sub}: {e}\nEl JSONL parcial queda guardado; volver a correr reanuda.")
            summary = {"subreddit": sub, "kind": kind, "estado": "abortada", "error": str(e)}
            failed = True
        summary["inicio"] = started
        with open(os.path.join(RAW, "descargas.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
