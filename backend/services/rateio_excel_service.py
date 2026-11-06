"""Preenche o formulário oficial Copel de associações em XLSX."""
import io
import re
from copy import copy
from datetime import date
from pathlib import Path

from flask import g
from openpyxl import load_workbook
from openpyxl.worksheet.cell_range import CellRange

from models.empresa import Empresa
from services.rateio_formulario_service import get_regras_documentos_rateio, montar_tabela_formulario, verificar_termos_adesao

ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
XLSX_TEMPLATE_NAME = 'formulario_copel_rateio.xlsx'
LINHA_INICIAL = 17
LINHA_TOTAL = 41
LINHAS_PRE_FORMATADAS = 24


def _template_path() -> Path:
    path = ASSETS_DIR / XLSX_TEMPLATE_NAME
    if not path.is_file():
        raise ValueError('Modelo XLSX do formulário Copel não encontrado em backend/assets.')
    return path


def _carregar_modelo():
    return load_workbook(_template_path())


def _validar(tabela: dict, plant_id: int) -> None:
    regras = {**get_regras_documentos_rateio(), **tabela.get('regrasDocumentos', {})}
    faltando = []
    if not tabela.get('ucGeradora'):
        faltando.append('UC da usina')
    if regras['documentoCnpjObrigatorio'] and not tabela.get('documentoCnpjOk'):
        faltando.append('CNPJ da empresa')
    if regras['documentoEstatutoObrigatorio'] and not tabela.get('documentoEstatutoOk'):
        faltando.append('Estatuto da empresa')
    if faltando:
        raise ValueError(f'Pré-requisitos faltando: {", ".join(faltando)}.')
    soma = round(sum(float(linha.get('percentual') or 0) for linha in tabela['linhas']), 2)
    if soma > 100:
        raise ValueError(f'Soma dos percentuais desta usina é {soma}% -- excede 100%. Ajuste antes de gerar.')
    if regras['termosAdesaoObrigatorios']:
        verificacao = verificar_termos_adesao(plant_id)
        if not verificacao['ok']:
            nomes = ', '.join(item['nome'] for item in verificacao['faltando'])
            raise ValueError(f'Termo de Adesão faltando para: {nomes}. Geração bloqueada.')


def _aplicar_linhas_override(tabela: dict, linhas_override: list[dict] | None) -> None:
    if linhas_override is None:
        return
    if not isinstance(linhas_override, list):
        raise ValueError('Linhas de revisão inválidas.')
    por_uc = {item.get('ucId'): item for item in linhas_override if isinstance(item, dict) and item.get('ucId') is not None}
    for linha in tabela['linhas']:
        override = por_uc.get(linha['ucId'])
        if not override:
            continue
        for campo in ('nome', 'documento', 'ucIdentificacao'):
            if campo in override:
                linha[campo] = str(override[campo] or '').strip()
        if 'percentual' in override:
            try:
                percentual = float(override['percentual'])
            except (TypeError, ValueError) as exc:
                raise ValueError('Percentual visual inválido no formulário.') from exc
            if not 0 <= percentual <= 100:
                raise ValueError('Percentual visual deve estar entre 0 e 100.')
            linha['percentual'] = percentual
    tabela['somaPercentual'] = round(sum(float(linha['percentual']) for linha in tabela['linhas']), 2)


def montar_preview_formulario(plant_id: int) -> dict:
    """Dados de leitura para a revisão, incluindo a linha fixa da associação."""
    tabela = montar_tabela_formulario(plant_id)
    associacao = {
        'ordem': 1, 'nome': tabela['empresaNome'], 'documento': tabela['empresaCnpj'],
        'ucIdentificacao': tabela['ucGeradora'], 'percentual': 0.0, 'termoAdesaoOk': None,
        'clienteId': None, 'ucId': None, 'fixa': True,
    }
    linhas = [{**linha, 'ordem': linha['ordem'] + 1} for linha in tabela['linhas']]
    total_linhas = len(linhas) + 1
    avisos = [f'A planilha será expandida para {total_linhas} linhas.'] if total_linhas > LINHAS_PRE_FORMATADAS else []
    return {**tabela, 'associacao': associacao, 'linhas': linhas, 'somaPercentual': round(sum(l['percentual'] for l in linhas), 2), 'avisos': avisos}


