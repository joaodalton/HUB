"""
Cria uma empresa (tenant) nova + um convite pro primeiro owner definir a
propria senha. Uso manual, direto no servidor -- roda depois que o pagamento
do plano foi confirmado (decisao registrada em VISAO.md secao 2.1: nao e
self-signup publico).

O comando imprime um LINK -- copie e mande pro cliente (WhatsApp/email, na
mao por enquanto; envio automatico entra quando a integracao de
email/WhatsApp for construida). O link expira em 7 dias.

USO (de dentro de backend/, com o venv ativado):
    python scripts/criar_empresa.py --nome "Nome da Empresa" --slug empresa --owner-email dono@empresa.com
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from config import Config
from extensions import db
from models.empresa import Empresa
from services.invitation_service import criar_convite


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nome', required=True, help='Nome de exibicao da empresa')
    parser.add_argument('--slug', required=True, help='Identificador curto, sem espaco (ex.: select)')
    parser.add_argument('--owner-email', required=True, help='Email de quem vai ser o owner (recebe o link)')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        if Empresa.query.filter_by(slug=args.slug).first():
            print(f'ERRO: ja existe uma empresa com slug "{args.slug}".')
            sys.exit(1)

        from services.email_template_service import ensure_seeded
        from services.message_template_service import seed_for_empresa
        ensure_seeded()
        empresa = Empresa(nome=args.nome, slug=args.slug, status='ativa')
        db.session.add(empresa)
        db.session.flush()
        seed_for_empresa(empresa.id, commit=False)

        try:
            _, token = criar_convite(empresa.id, args.owner_email, 'owner', invited_by_id=None)
        except ValueError as exc:
            db.session.rollback()
            print(f'ERRO: {exc}')
            sys.exit(1)

        db.session.commit()

        link = f'{Config.FRONTEND_URL}/aceitar-convite?token={token}'
        print(f'Empresa "{empresa.nome}" criada (id={empresa.id}, slug={empresa.slug}).')
        print('Link de convite (valido por 7 dias) -- copie e mande pro cliente:')
        print(link)


if __name__ == '__main__':
    main()
