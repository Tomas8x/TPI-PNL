# 02. Scraping de fuentes

Por cada fuente se documenta el script, los parámetros, la fecha de descarga y lo que se obtuvo. Los archivos crudos quedan en `data/raw/` sin modificar.

## Fuentes planificadas

| Fuente | Qué aporta | Corpus | Estado |
|---|---|---|---|
| r/devsarg, posts | conversación de devs argentinos, núcleo del corpus | posteos | parcial: 30.691 de ~42.800 |
| r/taquerosprogramadores, posts | contraste México, desde 2020 | posteos | pendiente |
| r/programacion, posts | habla hispana general, historia desde 2010 | posteos | pendiente |
| r/empleos_AR, posts | trabajo en Argentina en general, control para comparar IT con el resto | posteos | pendiente |
| r/devsarg, comentarios de posts de trabajo | volumen para el sentimiento, sobre todo antes del corte | posteos | pendiente |
| Hacker News "Who is hiring?" | avisos reales, mensuales desde 2011 (inglés, global) | ofertas | pendiente |
| Indeed Hiring Lab | índice diario de avisos de software (US, ES y otros; no hay Argentina) | ofertas (serie numérica) | pendiente |

## Pruebas previas (2026-10-17)

- **Arctic Shift, metadatos de subreddits** (`/api/subreddits/search`, campo `_meta`):

  | Subreddit | Posts | Comentarios | Primer post |
  |---|---|---|---|
  | devsarg | 42.811 | 886.815 | 2020-08-09 |
  | taquerosprogramadores | 16.028 | 301.724 | 2020-08-19 |
  | programacion | 34.761 | 247.338 | 2010-02-19 |
  | chileIT | 14.980 | 232.410 | 2023-05-17 |
  | empleos_AR | 43.395 | 671.949 | 2013-02-25 |
  | cscareerquestions | 566.645 | 7.309.231 | 2011-03-19 |

- **Otros subreddits argentinos relevados:**

  | Subreddit | Posts | Comentarios | Primer post | Nota |
  |---|---|---|---|---|
  | argentina | 623.607 | 18.785.812 | 2008-08-29 | general, demasiado grande para bajar entero |
  | AskArgentina | 176.055 | 4.373.844 | 2015-01-25 | preguntas generales |
  | RepublicaArgentina | 74.752 | 1.748.473 | 2012-08-26 | general |
  | ArgentinaBenderStyle | 61.621 | 1.505.878 | 2018-10-19 | general |
  | Cordoba | 55.245 | 573.965 | 2010-10-03 | regional |
  | merval | 38.848 | 662.155 | 2014-07-14 | finanzas, dólar |
  | Rosario | 20.105 | 203.494 | 2011-08-21 | regional |
  | UBA | 13.353 | 72.109 | 2012-04-08 | estudiantes |
  | UTN | 2.980 | 17.242 | 2016-03-06 | estudiantes, carreras de sistemas |

  No existen o tienen menos de 50 posts: sysarmy, devsAR, CienciaDeDatos, TrabajoArgentina, ITArgentina, trabajoAR, laburo, freelanceAR. Fuera de r/devsarg no hay otro sub argentino específico de IT con volumen.

- **Descartados:** r/chileIT no tiene datos antes del corte. r/cscareerquestions es demasiado grande para bajarlo entero y la búsqueda por texto de la API no es confiable. En r/empleos_AR, solo ~10% de una muestra de 100 posts eran ofertas ("Solicito empleado/s") y no son específicas de IT.
- **Comentarios:** `/api/comments/search?link_id=<id>` devuelve todos los comentarios de un post en una request (42 para un post que declaraba 41).
- **Hacker News:** la API de Algolia lista 185 hilos "Ask HN: Who is hiring?" del usuario `whoishiring`. Cada uno tiene entre 300 y 1.000 avisos como comentarios de primer nivel.
- **Indeed Hiring Lab:** el repo [hiring-lab/job_postings_tracker](https://github.com/hiring-lab/job_postings_tracker) tiene carpetas para AU, CA, DE, EA, ES, FR, GB, IE, IT, NL y US.
- **Flairs de r/devsarg:** `trabajo` (3.492), `sueldos` (1.394), `entrevistas` (674), `freelance` (348), `cursos y bootcamps` (319), `ai` (203) y `cv` (87) en los posts bajados hasta ahora.

## Descargas

<!-- Una sección por fuente: script, comando, fecha, parámetros, registros obtenidos, errores, tamaño. -->

### r/devsarg, posts

- Script: `scripts/viabilidad_reddit.py --sub devsarg`
- Primera tanda (2026-10-16): 23.267 posts, hasta el 2025-01-03. Cortada a mano para validar.
- Segunda tanda (2026-10-16): continuó hasta 30.691 posts (agosto de 2025). Cortada a mano para definir el corpus.
- Pendiente: completar hasta hoy.