def _substituir_placeholder(celula, pattern: str, valor: str, descricao: str) -> None:
    preenchido, substituicoes = re.subn(pattern, valor, str(celula.value or ''), count=1)
    if substituicoes != 1:
        raise ValueError(f'Placeholder de {descricao} não encontrado no modelo XLSX atual.')
    celula.value = preenchido


def _inserir_linhas_tabela(worksheet, extras: int) -> None:
    if not extras:
        return
    merges = [CellRange(str(merge)) for merge in worksheet.merged_cells.ranges if merge.max_row >= LINHA_TOTAL]
    for merge in merges:
        worksheet.unmerge_cells(str(merge))
    worksheet.insert_rows(LINHA_TOTAL, extras)
    for linha in range(LINHA_TOTAL, LINHA_TOTAL + extras):
        worksheet.row_dimensions[linha].height = worksheet.row_dimensions[LINHA_TOTAL - 1].height
        for coluna in range(1, 6):
            origem, destino = worksheet.cell(LINHA_TOTAL - 1, coluna), worksheet.cell(linha, coluna)
            destino._style = copy(origem._style)
            destino.number_format = origem.number_format
            destino.alignment = copy(origem.alignment)
            destino.protection = copy(origem.protection)
    for merge in merges:
        merge.shift(0, extras)
        worksheet.merge_cells(str(merge))


def gerar_formulario_excel(plant_id: int, responsavel_nome: str, responsavel_cpf: str,
                           linhas_override: list[dict] | None = None, excedente_energia: bool = False) -> bytes:
    if not responsavel_nome.strip() or not responsavel_cpf.strip():
        raise ValueError('Nome e CPF do responsável são obrigatórios.')
    tabela = montar_tabela_formulario(plant_id)
    _aplicar_linhas_override(tabela, linhas_override)
    _validar(tabela, plant_id)
    linhas = [{'ordem': 1, 'nome': tabela['empresaNome'], 'documento': tabela['empresaCnpj'],
               'ucIdentificacao': tabela['ucGeradora'], 'percentual': 0.0}] + [
        {**linha, 'ordem': linha['ordem'] + 1} for linha in tabela['linhas']
    ]
    workbook = _carregar_modelo()
    worksheet = workbook.active
    extras = max(0, len(linhas) - LINHAS_PRE_FORMATADAS)
    _inserir_linhas_tabela(worksheet, extras)
    _substituir_placeholder(worksheet['A4'], r'_{3,}', str(tabela['ucGeradora']), 'UC geradora')
    _substituir_placeholder(worksheet['A8'], r'_{3,}', str(tabela['ucAncora']), 'UC beneficiária âncora')
    worksheet['A11'] = 'SIM' if excedente_energia else 'NÃO'
    for linha in linhas:
        linha_excel = LINHA_INICIAL + linha['ordem'] - 1
        worksheet.cell(linha_excel, 1).value = linha['ordem']
        worksheet.cell(linha_excel, 2).value = linha['nome'] or ''
        worksheet.cell(linha_excel, 3).value = linha['documento'] or ''
        worksheet.cell(linha_excel, 4).value = linha['ucIdentificacao'] or ''
        worksheet.cell(linha_excel, 5).value = round(float(linha['percentual']) / 100, 4)
        worksheet.cell(linha_excel, 5).number_format = '0.00%'
    linha_total = LINHA_TOTAL + extras
    worksheet.cell(linha_total, 5).value = round(sum(float(linha['percentual']) for linha in linhas) / 100, 4)
    worksheet.cell(linha_total, 5).number_format = '0.00%'
    for endereco, valor in {
        f'C{71 + extras}': tabela['empresaNome'] or '', f'C{72 + extras}': tabela['empresaEmail'] or '',
        f'C{73 + extras}': tabela['empresaCnpj'] or '', f'C{75 + extras}': responsavel_nome.strip(),
        f'C{76 + extras}': responsavel_cpf.strip(),
    }.items():
        worksheet[endereco] = valor
    _substituir_placeholder(worksheet[f'A{81 + extras}'], r'_{2,}/_{2,}/\s*20_{2}', date.today().strftime('%d/%m/%Y'), 'data')
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
