"""Orquestra a geracao de relatorio: resolve credencial/scope, resolve pasta
de destino, coleta dado via services de dominio ja existentes (zero
duplicacao de query) e delega ao renderizador certo. _coletar_* ficam neste
mesmo arquivo nas Tasks 5-7 (cadastro, financeiro, rateio)."""
import re

from services.drive_service import _resolve_tenant_root_folder_id
from services.google_reports_auth import get_report_credentials
from services.google_report_renderers import (
    ReportTable, render_as_doc, render_as_doc_from_template, render_as_sheet, render_as_sheet_from_template,
    render_as_slide, render_as_slide_from_template,
)
from services.office_report_renderers import (
    render_as_docx, render_as_docx_from_template, render_as_pptx, render_as_pptx_from_template,
    render_as_xlsx, render_as_xlsx_from_template,
)
from services.client_service import list_clients
from services.uc_service import list_ucs
from services.plant_service import list_plants
from services.fatura_service import listar as listar_faturas
from services.rateio_service import list_historico as list_historico_rateio
from services.report_template_service import get_template
from services.report_source_template_service import resolve_drive_file_id, resolve_upload_bytes

_RENDERERS = {'doc': render_as_doc, 'sheet': render_as_sheet, 'slide': render_as_slide}
_OFFICE_RENDERERS = {'docx': render_as_docx, 'xlsx': render_as_xlsx, 'pptx': render_as_pptx}
_OFFICE_MIMETYPES = {
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}
# Categoria do template de ORIGEM (Relatorios > Templates) por formato --
# doc/docx usam a mesma categoria 'documento' (mesmo conteudo, dois
# formatos de arquivo), idem sheet/xlsx 'planilha' e slide/pptx 'apresentacao'.
_FORMATO_CATEGORIA = {
    'doc': 'documento', 'docx': 'documento',
    'sheet': 'planilha', 'xlsx': 'planilha',
    'slide': 'apresentacao', 'pptx': 'apresentacao',
}
def _render_from_template_google(formato: str, credentials, drive_file_id: str, tabela, pasta: str) -> dict:
    # if/elif em vez de dict de funcoes: um dict capturaria a funcao original
    # na importacao do modulo, e um teste que faz @patch('...render_as_doc_from_template')
    # nao afetaria mais essa referencia ja capturada. Nomes soltos aqui sao
    # resolvidos no namespace do modulo a cada chamada, entao o patch funciona.
    if formato == 'doc':
        return render_as_doc_from_template(credentials, drive_file_id, tabela, parent_folder_id=pasta)
    if formato == 'sheet':
        return render_as_sheet_from_template(credentials, drive_file_id, tabela, parent_folder_id=pasta)
    return render_as_slide_from_template(credentials, drive_file_id, tabela, parent_folder_id=pasta)


def _render_from_template_office(formato: str, template_bytes: bytes, tabela) -> bytes:
    if formato == 'docx':
        return render_as_docx_from_template(template_bytes, tabela)
    if formato == 'xlsx':
        return render_as_xlsx_from_template(template_bytes, tabela)
    return render_as_pptx_from_template(template_bytes, tabela)
_TIPOS_VALIDOS = {'cadastro', 'financeiro', 'rateio', 'producao'}
_MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
_COLETORES = {}  # populado pelas Tasks 5-7: {'cadastro': _coletar_cadastro, ...}


def _slugify_filename(titulo: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]+', '_', titulo).strip('_') or 'relatorio'


def _todos(list_fn, *args, **kwargs) -> list[dict]:
    """list_clients/list_ucs/list_plants agora paginam (page/pageSize) e
    retornam (itens, pagination). Relatorio precisa de TODOS os registros --
    percorre as paginas no tamanho maximo em vez de assumir lista completa
    de uma vez."""
    page, page_size, itens = 1, 200, []
    while True:
        pagina, pagination = list_fn(*args, page=page, page_size=page_size, **kwargs)
        itens.extend(pagina)
        if page >= pagination['pages']:
            break
        page += 1
    return itens


def _pasta_relatorios(empresa_id: int) -> str:
    raiz = _resolve_tenant_root_folder_id(empresa_id)
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
    for cliente in _todos(list_clients):
        linhas.append(['Cliente', cliente.get('nome') or '', _mascarar_documento(cliente.get('cpf'))])
    for uc in _todos(list_ucs):
        linhas.append(['UC', uc.get('codigo') or '', ''])
    for usina in _todos(list_plants):
        linhas.append(['Usina', usina.get('nome') or '', ''])
    return ReportTable(title='Relatorio de Cadastro', headers=['Tipo', 'Nome', 'Documento (mascarado)'], rows=linhas)


_COLETORES['cadastro'] = _coletar_cadastro


