"""Renderizadores finos: recebem uma forma canonica de tabela (ReportTable) e
escrevem um Google Doc/Sheet/Slide de verdade via API, dentro da pasta
indicada. Cada funcao cria o arquivo nativo via Drive API (ja com o parent
certo) e depois escreve o conteudo via a API de conteudo respectiva."""
from dataclasses import dataclass

from googleapiclient.discovery import build

from services.report_templates import ReportTemplate, default_template

# Marcador que a empresa escreve no PROPRIO arquivo (Google Doc existente, ou
# .docx que ela sobe) pra indicar onde a tabela de dados entra -- ver
# render_as_doc_from_template() e office_report_renderers.render_as_docx_from_template().
MARCADOR_TABELA = '{{TABELA}}'


@dataclass
class ReportTable:
    title: str
    headers: list[str]
    rows: list[list[str]]


def _hex_to_rgb01(hex_color: str) -> dict:
    return {
        'red': int(hex_color[0:2], 16) / 255,
        'green': int(hex_color[2:4], 16) / 255,
        'blue': int(hex_color[4:6], 16) / 255,
    }


def _create_native_file(credentials, mime_type: str, title: str, parent_folder_id: str) -> dict:
    drive = build('drive', 'v3', credentials=credentials)
    metadata = {'name': title, 'mimeType': mime_type}
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]
    return drive.files().create(body=metadata, fields='id,webViewLink').execute()


def render_as_sheet(credentials, table: ReportTable, parent_folder_id: str, template: ReportTemplate | None = None) -> dict:
    template = template or default_template()
    created = _create_native_file(
        credentials, 'application/vnd.google-apps.spreadsheet', table.title, parent_folder_id)
    sheets = build('sheets', 'v4', credentials=credentials)
    values = [table.headers, *table.rows]
    sheets.spreadsheets().values().update(
        spreadsheetId=created['id'], range='A1', valueInputOption='RAW', body={'values': values},
    ).execute()
    if template.accent_hex:
        sheets.spreadsheets().batchUpdate(spreadsheetId=created['id'], body={'requests': [{
            'repeatCell': {
                'range': {'sheetId': 0, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': max(len(table.headers), 1)},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': _hex_to_rgb01(template.accent_hex),
                    'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                }},
                'fields': 'userEnteredFormat(backgroundColor,textFormat)',
            }
        }]}).execute()
    return {'id': created['id'], 'webViewLink': created['webViewLink']}


def render_as_doc(credentials, table: ReportTable, parent_folder_id: str, template: ReportTemplate | None = None) -> dict:
    template = template or default_template()
    created = _create_native_file(
        credentials, 'application/vnd.google-apps.document', table.title, parent_folder_id)
    docs = build('docs', 'v1', credentials=credentials)
    lines = [table.title, '', ' | '.join(table.headers), *(' | '.join(row) for row in table.rows)]
    text = '\n'.join(lines) + '\n'

    offsets = []
    cursor = 1
    for line in lines:
        offsets.append((cursor, cursor + len(line)))
        cursor += len(line) + 1
    title_start, title_end = offsets[0]
    header_start, header_end = offsets[2]

    requests = [{'insertText': {'location': {'index': 1}, 'text': text}}]
    if template.accent_hex:
        color = {'color': {'rgbColor': _hex_to_rgb01(template.accent_hex)}}
        for start, end in ((title_start, title_end), (header_start, header_end)):
            if end > start:
                requests.append({'updateTextStyle': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'textStyle': {'bold': True, 'foregroundColor': color},
                    'fields': 'bold,foregroundColor',
                }})
    docs.documents().batchUpdate(documentId=created['id'], body={'requests': requests}).execute()
    return {'id': created['id'], 'webViewLink': created['webViewLink']}


