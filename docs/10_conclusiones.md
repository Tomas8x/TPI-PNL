# 10. Conclusiones y guion de la exposición

Resumen de los análisis de `04_sentimiento.md` a `09_cruce.md`. Cada número sale de esos documentos, donde están el método, los intervalos y las limitaciones.

## Resultado por hipótesis

| Hipótesis | Resultado | Evidencia principal |
|---|---|---|
| A. Tono: más negativo después del corte | Se cumple, pero la subida empieza antes | Textos negativos en r/devsarg: 17% en 2021, 25% en 2022, 37% en 2026. Antes del corte suben 0,76 puntos por mes; después, 0,17 |
| A. Temas: más despidos, búsqueda de empleo e IA | Se cumple para IA y despidos, no para búsqueda | IA en comentarios de r/devsarg: 0,7% antes, 12% en 2026. Despidos: de 0,35% a 1,18%. Búsqueda de empleo baja en r/devsarg (3,9% a 2,9%) |
| A. Temas: menos sueldos y cambio de trabajo | No se cumple | En r/devsarg los posts de sueldo y condiciones suben de 2,7% a 6,5% (BERTopic). Lo que cae es aprender a programar (14,3% a 6,6%) |
| B. El tono acompaña a las ofertas | Solo a escala de años | Correlación con Indeed −0,71 en niveles y 0,10 en variaciones mensuales. Los avisos ya caían desde febrero de 2022 |
| C. Cambia el vocabulario de "trabajo", "junior", "empresa" | No para esas palabras; sí para "ia", "remoto" y "mercado" | Solapamiento de vecinos de "ia" entre períodos 0,08, contra 0,29 dentro de un mismo período. "trabajo", "junior" y "empresa" quedan dentro del ruido |

## Lo que se puede afirmar

1. **La conversación sobre trabajo IT en Reddit se volvió más negativa entre 2021 y 2023, y después se estabilizó en un nivel alto.** El lanzamiento de ChatGPT cae en el medio de esa subida, no al comienzo.
2. **El cambio no es propio de IT ni de Argentina.** r/empleos_AR, que habla de trabajo en general, sigue la misma curva que r/devsarg, y el sub mexicano r/taquerosprogramadores sube igual desde 2023.
3. **La IA es el cambio de contenido más grande, pero llega en dos etapas.** Hay un primer escalón en 2023 con ChatGPT y uno mucho más grande en 2025 y 2026 con las herramientas para programar. En 2026, uno de cada ocho textos de r/devsarg menciona la IA, y Claude superó a ChatGPT como herramienta más nombrada.
4. **La palabra "ia" cambió de significado.** Antes de 2022 sus vecinos eran ciencia, estadística y científicos. Después son chatgpt, claude, llm y agentes.
5. **El mercado ya caía antes de ChatGPT.** Los avisos de software en EE.UU. cayeron 36% entre febrero y noviembre de 2022, y otro 44% después. El empleo informático registrado en Argentina siguió creciendo (+7,3% entre fines de 2022 y fines de 2025).

## Lo que no se puede afirmar

- **Que ChatGPT causó el cambio.** El corte coincide con los despidos tech globales, la suba de tasas de la Reserva Federal y la caída de avisos, y en Argentina con la devaluación de diciembre de 2023. Ninguno de los análisis separa esos efectos.
- **Que los juniors la pasan peor que antes según los avisos.** En Hacker News la proporción de avisos junior se mantiene en 5% o 6%. Cayeron en cantidad, pero igual que los senior.
- **Que el tono sigue al mercado mes a mes.** La correlación solo aparece en la tendencia general.

## Limitaciones generales

- El período anterior al corte es el 5% del corpus y empieza en 2021, cuando r/devsarg era una comunidad chica. Parte de la subida de la negatividad puede deberse al crecimiento del sub.
- r/empleos_AR cambió de público durante 2022, de avisos de programación a trabajo en general, así que como control antes del corte no es del todo limpio.
- Las medidas de mercado con texto (Hacker News) y la serie de Indeed son de EE.UU. No hay avisos argentinos con historia que se puedan descargar.
- El clasificador de sentimiento coincide con la revisión manual en el 82% de los casos y sobreestima lo negativo. El NER de spaCy rinde mal en este corpus, por eso las series de entidades salen de un diccionario.

## Guion para la exposición (7 minutos)

La presentación armada está en `presentacion/presentacion.html` (16 diapositivas interactivas, con notas del orador en la tecla N). Este guion es la versión original, de siete diapositivas de ~1 minuto. Las figuras están en `reports/figures/`; las versiones para proyectar son las `pres_*.png`.

| # | Diapositiva | Mensaje | Figura | Tiempo |
|---|---|---|---|---|
| 1 | Pregunta y corpus | ¿Cambió la conversación sobre trabajo IT desde ChatGPT? 1,9 millones de textos de r/devsarg, r/empleos_AR y r/taquerosprogramadores (2021 a 2026), más avisos de Hacker News, Indeed y SIPA | tabla de volumen de `03_consolidacion.md` | 0:45 |
| 2 | El tono | La negatividad sube de 17% a 37%, pero la subida empieza antes de ChatGPT y se aplana después | `sent_negatividad_mensual.png` | 1:15 |
| 3 | No es solo IT ni solo Argentina | r/empleos_AR y el sub mexicano siguen la misma curva. Más enojo, menos alegría | `sent_negatividad_trimestral.png` o `sent_emociones_trimestral.png` | 0:45 |
| 4 | De qué se habla | La IA pasa de 0,7% a 12% de los comentarios, en dos escalones (2023 y 2025). De ChatGPT a Claude | `temas_diccionarios_comentarios.png` y `ent_ia_herramientas.png` | 1:15 |
| 5 | Qué significa "ia" | Antes: ciencia, estadística. Después: chatgpt, claude, agentes. "trabajo", "junior" y "empresa" no cambian | tabla de vecinos de `06_vocabulario.md` y `vocab_cambio_jaccard.png` | 1:00 |
| 6 | El mercado | Los avisos caen desde febrero de 2022. Tono y avisos coinciden en la tendencia, no mes a mes | `mercado_demanda.png` o `cruce_mercado_sentimiento.png` | 1:00 |
| 7 | Conclusión | Cambió el tono y cambió de qué se habla, pero ChatGPT no es el punto de quiebre: es una etapa de un cambio que empezó antes y que la IA para programar profundizó en 2025 | sin figura, tabla de hipótesis resumida | 1:00 |
