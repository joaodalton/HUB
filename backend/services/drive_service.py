import io
import zipfile
from collections import deque

from flask import g
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from config import Config
from utils.files import safe_filename, unique_filename


def _escape_drive_literal(value: str) -> str:
    """Escapa um literal para a query da API do Drive. Escapar so a aspa deixava
    `\\'` fechar a string e injetar operadores (ex.: relaxar `in parents`)."""
    cleaned = ''.join(ch for ch in (value or '') if ch >= ' ')
    return cleaned.replace('\\', '\\\\').replace("'", "\\'")


class GoogleDriveService:
    def __init__(self, credentials, root_folder_id: str) -> None:
        self.client = build('drive', 'v3', credentials=credentials)
        self.root_folder_id = root_folder_id
        # Cache de IDs ja confirmados como descendentes legitimos da raiz, pra evitar
        # repetir a varredura cara de _descends_from_root a cada chamada igual. So
        # guarda confirmacao POSITIVA: a instancia (e esse cache junto) e descartada
        # inteira por invalidate_drive_cache() quando a config/conta do tenant muda,
        # e um item so entra aqui depois de achado dentro da raiz -- nunca negativo,
        # pra nao negar acesso a um item recem-movido pra dentro da raiz.
        self._confirmed_within_root: set[str] = set()

    # Lista fechada de proposito -- ainda e um whitelist, so mais largo que so PDF/pasta,
    # pra alimentar o filtro dinamico de "Tipo de arquivo" no frontend com algo real.
    _SEARCHABLE_MIME_TYPES = [
        'application/pdf',
        'application/vnd.google-apps.folder',
        'image/jpeg',
        'image/png',
        'application/vnd.google-apps.document',
        'application/vnd.google-apps.spreadsheet'
    ]

    def search_files(self, query_text: str) -> list[dict]:
        # Mesmo escape ja usado em find_duplicate() deste arquivo -- sem isso,
        # buscar por termo com apostrofo (ex.: "O'Brien") quebra a sintaxe da
        # query do Drive (erro 400 da API do Google, sem tratamento especifico
        # em drive_routes.py -- vira 500 cru pro usuario).
        escaped_query_text = _escape_drive_literal(query_text)
        mime_filter = ' or '.join(f"mimeType='{mime}'" for mime in self._SEARCHABLE_MIME_TYPES)
        query = (
            f"name contains '{escaped_query_text}' "
            f"and ({mime_filter}) "
            f"and trashed=false"
        )
        if self.root_folder_id:
            query += f" and '{self.root_folder_id}' in parents"

        results = self.client.files().list(
            q=query,
            fields="files(id, name, mimeType, webViewLink, iconLink, modifiedTime)",
            pageSize=50
        ).execute()

        return results.get('files', [])

    def list_folder(self, folder_id: str) -> list[dict]:
        try:
            metadata = self.get_authorized_item(folder_id)
        except ValueError as exc:
            raise ValueError('Pasta nao encontrada.') from exc

        if metadata.get('mimeType') != 'application/vnd.google-apps.folder':
            raise ValueError('Pasta nao encontrada.')

        mime_filter = ' or '.join(f"mimeType='{mime}'" for mime in self._SEARCHABLE_MIME_TYPES)
        results = self.client.files().list(
            q=f"'{folder_id}' in parents and ({mime_filter}) and trashed=false",
            fields="files(id, name, mimeType, webViewLink, iconLink, modifiedTime)",
            pageSize=50
        ).execute()
        return results.get('files', [])

    def list_root(self) -> list[dict]:
        """Lista o conteudo da raiz logica do tenant, sem o frontend precisar
        saber o ID dela: delega pra list_folder quando ha pasta configurada,
        ou usa o alias 'root' da API quando a raiz e a da propria conta Google."""
        if self.root_folder_id:
            return self.list_folder(self.root_folder_id)

        mime_filter = ' or '.join(f"mimeType='{mime}'" for mime in self._SEARCHABLE_MIME_TYPES)
        results = self.client.files().list(
            q=f"'root' in parents and ({mime_filter}) and trashed=false",
            fields="files(id, name, mimeType, webViewLink, iconLink, modifiedTime)",
            pageSize=50
        ).execute()
        return results.get('files', [])

    def get_authorized_item(self, item_id: str) -> dict:
        try:
            metadata = self.client.files().get(
                fileId=item_id,
                fields='id, name, mimeType, parents'
            ).execute()
        except Exception as exc:
            raise ValueError('Arquivo do Google Drive nao encontrado.') from exc

        if not self._is_within_root(item_id, metadata.get('parents', [])):
            raise ValueError('Arquivo do Google Drive nao encontrado.')
        return metadata

    def _is_within_root(self, item_id: str, parents: list[str]) -> bool:
        if item_id == self.root_folder_id:
            return True
        if item_id in self._confirmed_within_root:
            return True
        if not self.root_folder_id:
            # Raiz vazia so e permitida (ver _resolve_tenant_root_folder_id) quando
            # existe exatamente uma empresa no sistema -- nesse caso a raiz da conta
            # Google inteira E a raiz logica do tenant, entao "sem limite" e correto.
            # Se passar a existir mais de uma empresa, root_folder_id nunca fica vazio
            # (a resolucao exige configuracao explicita), entao cair aqui com root_folder_id
            # vazio so acontece no caso de empresa unica -- falha fechada em qualquer outro caso.
            return True

        if parents:
            return self._ascends_to_root(item_id, parents)

        # O Google as vezes omite/zera 'parents' no files().get() direto (acesso
        # via compartilhamento, nao por posse do item), mesmo quando o item E
        # filho real da raiz -- confirmado contra a API real. Tratar "parents
        # ausente" como "fora do escopo" nega item legitimo; tratar como "dentro
        # do escopo" reabriria o vazamento cross-tenant. Fallback: confirma por
        # busca DESCENDENTE a partir da raiz (mesma query que list_folder ja usa,
        # escopada no root_folder_id, nao depende do campo parents do item alvo).
        return self._descends_from_root(item_id)

    def _ascends_to_root(self, item_id: str, parents: list[str]) -> bool:
        pending = list(parents)
        visited = {item_id}
        while pending:
            parent_id = pending.pop()
            if parent_id == self.root_folder_id:
                return True
            if parent_id in visited:
                continue
            visited.add(parent_id)
            try:
                metadata = self.client.files().get(fileId=parent_id, fields='id, parents').execute()
            except Exception:
                return False
            pending.extend(metadata.get('parents', []))
        return False

    # shortcut: BFS descendente limitado a _MAX_DESCEND_NODES pastas visitadas --
    # arvores legitimas maiores que isso falham fechado (nega acesso) em vez de
    # custar uma varredura ilimitada. O cache em _confirmed_within_root evita
    # repetir essa varredura pra IDs ja confirmados antes.
    _MAX_DESCEND_NODES = 500

    def _descends_from_root(self, item_id: str) -> bool:
        pending: deque[str] = deque([self.root_folder_id])
        visited: set[str] = set()
        while pending and len(visited) < self._MAX_DESCEND_NODES:
            folder_id = pending.popleft()
            if folder_id in visited:
                continue
            visited.add(folder_id)
            page_token = None
            while True:
                try:
                    results = self.client.files().list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        fields="nextPageToken, files(id, mimeType)",
                        pageSize=1000,
                        pageToken=page_token
                    ).execute()
                except Exception:
                    break
                for child in results.get('files', []):
                    if child.get('id') == item_id:
                        self._confirmed_within_root.add(item_id)
                        return True
                    if child.get('mimeType') == 'application/vnd.google-apps.folder':
                        self._confirmed_within_root.add(child['id'])
                        pending.append(child['id'])
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
        return False

    def create_reserved_zip(self, file_ids: list[str]) -> io.BytesIO:
        zip_buffer = io.BytesIO()
        used_names: set[str] = set()
        skipped: list[str] = []

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_id in file_ids:
                metadata = self.get_authorized_item(file_id)

                if metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                    skipped.append(metadata.get('name', file_id))
                    continue

                file_buffer = io.BytesIO()
                request_media = self.client.files().get_media(fileId=file_id)
                downloader = MediaIoBaseDownload(file_buffer, request_media)

                done = False
                while not done:
                    _, done = downloader.next_chunk()

                filename = unique_filename(safe_filename(metadata.get('name', file_id)), used_names)
                zip_file.writestr(filename, file_buffer.getvalue())

            if skipped:
                zip_file.writestr(
                    'pastas-nao-baixadas.txt',
                    'Estas pastas foram reservadas, mas nao entram no ZIP automaticamente:\n'
                    + '\n'.join(skipped)
                )

        zip_buffer.seek(0)
        return zip_buffer

    def download_file(self, file_id: str) -> bytes:
        """Baixa somente arquivos pertencentes a pasta raiz do tenant atual."""
        metadata = self.get_authorized_item(file_id)
        if metadata.get('mimeType') == 'application/vnd.google-apps.folder':
            raise ValueError('Pastas nao podem ser baixadas como documento.')

        file_buffer = io.BytesIO()
        request_media = self.client.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(file_buffer, request_media)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return file_buffer.getvalue()

    def find_duplicate(self, name: str, md5: str, parent_folder_id: str | None) -> str | None:
        """Procura, dentro da pasta configurada, um arquivo com o MESMO nome E o
        MESMO conteudo (md5Checksum) do que esta prestes a ser enviado. So o nome
        bater nao e suficiente pra considerar duplicata -- dois arquivos diferentes
        podem ter o mesmo nome por coincidencia; o md5 e quem garante que e
        realmente o mesmo arquivo. Retorna o fileId existente, ou None se nao achar."""
        escaped_name = name.replace("'", "\\'")
        query = f"name = '{escaped_name}' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        results = self.client.files().list(
            q=query,
            fields="files(id, name, md5Checksum)",
            pageSize=10
        ).execute()

        for candidate in results.get('files', []):
            if candidate.get('md5Checksum') == md5:
                return candidate['id']

        return None

    def upload_file(self, file_bytes: bytes, name: str, mime_type: str | None, parent_folder_id: str | None) -> str:
        """Envia o arquivo de verdade pro Drive (nao e link, e copia real). Usada
        pelo upload de Documento -- substitui o disco local, que some a cada
        deploy no Render (filesystem efemero)."""
        metadata: dict = {'name': name}
        if parent_folder_id:
            metadata['parents'] = [parent_folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype=mime_type or 'application/octet-stream',
            resumable=False
        )

        created = self.client.files().create(
            body=metadata,
            media_body=media,
            fields='id'
        ).execute()

        return created['id']

    def delete_file(self, file_id: str) -> None:
        """Remove um upload novo cuja transacao de Document nao foi concluida."""
        self.client.files().delete(fileId=file_id).execute()


