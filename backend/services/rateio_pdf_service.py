# backend/services/rateio_pdf_service.py
"""
Geracao dos 2 PDFs finais do rateio (Sprint 4 de RATEIO.md, secoes 8-10):

  gerar_formulario_pdf() -> overlay de texto em cima do PDF oficial em
      branco da Copel (backend/assets/formulario_copel_associacao.pdf),
      nas coordenadas calibradas manualmente contra o PDF real.

  gerar_termos_adesao_pdf() -> baixa do Google Drive o Termo de Adesao de
      cada UC beneficiaria (na mesma ordem alfabetica da tabela) e mescla
      tudo num PDF unico.

Os outros 2 documentos que a Copel pede (CNPJ e Estatuto) NAO precisam de
geracao -- ja sao Document normais, baixados via GET /documents/<id>/download
(ver empresa.documento_cnpj / empresa.documento_estatuto).
"""
import io
from datetime import date
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import black
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from services.rateio_formulario_service import (
    MAX_LINHAS_BENEFICIARIAS,
    buscar_termo_adesao,
    montar_tabela_formulario,
    verificar_termos_adesao,
)
from services.drive_service import get_drive_service

ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
TEMPLATE_PATH = ASSETS_DIR / 'formulario_copel_associacao.pdf'

# Dimensoes reais do PDF (pdfplumber): 841.92 x 595.32 pt (landscape!)
PAGE_WIDTH = 841.92
PAGE_HEIGHT = 595.32

# Colunas da tabela (x0 = esquerda da celula) -- calibradas com pdfplumber
# contra o PDF real. Nome: x0=86.06 (mesma posicao do indice da linha).
# Os campos CPF/CNPJ, UC e % estao em colunas para a direita.
COL_NOME_X = 97.0
COL_DOCUMENTO_X = 390.0
COL_UC_X = 542.0
COL_PERCENTUAL_X = 754.0

# Linhas da tabela (top em pdfplumber = distancia do topo da pagina ate
# a baseline do texto daquela linha).
# Pagina 0 (formulario): linhas 1..16.
ROW_TOPS_P0 = [
    304.03,  # linha 1
    318.55,  # linha 2
    333.07,  # linha 3
    347.59,  # linha 4
    362.11,  # linha 5
    376.63,  # linha 6
    391.15,  # linha 7
    405.67,  # linha 8
    420.19,  # linha 9
    434.74,  # linha 10
    449.26,  # linha 11
    463.78,  # linha 12
    478.30,  # linha 13
    492.82,  # linha 14
    507.34,  # linha 15
    521.86,  # linha 16
]

# Pagina 1: linhas 17..24
ROW_TOPS_P1 = [
    57.14,   # linha 17
    71.66,   # linha 18
    86.18,   # linha 19
    100.70,  # linha 20
    115.22,  # linha 21
    129.74,  # linha 22
    144.26,  # linha 23
    158.78,  # linha 24
]

# Campos de topo (pagina 0) - "UC Geradora" e "UC Ancora"
# campo âncora: top=158.78, x0=212.42 (palavra "âncora" no pdfplumber)
CAMPO_UC_ANCORA = {'x': 260.0, 'top': 166.0}
# campo geradora: a linha "geradora de nº ____" - calibrada
# (o texto "geradora" nao foi extraido, mas a linha está na mesma area)
# Vou usar x=132.62 (posicao do "Nome" do titular) como referencia
# e top=275.09 (top do texto "Nome do Titular")
CAMPO_UC_GERADORA = {'x': 340.0, 'top': 108.0}

# Rodape (pagina 2) - campos extraidos com pdfplumber
# 'Titular' → top=129.74, x0=52.80
# 'E-mail' → top=144.26, x0=52.80
# 'CNPJ:' → top=158.78, x0=52.80
# 'CPF:' → top=202.37, x0=52.80 (campo CPF do responsavel)
CAMPO_TITULAR = {'x': 390.0, 'top': 137.0}
CAMPO_EMAIL = {'x': 390.0, 'top': 151.5}
CAMPO_CNPJ = {'x': 390.0, 'top': 166.0}
CAMPO_RESPONSAVEL_NOME = {'x': 390.0, 'top': 195.0}
CAMPO_RESPONSAVEL_CPF = {'x': 390.0, 'top': 209.5}
CAMPO_DATA = {'x': 82.0, 'top': 282.0}
CAMPO_DATA_ANO = {'x': 143.0, 'top': 282.0}

FONT_NAME = 'Helvetica'
FONT_SIZE = 9


