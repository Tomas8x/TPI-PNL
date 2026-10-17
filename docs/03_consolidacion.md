# 03. Consolidación de corpus

Pendiente. Acá va a quedar registrado cómo se arma cada corpus final a partir de `data/raw/` y qué se deja afuera.

## Corpus previstos

- **Posteos:** posts y comentarios de Reddit, un registro por texto, con subreddit, fecha, autor, tipo (post o comentario), flair y período (antes o después del corte).
- **Ofertas:** avisos de Hacker News "Who is hiring?" como texto, más el índice de Indeed como serie mensual.

## Decisiones a documentar

- Qué posts entran: todos, o solo los de flairs y palabras clave vinculadas con trabajo.
- Qué hacer con `[removed]` y `[deleted]`, con duplicados y con bots (AutoModerator).
- Rango temporal común entre fuentes.
- Cantidad de registros que quedan después de cada filtro.
