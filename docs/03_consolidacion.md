# 03. Consolidación de corpus

Script: `scripts/consolidar.py` (2026-10-27, ~1 minuto). Lee `data/raw/` sin modificarlo y escribe en `data/processed/`. Los conteos de cada filtro quedan en `data/processed/consolidacion.json`.

## Salidas

| Archivo | Contenido | Registros |
|---|---|---|
| `posteos.jsonl` | posts y comentarios de Reddit, un registro por texto | 1.892.690 |
| `avisos_hn.jsonl` | avisos de Hacker News "Who is hiring?" en texto plano | 93.378 |
| `indeed_software_mensual.csv` | índice de avisos de software en EE.UU. (`new postings` y `total postings`), promedio mensual | 81 meses (2020-02 a 2026-10) |
| `sipa_informatica_trimestral.csv` | empleo asalariado registrado en la rama 72 (informática), total del sector privado y proporción | 121 trimestres (1996-T1 a 2026-T1) |

Campos de `posteos.jsonl`: `id`, `tipo` (post o comentario), `subreddit`, `created_utc`, `fecha`, `trimestre`, `periodo` (antes o después del 2022-11-30), `autor`, `flair`, `post_id`, `titulo`, `texto`, `score`, `num_comments` y `removido`. Los comentarios heredan el flair de su post. En los posts, `texto` es el título más el cuerpo.

Campos de `avisos_hn.jsonl`: `id`, `hilo_id`, `mes`, `periodo`, `autor` y `texto`. El mes es el del hilo, que se publica el día 1, aunque el aviso se haya escrito días después.

## Decisiones

- **Rango temporal:** de 2021-01-01 a 2026-09-30, igual para los tres subs. r/devsarg tiene 3 posts en 2020 y arranca de verdad en 2021-T1. 2026-T4 está incompleto (la descarga terminó el 17 de octubre).
- **Qué posts entran:** todos. r/devsarg y r/empleos_AR hablan casi todo el tiempo de trabajo, y el filtro por tema o por flair se decide en cada análisis. El flair queda como campo.
- **Bots:** se descartan AutoModerator y las cuentas de moderación `<sub>-ModTeam`, que publican avisos de reglas.
- **`[removed]` y `[deleted]`:** los comentarios con esos textos se descartan. En los posts se descarta el cuerpo, pero se conserva el título, que Arctic Shift guarda igual. Los posts que los moderadores o Reddit eliminaron después de archivados quedan marcados con `removido`. Los autores `[deleted]` se conservan si el texto sigue.
- **Repetidos:** se descarta un texto si el mismo autor ya publicó exactamente el mismo texto (reposteos y mensajes pegados). No se aplica a autores `[deleted]`.
- **Textos cortos:** se conservan ("Si", "No", "?"). Cada análisis decide un largo mínimo.
- **Hacker News:** el HTML se pasa a texto plano y se descartan los avisos vacíos, `[deleted]` o `[flagged]`.

## Conteos por filtro

| Fuente | Crudos | Fuera de rango | Bot | Borrado | Repetido | Finales |
|---|---|---|---|---|---|---|
| r/devsarg, posts | 42.975 | 431 | 218 | | 514 | 41.812 |
| r/devsarg, comentarios | 890.705 | 11.935 | 4.619 | 8.823 | 7.880 | 857.448 |
| r/empleos_AR, posts | 43.627 | 1.488 | 0 | | 461 | 41.678 |
| r/empleos_AR, comentarios | 676.041 | 15.640 | 938 | 7.971 | 6.215 | 645.277 |
| r/taquerosprogramadores, posts | 16.120 | 237 | 75 | | 309 | 15.499 |
| r/taquerosprogramadores, comentarios | 303.216 | 3.701 | 2.885 | 3.160 | 2.494 | 290.976 |
| HN "Who is hiring?" | 93.392 | | | 14 | | 93.378 |

Posts con `removido`: 5.666 en r/devsarg, 2.084 en r/empleos_AR y 2.372 en r/taquerosprogramadores.

## Corpus final por período

| Subreddit | Posts antes | Posts después | Comentarios antes | Comentarios después |
|---|---|---|---|---|
| r/devsarg | 2.096 | 39.716 | 30.749 | 826.699 |
| r/empleos_AR | 1.480 | 40.198 | 17.703 | 627.574 |
| r/taquerosprogramadores | 0 | 15.499 | 0 | 290.976 |

Consecuencias para el análisis:

- El período anterior es el 5% del corpus de r/devsarg. Hay que comparar proporciones y promedios por trimestre, no conteos. Para word2vec antes del corte hay ~33.000 textos de r/devsarg; conviene sumar comentarios y unir los dos subs argentinos.
- r/taquerosprogramadores solo sirve para comparar Argentina con México después del corte, por ejemplo la evolución de 2023-T3 en adelante.

## Pendiente

- Línea de tiempo de eventos (ChatGPT, GPT-4, despidos tech, devaluación de diciembre de 2023).
- "Who wants to be hired?" de Hacker News y Djinni no se consolidaron; quedan de reserva.
