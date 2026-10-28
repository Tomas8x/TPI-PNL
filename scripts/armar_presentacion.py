"""Genera una versión de la presentación en un solo archivo, con las figuras incrustadas.

Uso:
    .venv/Scripts/python scripts/armar_presentacion.py

Lee presentacion/presentacion.html (que usa rutas relativas a reports/figures/)
y escribe presentacion/presentacion_completa.html, que se puede abrir en
cualquier navegador sin el resto del repo.
"""

import base64
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRADA = os.path.join(ROOT, "presentacion", "presentacion.html")
SALIDA = os.path.join(ROOT, "presentacion", "presentacion_completa.html")


def incrustar(m):
    ruta = os.path.normpath(os.path.join(os.path.dirname(ENTRADA), m.group(1)))
    with open(ruta, "rb") as f:
        datos = base64.b64encode(f.read()).decode("ascii")
    return f'src="data:image/png;base64,{datos}"'


def main():
    with open(ENTRADA, encoding="utf-8") as f:
        html = f.read()
    html, n = re.subn(r'src="([^"]+\.png)"', incrustar, html)
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{n} imágenes incrustadas, {os.path.getsize(SALIDA) / 1e6:.1f} MB: {SALIDA}")


if __name__ == "__main__":
    main()
