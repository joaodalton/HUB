from pathlib import Path
import subprocess
import json
import time

BASE_DIR = Path(__file__).resolve().parent.parent

PYTHON = BASE_DIR / "backend" / "venv" / "Scripts" / "python.exe"
BACKEND = BASE_DIR / "backend" / "app.py"
FRONTEND = BASE_DIR / "frontend"
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def iniciar():

    print("=" * 40)
    print("Iniciando HUB")
    print("=" * 40)

    python_executable = str(PYTHON) if PYTHON.exists() else "python"
    backend = subprocess.Popen(
        [python_executable, str(BACKEND)],
        cwd=BASE_DIR / "backend",
        creationflags=CREATE_NEW_CONSOLE
    )

    print("✔ Backend iniciado")

    time.sleep(2)

    frontend = subprocess.Popen(
        ["npm.cmd", "run", "dev"],
        cwd=FRONTEND,
        creationflags=CREATE_NEW_CONSOLE
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
