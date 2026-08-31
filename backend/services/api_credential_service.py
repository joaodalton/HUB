"""Credenciais de API por tenant, com segredo exclusivamente criptografado."""
from flask import g
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.api_credential import ApiCredential
from models.log_entry import LogEntry
from services.log_service import LogService
from utils.crypto import encrypt_value


PROVIDERS_VALIDOS = frozenset({'resend', 'whatsapp', 'asaas', 'concessionaria'})


class CredentialConflictError(ValueError):
    pass


def listar() -> list[dict]:
    credentials = (
        ApiCredential.query
        .filter(ApiCredential.empresa_id == g.current_empresa_id)
        .order_by(ApiCredential.provider.asc(), ApiCredential.nome.asc(), ApiCredential.id.asc())
        .all()
    )
    return [credential.to_dict() for credential in credentials]


def obter(credential_id: int) -> ApiCredential | None:
    return ApiCredential.query.filter_by(id=credential_id, empresa_id=g.current_empresa_id).first()


def criar(data: dict) -> dict:
    provider = _validar_provider(data.get('provider'))
    nome = _validar_nome(data.get('nome'))
    segredo = _validar_segredo(data.get('segredo'), obrigatorio=True)
    credential = ApiCredential(empresa_id=g.current_empresa_id, provider=provider, nome=nome, segredo_encrypted='')
    credential.set_segredo(segredo)
    db.session.add(credential)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise CredentialConflictError('Ja existe uma credencial com este provider e nome nesta empresa.') from exc
    _audit('api_credential_create', credential)
    return credential.to_dict()


def atualizar(credential_id: int, data: dict) -> dict | None:
    credential = obter(credential_id)
    if not credential:
        return None
    if 'provider' in data and _validar_provider(data['provider']) != credential.provider:
        raise ValueError('Provider nao pode ser alterado; crie uma nova credencial.')
    novo_nome = credential.nome
    if 'nome' in data:
        novo_nome = _validar_nome(data['nome'])
    novo_segredo_encrypted = credential.segredo_encrypted
    if 'segredo' in data:
        # Criptografa antes de alterar o registro: falha de chave/cifra nao
        # persiste nome parcialmente atualizado nem apaga o segredo anterior.
        novo_segredo = _validar_segredo(data['segredo'], obrigatorio=True)
        novo_segredo_encrypted = encrypt_value(novo_segredo)
    credential.nome = novo_nome
    credential.segredo_encrypted = novo_segredo_encrypted
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise CredentialConflictError('Ja existe uma credencial com este provider e nome nesta empresa.') from exc
    _audit('api_credential_update', credential)
    return credential.to_dict()


def excluir(credential_id: int) -> bool:
    credential = obter(credential_id)
    if not credential:
        return False
    provider, identifier = credential.provider, credential.id
    db.session.delete(credential)
    # Exclusao e auditoria precisam ser atomicas. LogService faz commit proprio
    # e engole falhas por desenho; aqui o log faz parte da mesma transacao.
    db.session.add(LogEntry(
        empresa_id=g.current_empresa_id,
        nivel='info',
        acao='api_credential_delete',
        entidade='ApiCredential',
        entidade_id=identifier,
        mensagem='Credencial de API excluida',
        metadados={'provider': provider},
    ))
    db.session.commit()
    return True


def testar(credential_id: int) -> dict | None:
    credential = obter(credential_id)
    if not credential:
        return None
    try:
        # Dry-run local: confirma que a cifra pode ser lida, mas nao expõe nem
        # transmite o valor. A chamada real depende de decisao por provider.
        if not credential.get_segredo():
            raise ValueError('Credencial indisponivel.')
    except RuntimeError as exc:
        raise RuntimeError('Credencial indisponivel para teste local.') from exc
    except ValueError as exc:
        raise ValueError('Credencial indisponivel para teste local.') from exc
    _audit('api_credential_test_dry_run', credential)
    return {'ok': True, 'modo': 'dry-run', 'provider': credential.provider}


def _validar_provider(valor) -> str:
    provider = (valor or '').strip().lower()
    if provider not in PROVIDERS_VALIDOS:
        raise ValueError('Provider invalido. Use resend, whatsapp, asaas ou concessionaria.')
    return provider


def _validar_nome(valor) -> str:
    nome = (valor or '').strip()
    if not nome or len(nome) > 100:
        raise ValueError('Nome e obrigatorio e deve ter no maximo 100 caracteres.')
    return nome


def _validar_segredo(valor, *, obrigatorio: bool) -> str:
    if not isinstance(valor, str) or (obrigatorio and not valor.strip()):
        raise ValueError('Segredo e obrigatorio.')
    segredo = valor.strip()
    if len(segredo) > 10000:
        raise ValueError('Segredo excede o tamanho permitido.')
    return segredo


def _audit(acao: str, credential: ApiCredential) -> None:
    LogService.info(acao=acao, mensagem='Credencial de API alterada', entidade='ApiCredential', entidade_id=credential.id, metadados={'provider': credential.provider})