def _y_for_reportlab(top_pdfplumber: float) -> float:
    """Converte 'top' do pdfplumber (distancia do topo da pagina ate a
    baseline do texto) para y do reportlab (distancia do bottom da pagina
    ate a baseline).
    Fórmula: y_reportlab = PAGE_HEIGHT - top_pdfplumber
    """
    return PAGE_HEIGHT - top_pdfplumber


def _draw_text(
    c: canvas.Canvas,
    x: float,
    top_pdfplumber: float,
    text: str,
    align_right: bool = False,
    max_width: float | None = None,
) -> None:
    if not text:
        return
    c.setFont(FONT_NAME, FONT_SIZE)
    c.setFillColor(black)
    if max_width and stringWidth(text, FONT_NAME, FONT_SIZE) > max_width:
        while text and stringWidth(text + '...', FONT_NAME, FONT_SIZE) > max_width:
            text = text[:-1]
        text += '...'
    y = _y_for_reportlab(top_pdfplumber)
    if align_right:
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def _formatar_percentual(valor: float) -> str:
    return f'{valor:.2f}'.replace('.', ',') + '%'


def _validar_pre_requisitos(tabela: dict) -> None:
    faltando = []
    if not tabela.get('ucGeradora'):
        faltando.append('UC da usina')
    if not tabela.get('documentoCnpjOk'):
        faltando.append('CNPJ da empresa')
    if not tabela.get('documentoEstatutoOk'):
        faltando.append('Estatuto da empresa')
    if faltando:
        raise ValueError(f'Pre-requisitos faltando: {", ".join(faltando)}.')


def gerar_formulario_pdf(
    plant_id: int,
    responsavel_nome: str,
    responsavel_cpf: str,
    linhas_override: list[dict] | None = None,
) -> bytes:
    """Gera o PDF do Formulario Copel (Associacoes) preenchido, por overlay
    em cima do template oficial em branco. Bloqueia (ValueError) se faltar
    Termo de Adesao de alguma UC beneficiaria, ou se passar de 24 linhas."""
    if not TEMPLATE_PATH.exists():
        raise ValueError(
            f'Template do formulario nao encontrado em {TEMPLATE_PATH}. '
            'Coloque o PDF oficial da Copel nesse caminho antes de gerar.'
        )

    tabela = montar_tabela_formulario(plant_id)
    _validar_pre_requisitos(tabela)

    if linhas_override is not None:
        if not isinstance(linhas_override, list):
            raise ValueError('Linhas de revisao invalidas.')
        overrides_por_uc = {
            item.get('ucId'): item for item in linhas_override
            if isinstance(item, dict) and item.get('ucId') is not None
        }
        for linha in tabela['linhas']:
            override = overrides_por_uc.get(linha['ucId'])
            if not override:
                continue
            for campo in ('nome', 'documento', 'ucIdentificacao'):
                if campo in override:
                    linha[campo] = str(override[campo] or '').strip()
            if 'percentual' in override:
                try:
                    percentual = float(override['percentual'])
                except (TypeError, ValueError) as exc:
                    raise ValueError('Percentual visual invalido no formulario.') from exc
                if percentual < 0 or percentual > 100:
                    raise ValueError('Percentual visual deve estar entre 0 e 100.')
                linha['percentual'] = percentual

    if tabela['excedeLimiteLinhas']:
        raise ValueError(
            f'Esta usina tem {len(tabela["linhas"])} UCs beneficiarias, mas o '
            f'formulario da Copel so suporta {MAX_LINHAS_BENEFICIARIAS}.'
        )

    verificacao = verificar_termos_adesao(plant_id)
    if not verificacao['ok']:
        nomes = ', '.join(item['nome'] for item in verificacao['faltando'])
        raise ValueError(f'Termo de Adesao faltando para: {nomes}. Geracao bloqueada.')

    reader_template = PdfReader(str(TEMPLATE_PATH))
    num_paginas = len(reader_template.pages)

    # Um canvas por pagina do template -- so escreve algo nas paginas 0 (p1),
    # 1 (p2) e 2 (p3); a pagina 3 (p4, texto informativo) fica intocada.
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    for pagina_idx in range(num_paginas):
        if pagina_idx == 0:
            # Campos de topo
            _draw_text(c, CAMPO_UC_GERADORA['x'], CAMPO_UC_GERADORA['top'], tabela['ucGeradora'] or '')
            _draw_text(c, CAMPO_UC_ANCORA['x'], CAMPO_UC_ANCORA['top'], tabela['ucAncora'] or '')

            # Tabela (pagina 0, linhas 1..16)
            for linha in tabela['linhas']:
                if linha['ordem'] > 16:
                    continue
                top = ROW_TOPS_P0[linha['ordem'] - 1] + 8
                _draw_text(c, COL_NOME_X, top, linha['nome'] or '', max_width=285)
                _draw_text(c, COL_DOCUMENTO_X, top, linha['documento'] or '', max_width=143)
                _draw_text(c, COL_UC_X, top, linha['ucIdentificacao'] or '', max_width=105)
                _draw_text(c, COL_PERCENTUAL_X, top, _formatar_percentual(linha['percentual']), align_right=True, max_width=100)

        elif pagina_idx == 1:
            # Tabela (pagina 1, linhas 17..24)
            for linha in tabela['linhas']:
                if linha['ordem'] < 17 or linha['ordem'] > 24:
                    continue
                top = ROW_TOPS_P1[linha['ordem'] - 17] + 8
                _draw_text(c, COL_NOME_X, top, linha['nome'] or '', max_width=285)
                _draw_text(c, COL_DOCUMENTO_X, top, linha['documento'] or '', max_width=143)
                _draw_text(c, COL_UC_X, top, linha['ucIdentificacao'] or '', max_width=105)
                _draw_text(c, COL_PERCENTUAL_X, top, _formatar_percentual(linha['percentual']), align_right=True, max_width=100)

        elif pagina_idx == 2:
            # Rodape (pagina 2)
            hoje = date.today()
            _draw_text(c, CAMPO_TITULAR['x'], CAMPO_TITULAR['top'], tabela['empresaNome'] or '')
            _draw_text(c, CAMPO_EMAIL['x'], CAMPO_EMAIL['top'], tabela['empresaEmail'] or '')
            _draw_text(c, CAMPO_CNPJ['x'], CAMPO_CNPJ['top'], tabela['empresaCnpj'] or '')
            _draw_text(c, CAMPO_RESPONSAVEL_NOME['x'], CAMPO_RESPONSAVEL_NOME['top'], responsavel_nome or '')
            _draw_text(c, CAMPO_RESPONSAVEL_CPF['x'], CAMPO_RESPONSAVEL_CPF['top'], responsavel_cpf or '')
            _draw_text(c, CAMPO_DATA['x'], CAMPO_DATA['top'], f'{hoje.day:02d}/{hoje.month:02d}/')
            _draw_text(c, CAMPO_DATA_ANO['x'], CAMPO_DATA_ANO['top'], f'{hoje.year % 100:02d}')

        c.showPage()

    c.save()
    overlay_buffer.seek(0)

    reader_overlay = PdfReader(overlay_buffer)
    writer = PdfWriter()

    for pagina_idx in range(num_paginas):
        pagina_base = reader_template.pages[pagina_idx]
        pagina_base.merge_page(reader_overlay.pages[pagina_idx])
        writer.add_page(pagina_base)

    output_buffer = io.BytesIO()
    writer.write(output_buffer)
    return output_buffer.getvalue()


