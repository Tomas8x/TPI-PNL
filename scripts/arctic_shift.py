"""Cliente mínimo de la API de Arctic Shift con paginación reanudable.

Lo usan descargar_reddit.py y viabilidad_reddit.py.
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

BASE = "https://arctic-shift.photon-reddit.com/api"
SLEEP_S = 2.0
TIMEOUT_BACKOFF_S = (30, 60)  # esperas ante "Timeout. Maybe slow down a bit"
TIMEOUT_S = 60


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


def fmt(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def edge_item(kind, subreddit, sort):
    """Primer (sort="asc") o último (sort="desc") post o comentario del sub."""
    data = api_get(f"/{kind}/search", {"subreddit": subreddit, "sort": sort, "limit": 1,
                                       "fields": "id,created_utc"})
    if not data:
        raise ApiError(f"/{kind}/search sort={sort} limit=1 devolvió vacío para r/{subreddit}: "
                       "el sub no tiene datos o el nombre está mal")
    return data[0]


def load_existing(path):
    seen, last_ts = set(), None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                seen.add(p["id"])
                last_ts = p["created_utc"] if last_ts is None else max(last_ts, p["created_utc"])
    return seen, last_ts


def download(kind, subreddit, out_path, fields=None):
    """Baja todos los posts o comentarios del sub, en orden cronológico, a un JSONL.

    Reanuda desde el último created_utc guardado. Devuelve un resumen con los
    totales para documentar la descarga.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    seen, last_ts = load_existing(out_path)
    n_before = len(seen)
    if last_ts is not None:
        print(f"Reanudando r/{subreddit} {kind}: {len(seen)} ya guardados, último {fmt(last_ts)}")
        after = last_ts
    else:
        after = edge_item(kind, subreddit, "asc")["created_utc"] - 1
    # Fin esperado de la descarga: el registro más reciente al momento de arrancar.
    newest_ts = edge_item(kind, subreddit, "desc")["created_utc"]
    params = {"subreddit": subreddit, "sort": "asc", "limit": 100}
    if fields:
        params["fields"] = fields
    n_req, t0 = 0, time.time()
    with open(out_path, "a", encoding="utf-8") as f:
        while True:
            data = api_get(f"/{kind}/search", {**params, "after": after})
            n_req += 1
            new = [p for p in data if p["id"] not in seen]
            for p in new:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
                seen.add(p["id"])
            if data:
                page_last = max(p["created_utc"] for p in data)
                if n_req % 20 == 0:
                    f.flush()
                    print(f"  {n_req} requests, {len(seen)} {kind}, voy por {fmt(page_last)}")
                if not new and page_last <= after:
                    raise ApiError(f"La paginación no avanza (after={after}). Corto para no loopear.")
                # after es estricto: si en el borde quedaron registros con el mismo segundo,
                # retrocedo 1s y el dedupe por id evita duplicados.
                after = page_last - 1 if new else page_last
            else:
                if after + 1 < newest_ts:
                    raise ApiError(f"Página vacía inesperada en {fmt(after)}, pero la API informa "
                                   f"registros hasta {fmt(newest_ts)}. Puede faltar data.")
                break
            time.sleep(SLEEP_S)
    summary = {"subreddit": subreddit, "kind": kind, "total": len(seen), "nuevos": len(seen) - n_before,
               "requests": n_req, "minutos": round((time.time() - t0) / 60, 1),
               "hasta": fmt(after), "archivo": os.path.relpath(out_path)}
    print(f"Descarga terminada: {summary}")
    return summary
