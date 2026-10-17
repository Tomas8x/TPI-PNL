"""Corre todas las descargas pendientes en paralelo, pensado para dejarlo de noche.

Uso: python scripts/correr_descargas.py [--apagar]

- Tres líneas en paralelo (LINEAS). Cada una corre sus pasos en orden. No
  se usan más de 3 líneas contra Arctic Shift porque el servidor ya da
  timeouts por carga.
- Mantiene la PC despierta mientras corre (SetThreadExecutionState), sin
  cambiar la configuración de energía.
- Si un paso aborta (por ejemplo, timeouts persistentes del servidor), espera
  REINTENTO_ESPERA_S y lo vuelve a correr, hasta REINTENTOS veces. Es seguro
  porque cada descarga reanuda desde el último registro guardado.
- Con --apagar, cuando terminan las tres líneas programa el apagado de
  Windows con 5 minutos de margen (se cancela con `shutdown /a`).

Logs: data/raw/logs/correr_descargas_<fecha>_<línea>.log
"""

import ctypes
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
REDDIT = os.path.join("scripts", "descargar_reddit.py")
LINEAS = {
    "devsarg": [
        [REDDIT, "devsarg"],
        [REDDIT, "devsarg", "--comentarios"],
    ],
    "taqueros": [
        [REDDIT, "taquerosprogramadores"],
        [REDDIT, "taquerosprogramadores", "--comentarios"],
        [os.path.join("scripts", "descargar_hn.py"), "--tipo", "hired"],
        [os.path.join("scripts", "descargar_series.py"), "djinni"],
    ],
    "empleos": [
        [REDDIT, "empleos_AR"],
        [REDDIT, "empleos_AR", "--comentarios"],
    ],
}
REINTENTOS = 3
REINTENTO_ESPERA_S = 600
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
STAMP = f"{datetime.now():%Y%m%d_%H%M}"
LOGS = os.path.join(ROOT, "data", "raw", "logs")


def log(f, msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    f.write(line + "\n")
    f.flush()


def correr_linea(nombre, pasos, resultados):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    with open(os.path.join(LOGS, f"correr_descargas_{STAMP}_{nombre}.log"), "a", encoding="utf-8") as f:
        for paso in pasos:
            for intento in range(1, REINTENTOS + 2):
                log(f, f"Paso {paso}, intento {intento}")
                p = subprocess.run([PY, *paso], cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
                if p.returncode == 0:
                    log(f, f"Paso {paso} completo")
                    resultados.append((nombre, paso, "completo"))
                    break
                if intento <= REINTENTOS:
                    log(f, f"Paso {paso} abortó (exit {p.returncode}). Espero {REINTENTO_ESPERA_S}s y reanudo.")
                    time.sleep(REINTENTO_ESPERA_S)
                else:
                    log(f, f"Paso {paso} abortó {intento} veces. Lo dejo y sigo con el próximo.")
                    resultados.append((nombre, paso, "abortado"))
        log(f, "Fin de la línea")


def main():
    os.makedirs(LOGS, exist_ok=True)
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    resultados = []
    hilos = [threading.Thread(target=correr_linea, args=(n, p, resultados)) for n, p in LINEAS.items()]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    with open(os.path.join(LOGS, f"correr_descargas_{STAMP}_resumen.log"), "a", encoding="utf-8") as f:
        for r in resultados:
            log(f, f"{r[0]}: {' '.join(r[1][1:]) or r[1][0]} -> {r[2]}")
        if "--apagar" in sys.argv:
            log(f, "Programo el apagado en 5 minutos (cancelar con: shutdown /a)")
            subprocess.run(["shutdown", "/s", "/t", "300", "/c",
                            "Descargas del TPI terminadas. Apagado en 5 minutos (shutdown /a para cancelar)."])
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


if __name__ == "__main__":
    main()