_drive_service_cache: dict[int, GoogleDriveService] = {}


def _build_oauth_credentials(empresa_id: int):
    """Credenciais da conta Google conectada via OAuth (a marcada is_active=True)
    DA EMPRESA INFORMADA -- sem o filtro por empresa_id, a primeira conta OAuth
    ativa no banco (de qualquer tenant) seria usada pra todo mundo. Retorna None
    se nao houver conta conectada ou se o token nao puder ser renovado -- nesses
    casos get_drive_service() cai pro credentials.json de service account, em
    vez de derrubar a rota."""
    from models.google_account import GoogleAccount  # import tardio: evita ciclo no app factory
    from services.log_service import LogService

    account = GoogleAccount.query.filter_by(empresa_id=empresa_id, is_active=True).first()
    if not account:
        return None

    try:
        refresh_token = account.get_refresh_token()
        if not refresh_token:
            return None
        # Usa os scopes realmente concedidos na conta, nao Config.GOOGLE_DRIVE_SCOPES:
        # contas conectadas antes de uma reducao de scope so tem o conjunto antigo
        # autorizado, e pedir refresh com scopes nunca concedidos o Google rejeita
        # (invalid_scope), derrubando o Drive de leitura que ja funcionava.
        granted_scopes = [s for s in (account.scopes or '').split(',') if s] or None
        credentials = OAuthCredentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=Config.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=Config.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=granted_scopes
        )
        credentials.refresh(GoogleAuthRequest())
    except Exception as exc:  # RefreshError (token revogado/expirado) ou falha de rede -- nunca derruba a rota
        LogService.warning(
            acao='oauth_refresh_failed',
            mensagem=f'Token da conta {account.email} nao renovou (revogacao/expiracao ou rede fora do ar). Reconecte em Configuracoes se persistir.',
            entidade='GoogleAccount',
            metadados={'id': account.id, 'erro': str(exc)}
        )
        _registrar_pendencia_conta_desconectada(account)
        return None

    _resolver_pendencia_conta_desconectada(account)
    return credentials


