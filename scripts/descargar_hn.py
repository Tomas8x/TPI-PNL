"""Descarga los avisos de los hilos mensuales "Ask HN: Who is hiring?" de Hacker News.

Uso: python scripts/descargar_hn.py

Fuente: API de Algolia (https://hn.algolia.com/api). Los hilos los publica la
cuenta `whoishiring` y cada aviso es un comentario de primer nivel del hilo.

Salida: data/raw/hn/whoishiring.jsonl, un aviso por línea con los campos que
devuelve la API (sin las respuestas anidadas), más el id, título y fecha del
hilo. El texto viene en HTML. Reanuda salteando los hilos ya descargados.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://hn.algolia.com/api/v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "hn")
OUT = os.path.join(RAW, "whoishiring.jsonl")
SLEEP_S = 1.0
TIMEOUT_S = 60


def get(path, params=None):
    r = requests.get(f"{API}{path}", params=params, timeout=TIMEOUT_S)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} en {path}: {r.text[:300]}")
    return r.json()


def list_threads():
    data = get("/search_by_date", {"tags": "story,author_whoishiring", "hitsPerPage": 1000})
    if data["nbHits"] > len(data["hits"]):
        raise RuntimeError(f"La API informa {data['nbHits']} hilos y devolvió {len(data['hits'])}: "
                           "hace falta paginar.")
    threads = [h for h in data["hits"] if h["title"].lower().startswith("ask hn: who is hiring?")]
    return sorted(threads, key=lambda h: h["created_at_i"])


def done_threads():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                done.add(json.loads(line)["thread_id"])
    return done


def main():
    os.makedirs(RAW, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    threads = list_threads()
    done = done_threads()
    print(f"{len(threads)} hilos 'Who is hiring?', {len(done)} ya descargados")
    n_posts = 0
    with open(OUT, "a", encoding="utf-8") as f:
        for i, t in enumerate(threads, 1):
            if t["objectID"] in done:
                continue
            item = get(f"/items/{t['objectID']}")
            for c in item.get("children", []):
                c = {k: v for k, v in c.items() if k != "children"}
                c.update(thread_id=t["objectID"], thread_title=t["title"], thread_created_at=t["created_at"])
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                n_posts += 1
            f.flush()
            if i % 20 == 0:
                print(f"  {i}/{len(threads)} hilos, {n_posts} avisos nuevos, voy por {t['title']}")
            time.sleep(SLEEP_S)
    summary = {"fuente": "hn_whoishiring", "hilos": len(threads), "avisos_nuevos": n_posts,
               "primer_hilo": threads[0]["title"], "ultimo_hilo": threads[-1]["title"],
               "inicio": started, "archivo": os.path.relpath(OUT)}
    with open(os.path.join(RAW, "descargas.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(f"Descarga terminada: {summary}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, requests.RequestException) as e:
        sys.exit(f"ABORTO: {e}\nLo descargado queda guardado; volver a correr reanuda.")
