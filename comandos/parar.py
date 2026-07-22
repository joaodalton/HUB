import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PYTHON = BASE_DIR / "backend" / "venv" / "Scripts" / "python.exe"
FRONTEND = BASE_DIR / "frontend"

def parar():

    arquivo = BASE_DIR / "processos.json"

    if not arquivo.exists():
        print("Nenhum processo salvo.")
        return

    with open(arquivo) as f:
        processos = json.load(f)

    for nome, pid in processos.items():

        try:
            os.kill(pid, 9)
            print(f"✔ {nome} encerrado")

        except Exception:
            print(f"{nome} já estava parado.")

    arquivo.unlink()