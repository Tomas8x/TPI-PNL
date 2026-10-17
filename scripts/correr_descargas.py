"""Corre todas las descargas de Reddit en secuencia, pensado para dejarlo de noche.

Uso: python scripts/correr_descargas.py [--apagar]

- Mantiene la PC despierta mientras corre (SetThreadExecutionState), sin
  cambiar la configuración de energía.
- Si un paso aborta (por ejemplo, timeouts persistentes del servidor), espera
  REINTENTO_ESPERA_S y lo vuelve a correr, hasta REINTENTOS veces. Es seguro
  porque cada descarga reanuda desde el último registro guardado.
- Con --apagar, al terminar programa el apagado de Windows con 5 minutos de
  margen (se cancela con `shutdown /a`).

Log: data/raw/reddit/logs/correr_descargas_<fecha>.log
"""

import ctypes
import os
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
STEPS = [
    ["devsarg"],
    ["taquerosprogramadores"],
    ["empleos_AR"],
    ["devsarg", "--comentarios"],
]
REINTENTOS = 3
REINTENTO_ESPERA_S = 600
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def log(f, msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    f.write(line + "\n")
    f.flush()


def main():
    logs = os.path.join(ROOT, "data", "raw", "reddit", "logs")
    os.makedirs(logs, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    with open(os.path.join(logs, f"correr_descargas_{datetime.now():%Y%m%d_%H%M}.log"),
              "a", encoding="utf-8") as f:
        log(f, f"Inicio. Pasos: {STEPS}")
        for step in STEPS:
            for intento in range(1, REINTENTOS + 2):
                log(f, f"Paso {step}, intento {intento}")
                p = subprocess.run([PY, os.path.join(ROOT, "scripts", "descargar_reddit.py"), *step],
                                   cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
                if p.returncode == 0:
                    log(f, f"Paso {step} completo")
                    break
                if intento <= REINTENTOS:
                    log(f, f"Paso {step} abortó (exit {p.returncode}). Espero {REINTENTO_ESPERA_S}s y reanudo.")
                    time.sleep(REINTENTO_ESPERA_S)
                else:
                    log(f, f"Paso {step} abortó {intento} veces. Lo dejo y sigo con el próximo.")
        log(f, "Fin de todos los pasos")
        if "--apagar" in sys.argv:
            log(f, "Programo el apagado en 5 minutos (cancelar con: shutdown /a)")
            subprocess.run(["shutdown", "/s", "/t", "300", "/c",
                            "Descargas del TPI terminadas. Apagado en 5 minutos (shutdown /a para cancelar)."])
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


if __name__ == "__main__":
    main()