def _registrar_pendencia_conta_desconectada(account) -> None:
    """Erro em Pendencias (categoria Sistema) quando o refresh falha. Essa
    funcao roda em toda requisicao que use o Drive -- dedupe agressivo
    obrigatorio (so cria se nao houver nenhuma pendencia aberta pra essa
    conta ainda). Nunca propaga: falha aqui nao pode derrubar a rota."""
    try:
        from extensions import db
        from models.pendencia import Pendencia
        from services.automacao_regras import REGRA_CONTA_DESCONECTADA

        abertas = Pendencia.query.filter_by(
            empresa_id=account.empresa_id, status='aberta', categoria='Sistema',
        ).all()
        if any(
            isinstance(p.metadados, dict)
            and p.metadados.get('regra') == REGRA_CONTA_DESCONECTADA
            and p.metadados.get('googleAccountId') == account.id
            for p in abertas
        ):
            return
        db.session.add(Pendencia(
            empresa_id=account.empresa_id, tipo='erro', categoria='Sistema',
            origem='Automacao',
            titulo=f'Conta Google {account.email} desconectada',
            descricao=(
                f'Token da conta {account.email} nao renovou (revogacao/expiracao '
                f'ou rede fora do ar). Reconecte em Configuracoes se persistir.'
            ),
            prioridade='alta',
            metadados={'regra': REGRA_CONTA_DESCONECTADA, 'googleAccountId': account.id},
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _resolver_pendencia_conta_desconectada(account) -> None:
    """Auto-resolve a pendencia de conta desconectada na primeira chamada que
    conseguir renovar o token de novo. Nunca propaga."""
    try:
        from datetime import datetime

        from extensions import db
        from models.pendencia import Pendencia
        from services.automacao_regras import REGRA_CONTA_DESCONECTADA

        abertas = Pendencia.query.filter_by(
            empresa_id=account.empresa_id, status='aberta', categoria='Sistema',
        ).all()
        for pendencia in abertas:
            metadados = pendencia.metadados or {}
            if (
                isinstance(metadados, dict)
                and metadados.get('regra') == REGRA_CONTA_DESCONECTADA
                and metadados.get('googleAccountId') == account.id
            ):
                pendencia.status = 'resolvida'
                pendencia.resolved_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()


def _build_service_account_credentials():
    # Caminho vem exclusivamente de variavel de ambiente (Config). A escrita do
    # .env via HTTP (database_config_service) foi removida: era superficie de
    # ataque e nao tinha consumidor no frontend.
    return service_account.Credentials.from_service_account_file(
        str(Config.GOOGLE_SERVICE_ACCOUNT_FILE),
        scopes=Config.GOOGLE_DRIVE_SCOPES
    )


def get_drive_service() -> GoogleDriveService:
    """Prefere a conta OAuth ativa (multi-conta, sem precisar compartilhar pasta
    manualmente); cai pro credentials.json de service account se nao houver
    conta conectada ou o token dela estiver morto."""
    global _drive_service_cache

    empresa_id = getattr(g, 'current_empresa_id', None)
    if empresa_id is None:
        raise RuntimeError('Empresa atual nao definida para acesso ao Google Drive.')

    if empresa_id in _drive_service_cache:
        return _drive_service_cache[empresa_id]

    credentials = _build_oauth_credentials(empresa_id)
    if credentials is None:
        credentials = _build_service_account_credentials()

    root_folder_id = _resolve_tenant_root_folder_id(empresa_id)

    service = GoogleDriveService(credentials, root_folder_id)
    _drive_service_cache[empresa_id] = service
    return service


def _resolve_tenant_root_folder_id(empresa_id: int) -> str:
    from models.empresa import Empresa
    from models.setting import Setting

    setting = Setting.query.filter_by(empresa_id=empresa_id, chave='google_drive_root_folder_id').first()
    if setting and setting.valor:
        return setting.valor.strip()

    # So empresa UNICA no sistema pode ficar sem pasta configurada: nesse caso
    # nao ha outro tenant pra vazar dado, e a raiz da propria conta (OAuth ou
    # Config.GOOGLE_DRIVE_ROOT_FOLDER_ID) e um limite seguro. Com mais de uma
    # empresa, exigir configuracao explicita e o unico jeito de garantir
    # isolamento -- por isso o branch OAuth e o branch Config usam o MESMO guard.
    if Empresa.query.count() == 1:
        return Config.GOOGLE_DRIVE_ROOT_FOLDER_ID or ''

    raise RuntimeError(
        'Pasta raiz do Google Drive nao configurada para esta empresa. '
        'Defina google_drive_root_folder_id nas configuracoes do tenant.'
    )


def invalidate_drive_cache(empresa_id: int | None = None) -> None:
    """Chamado pelo oauth_service ao conectar/ativar/desconectar uma conta, pra
    forcar o proximo get_drive_service() a reconstruir com a credencial certa."""
    global _drive_service_cache
    if empresa_id is None:
        _drive_service_cache.clear()
    else:
        _drive_service_cache.pop(empresa_id, None)


