"""Descarga archivos sueltos (sin paginar): series de empleo y avisos, y Djinni.

Uso:
    python scripts/descargar_series.py           # todos
    python scripts/descargar_series.py djinni    # solo los que contienen "djinni"

- OEDE / SIPA (Secretaría de Trabajo): empleo asalariado privado registrado por
  rama, trimestral. Incluye "Actividades de informática".
- Indeed Hiring Lab: avisos publicados por sector en EE.UU., diario, índice
  base 2020-02-01 = 100. Incluye "Software Development".
- Djinni (Hugging Face, MIT): 141.897 avisos IT de Ucrania en inglés, con texto
  y años de experiencia pedidos, 2020-01 a 2023-09. Queda de reserva.

Salida: data/raw/<carpeta>/, cada archivo tal como se publica, más
descargas.jsonl con URL, fecha, tamaño y hash SHA-256 de cada descarga
(las fuentes se actualizan y el hash permite saber qué versión se usó).
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
SOURCES = {
    "series/sipa_empleo_trimestral_por_rama.xlsx":
        "https://www.argentina.gob.ar/sites/default/files/nacional_serie_empleo_trimestral_8.xlsx",
    "series/indeed_job_postings_by_sector_US.csv":
        "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/job_postings_by_sector_US.csv",
    "djinni/djinni_job_descriptions_en.parquet":
        "https://huggingface.co/datasets/lang-uk/recruitment-dataset-job-descriptions-english/resolve/main/data/train-00000-of-00001.parquet",
}


def main():
    filters = sys.argv[1:]
    failed = False
    for name, url in SOURCES.items():
        if filters and not any(x in name for x in filters):
            continue
        folder = os.path.join(RAW, os.path.dirname(name))
        os.makedirs(folder, exist_ok=True)
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            r = requests.get(url, timeout=600)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"ABORTO {name}: {e}")
            failed = True
            continue
        with open(os.path.join(RAW, name), "wb") as f:
            f.write(r.content)
        summary = {"archivo": name, "url": url, "inicio": started, "bytes": len(r.content),
                   "sha256": hashlib.sha256(r.content).hexdigest()}
        with open(os.path.join(folder, "descargas.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        print(f"OK {name}: {len(r.content):,} bytes")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
