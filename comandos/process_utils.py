# comandos/process_utils.py
"""Helpers de processo compartilhados entre iniciar.py, parar.py e status.py.
Nao duplicar essa logica em nenhum dos tres -- importar daqui.

Por que nao confiar so em processos.json: ele so lembra o PID PAI da ultima
chamada de iniciar(). No Windows, tanto o Flask com reloader quanto
'npm run dev' criam processo(s) filho(s) -- matar so o pai deixa o filho
vivo segurando a porta. E se iniciar() rodou mais de uma vez sem parar()
direito antes (foi exatamente o que causou a bagunca), sobra processo orfao
que processos.json nunca chegou a saber que existia. Por isso os helpers
aqui varrem os processos do sistema procurando por cwd/cmdline dentro da
pasta do projeto, em vez de confiar em PID salvo.
"""
import socket
import subprocess
from pathlib import Path

import psutil

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND = BASE_DIR / "frontend"
PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173


def find_pids(component_dir: Path) -> list[int]:
    """Acha todo processo vivo cujo cwd (ou, se cwd nao acessivel, a linha de
    comando) aponte pra dentro de component_dir."""
    target = str(component_dir)
    pids: list[int] = []

    for proc in psutil.process_iter(['pid', 'cmdline', 'cwd']):
        try:
            cwd = proc.info['cwd'] or ''
            cmdline = ' '.join(proc.info['cmdline'] or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        if target in cwd or target in cmdline:
            pids.append(proc.info['pid'])

    return pids


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def kill_tree(pid: int) -> None:
    """Mata o processo E toda a arvore de filhos dele. 'taskkill /T' e o jeito
    correto de fazer isso no Windows -- os.kill(pid) so mata aquele PID
    especifico e ignora os filhos, que e exatamente o bug que deixava
    backend/frontend orfaos rodando depois de 'parar'."""
    subprocess.run(
        ['taskkill', '/PID', str(pid), '/T', '/F'],
        capture_output=True,
        check=False
    )