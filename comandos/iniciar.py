from pathlib import Path
import subprocess
import json
import time
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"

PYTHON = BASE_DIR / "backend" / "venv" / "Scripts" / "python.exe"
FRONTEND = BASE_DIR / "frontend"

BACKEND_URL = "http://127.0.0.1:8000/"
FRONTEND_URL = "http://localhost:5173"


def iniciar():

    print("=" * 40)
    print("Iniciando HUB")
    print("=" * 40)

    if not PYTHON.exists():
        print(f"ERRO: nao encontrei o python do venv em: {PYTHON}")
        print("Confirma se o venv foi criado dentro de backend/ (backend\\venv), nao na raiz do projeto.")
        return

    LOGS_DIR.mkdir(exist_ok=True)
    backend_log_path = LOGS_DIR / "backend.log"
    frontend_log_path = LOGS_DIR / "frontend.log"
    backend_log = open(backend_log_path, "w", encoding="utf-8")
    frontend_log = open(frontend_log_path, "w", encoding="utf-8")

    # Sem janela propria (CREATE_NO_WINDOW) -- antes usava CREATE_NEW_CONSOLE,
    # que abre um cmd que fecha sozinho se o processo cair, sem dar tempo de
    # ler o erro. Agora tudo vai pro arquivo de log, que fica disponivel
    # mesmo depois do processo morrer.
    backend = subprocess.Popen(
        [str(PYTHON), "app.py"],
        cwd=BASE_DIR / "backend",
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    print(f"Backend iniciando... (log em {backend_log_path.relative_to(BASE_DIR)})")

    if _esperar_url(BACKEND_URL):
        print(f"✔ Backend respondendo em {BACKEND_URL}")
    else:
        print(f"✘ Backend NAO respondeu depois de 15s. Ultimas linhas de {backend_log_path.relative_to(BASE_DIR)}:")
        _mostrar_ultimas_linhas(backend_log_path)
        backend_log.close()
        frontend_log.close()
        return  # nao sobe o frontend se o backend nem levantou

    frontend = subprocess.Popen(
        ["npm.cmd", "run", "dev"],
        cwd=FRONTEND,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    print(f"✔ Frontend iniciado (log em {frontend_log_path.relative_to(BASE_DIR)})")

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
    print(f"Backend : {BACKEND_URL}")
    print(f"Frontend: {FRONTEND_URL}")


def _esperar_url(url: str, tentativas: int = 15) -> bool:
    for _ in range(tentativas):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1)
    return False


def _mostrar_ultimas_linhas(caminho: Path, quantidade: int = 25) -> None:
    if not caminho.exists() or caminho.stat().st_size == 0:
        print("  (log vazio -- o processo pode nem ter chegado a rodar. Confirma o venv/dependencias.)")
        return

    linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    for linha in linhas[-quantidade:]:
        print("  " + linha)