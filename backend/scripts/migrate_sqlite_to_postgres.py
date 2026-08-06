"""
Script PONTUAL -- roda uma vez, migrando os dados reais do SQLite local
(backend/database/hub.db) para o Postgres apontado pela DATABASE_URL atual
(Neon local de dev, ou Neon de producao mais tarde -- ver PROGRESS.md, Etapa 3
do plano de deploy). Depois de confirmado que os dados bateram, pode apagar
este arquivo -- ele nao faz parte do funcionamento normal do HUB.

Nao usa a ORM (nao instancia Client/Plant/etc.) de proposito: le e escreve
direto via SQLAlchemy Core (db.metadata.sorted_tables), copiando toda coluna
tal como esta no SQLite, incluindo id, created_at e updated_at originais --
isso preserva as referencias entre tabelas (FK) sem reescrever nada.

USO (de dentro de backend/, com o venv ativado):
    python scripts/migrate_sqlite_to_postgres.py                  # dry-run: so mostra o que faria
    python scripts/migrate_sqlite_to_postgres.py --apply          # migra de verdade
    python scripts/migrate_sqlite_to_postgres.py --apply --force  # migra e ZERA tabela de destino que ja tiver dado
    python scripts/migrate_sqlite_to_postgres.py --apply --include-users  # tambem migra a tabela users (ver aviso abaixo)

Por que 'users' fica de fora por padrao: se voce ja testou a Etapa 2 (Postgres
local) fazendo bootstrap + login pela tela, o Postgres de destino ja tem 1
usuario funcionando -- migrar o 'users' do SQLite por cima criaria um segundo
registro (ou colidiria no email unico) sem necessidade. Use --include-users
só se quiser preservar o usuario admin original em vez do que foi criado
durante o teste.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text

from app import create_app
from extensions import db

SQLITE_PATH = Path(__file__).resolve().parent.parent / 'database' / 'hub.db'

# Ordem de insercao segue db.metadata.sorted_tables (topological sort pelas FKs
# de verdade) -- nao precisa manter essa lista na mao. 'users' e tratado a
# parte por causa do unique constraint em email (ver docstring acima).
SKIP_BY_DEFAULT = {'users', 'alembic_version'}


def fetch_sqlite_rows(sqlite_conn: sqlite3.Connection, table_name: str) -> list[dict]:
    sqlite_conn.row_factory = sqlite3.Row
    cur = sqlite_conn.execute(f'SELECT * FROM "{table_name}"')
    return [dict(row) for row in cur.fetchall()]


def reset_sequence(pg_conn, table_name: str) -> None:
    """Depois de inserir com id explicito, a sequence do Postgres nao sabe que
    avancou -- sem isso, o proximo INSERT feito pela aplicacao (sem id) colide
    com um id que ja existe."""
    pg_conn.execute(text(
        "SELECT setval(pg_get_serial_sequence(:table, 'id'), "
        "COALESCE((SELECT MAX(id) FROM \"" + table_name + "\"), 1))"
    ), {'table': table_name})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Executa de verdade. Sem essa flag, so mostra o plano (dry-run).')
    parser.add_argument('--force', action='store_true', help='Zera (TRUNCATE) uma tabela de destino que ja tiver dado, antes de reinserir.')
    parser.add_argument('--include-users', action='store_true', help='Tambem migra a tabela users (ver docstring).')
    args = parser.parse_args()

    if not SQLITE_PATH.exists():
        print(f'ERRO: nao encontrei {SQLITE_PATH}. Rode este script de dentro de backend/, na mesma maquina onde estava o SQLite antigo.')
        sys.exit(1)

    app = create_app()

    with app.app_context():
        pg_url = app.config['SQLALCHEMY_DATABASE_URI']

        if pg_url.startswith('sqlite'):
            print('ERRO: a DATABASE_URL atual ainda aponta pro SQLite. Configure DATABASE_URL pro Postgres (Etapa 2) antes de rodar isso.')
            sys.exit(1)

        print(f'Origem : {SQLITE_PATH}')
        print(f'Destino: {pg_url.split("@")[-1] if "@" in pg_url else pg_url}  (senha omitida do print)')
        print(f'Modo   : {"APLICANDO DE VERDADE" if args.apply else "DRY-RUN (nada sera escrito)"}')
        print()

        sqlite_conn = sqlite3.connect(SQLITE_PATH)
        pg_engine = create_engine(pg_url)

        skip = set(SKIP_BY_DEFAULT)
        if args.include_users:
            skip.discard('users')

        tables = [t for t in db.metadata.sorted_tables if t.name not in skip]

        with pg_engine.begin() as pg_conn:
            for table in tables:
                rows = fetch_sqlite_rows(sqlite_conn, table.name)

                if not rows:
                    print(f'  {table.name:<20} 0 registros no SQLite -- pulando.')
                    continue

                existing = pg_conn.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar()

                if existing and not args.force:
                    print(f'  {table.name:<20} DESTINO JA TEM {existing} registro(s) -- pulando (use --force pra zerar e reinserir).')
                    continue

                print(f'  {table.name:<20} {len(rows)} registro(s) no SQLite'
                      + (f' -- {existing} no destino, sera(m) zerado(s) (--force)' if existing else ''))

                if not args.apply:
                    continue

                if existing and args.force:
                    pg_conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))

                pg_conn.execute(table.insert(), rows)
                reset_sequence(pg_conn, table.name)

        sqlite_conn.close()

    print()
    if not args.apply:
        print('Dry-run concluido. Confira a lista acima e rode de novo com --apply pra migrar de verdade.')
    else:
        print('Migracao concluida. Confira as contagens no frontend/telas do HUB (ou --include-users se precisar do usuario original).')
        if 'users' in skip:
            print('Tabela "users" NAO foi tocada -- login continua sendo o que voce ja usa no Postgres de destino.')


if __name__ == '__main__':
    main()