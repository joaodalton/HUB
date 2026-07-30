from comandos.process_utils import BACKEND_DIR, BASE_DIR, FRONTEND, find_pids, kill_tree


def parar():
    print("=" * 40)
    print("Parando HUB")
    print("=" * 40)

    # Varre os processos do sistema em vez de so ler processos.json -- assim
    # tambem limpa orfaos deixados por uma execucao anterior que nao foi
    # parada direito (o proprio motivo dessa reescrita existir).
    backend_pids = find_pids(BACKEND_DIR)
    frontend_pids = find_pids(FRONTEND)

    if not backend_pids and not frontend_pids:
        print("Nenhum processo do HUB encontrado rodando.")
    else:
        for pid in backend_pids:
            kill_tree(pid)
            print(f"✔ Backend (PID {pid}) e toda a arvore de processos dele encerrados")

        for pid in frontend_pids:
            kill_tree(pid)
            print(f"✔ Frontend (PID {pid}) e toda a arvore de processos dele encerrados")

    processos_file = BASE_DIR / "processos.json"
    if processos_file.exists():
        processos_file.unlink()
        print("✔ processos.json removido")