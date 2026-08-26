from flask import g, has_request_context
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import event
from sqlalchemy import inspect
from sqlalchemy.orm import Session, with_loader_criteria
from flask_sqlalchemy.query import Query

class TenantQuery(Query):
    """
    Impede que uma busca por PK ignore o escopo do tenant.

    Query.get() e Session.get() podem devolver uma instância do
    identity map sem emitir SELECT. Isso não é uma base segura para o filtro
    injetado no listener abaixo. Para modelos com TenantMixin e numa request
    autenticada, transformamos o get numa consulta explícita por PK e
    empresa_id, que sempre passa pelo banco.
    """
    def get(self, ident, populate_existing=False, with_for_update=None,
            identity_token=None, execution_options=None):
        model = self.column_descriptions[0].get('entity') if self.column_descriptions else None
        empresa_id = getattr(g, 'current_empresa_id', None) if has_request_context() else None

        if not model or empresa_id is None or not issubclass(model, TenantMixin):
            # Query.get() clássico do SQLAlchemy aceita só `ident` -- os
            # kwargs extras (populate_existing, with_for_update,
            # identity_token, execution_options) são da assinatura do
            # Session.get(), não do Query.get(). Repassá-los aqui pro
            # super().get() estourava TypeError em qualquer
            # Model.query.get(id) que cai neste fallback -- inclusive
            # User.query.get(), usado no login/middleware de auth.
            return super().get(ident)

        primary_keys = inspect(model).primary_key
        if isinstance(ident, dict):
            criteria = ident
        elif isinstance(ident, (tuple, list)):
            if len(ident) != len(primary_keys):
                raise ValueError('Quantidade de chaves primárias inválida.')
            criteria = {column.key: value for column, value in zip(primary_keys, ident)}
        else:
            criteria = {primary_keys[0].key: ident}

        query = self.filter_by(**criteria, empresa_id=empresa_id)
        if populate_existing:
            query = query.populate_existing()
        if with_for_update:
            query = query.with_for_update(**(with_for_update if isinstance(with_for_update, dict) else {}))
        return query.first()


from flask_sqlalchemy.session import Session as FSSession
from sqlalchemy.orm import Session as BaseSession

class TenantSession(FSSession):
    """
    Subclasse de Session que protege db.session.get() para modelos com TenantMixin.

    Session.get() do SQLAlchemy verifica o identity map antes de emitir SELECT.
    Se o objeto já estiver no identity map (de uma request anterior ou de uma
    query prévia), ele devolve imediatamente sem passar pelo filtro de tenant
    injetado pelo listener do_orm_execute. Isso permite vazamento de dados
    entre empresas em um SaaS multi-tenant.

    Esta subclasse garante que, para modelos com TenantMixin, sempre emitimos
    um SELECT com o filtro de empresa_id, mesmo se o objeto estiver no identity map.

    ASSINATURA: Segue a assinatura oficial do SQLAlchemy 2.x Session.get().
    """
    def get(self, entity, ident, options=None, populate_existing=False,
            with_for_update=None, identity_token=None, execution_options=None,
            bind_arguments=None):
        cls = entity

        # Verifica se é um modelo com TenantMixin em contexto de request
        if has_request_context():
            empresa_id = getattr(g, 'current_empresa_id', None)
            if empresa_id is not None and issubclass(cls, TenantMixin):
                # Emite SELECT explícito com filtro de tenant
                primary_keys = inspect(cls).primary_key
                if isinstance(ident, dict):
                    criteria = ident
                elif isinstance(ident, (tuple, list)):
                    if len(ident) != len(primary_keys):
                        raise ValueError('Quantidade de chaves primárias inválida.')
                    criteria = {column.key: value for column, value in zip(primary_keys, ident)}
                else:
                    criteria = {primary_keys[0].key: ident}

                query = self.query(cls).filter_by(**criteria, empresa_id=empresa_id)
                if populate_existing:
                    query = query.populate_existing()
                if with_for_update:
                    query = query.with_for_update(**(with_for_update if isinstance(with_for_update, dict) else {}))
                return query.first()

        # Fallback para comportamento padrão (modelos sem tenant ou fora de request)
        return super().get(entity, ident, options=options, populate_existing=populate_existing,
                           with_for_update=with_for_update, identity_token=identity_token,
                           execution_options=execution_options, bind_arguments=bind_arguments)


db = SQLAlchemy(query_class=TenantQuery, session_options={'class_': TenantSession})
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, storage_uri='memory://')


class TenantMixin:
    """
    Toda tabela que pertence a uma empresa herda daqui em vez de repetir
    a coluna 'empresa_id' e o filtro na mão em cada service/rota. O listener
    abaixo injeta automaticamente WHERE empresa_id = <empresa da
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

    # Setado pelo middleware de auth (utils/auth.py) a partir do usuário
    # logado. Ausente = requisição ainda não autenticada, ou execução fora
    # de request (scripts, migrations) -- nesses casos não filtra, quem
    # decide o escopo é o próprio script/rota.
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
