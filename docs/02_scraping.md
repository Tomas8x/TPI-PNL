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

- **Descartados:** r/chileIT no tiene datos antes del corte. r/cscareerquestions es demasiado grande para bajarlo entero y la búsqueda por texto de la API no es confiable. Como fuente de ofertas se descarta r/empleos_AR: solo ~10% de una muestra de 100 posts eran ofertas ("Solicito empleado/s") y no son específicas de IT. Sí entra en el corpus de posteos como control.
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

## Relevamiento de fuentes de ofertas (2026-10-17)

Búsqueda de fuentes con historia que atraviesen noviembre de 2022. Las URLs se verificaron con requests puntuales, sin descargas masivas.

| Fuente | Tipo | Geografía | Rango | Acceso y licencia | Evaluación |
|---|---|---|---|---|---|
| [Djinni, recruitment dataset](https://huggingface.co/datasets/lang-uk/recruitment-dataset-job-descriptions-english) | texto de 141.897 avisos IT, con años de experiencia pedidos | Ucrania | 2020-01 a 2023-09, mensual | Parquet (~146 MB), MIT | único corpus de avisos con texto y período antes y después del corte; la invasión de 2022-02 se mezcla con el efecto ChatGPT |
| [OEDE / SIPA, empleo trimestral por rama](https://www.argentina.gob.ar/trabajo/estadisticas/oede-estadisticas-nacionales) | serie numérica, incluye "Actividades de informática" | Argentina | anterior a 2020 hasta 2026-T2 | XLSX oficial | mejor serie argentina oficial y actualizada |
| [Online Labour Index](https://figshare.com/articles/dataset/3761562) | índice diario de proyectos freelance por ocupación, más trabajadores por país | global, incluye Argentina | 2016-05 a 2024-09 | Figshare, CC BY 4.0 | demanda global de software con historia |
| [CEP XXI, puestos por CLAE](https://datos.produccion.gob.ar/dataset/puestos-de-trabajo-por-sector-productivo) | puestos privados mensuales, CLAE 62, total y jóvenes | Argentina | 2007-01 a 2023-11 (jóvenes hasta 2024-01) | CSV, CC BY 4.0 | tiene el corte de jóvenes, pero termina antes |
| Hacker News "Who is hiring?" | texto de avisos | global | 2011 a hoy | API de Algolia | ya relevado |
| [Sysarmy / OpenQube](https://github.com/openqube/openqube-sueldos/tree/master/data/csv/argentina) | encuesta semestral de sueldos, campos cerrados | Argentina | 2014 a 2026 (CSV en GitHub hasta 2021.02, después en Google Sheets) | licencia de datos no explícita | contexto de salarios, no son ofertas |
| Layoffs.fyi (copia en Kaggle `swaptr/layoffs-2022`) | despidos en empresas tech | global | 2020-03 a 2025-04 | uso con atribución | contexto |
| Wayback Machine, Get on Board | HTML archivado de avisos | LatAm | 2019 a 2024, 1.000 a 3.000 URLs por año | API CDX | viable, pero la muestra depende de qué archivó Wayback; solo sirve para proporciones |

Descartadas:

- **Get on Board API:** solo devuelve avisos vigentes. El más viejo de la categoría `programming` es de mayo de 2025.
- **LinkedIn en Kaggle:** solo cubre 2023 y 2024, sin datos de antes del corte.
- **Remotive:** solo avisos vigentes, y su aviso legal prohíbe redistribuirlos.
- **Web Data Commons:** son instantáneas anuales en RDF, de 7 GB cada una.
- **CESSI/OPSSI, Banco Mundial:** solo informes en PDF.
- **Bumeran:** solo notas de prensa.
- **UTDT:** no se encontraron datos posteriores a 2013.
- **TrueUp, OECD.AI:** no se pudieron verificar.

No se encontró texto de avisos argentinos con historia que se pueda descargar.
