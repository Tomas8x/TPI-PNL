# Propuesta para el foro

**Asunto:** Propuesta TPI: el mercado laboral IT en Reddit desde la llegada de ChatGPT

## 1. Corpus seleccionado

Publicaciones y comentarios de comunidades de Reddit, entre 2020 y 2026:

- [r/devsarg](https://www.reddit.com/r/devsarg/): comunidad de programadores argentinos, con unos 43.000 posts y 890.000 comentarios desde 2020. Es el núcleo del corpus.
- [r/empleos_AR](https://www.reddit.com/r/empleos_AR/): trabajo en Argentina en general, unos 43.000 posts. Sirve para comparar lo que pasa en IT con el resto del mercado.
- [r/programacion](https://www.reddit.com/r/programacion/) y [r/taquerosprogramadores](https://www.reddit.com/r/taquerosprogramadores/): comunidades de programación en español (general y México), como contraste fuera de Argentina.

Los datos se obtienen con la API de [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift), un archivo público de Reddit.

Para las ofertas laborales usamos los avisos mensuales de [Hacker News "Ask HN: Who is hiring?"](https://news.ycombinator.com/submitted?id=whoishiring), publicados desde 2011, y el índice de avisos de software de [Indeed Hiring Lab](https://github.com/hiring-lab/job_postings_tracker). Estamos evaluando también fuentes argentinas con historia.

Fecha de corte: 30/11/2022, lanzamiento de ChatGPT.

## 2. Situación o fenómeno

Desde fines de 2022 se habla de una crisis del empleo IT: despidos en empresas tecnológicas, menos búsquedas de perfiles junior y herramientas de IA que escriben código. En Argentina se suma el contexto económico. Queremos ver cómo se refleja esto en la conversación de quienes trabajan o quieren trabajar en IT: si cambió el tono, de qué se habla y cómo se habla del trabajo, y si esos cambios acompañan lo que muestran las ofertas laborales.

## 3. Hipótesis inicial

Desde la llegada de ChatGPT, la conversación sobre trabajo IT en Reddit se volvió más negativa y cambió de tema. Se habla menos de sueldos y de cambiar de trabajo, y más de despidos, de la dificultad para conseguir empleo y de la IA. Además esperamos que:

- el cambio de tono acompañe la caída de las ofertas laborales de software;
- palabras como "trabajo", "junior" o "empresa" aparezcan asociadas a términos distintos antes y después de 2022.

## 4. Estrategia preliminar

- **Tono:** análisis de sentimiento y emociones con un modelo en español, por trimestre y por comunidad.
- **Temas:** identificación de temas y su evolución en el tiempo, y términos característicos de cada período con TF-IDF.
- **Vocabulario:** modelos word2vec entrenados antes y después del corte, comparando las palabras cercanas a términos clave.
- **Actores:** entidades nombradas (empresas, tecnologías, herramientas de IA) y su frecuencia en el tiempo.
- **Cruce con ofertas:** comparar la serie mensual de sentimiento con la cantidad de avisos y con los perfiles que piden, por ejemplo cuántos avisos mencionan junior o IA.
