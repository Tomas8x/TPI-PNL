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
reports/figures/  gráficos
data/             datos crudos y procesados (fuera de git, se regeneran)
```

## Cómo reproducir

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # en Linux/macOS: .venv/bin/pip
python scripts/viabilidad_reddit.py --sub devsarg
```

Cada descarga reanuda desde el último registro guardado, así que se puede cortar y volver a correr.
