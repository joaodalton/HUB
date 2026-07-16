import json
from pathlib import Path

import psutil

BASE_DIR = Path(__file__).resolve().parent.parent


def status():

    arquivo = BASE_DIR / "processos.json"

    if not arquivo.exists():
        print("HUB não iniciado.")
        return

    with open(arquivo) as f:
        processos = json.load(f)

    print("=" * 35)
    print("STATUS DO HUB")
    print("=" * 35)

    for nome, pid in processos.items():

        online = psutil.pid_exists(pid)

        print(
            f"{nome.capitalize():10} : {'🟢 Online' if online else '🔴 Offline'}"
        )