# 02. Scraping de fuentes

Por cada fuente se documenta el script, los parámetros, la fecha de descarga y lo que se obtuvo. Los archivos crudos quedan en `data/raw/` sin modificar.

## Fuentes elegidas (2026-10-17)

Criterio: cada fuente tiene que responder a una hipótesis o a una de las tres comparaciones del diseño (antes y después, IT contra el resto, Argentina contra otro país), al menor costo de descarga.

| Fuente | Rol | Hip. | Costo estimado | Estado |
|---|---|---|---|---|
| r/devsarg, posts | núcleo: antes y después | A, C | ~15 min (faltan ~12k) | completa: 42.975 |
| r/devsarg, comentarios | volumen para tono y vocabulario, sobre todo antes del corte | A, C | ~7 h (887k) | completa: 890.705 |
| r/empleos_AR, posts | control: mercado laboral argentino general | A | ~55 min (43k) | completa: 43.627 |
| r/taquerosprogramadores, posts | control: otro país (solo después del corte, ver abajo) | A | ~20 min (16k) | completa: 16.120 |
| Hacker News "Who is hiring?" | texto de avisos: cuántos piden junior o mencionan IA | B | 13 min (184 hilos) | completa: 93.392 avisos |
| OEDE / SIPA, empleo trimestral por rama | empleo registrado en informática en Argentina | B | 1 archivo (3,4 MB) | completa |
| Indeed Hiring Lab, avisos por sector (US) | demanda global de software, diaria | B | 1 archivo (12 MB) | completa |
| Línea de tiempo de eventos | fechas de ChatGPT, GPT-4, despidos tech, devaluación, etc., para ubicar dónde cambian las curvas | A, B | armado a mano con fuentes | pendiente |

Descartadas en esta etapa, con motivo:

- **r/programacion:** mezcla España y Latinoamérica y casi no habla de trabajo, así que no sirve como control de país. r/taquerosprogramadores cumple ese rol con un solo país.
- **Djinni:** es el único corpus de avisos con texto y seniority antes y después del corte. Pero es de Ucrania, la invasión de 2022-02 se superpone con el efecto ChatGPT y termina en 2023-09. Explicar eso consume tiempo de una exposición de 7 minutos. Queda como opción si Hacker News no alcanza.
- **Online Labour Index:** se superpone con Indeed y termina en 2024-09.
- **CEP XXI:** tiene el corte de jóvenes, pero termina en 2023-11. SIPA cubre Argentina hasta 2026.
- **Comentarios de r/empleos_AR y r/taquerosprogramadores:** para los controles alcanzan los posts. Se suman solo si hace falta más volumen.

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

Scripts:

- `scripts/arctic_shift.py`: cliente de Arctic Shift. Pagina por `created_utc` ascendente de a 100 registros, con 2 s de pausa. Reintenta solo ante 429 y ante el timeout intermitente del servidor, y aborta ante cualquier otro error. Reanuda desde el último registro guardado. Considera terminada la descarga cuando llega al registro más reciente que informa la API al arrancar.
- `scripts/descargar_reddit.py <subs...> [--comentarios]`: posts completos o comentarios con campos seleccionados. Registra cada corrida en `data/raw/reddit/descargas.jsonl`.
- `scripts/descargar_hn.py`: hilos "Who is hiring?" de Hacker News.
- `scripts/descargar_series.py`: series de SIPA e Indeed, con hash SHA-256 de cada archivo.

Prueba de los scripts de Reddit con r/devsAR (18 posts, 28 comentarios): descarga completa, segunda corrida sin duplicados. En esa prueba apareció un error en el criterio de fin, que exigía que el último registro tuviera menos de 72 h y fallaba en subs inactivos. Se reemplazó por la comparación con el registro más reciente.

### Reddit (2026-10-17)

Las tres primeras descargas de posts se hicieron con `scripts/viabilidad_reddit.py --sub devsarg`, en dos tandas cortadas a mano (23.267 y 30.691 posts). El resto se bajó con `scripts/correr_descargas.py --apagar`, que corre `descargar_reddit.py` en tres líneas paralelas y reanuda cada paso si aborta. Empezó a la 01:16 y terminó a las 16:16.

| Archivo | Registros | Requests | Duración | Rango |
|---|---|---|---|---|
| `devsarg_posts.jsonl` | 42.975 | 87 (faltaban 8.323) | 7 min | 2020-08-09 a 2026-10-17 |
| `devsarg_comments.jsonl` | 890.705 | ~8.900 | ~15 h | 2020-08-28 a 2026-10-17 |
| `empleos_AR_posts.jsonl` | 43.627 | 443 | 38 min | 2013-02-25 a 2026-10-17 |
| `empleos_AR_comments.jsonl` | 676.041 | ~6.800 | ~10 h | 2013-02-25 a 2026-10-17 |
| `taquerosprogramadores_posts.jsonl` | 16.120 | 165 | 11 min | 2020-08-19 a 2026-10-17 |
| `taquerosprogramadores_comments.jsonl` | 303.216 | 3.065 | 4 h 47 min | 2023-07-18 a 2026-10-17 |

