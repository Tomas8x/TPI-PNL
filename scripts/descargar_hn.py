"""Descarga los hilos mensuales de empleo de Hacker News.

Uso:
    python scripts/descargar_hn.py                  # "Ask HN: Who is hiring?" (avisos)
    python scripts/descargar_hn.py --tipo hired     # "Ask HN: Who wants to be hired?" (candidatos)

Fuente: API de Algolia (https://hn.algolia.com/api). Los hilos los publica la
cuenta `whoishiring` y cada aviso o candidato es un comentario de primer nivel.

Salida: data/raw/hn/whoishiring.jsonl o whowantstobehired.jsonl, un comentario
por línea con los campos que devuelve la API (sin las respuestas anidadas),
más el id, título y fecha del hilo. El texto viene en HTML. Al reanudar
saltea los hilos ya descargados y rehace el último, por si quedó a medias.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

from arctic_shift import repair_tail

API = "https://hn.algolia.com/api/v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "hn")
TIPOS = {"hiring": ("ask hn: who is hiring?", "whoishiring.jsonl"),
         "hired": ("ask hn: who wants to be hired?", "whowantstobehired.jsonl")}
SLEEP_S = 1.0
TIMEOUT_S = 60


def get(path, params=None):
    r = requests.get(f"{API}{path}", params=params, timeout=TIMEOUT_S)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} en {path}: {r.text[:300]}")
    return r.json()


def list_threads(prefix):
    data = get("/search_by_date", {"tags": "story,author_whoishiring", "hitsPerPage": 1000})
    if data["nbHits"] > len(data["hits"]):
        raise RuntimeError(f"La API informa {data['nbHits']} hilos y devolvió {len(data['hits'])}: "
                           "hace falta paginar.")
    threads = [h for h in data["hits"] if h["title"].lower().startswith(prefix)]
    return sorted(threads, key=lambda h: h["created_at_i"])


def load_existing(out):
    """Hilos e ids ya guardados. El último hilo se rehace: puede haber quedado a medias."""
    repair_tail(out)
    done, ids, last = set(), set(), None
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                done.add(c["thread_id"])
                ids.add(c["id"])
                last = c["thread_id"]
    done.discard(last)
    return done, ids


def main():
    os.makedirs(RAW, exist_ok=True)
    tipo = sys.argv[sys.argv.index("--tipo") + 1] if "--tipo" in sys.argv else "hiring"
    prefix, filename = TIPOS[tipo]
    out = os.path.join(RAW, filename)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    threads = list_threads(prefix)
    done, ids = load_existing(out)
    print(f"{len(threads)} hilos '{prefix}', {len(done)} ya descargados")
    n_posts = 0
    with open(out, "a", encoding="utf-8") as f:
        for i, t in enumerate(threads, 1):
            if t["objectID"] in done:
                continue
            item = get(f"/items/{t['objectID']}")
            for c in item.get("children", []):
                if c["id"] in ids:
                    continue
                c = {k: v for k, v in c.items() if k != "children"}
                c.update(thread_id=t["objectID"], thread_title=t["title"], thread_created_at=t["created_at"])
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                n_posts += 1
            f.flush()
            if i % 20 == 0:
                print(f"  {i}/{len(threads)} hilos, {n_posts} comentarios nuevos, voy por {t['title']}")
            time.sleep(SLEEP_S)
    summary = {"fuente": f"hn_{tipo}", "hilos": len(threads), "comentarios_nuevos": n_posts,
               "primer_hilo": threads[0]["title"], "ultimo_hilo": threads[-1]["title"],
               "inicio": started, "archivo": os.path.relpath(out)}
    with open(os.path.join(RAW, "descargas.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(f"Descarga terminada: {summary}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, requests.RequestException) as e:
        sys.exit(f"ABORTO: {e}\nLo descargado queda guardado; volver a correr reanuda.")
