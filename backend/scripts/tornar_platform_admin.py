"""Concede o acesso administrativo global a um usuario existente.

Uso (dentro de backend/, com o ambiente virtual ativo):
    python scripts/tornar_platform_admin.py --email voce@exemplo.com
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from extensions import db
from models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True, help='E-mail do usuário administrador da plataforma')
    args = parser.parse_args()
    email = args.email.strip().lower()

    app = create_app()
    with app.app_context():
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user:
            print(f'ERRO: nenhum usuário encontrado para "{email}".')
            sys.exit(1)

        user.is_platform_admin = True
        db.session.commit()
        print(f'Usuário "{user.email}" agora é administrador da plataforma.')


if __name__ == '__main__':
    main()
