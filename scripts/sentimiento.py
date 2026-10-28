"""Sentimiento y emociones de cada texto de posteos.jsonl, con modelos de pysentimiento.

Uso:
    .venv/Scripts/python scripts/sentimiento.py

Modelos (RoBERTuito, entrenados con tuits en español):
- pysentimiento/robertuito-sentiment-analysis: NEG, NEU, POS.
- pysentimiento/robertuito-emotion-analysis: others, joy, sadness, anger,
  surprise, disgust, fear.

Los textos pasan por el preprocesamiento de pysentimiento (usuarios, URLs,
emojis) y se truncan a 128 tokens, el máximo del modelo: en posts largos se
clasifica el título y el comienzo del cuerpo.

Salida: data/processed/sentimiento/bloque_NNN.parquet, de hasta 100.000 textos
cada uno, con el id y las probabilidades de cada clase. Si se corta o cambia la
consolidación, volver a correr clasifica solo los ids que no tienen resultado.
Corre en GPU con fp16, a ~900 textos/s por modelo en una RTX 3050.
"""

import glob
import json
import os
import time

import pandas as pd
import torch
from pysentimiento.preprocessing import preprocess_tweet
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRADA = os.path.join(ROOT, "data", "processed", "posteos.jsonl")
SALIDA = os.path.join(ROOT, "data", "processed", "sentimiento")
MODELOS = {
    "sent": "pysentimiento/robertuito-sentiment-analysis",
    "emo": "pysentimiento/robertuito-emotion-analysis",
}
BLOQUE = 100_000
LOTE = 256


def cargar(nombre):
    tok = AutoTokenizer.from_pretrained(nombre)
    modelo = AutoModelForSequenceClassification.from_pretrained(nombre).half().cuda().eval()
    etiquetas = [modelo.config.id2label[i] for i in range(modelo.config.num_labels)]
    return tok, modelo, etiquetas


@torch.inference_mode()
def clasificar(textos, tok, modelo):
    """Probabilidades por clase, en el orden de entrada. Agrupa por largo para rellenar menos."""
    orden = sorted(range(len(textos)), key=lambda i: len(textos[i]))
    probs = [None] * len(textos)
    for b in range(0, len(orden), LOTE):
        idx = orden[b:b + LOTE]
        enc = tok([textos[i] for i in idx], truncation=True, max_length=128,
                  padding=True, return_tensors="pt").to("cuda")
        p = torch.softmax(modelo(**enc).logits.float(), dim=-1).cpu().numpy()
        for i, fila in zip(idx, p):
            probs[i] = fila
    return probs


def main():
    os.makedirs(SALIDA, exist_ok=True)
    ids, textos = [], []
    with open(ENTRADA, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            ids.append(d["id"])
            textos.append(d["texto"])
    # Se clasifican solo los ids que no están en ningún bloque guardado, así una
    # nueva consolidación no obliga a rehacer todo.
    existentes = sorted(glob.glob(os.path.join(SALIDA, "bloque_*.parquet")))
    hechos = set()
    for p in existentes:
        hechos.update(pd.read_parquet(p, columns=["id"]).id)
    faltan = [i for i, x in enumerate(ids) if x not in hechos]
    print(f"{len(ids)} textos, {len(ids) - len(faltan)} ya clasificados, faltan {len(faltan)}")
    if not faltan:
        return
    modelos = {k: cargar(v) for k, v in MODELOS.items()}
    siguiente = len(existentes)
    for n, b in enumerate(range(0, len(faltan), BLOQUE)):
        t = time.time()
        sel = faltan[b:b + BLOQUE]
        pre = [preprocess_tweet(textos[i], lang="es") for i in sel]
        df = pd.DataFrame({"id": [ids[i] for i in sel]})
        for clave, (tok, modelo, etiquetas) in modelos.items():
            probs = clasificar(pre, tok, modelo)
            for j, etiqueta in enumerate(etiquetas):
                df[f"{clave}_{etiqueta.lower()}"] = [float(p[j]) for p in probs]
        df.to_parquet(os.path.join(SALIDA, f"bloque_{siguiente + n:03d}.parquet"), index=False)
        print(f"bloque {siguiente + n:03d}: {len(df)} textos en {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
