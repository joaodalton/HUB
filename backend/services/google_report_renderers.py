"""Renderizadores finos: recebem uma forma canonica de tabela (ReportTable) e
escrevem um Google Doc/Sheet/Slide de verdade via API, dentro da pasta
indicada. Cada funcao cria o arquivo nativo via Drive API (ja com o parent
certo) e depois escreve o conteudo via a API de conteudo respectiva."""
from dataclasses import dataclass

from googleapiclient.discovery import build


@dataclass
class ReportTable:
    title: str
    headers: list[str]
    rows: list[list[str]]


def _create_native_file(credentials, mime_type: str, title: str, parent_folder_id: str) -> dict:
    drive = build('drive', 'v3', credentials=credentials)
    metadata = {'name': title, 'mimeType': mime_type}
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]
    return drive.files().create(body=metadata, fields='id,webViewLink').execute()


def render_as_sheet(credentials, table: ReportTable, parent_folder_id: str) -> dict:
    created = _create_native_file(
        credentials, 'application/vnd.google-apps.spreadsheet', table.title, parent_folder_id)
    sheets = build('sheets', 'v1', credentials=credentials)
    values = [table.headers, *table.rows]
    sheets.spreadsheets().values().update(
        spreadsheetId=created['id'], range='A1', valueInputOption='RAW', body={'values': values},
    ).execute()
    return {'id': created['id'], 'webViewLink': created['webViewLink']}


def render_as_doc(credentials, table: ReportTable, parent_folder_id: str) -> dict:
    created = _create_native_file(
        credentials, 'application/vnd.google-apps.document', table.title, parent_folder_id)
    docs = build('docs', 'v1', credentials=credentials)
    lines = [table.title, '', ' | '.join(table.headers), *(' | '.join(row) for row in table.rows)]
    text = '\n'.join(lines) + '\n'
    docs.documents().batchUpdate(
        documentId=created['id'],
        body={'requests': [{'insertText': {'location': {'index': 1}, 'text': text}}]},
    ).execute()
    return {'id': created['id'], 'webViewLink': created['webViewLink']}


def render_as_slide(credentials, table: ReportTable, parent_folder_id: str) -> dict:
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
    slides.presentations().batchUpdate(presentationId=created['id'], body={'requests': requests}).execute()
    return {'id': created['id'], 'webViewLink': created['webViewLink']}