- El servidor dio más de 800 timeouts entre las tres líneas. Los comentarios de r/devsarg y de r/empleos_AR abortaron después de tres fallos seguidos; el runner esperó 10 minutos y los retomó sin perder registros.
- No hay ids duplicados en ningún archivo.
- **r/taquerosprogramadores no sirve para comparar antes y después.** Tiene 1 post anterior al corte y el primer comentario es de julio de 2023: el sub se activó en 2023-T3. Solo sirve como control de país dentro del período posterior.
- **El período anterior al corte es chico.** En r/devsarg son 2.114 posts y 32.254 comentarios (el 5% y el 4% del total), y en r/empleos_AR 2.276 posts y 21.357 comentarios. Los dos subs crecieron mucho después del corte, así que las comparaciones tienen que usar proporciones, no conteos absolutos.

Registros por trimestre (posts y comentarios):

| Trimestre | devsarg posts | devsarg com. | empleos_AR posts | empleos_AR com. | taqueros posts | taqueros com. |
|---|---|---|---|---|---|---|
| 2021-T1 | 65 | 506 | 196 | 1.675 | 0 | 0 |
| 2021-T3 | 89 | 794 | 182 | 1.016 | 0 | 0 |
| 2022-T1 | 192 | 2.426 | 185 | 2.258 | 0 | 0 |
| 2022-T3 | 636 | 10.786 | 109 | 1.647 | 0 | 0 |
| 2022-T4 | 807 | 14.599 | 574 | 13.448 | 0 | 0 |
| 2023-T1 | 1.150 | 24.475 | 880 | 19.086 | 0 | 0 |
| 2023-T3 | 2.457 | 51.400 | 1.347 | 27.008 | 54 | 851 |
| 2024-T1 | 3.434 | 69.734 | 2.062 | 36.265 | 1.112 | 21.391 |
| 2025-T1 | 2.741 | 53.678 | 3.332 | 49.601 | 1.562 | 32.237 |
| 2026-T1 | 2.993 | 63.651 | 4.006 | 56.885 | 1.514 | 24.521 |
| 2026-T3 | 2.485 | 53.463 | 4.234 | 61.338 | 1.268 | 24.556 |

### Hacker News "Who is hiring?"

- Script: `scripts/descargar_hn.py`, 2026-10-17, 13 minutos.
- 184 hilos, de abril de 2011 a octubre de 2026. Se buscó el título "Ask HN: Who is hiring?" sin distinguir mayúsculas. Faltan abril y mayo de 2015, que la cuenta `whoishiring` no publicó; quedan fuera del período de análisis.
- 93.392 avisos (comentarios de primer nivel), 0 ids duplicados, 85 vacíos o borrados. Archivo de 128 MB. El texto viene en HTML.
- Avisos por año:

  | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (10 hilos) |
  |---|---|---|---|---|---|---|---|
  | 8.439 | 7.125 | 10.285 | 7.584 | 4.171 | 3.923 | 4.037 | 2.952 |

- "Who wants to be hired?" (gente que busca trabajo), 2026-10-17: 147 hilos, de julio de 2014 a octubre de 2026, 38.100 comentarios en `data/raw/hn/whowantstobehired.jsonl` (47 MB). No entra en la consolidación por ahora.

### Djinni

- Script: `scripts/descargar_series.py`, 2026-10-17. Parquet de 146 MB (sha256 `71dddaf0d9660f34...`) en `data/raw/djinni/`.
- Queda de reserva, por los motivos de arriba. Para leerlo hace falta `pyarrow`, que no está instalado.

### Series numéricas

- Script: `scripts/descargar_series.py`, 2026-10-17.
- `sipa_empleo_trimestral_por_rama.xlsx` (3,4 MB, sha256 `488d891136a116c1...`): de 1996-T1 a 2026-T1, trimestral. La rama 72 es "Actividades de informática" (cuadro C4) y la 722, "Servicios de consultores en informática y suministros de programas" (cuadro C6).
- `indeed_job_postings_by_sector_US.csv` (12 MB, sha256 `11501409680563c0...`): "Software Development" en EE.UU., diario, del 2020-02-01 al 2026-10-09, con índice base 100 al 2020-02-01. El último valor es 81,55 (`new postings`). Hay variables `total postings` y `new postings`.

## Relevamiento de fuentes de ofertas (2026-10-17)

Búsqueda de fuentes con historia que atraviesen noviembre de 2022. Las URLs se verificaron con requests puntuales, sin descargas masivas.

| Fuente | Tipo | Geografía | Rango | Acceso y licencia | Evaluación |
|---|---|---|---|---|---|
| [Djinni, recruitment dataset](https://huggingface.co/datasets/lang-uk/recruitment-dataset-job-descriptions-english) | texto de 141.897 avisos IT, con años de experiencia pedidos | Ucrania | 2020-01 a 2023-09, mensual | Parquet (~146 MB), MIT | único corpus de avisos con texto y período antes y después del corte; la invasión de 2022-02 se mezcla con el efecto ChatGPT |
| [OEDE / SIPA, empleo trimestral por rama](https://www.argentina.gob.ar/trabajo/estadisticas/oede-estadisticas-nacionales) | serie numérica, incluye "Actividades de informática" | Argentina | 1996-T1 a 2026-T1 | XLSX oficial | mejor serie argentina oficial y actualizada |
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