def gerar_termos_adesao_pdf(plant_id: int) -> bytes:
    """Baixa do Google Drive o Termo de Adesao de cada UC beneficiaria (mesma
    ordem alfabetica da tabela) e mescla num PDF unico. Bloqueia se faltar
    algum -- mesma checagem que gerar_formulario_pdf, pra nao gerar um PDF
    incompleto sem avisar."""
    tabela = montar_tabela_formulario(plant_id)
    _validar_pre_requisitos(tabela)

    verificacao = verificar_termos_adesao(plant_id)
    if not verificacao['ok']:
        nomes = ', '.join(item['nome'] for item in verificacao['faltando'])
        raise ValueError(f'Termo de Adesao faltando para: {nomes}. Geracao bloqueada.')

    drive = get_drive_service()
    writer = PdfWriter()
    algum_anexado = False

    for linha in tabela['linhas']:
        documento = buscar_termo_adesao(linha['clienteId'], linha['ucId'])
        if not documento or documento.storage_provider != 'google_drive':
            raise ValueError(f'Termo de Adesao de {linha["nome"]} nao esta disponivel no Google Drive.')

        try:
            file_bytes = drive.download_file(documento.storage_ref)
        except Exception as exc:
            raise ValueError(f'Nao foi possivel baixar o Termo de Adesao de {linha["nome"]}.') from exc

        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            if not reader.pages:
                raise ValueError('PDF sem paginas')
        except Exception as exc:
            raise ValueError(f'Termo de Adesao de {linha["nome"]} nao e um PDF valido.') from exc

        for pagina in reader.pages:
            writer.add_page(pagina)
        algum_anexado = True

    if not algum_anexado:
        raise ValueError('Nenhum Termo de Adesao valido (PDF) encontrado para mesclar.')

    output_buffer = io.BytesIO()
    writer.write(output_buffer)
    return output_buffer.getvalue()
