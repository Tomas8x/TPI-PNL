"""Arma los corpus finales a partir de data/raw/ (ver docs/03_consolidacion.md).

Uso:
    python scripts/consolidar.py

Salida en data/processed/:
- posteos.jsonl: posts y comentarios de Reddit, un registro por texto.
- avisos_hn.jsonl: avisos de Hacker News "Who is hiring?" en texto plano.
- indeed_software_mensual.csv: índice de avisos de software (EE.UU.), promedio mensual.
- sipa_informatica_trimestral.csv: empleo registrado en informática (rama 72) y total.
- consolidacion.json: cuántos registros quedan después de cada filtro.

Lee los JSONL línea por línea para no cargar ~1,9 millones de textos en memoria.
"""

import hashlib
import html
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "processed")

SUBS = ("devsarg", "empleos_AR", "taquerosprogramadores")
DESDE = datetime(2021, 1, 1, tzinfo=timezone.utc)
HASTA = datetime(2026, 10, 1, tzinfo=timezone.utc)  # 2026-T4 está incompleto
CORTE = datetime(2022, 11, 30, tzinfo=timezone.utc)
BORRADOS = {"[removed]", "[deleted]", "[flagged]", ""}


def es_bot(autor):
    return autor == "AutoModerator" or (autor or "").endswith("-ModTeam")