def _coletar_financeiro(empresa_id: int, competencia: str | None) -> ReportTable:
    filtros = {'competencia': competencia} if competencia else {}
    faturas = listar_faturas(empresa_id, filtros)
    linhas = []
    for fatura in faturas:
        valor = fatura.get('valor')
        valor_str = f'{valor:.2f}' if valor is not None else ''
        linhas.append([
            fatura.get('competencia') or '',
            fatura.get('clienteNome') or '',
            fatura.get('ucCodigo') or '',
            valor_str,
            fatura.get('mesVencimento') or '',
            fatura.get('statusInterno') or '',
            fatura.get('asaasStatus') or '',
        ])
    return ReportTable(
        title='Relatorio Financeiro',
        headers=['Competencia', 'Cliente', 'UC', 'Valor', 'Vencimento', 'Status Emissão', 'Status Pagamento'],
        rows=linhas,
    )


_COLETORES['financeiro'] = _coletar_financeiro


def _coletar_rateio(empresa_id: int, competencia: str | None) -> ReportTable:
    historico = list_historico_rateio(competencia=competencia)
    linhas = [
        [item.get('competencia') or '', item.get('usinaNome') or '', item.get('ucCodigo') or '', f"{item.get('percentual', 0)}%"]
        for item in historico
    ]
    return ReportTable(title='Relatorio de Rateio', headers=['Competencia', 'Usina', 'UC', 'Percentual'], rows=linhas)


_COLETORES['rateio'] = _coletar_rateio


def _coletar_producao(empresa_id: int, competencia: str | None) -> ReportTable:
    linhas = []
    for usina in _todos(list_plants):
        mensal = usina.get('producaoMensal') or {}
        media = usina.get('producaoMedia')
        linhas.append([
            usina.get('nome') or '',
            f"{usina.get('kwPico', 0):.2f}",
            *[f'{mensal.get(mes, 0):.2f}' for mes in _MESES],
            f'{media:.2f}' if media is not None else '',
        ])
    return ReportTable(
        title='Estimativa de Produção',
        headers=['Usina', 'kWp', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Média'],
        rows=linhas,
    )


_COLETORES['producao'] = _coletar_producao


def gerar_relatorio(empresa_id: int, tipo: str, formato: str, competencia: str | None = None, template_id: str | None = None) -> dict:
    if tipo not in _TIPOS_VALIDOS:
        raise ValueError('Tipo de relatorio invalido.')
    if formato not in _RENDERERS:
        raise ValueError('Formato invalido.')

    credentials = get_report_credentials(empresa_id)
    pasta = _pasta_relatorios(empresa_id)
    tabela = _COLETORES[tipo](empresa_id, competencia)

    # Se a empresa configurou um arquivo PROPRIO do Google Drive como origem
    # pra esta categoria (Relatorios > Templates), usa ele em vez de gerar
    # do zero -- preserva a marca da empresa, a cor do template (abaixo)
    # nunca se aplica nesse caminho.
    drive_file_id = resolve_drive_file_id(_FORMATO_CATEGORIA[formato], empresa_id)
    if drive_file_id:
        resultado = _render_from_template_google(formato, credentials, drive_file_id, tabela, pasta)
        return {'driveFileId': resultado['id'], 'webViewLink': resultado['webViewLink']}

    template = get_template(template_id, empresa_id)
    resultado = _RENDERERS[formato](credentials, tabela, parent_folder_id=pasta, template=template)
    return {'driveFileId': resultado['id'], 'webViewLink': resultado['webViewLink']}


def gerar_relatorio_arquivo(empresa_id: int, tipo: str, formato: str, competencia: str | None = None, template_id: str | None = None) -> tuple[bytes, str, str]:
    """Gera o relatorio localmente (docx/xlsx/pptx), sem depender de credencial
    Google -- reaproveita o mesmo coletor usado pelos formatos nativos."""
    if tipo not in _TIPOS_VALIDOS:
        raise ValueError('Tipo de relatorio invalido.')
    if formato not in _OFFICE_RENDERERS:
        raise ValueError('Formato invalido.')

    tabela = _COLETORES[tipo](empresa_id, competencia)

    # Mesma logica do formato Google em gerar_relatorio() -- se tem arquivo
    # office proprio configurado pra esta categoria, usa ele.
    template_bytes = resolve_upload_bytes(_FORMATO_CATEGORIA[formato], empresa_id)
    if template_bytes:
        dados = _render_from_template_office(formato, template_bytes, tabela)
        filename = f'{_slugify_filename(tabela.title)}.{formato}'
        return dados, filename, _OFFICE_MIMETYPES[formato]

    template = get_template(template_id, empresa_id)
    dados = _OFFICE_RENDERERS[formato](tabela, template=template)
    filename = f'{_slugify_filename(tabela.title)}.{formato}'
    return dados, filename, _OFFICE_MIMETYPES[formato]
