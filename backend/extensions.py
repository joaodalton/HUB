import os
from flask import g, has_request_context, request
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.query import Query
from flask_sqlalchemy.session import Session
from flask_limiter import Limiter
from sqlalchemy import event, inspect
from sqlalchemy.orm import with_loader_criteria

migrate = Migrate()


def _tenant_pk_criteria(model, ident):
    """Normaliza o `ident` de um get() (escalar, tupla ou dict) em filtro
    por coluna, igual ao que Query.get()/Session.get() fariam por dentro."""
    primary_keys = inspect(model).primary_key
    if isinstance(ident, dict):
        return dict(ident)
    if isinstance(ident, (tuple, list)):
        if len(ident) != len(primary_keys):
            raise ValueError('Quantidade de chaves primárias inválida.')
        return {column.key: value for column, value in zip(primary_keys, ident)}
    return {primary_keys[0].key: ident}


class TenantQuery(Query):
    """Impede que `Model.query.get()` ignore o escopo do tenant.

    `Query.get()` pode devolver uma instância do identity map sem emitir
    SELECT -- o listener `do_orm_execute` abaixo não cobre esse caminho.
    Para modelos com TenantMixin e numa request autenticada, transformamos
    o get numa consulta explícita por PK e empresa_id, que sempre passa
    pelo banco.
    """
    def get(self, ident):
        model = self.column_descriptions[0].get('entity') if self.column_descriptions else None
        empresa_id = getattr(g, 'current_empresa_id', None) if has_request_context() else None

        if not model or empresa_id is None or not issubclass(model, TenantMixin):
            return super().get(ident)

        criteria = _tenant_pk_criteria(model, ident)
        criteria['empresa_id'] = empresa_id
        return self.filter_by(**criteria).first()


class TenantSession(Session):
    """Mesma proteção de `TenantQuery.get()`, pro caminho `db.session.get()`
    -- `Session.get()` acessa o identity map direto, sem passar por Query."""
    def get(self, entity, ident, *, options=None, populate_existing=False,
            with_for_update=None, identity_token=None, execution_options=None,
            bind_arguments=None):
        empresa_id = getattr(g, 'current_empresa_id', None) if has_request_context() else None

        if empresa_id is None or not isinstance(entity, type) or not issubclass(entity, TenantMixin):
            return super().get(
                entity, ident, options=options, populate_existing=populate_existing,
                with_for_update=with_for_update, identity_token=identity_token,
                execution_options=execution_options, bind_arguments=bind_arguments,
            )

        criteria = _tenant_pk_criteria(entity, ident)
        criteria['empresa_id'] = empresa_id
        query = self.query(entity).filter_by(**criteria)
        if options:
            query = query.options(*options)
        if populate_existing:
            query = query.populate_existing()
        if with_for_update:
            query = query.with_for_update(**(with_for_update if isinstance(with_for_update, dict) else {}))
        return query.first()


db = SQLAlchemy(query_class=TenantQuery, session_options={'class_': TenantSession})


def client_ip() -> str:
    """IP real do cliente. access_route[0] e o primeiro IP do cabecalho
    X-Forwarded-For, escrito pelo proprio cliente -- quem tenta adivinhar
    senha troca esse valor a cada tentativa e foge do rate limit. remote_addr
    e o que o ProxyFix (app.py) corrige para o IP de origem real, usando
    apenas os proxies configurados em TRUSTED_PROXY_COUNT; sem ProxyFix
    (modo debug) remote_addr já é o IP real da conexão TCP."""
    return request.remote_addr or '127.0.0.1'


limiter = Limiter(
    key_func=client_ip,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)


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
