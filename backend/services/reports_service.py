"""Orquestra a geracao de relatorio: resolve credencial/scope, resolve pasta
de destino, coleta dado via services de dominio ja existentes (zero
duplicacao de query) e delega ao renderizador certo. _coletar_* ficam neste
mesmo arquivo nas Tasks 5-7 (cadastro, financeiro, rateio)."""
from services.drive_service import _resolve_tenant_root_folder_id
from services.google_reports_auth import get_report_credentials
from services.google_report_renderers import render_as_doc, render_as_sheet, render_as_slide

_RENDERERS = {'doc': render_as_doc, 'sheet': render_as_sheet, 'slide': render_as_slide}
_TIPOS_VALIDOS = {'cadastro', 'financeiro', 'rateio'}
_COLETORES = {}  # populado pelas Tasks 5-7: {'cadastro': _coletar_cadastro, ...}


def _pasta_relatorios(empresa_id: int) -> str:
    raiz = _resolve_tenant_root_folder_id(allow_account_root=True)
    # Nesta primeira entrega os arquivos vao direto na raiz do tenant (mesma
    # pasta que o Drive ja usa) -- criar uma subpasta dedicada "Relatorios HUB"
    # fica pra uma iteracao futura se o volume de relatorios justificar.
    return raiz


def gerar_relatorio(empresa_id: int, tipo: str, formato: str, competencia: str | None = None) -> dict:
    if tipo not in _TIPOS_VALIDOS:
        raise ValueError('Tipo de relatorio invalido.')
    if formato not in _RENDERERS:
        raise ValueError('Formato invalido.')

    credentials = get_report_credentials(empresa_id)
    pasta = _pasta_relatorios(empresa_id)
    tabela = _COLETORES[tipo](empresa_id, competencia)
    resultado = _RENDERERS[formato](credentials, tabela, parent_folder_id=pasta)
    return {'driveFileId': resultado['id'], 'webViewLink': resultado['webViewLink']}
