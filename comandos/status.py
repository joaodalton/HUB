from comandos.process_utils import (
    BACKEND_DIR,
    BACKEND_PORT,
    FRONTEND,
    FRONTEND_PORT,
    find_pids,
    port_in_use
)


def status():
    print("=" * 40)
    print("STATUS DO HUB")
    print("=" * 40)

    _print_component('Backend', find_pids(BACKEND_DIR), BACKEND_PORT)
    _print_component('Frontend', find_pids(FRONTEND), FRONTEND_PORT)


def _print_component(label: str, pids: list[int], port: int) -> None:
    if not pids:
        print(f"{label:10} : 🔴 Offline")
        return

    porta_aberta = port_in_use(port)
    icone = '🟢 Online' if porta_aberta else '🟡 Processo ativo, porta ainda fechada'
    pid_texto = ', '.join(str(pid) for pid in pids)

    if len(pids) > 1:
        print(f"{label:10} : ⚠️  {len(pids)} processos encontrados (PIDs {pid_texto}) -- rode 'python hub.py parar' pra limpar antes de continuar")
    else:
        print(f"{label:10} : {icone}  (PID {pid_texto}, porta {port})")