def fecha(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def campos_tiempo(dt):
    return {
        "fecha": dt.strftime("%Y-%m-%d"),
        "trimestre": f"{dt.year}Q{(dt.month - 1) // 3 + 1}",
        "periodo": "antes" if dt < CORTE else "despues",
    }


def leer(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def consolidar_reddit(salida):
    conteo = defaultdict(Counter)
    # (subreddit, tipo, autor, hash del texto): un texto repetido solo se descarta
    # dentro del mismo sub y tipo, para no sacarle a un sub lo que se cruzó desde otro.
    vistos = set()

    def repetido(sub, tipo, autor, texto):
        if autor == "[deleted]":
            return False
        clave = (sub, tipo, autor, hashlib.md5(texto.encode("utf-8")).digest())
        if clave in vistos:
            return True
        vistos.add(clave)
        return False

    with open(salida, "w", encoding="utf-8") as out:
        for sub in SUBS:
            flairs = {}
            c = conteo[f"{sub}_posts"]
            for d in leer(os.path.join(RAW, "reddit", f"{sub}_posts.jsonl")):
                c["crudos"] += 1
                dt = fecha(d["created_utc"])
                if not DESDE <= dt < HASTA:
                    c["fuera de rango"] += 1
                    continue
                flairs[d["id"]] = d.get("link_flair_text")
                if es_bot(d.get("author")):
                    c["bot"] += 1
                    continue
                titulo = (d.get("title") or "").strip()
                cuerpo = (d.get("selftext") or "").strip()
                if cuerpo in BORRADOS:
                    cuerpo = ""
                texto = f"{titulo}\n\n{cuerpo}" if cuerpo else titulo
                if repetido(sub, "post", d.get("author"), texto):
                    c["repetido"] += 1
                    continue
                removido = bool(d.get("removed_by_category"))
                c["removido (queda el título)"] += removido
                c["finales"] += 1
                out.write(json.dumps({
                    "id": d["id"], "tipo": "post", "subreddit": sub,
                    "created_utc": int(d["created_utc"]), **campos_tiempo(dt),
                    "autor": d.get("author"), "flair": d.get("link_flair_text"),
                    "post_id": d["id"], "titulo": titulo, "texto": texto,
                    "score": d.get("score"), "num_comments": d.get("num_comments"),
                    "removido": removido,
                }, ensure_ascii=False) + "\n")

            c = conteo[f"{sub}_comentarios"]
            for d in leer(os.path.join(RAW, "reddit", f"{sub}_comments.jsonl")):
                c["crudos"] += 1
                dt = fecha(d["created_utc"])
                if not DESDE <= dt < HASTA:
                    c["fuera de rango"] += 1
                    continue
                if es_bot(d.get("author")):
                    c["bot"] += 1
                    continue
                texto = (d.get("body") or "").strip()
                if texto in BORRADOS:
                    c["borrado"] += 1
                    continue
                if repetido(sub, "comentario", d.get("author"), texto):
                    c["repetido"] += 1
                    continue
                post_id = (d.get("link_id") or "").removeprefix("t3_")
                c["finales"] += 1
                out.write(json.dumps({
                    "id": d["id"], "tipo": "comentario", "subreddit": sub,
                    "created_utc": int(d["created_utc"]), **campos_tiempo(dt),
                    "autor": d.get("author"), "flair": flairs.get(post_id),
                    "post_id": post_id, "titulo": None, "texto": texto,
                    "score": d.get("score"), "num_comments": None, "removido": False,
                }, ensure_ascii=False) + "\n")
    return conteo


def html_a_texto(s):
    s = re.sub(r"<p>|<br\s*/?>", "\n", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def consolidar_hn(salida):
    c = Counter()
    avisos = list(leer(os.path.join(RAW, "hn", "whoishiring.jsonl")))
    # El mes de un aviso es el de su hilo, que se publica el día 1.
    inicio_hilo = {}
    for d in avisos:
        sid = d["story_id"]
        inicio_hilo[sid] = min(inicio_hilo.get(sid, d["created_at_i"]), d["created_at_i"])
    with open(salida, "w", encoding="utf-8") as out:
        for d in avisos:
            c["crudos"] += 1
            texto = html_a_texto(d.get("text"))
            if not texto or texto in BORRADOS:
                c["vacío o borrado"] += 1
                continue
            dt = fecha(inicio_hilo[d["story_id"]])
            c["finales"] += 1
            out.write(json.dumps({
                "id": d["id"], "hilo_id": d["story_id"], "mes": dt.strftime("%Y-%m"),
                "periodo": "antes" if dt < CORTE else "despues",
                "autor": d.get("author"), "texto": texto,
            }, ensure_ascii=False) + "\n")
    return c


def consolidar_indeed(salida):
    df = pd.read_csv(os.path.join(RAW, "series", "indeed_job_postings_by_sector_US.csv"),
                     parse_dates=["date"])
    df = df[df.display_name == "Software Development"]
    serie = (df.pivot_table(index=df.date.dt.to_period("M"), columns="variable",
                            values="indeed_job_postings_index", aggfunc="mean")
             .round(2))
    serie.index = serie.index.astype(str)
    serie.index.name = "mes"
    serie.to_csv(salida)
    return len(serie)


def consolidar_sipa(salida):
    df = pd.read_excel(os.path.join(RAW, "series", "sipa_empleo_trimestral_por_rama.xlsx"),
                       sheet_name="C4", header=None)
    cabecera = df.iloc[2, 2:]
    informatica = df[df[0].astype(str).str.strip() == "72"].iloc[0, 2:]
    total = df[df[0].astype(str).str.strip() == "Total general"].iloc[0, 2:]
    filas = []
    for col, nombre in cabecera.items():
        if pd.isna(nombre):
            break  # después de los trimestres vienen columnas de variación
        m = re.match(r"(\d)\D+(\d{4})", str(nombre))
        filas.append({"trimestre": f"{m.group(2)}Q{m.group(1)}",
                      "informatica": int(informatica[col]), "total": int(total[col])})
    serie = pd.DataFrame(filas)
    serie["prop_informatica"] = (serie.informatica / serie.total).round(5)
    serie.to_csv(salida, index=False)
    return len(serie)


def main():
    os.makedirs(OUT, exist_ok=True)
    resumen = {k: dict(v) for k, v in consolidar_reddit(os.path.join(OUT, "posteos.jsonl")).items()}
    resumen["hn_avisos"] = dict(consolidar_hn(os.path.join(OUT, "avisos_hn.jsonl")))
    resumen["indeed_meses"] = consolidar_indeed(os.path.join(OUT, "indeed_software_mensual.csv"))
    resumen["sipa_trimestres"] = consolidar_sipa(os.path.join(OUT, "sipa_informatica_trimestral.csv"))
    with open(os.path.join(OUT, "consolidacion.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
