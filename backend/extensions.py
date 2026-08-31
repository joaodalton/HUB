from flask import g
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, storage_uri='memory://')


class TenantMixin:
    """Toda tabela que pertence a uma empresa herda daqui em vez de repetir
    a coluna 'empresa_id' e o filtro na mão em cada service/rota. O listener
    logo abaixo injeta automaticamente WHERE empresa_id = <empresa da
    sessão atual> em toda query ORM contra uma classe que usa esse mixin --
    é a mitigação estrutural do risco que o VISAO.md (secao 2.1) apontava
    pro modelo multi-tenant ('query esquecida vaza dado entre empresas').
    Exceção deliberada: User NÃO usa esse mixin (ver models/user.py) porque
    o login precisa localizar o usuário ANTES de existir uma empresa "atual"
    na sessão -- filtrar User aqui criaria um problema de ovo-e-galinha.
    """
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False, index=True)


@event.listens_for(db.session, 'do_orm_execute')
def _filtrar_por_empresa(execute_state):
    if not execute_state.is_select:
        return

    empresa_id = getattr(g, 'current_empresa_id', None)
    if empresa_id is None:
        return

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.empresa_id == empresa_id,
            include_aliases=True
        )
    )
