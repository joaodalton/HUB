from pathlib import Path
import subprocess
import json
import time

BASE_DIR = Path(__file__).resolve().parent.parent

PYTHON = BASE_DIR / "backend" / "venv" / "Scripts" / "python.exe"
FRONTEND = BASE_DIR / "frontend"


def iniciar():

    print("=" * 40)
    print("Iniciando HUB")
    print("=" * 40)

    if not PYTHON.exists():
        print(f"ERRO: nao encontrei o python do venv em: {PYTHON}")
        print("Confirma se o venv foi criado dentro de backend/ (backend\\venv), nao na raiz do projeto.")
        return

    backend = subprocess.Popen(
        [str(PYTHON), "app.py"],
        cwd=BASE_DIR / "backend",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    print("✔ Backend iniciado (janela propria, PID real salvo)")

    time.sleep(2)

    frontend = subprocess.Popen(
        ["npm.cmd", "run", "dev"],
        cwd=BASE_DIR / "frontend",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

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