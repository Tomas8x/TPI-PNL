# TPI PLN: el mercado laboral IT en Reddit desde la llegada de ChatGPT

Trabajo Práctico Integrador de Procesamiento del Lenguaje Natural (Licenciatura en Ciencia de Datos, UGR).

## Hipótesis

Fecha de corte: 2022-11-30, lanzamiento de ChatGPT.

- **A.** Desde la llegada de ChatGPT, el sentimiento de las conversaciones sobre trabajo IT en Reddit se volvió más negativo. También cambiaron los temas: se habla menos de sueldos y de cambiar de trabajo, y más de despidos, de lo difícil que es conseguir trabajo y de la IA.
- **B.** El sentimiento de la conversación en Reddit acompaña al mercado laboral IT real: cuando caen las ofertas de trabajo, la conversación se vuelve más negativa.
- **C.** Después de 2022 cambió el vocabulario con que se habla del trabajo IT. Palabras como "trabajo", "junior" o "empresa" aparecen asociadas a términos distintos que antes.

## Estructura

```
scripts/          scripts de descarga, consolidación y análisis
docs/             documentación de cada etapa
  01_viabilidad.md     chequeo inicial de volumen en r/devsarg
  02_scraping.md       fuentes, scripts, parámetros y resultados de cada descarga
  03_consolidacion.md  cómo se arman los corpus finales y qué queda afuera
  04_sentimiento.md    tono: sentimiento y emociones (hipótesis A)
  05_temas.md          temas: diccionarios, TF-IDF y BERTopic (hipótesis A)
  06_vocabulario.md    word2vec antes y después del corte (hipótesis C)
  07_entidades.md      actores: NER y herramientas de IA
  08_mercado.md        ofertas: Hacker News, Indeed y SIPA (hipótesis B)
  09_cruce.md          tono contra mercado (hipótesis B)
  10_conclusiones.md   resultado por hipótesis y guion de la exposición
  eventos.csv          línea de tiempo de eventos que se superponen con el corte
presentacion/     exposición en HTML interactiva (abrir presentacion.html en el navegador)
reports/figures/  gráficos
reports/tablas/   tablas de resultados (CSV)
reports/modelos/  centroides de los temas de BERTopic (fijan los temas entre corridas)
data/             datos crudos y procesados (fuera de git, se regeneran)
```

## Cómo reproducir

Requiere Python 3.13. El sentimiento y los embeddings de BERTopic usan GPU con CUDA (se probó con una RTX 3050 de 6 GB).

```bash
python -m venv .venv
.venv/Scripts/pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/pip install -r requirements.txt   # en Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m spacy download es_core_news_lg
```

Para no repetir las descargas, bajar el zip con todos los datos (1,1 GB) de la [release del 28/10/2026](https://github.com/Tomas8x/TPI-PNL/releases/tag/datos-2026-10-28) y descomprimirlo en la raíz del repo: crea `data/raw/` y `data/processed/`. Con eso se pueden correr directamente los scripts de análisis.

Descargas desde cero (horas, ver `docs/02_scraping.md`). Cada descarga reanuda desde el último registro guardado, así que se puede cortar y volver a correr:

```bash
.venv/Scripts/python scripts/correr_descargas.py      # Reddit, Hacker News "who wants to be hired", Djinni
.venv/Scripts/python scripts/descargar_hn.py          # Hacker News "who is hiring"
.venv/Scripts/python scripts/descargar_series.py      # SIPA e Indeed
```

Consolidación y análisis, en este orden:

```bash
.venv/Scripts/python scripts/consolidar.py            # ~1 min
.venv/Scripts/python scripts/sentimiento.py           # ~80 min en GPU, reanuda si se corta
.venv/Scripts/python scripts/analisis_sentimiento.py  # ~3 min
.venv/Scripts/python scripts/analisis_temas.py        # ~6 min (+2 min de embeddings en GPU la primera vez)
.venv/Scripts/python scripts/analisis_vocabulario.py  # ~12 min
.venv/Scripts/python scripts/analisis_entidades.py    # ~10 min
.venv/Scripts/python scripts/analisis_mercado.py      # ~1 min
.venv/Scripts/python scripts/analisis_cruce.py        # segundos
.venv/Scripts/python scripts/figuras_presentacion.py  # figuras pres_*.png para la exposición
.venv/Scripts/python scripts/armar_presentacion.py    # presentacion/presentacion.html (interactiva)
```

## Presentación

`presentacion/presentacion.html` es un solo archivo, sin dependencias, que se abre en cualquier navegador. Los gráficos se dibujan en el navegador a partir de los datos del análisis: las líneas se trazan solas y al pasar el mouse se ve el valor de cada mes. En la diapositiva de vocabulario se puede elegir la palabra.

- Flechas, espacio o clic: avanzar. Varias diapositivas se arman en pasos.
- `N`: notas del orador. `F`: pantalla completa. `P`: todas las diapositivas juntas (para imprimir a PDF con Ctrl+P).

La fuente es `presentacion/plantilla.html`. Después de editarla, o si cambian los datos, correr `.venv/Scripts/python scripts/armar_presentacion.py`, que inserta los datos y genera `presentacion.html`.
