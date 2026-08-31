from pathlib import Path
import subprocess
import json
import time
import urllib.request
import urllib.error

from comandos.mapear import mapear
from comandos.process_utils import (
    BACKEND_DIR,
    BACKEND_PORT,
    BASE_DIR,
    FRONTEND,
    FRONTEND_PORT,
    PYTHON,
    find_pids
)

LOGS_DIR = BASE_DIR / "logs"
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}/"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"


def iniciar():
    print("=" * 40)
    print("Iniciando HUB")
    print("=" * 40)

    if not PYTHON.exists():
        print(f"ERRO: nao encontrei o python do venv em: {PYTHON}")
        print("Confirma se o venv foi criado dentro de backend/ (backend\\venv), nao na raiz do projeto.")
        return

    # Trava de instancia unica -- varre processos de verdade (nao so
    # processos.json), entao pega ate orfao que uma execucao anterior mal
    # encerrada deixou pra tras. Foi rodar 'iniciar' varias vezes sem 'parar'
    # direito antes que causou multiplos backends/frontends duplicados.
    ja_rodando = find_pids(BACKEND_DIR) + find_pids(FRONTEND)
    if ja_rodando:
        print("✘ O HUB ja parece estar rodando.")
        print(f"  PIDs encontrados: {', '.join(str(pid) for pid in ja_rodando)}")
        print("  Rode 'python hub.py parar' antes de iniciar de novo.")
        return

    LOGS_DIR.mkdir(exist_ok=True)

    # Atualiza ARCHITECTURE.md com o mapa real de dependencias antes de subir
    # os processos -- roda toda vez que o HUB inicia, nunca fica desatualizado.
    # Erro aqui NUNCA deve impedir o start (por isso o try/except): pior caso,
    # o mapa so nao atualiza dessa vez.
    try:
        mapear()
        print("✔ Mapa de dependencias atualizado (ARCHITECTURE.md)")
    except Exception as exc:
        print(f"⚠ Nao foi possivel atualizar o mapa de dependencias: {exc}")

    backend_log_path = LOGS_DIR / "backend.log"
    frontend_log_path = LOGS_DIR / "frontend.log"
    backend_log = open(backend_log_path, "w", encoding="utf-8")
    frontend_log = open(frontend_log_path, "w", encoding="utf-8")

    # Sem janela propria (CREATE_NO_WINDOW) -- tudo vai pro arquivo de log,
    # que fica disponivel mesmo depois do processo morrer.
    backend = subprocess.Popen(
        [str(PYTHON), "app.py"],
        cwd=BACKEND_DIR,
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