def _localizar_marcador(documento: dict, marcador: str) -> tuple[int | None, int | None]:
    """Varre os paragrafos do corpo do documento procurando o texto do
    marcador, devolve o range absoluto (startIndex, endIndex) dele no
    documento. Assume que o marcador fica inteiro dentro de um unico
    textRun (nao quebrado por formatacao parcial) -- suficiente pro caso de
    uso real (usuario digita o marcador como texto simples)."""
    for elemento in documento.get('body', {}).get('content', []):
        paragrafo = elemento.get('paragraph')
        if not paragrafo:
            continue
        texto = ''
        runs = []
        for el in paragrafo.get('elements', []):
            run = el.get('textRun')
            if not run:
                continue
            conteudo = run.get('content', '')
            runs.append((el.get('startIndex'), conteudo))
            texto += conteudo
        posicao = texto.find(marcador)
        if posicao == -1:
            continue
        cursor = 0
        for start_index, conteudo in runs:
            if cursor <= posicao < cursor + len(conteudo):
                marcador_start = start_index + (posicao - cursor)
                return marcador_start, marcador_start + len(marcador)
            cursor += len(conteudo)
    return None, None


def _localizar_celulas_tabela(documento: dict) -> dict[tuple[int, int], int]:
    """Acha a PRIMEIRA tabela do corpo do documento e devolve, pra cada
    celula, o startIndex do primeiro elemento de texto dela -- e onde um
    insertText precisa apontar pra escrever dentro daquela celula."""
    for elemento in documento.get('body', {}).get('content', []):
        tabela = elemento.get('table')
        if not tabela:
            continue
        celulas: dict[tuple[int, int], int] = {}
        for linha_idx, linha in enumerate(tabela.get('tableRows', [])):
            for col_idx, celula in enumerate(linha.get('tableCells', [])):
                conteudo = celula.get('content', [])
                if not conteudo:
                    continue
                elementos = conteudo[0].get('paragraph', {}).get('elements', [])
                if elementos:
                    celulas[(linha_idx, col_idx)] = elementos[0].get('startIndex')
        return celulas
    return {}


def _copiar_arquivo_do_drive(drive, drive_file_id: str, titulo: str, parent_folder_id: str) -> dict:
    metadata = {'name': titulo}
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]
    return drive.files().copy(fileId=drive_file_id, body=metadata, fields='id,webViewLink').execute()


def render_as_doc_from_template(credentials, drive_file_id: str, table: ReportTable, parent_folder_id: str) -> dict:
    """Copia o Google Doc que JA e da empresa (ela que escolheu, em
    Relatorios > Templates), troca o marcador MARCADOR_TABELA por uma
    tabela de verdade com os dados -- preserva 100% da formatacao/marca da
    empresa, a gente so entra com a tabela."""
    drive = build('drive', 'v3', credentials=credentials)
    copiado = _copiar_arquivo_do_drive(drive, drive_file_id, table.title, parent_folder_id)
    novo_id = copiado['id']

    docs = build('docs', 'v1', credentials=credentials)
    documento = docs.documents().get(documentId=novo_id).execute()
    marcador_start, marcador_end = _localizar_marcador(documento, MARCADOR_TABELA)
    if marcador_start is None:
        raise ValueError(f'O template nao tem o marcador {MARCADOR_TABELA} em nenhum paragrafo.')

    cols = max(len(table.headers), 1)
    linhas_tabela = len(table.rows) + 1
    docs.documents().batchUpdate(documentId=novo_id, body={'requests': [
        {'deleteContentRange': {'range': {'startIndex': marcador_start, 'endIndex': marcador_end}}},
        {'insertTable': {'rows': linhas_tabela, 'columns': cols, 'location': {'index': marcador_start}}},
    ]}).execute()

    documento = docs.documents().get(documentId=novo_id).execute()
    celulas = _localizar_celulas_tabela(documento)

    valores = [table.headers, *table.rows]
    requests = []
    for linha_idx in range(len(valores) - 1, -1, -1):
        linha = valores[linha_idx]
        for col_idx in range(len(linha) - 1, -1, -1):
            valor = linha[col_idx]
            start_index = celulas.get((linha_idx, col_idx))
            if not valor or start_index is None:
                continue
            requests.append({'insertText': {'location': {'index': start_index}, 'text': str(valor)}})
    if requests:
        docs.documents().batchUpdate(documentId=novo_id, body={'requests': requests}).execute()

    return {'id': novo_id, 'webViewLink': copiado['webViewLink']}


