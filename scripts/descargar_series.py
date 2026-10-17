"""Descarga las series numéricas de empleo y avisos (archivos sueltos, sin paginar).

Uso: python scripts/descargar_series.py

- OEDE / SIPA (Secretaría de Trabajo): empleo asalariado privado registrado por
  rama, trimestral. Incluye "Actividades de informática".
- Indeed Hiring Lab: avisos publicados por sector en EE.UU., diario, índice
  base 2020-02-01 = 100. Incluye "Software Development".

Salida: data/raw/series/, cada archivo tal como se publica, más
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
RAW = os.path.join(ROOT, "data", "raw", "series")
SOURCES = {
    "sipa_empleo_trimestral_por_rama.xlsx":
        "https://www.argentina.gob.ar/sites/default/files/nacional_serie_empleo_trimestral_8.xlsx",
    "indeed_job_postings_by_sector_US.csv":
        "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/job_postings_by_sector_US.csv",
}


def main():
    os.makedirs(RAW, exist_ok=True)
    failed = False
    for name, url in SOURCES.items():
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"ABORTO {name}: {e}")
            failed = True
            continue
        with open(os.path.join(RAW, name), "wb") as f:
            f.write(r.content)
        summary = {"archivo": name, "url": url, "inicio": started, "bytes": len(r.content),
                   "sha256": hashlib.sha256(r.content).hexdigest()}
        with open(os.path.join(RAW, "descargas.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        print(f"OK {name}: {len(r.content):,} bytes")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
