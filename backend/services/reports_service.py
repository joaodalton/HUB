"""Orquestra a geracao de relatorio: resolve credencial/scope, resolve pasta
de destino, coleta dado via services de dominio ja existentes (zero
duplicacao de query) e delega ao renderizador certo. _coletar_* ficam neste
mesmo arquivo nas Tasks 5-7 (cadastro, financeiro, rateio)."""
from services.drive_service import _resolve_tenant_root_folder_id
from services.google_reports_auth import get_report_credentials
from services.google_report_renderers import ReportTable, render_as_doc, render_as_sheet, render_as_slide
from services.client_service import list_clients
from services.uc_service import list_ucs
from services.plant_service import list_plants

_RENDERERS = {'doc': 'render_as_doc', 'sheet': 'render_as_sheet', 'slide': 'render_as_slide'}
_TIPOS_VALIDOS = {'cadastro', 'financeiro', 'rateio'}
_COLETORES = {}  # populado pelas Tasks 5-7: {'cadastro': _coletar_cadastro, ...}


def _pasta_relatorios(empresa_id: int) -> str:
    raiz = _resolve_tenant_root_folder_id(allow_account_root=True)
    # Nesta primeira entrega os arquivos vao direto na raiz do tenant (mesma
    # pasta que o Drive ja usa) -- criar uma subpasta dedicada "Relatorios HUB"
    # fica pra uma iteracao futura se o volume de relatorios justificar.
    return raiz


def _mascarar_documento(valor: str | None) -> str:
    if not valor:
        return ''
    digitos = ''.join(ch for ch in valor if ch.isdigit())
    if len(digitos) < 4:
        return '***'
    return f'***.***.{digitos[-4:-2]}-{digitos[-2:]}' if len(digitos) == 11 else f'***{digitos[-4:]}'


def _coletar_cadastro(empresa_id: int, competencia: str | None) -> ReportTable:
    linhas = []
    for cliente in list_clients():
        linhas.append(['Cliente', cliente.get('nome') or '', _mascarar_documento(cliente.get('documento'))])
    for uc in list_ucs():
        linhas.append(['UC', uc.get('codigo') or '', ''])
    for usina in list_plants():
        linhas.append(['Usina', usina.get('nome') or '', ''])
    return ReportTable(title='Relatorio de Cadastro', headers=['Tipo', 'Nome', 'Documento (mascarado)'], rows=linhas)


_COLETORES['cadastro'] = '_coletar_cadastro'


def gerar_relatorio(empresa_id: int, tipo: str, formato: str, competencia: str | None = None) -> dict:
    if tipo not in _TIPOS_VALIDOS:
        raise ValueError('Tipo de relatorio invalido.')
    if formato not in _RENDERERS:
        raise ValueError('Formato invalido.')

    credentials = get_report_credentials(empresa_id)
    pasta = _pasta_relatorios(empresa_id)
    # _COLETORES/_RENDERERS guardam o NOME da funcao (nao a referencia) para
    # que @patch('services.reports_service._coletar_X'/'render_as_X') em
    # teste funcione: a resolucao via globals() acontece a cada chamada,
    # apos o patch ja ter substituido o atributo do modulo.
    tabela = globals()[_COLETORES[tipo]](empresa_id, competencia)
    resultado = globals()[_RENDERERS[formato]](credentials, tabela, parent_folder_id=pasta)
    return {'driveFileId': resultado['id'], 'webViewLink': resultado['webViewLink']}
