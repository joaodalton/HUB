from pathlib import Path
import subprocess
import json
import time

BASE_DIR = Path(__file__).resolve().parent.parent

PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"
BACKEND = BASE_DIR / "backend" / "app.py"
FRONTEND = BASE_DIR / "frontend"


def iniciar():

    print("=" * 40)
    print("Iniciando HUB")
    print("=" * 40)

    backend = subprocess.Popen(["cmd", "/k", str(PYTHON), "app.py"], cwd=BASE_DIR / "backend" )

    print("✔ Backend iniciado")

    time.sleep(2)

    frontend = subprocess.Popen(["cmd", "/k", "npm", "run", "dev"], cwd=BASE_DIR / "frontend")

    print("✔ Frontend iniciado")

    with open(BASE_DIR / "processos.json", "w") as arquivo:
        json.dump(
            {
                "backend": backend.pid,
                "frontend": frontend.pid
            },
            arquivo,
            indent=4
        )

    print()
    print("Backend : http://127.0.0.1:8000")
    print("Frontend: http://localhost:5173")