def render_as_slide(credentials, table: ReportTable, parent_folder_id: str, template: ReportTemplate | None = None) -> dict:
    template = template or default_template()
    created = _create_native_file(
        credentials, 'application/vnd.google-apps.presentation', table.title, parent_folder_id)
    slides = build('slides', 'v1', credentials=credentials)
    rows = len(table.rows) + 1
    cols = max(len(table.headers), 1)
    slide_id = 'reportSlide'
    table_id = 'reportTable'
    requests = [
        {'createSlide': {'objectId': slide_id, 'insertionIndex': 0}},
        {'createTable': {'objectId': table_id, 'elementProperties': {'pageObjectId': slide_id}, 'rows': rows, 'columns': cols}},
    ]
    for col_index, header in enumerate(table.headers):
        if header:
            requests.append({'insertText': {'objectId': table_id, 'cellLocation': {'rowIndex': 0, 'columnIndex': col_index}, 'text': header}})
    for row_index, row in enumerate(table.rows, start=1):
        for col_index, value in enumerate(row):
            if value:
                requests.append({'insertText': {'objectId': table_id, 'cellLocation': {'rowIndex': row_index, 'columnIndex': col_index}, 'text': value}})
    if template.accent_hex:
        color = {'rgbColor': _hex_to_rgb01(template.accent_hex)}
        for col_index in range(cols):
            requests.append({'updateTableCellProperties': {
                'objectId': table_id,
                'tableRange': {'location': {'rowIndex': 0, 'columnIndex': col_index}, 'rowSpan': 1, 'columnSpan': 1},
                'tableCellProperties': {'tableCellBackgroundFill': {'solidFill': {'color': color}}},
                'fields': 'tableCellBackgroundFill.solidFill.color',
            }})
            header_len = len(table.headers[col_index] or '')
            if header_len:
                requests.append({'updateTextStyle': {
                    'objectId': table_id,
                    'cellLocation': {'rowIndex': 0, 'columnIndex': col_index},
                    'textRange': {'type': 'FIXED_RANGE', 'startIndex': 0, 'endIndex': header_len},
                    'style': {'bold': True, 'foregroundColor': {'opaqueColor': {'rgbColor': _hex_to_rgb01('FFFFFF')}}},
                    'fields': 'bold,foregroundColor',
                }})
    slides.presentations().batchUpdate(presentationId=created['id'], body={'requests': requests}).execute()
    return {'id': created['id'], 'webViewLink': created['webViewLink']}


def _coluna_para_letra_a1(indice: int) -> str:
    letras = ''
    indice += 1
    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _localizar_marcador_sheet(planilha: dict, marcador: str) -> tuple[int, str, int, int] | None:
    """Varre os dados (includeGridData) de cada aba procurando uma celula
    com o texto exato do marcador. Devolve (sheetId, titulo da aba, linha,
    coluna), todos 0-based."""
    for sheet in planilha.get('sheets', []):
        sheet_id = sheet['properties']['sheetId']
        sheet_title = sheet['properties']['title']
        for row_idx, row_data in enumerate(sheet.get('data', [{}])[0].get('rowData', []) if sheet.get('data') else []):
            for col_idx, cell_data in enumerate(row_data.get('values', [])):
                valor = cell_data.get('formattedValue')
                if valor == marcador:
                    return sheet_id, sheet_title, row_idx, col_idx
    return None


def render_as_sheet_from_template(credentials, drive_file_id: str, table: ReportTable, parent_folder_id: str) -> dict:
    """Copia a planilha que JA e da empresa, escreve a tabela a partir da
    celula que tem o marcador MARCADOR_TABELA (sobrescreve o marcador com o
    cabecalho) -- preserva 100% da formatacao/marca da empresa."""
    drive = build('drive', 'v3', credentials=credentials)
    copiado = _copiar_arquivo_do_drive(drive, drive_file_id, table.title, parent_folder_id)
    novo_id = copiado['id']

    sheets = build('sheets', 'v4', credentials=credentials)
    planilha = sheets.spreadsheets().get(spreadsheetId=novo_id, includeGridData=True).execute()
    localizacao = _localizar_marcador_sheet(planilha, MARCADOR_TABELA)
    if localizacao is None:
        raise ValueError(f'O template nao tem o marcador {MARCADOR_TABELA} em nenhuma celula.')
    _sheet_id, sheet_title, linha, coluna = localizacao

    valores = [table.headers, *table.rows]
    range_a1 = f"'{sheet_title}'!{_coluna_para_letra_a1(coluna)}{linha + 1}"
    sheets.spreadsheets().values().update(
        spreadsheetId=novo_id, range=range_a1, valueInputOption='RAW', body={'values': valores},
    ).execute()

    return {'id': novo_id, 'webViewLink': copiado['webViewLink']}


