"""Suspende assinaturas do plano 'teste' cujo trial de 14 dias venceu.

Idempotente: assinaturas ja suspensas nao sao tocadas de novo. Pensado para
rodar agendado (cron/Render cron job), sem argumentos.

USO (de dentro de backend/, com o ambiente virtual ativo):
    python scripts/expirar_planos_teste.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def expirar_planos_teste() -> int:
    """Suspende assinaturas do plano teste cujo trial de 14 dias venceu.
    Idempotente. Retorna a quantidade de assinaturas afetadas."""
    from extensions import db
    from models.assinatura import Assinatura
    from services.log_service import LogService, NO_EMPRESA
    expiradas = Assinatura.query.filter(
        Assinatura.plano_chave == 'teste',
        Assinatura.status != 'suspensa',
        Assinatura.trial_expira_em < datetime.utcnow(),
    ).update({'status': 'suspensa'}, synchronize_session=False)
    db.session.commit()
    if expiradas:
        LogService.info(acao='plano_teste_expirado', mensagem=f'{expiradas} assinatura(s) do plano teste suspensa(s) por trial vencido', entidade='Assinatura', empresa_id=NO_EMPRESA)
    return expiradas


def main() -> int:
    # Import tardio: evita import circular quando o comando CLI em app.py
    # importar este modulo durante create_app() (senao reimportaria app
    # ainda em definicao).
    from app import create_app
    app = create_app()
    with app.app_context():
        from extensions import db
        expiradas = expirar_planos_teste()
        print(f'{expiradas} assinatura(s) do plano teste suspensa(s).')
        db.session.remove()
        db.engine.dispose()
        return expiradas


if __name__ == '__main__':
    main()