def _localizar_marcador_slide(apresentacao: dict, marcador: str) -> tuple[str, str, dict, dict] | None:
    """Varre os shapes de cada slide procurando um com o texto do
    marcador. Devolve (pageObjectId, shapeObjectId, transform, size) do
    PRIMEIRO shape encontrado -- usado pra criar a tabela na mesma posicao."""
    for slide in apresentacao.get('slides', []):
        page_id = slide.get('objectId')
        for elemento in slide.get('pageElements', []):
            shape = elemento.get('shape')
            if not shape:
                continue
            texto = ''.join(
                te.get('textRun', {}).get('content', '')
                for te in shape.get('text', {}).get('textElements', [])
            )
            if marcador in texto:
                return page_id, elemento['objectId'], elemento.get('transform'), elemento.get('size')
    return None


def render_as_slide_from_template(credentials, drive_file_id: str, table: ReportTable, parent_folder_id: str) -> dict:
    """Copia a apresentacao que JA e da empresa, troca o SHAPE que tem o
    marcador MARCADOR_TABELA por uma tabela de verdade, na mesma posicao e
    tamanho do shape original -- preserva 100% do slide master/layout da
    empresa."""
    drive = build('drive', 'v3', credentials=credentials)
    copiado = _copiar_arquivo_do_drive(drive, drive_file_id, table.title, parent_folder_id)
    novo_id = copiado['id']

    slides = build('slides', 'v1', credentials=credentials)
    apresentacao = slides.presentations().get(presentationId=novo_id).execute()
    localizacao = _localizar_marcador_slide(apresentacao, MARCADOR_TABELA)
    if localizacao is None:
        raise ValueError(f'O template nao tem o marcador {MARCADOR_TABELA} em nenhum slide.')
    page_id, shape_id, transform, size = localizacao

    # createTable exige scaleX/scaleY == 1 na transform -- o shape original
    # pode ter escala/rotacao residual (ex.: de arrastar na UI do Slides),
    # entao so aproveita a POSICAO dele (translateX/translateY) e descarta
    # o resto; o tamanho vem do 'size' (nao escalado), que sim e respeitado.
    transform_tabela = {
        'scaleX': 1, 'scaleY': 1,
        'translateX': (transform or {}).get('translateX', 0),
        'translateY': (transform or {}).get('translateY', 0),
        'unit': (transform or {}).get('unit', 'EMU'),
    }

    rows = len(table.rows) + 1
    cols = max(len(table.headers), 1)
    table_id = 'reportTable'
    requests = [
        {'deleteObject': {'objectId': shape_id}},
        {'createTable': {
            'objectId': table_id,
            'elementProperties': {'pageObjectId': page_id, 'size': size, 'transform': transform_tabela},
            'rows': rows, 'columns': cols,
        }},
    ]
    for col_index, header in enumerate(table.headers):
        if header:
            requests.append({'insertText': {'objectId': table_id, 'cellLocation': {'rowIndex': 0, 'columnIndex': col_index}, 'text': header}})
    for row_index, row in enumerate(table.rows, start=1):
        for col_index, value in enumerate(row):
            if value:
                requests.append({'insertText': {'objectId': table_id, 'cellLocation': {'rowIndex': row_index, 'columnIndex': col_index}, 'text': value}})
    slides.presentations().batchUpdate(presentationId=novo_id, body={'requests': requests}).execute()

    return {'id': novo_id, 'webViewLink': copiado['webViewLink']}
