"""Reconstrução anônima da geometria observada no DANF3EA4B V1.06.

Não lê o PDF privado. Todo valor abaixo é fictício; imagens/QRs/metadados
originais não são copiados. Também produz variações controladas em memória.
"""
from io import BytesIO
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas


BLOCKS = {
    'header': (204, 830, 7, 'DANF3E - DOCUMENTO AUXILIAR DA'),
    'title': (204, 822, 7, 'NOTA FISCAL ELETRÔNICA DE ENERGIA ELÉTRICA'),
    'issuer': (204, 814, 7, 'Copel Distribuição S.A.'),
    'issuer_cnpj': (204, 788, 7, 'CNPJ 04.368.898/0001-06'),
    'classification': (23, 728, 6, 'B1 Residencial / Residencial'),
    'readings': (347, 720, 7, '01/07/2030     01/08/2030    31    01/09/2030'),
    'uc': (211, 692, 10, '000000000000001'),
    'reference': (31, 615, 10, '08/2030'),
    'due': (115, 615, 10, '10/09/2030'),
    'total': (210, 615, 10, 'R$1.234,567890'),
    'name': (23, 708, 8, 'Nome: CLIENTE FICTICIO PARA TESTES'),
    'address': (23, 691, 8, 'Endereço: R Exemplo, 999 - Ap 001'),
    'district': (23, 682, 8, '- Bairro Ficticio'),
    'postcode': (23, 674, 7, 'CEP: 00000-000'),
    'city': (23, 666, 7, 'Cidade: Cidade Ficticia - Estado: PR'),
    'cpf': (23, 657, 7, 'CPF: ***.***.*00-00'),
    'fiscal': (377, 677, 4, 'NOTA FISCAL No. 000000001 - SÉRIE 1 / DATA DE EMISSÃO: 02/08/2030'),
    'consult': (377, 666, 5, 'Consulte Chave de Acesso em:'),
    'key_label': (377, 655, 5, 'Chave de Acesso'),
    'key': (377, 649, 5, '0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0001'),
    'item': (23, 536, 5, 'ENERGIA ELET CONSUMO'),
    'meter': (23, 340, 5, '0000000001     CONSUMO kWh     TP     10000     10225     1     225,123456'),
    'footer': (490, 5, 5, 'DANF3EA4B (V1.06)'),
}

ITEMS = (
    ('ENERGIA ELET CONSUMO', 'kWh', '999,99', '0,234567', '12,34', '1,23', '2,34', '0,123456'),
    ('ENERGIA ELET USO SISTEMA', 'kWh', '100', '0,345678', '23,45', '2,34', '3,45', '0,234567'),
    ('ENERGIA CONS. B.AMARELA', 'kWh', '100,00', '0,012345', '1,23', '0,12', '0,23', '0,001234'),
    ('CONT ILUMIN PUBLICA MUNICIPIO', 'UN', '', '8,880000', '8,88', '', '', ''),
)
TAXES = (('ICMS', '100,01', '19%', '19,00'), ('COFINS', '80,02', '6,1234%', '4,90'), ('PIS', '80,02', '1,1234%', '0,90'))
MONTHS = ('AGO30', 'JUL30', 'JUN30', 'MAI30', 'ABR30', 'MAR30', 'FEV30', 'JAN30', 'DEZ29', 'NOV29', 'OUT29', 'SET29', 'AGO29')


def make_pdf(*, changes=None, omitted=(), duplicate=None, shift=(0, 0), items=ITEMS, taxes=TAXES,
             history=True, pre_item_lines=()):
    output = BytesIO()
    canvas = Canvas(output, pagesize=(595.28, 841.89), invariant=True)
    canvas.setTitle('Fixture anonima Copel - dados ficticios')
    canvas.setAuthor('HUB tests')
    canvas.translate(*shift)
    for key, (x, y, size, text) in BLOCKS.items():
        if key == 'item':
            continue  # agora desenhado como linha completa abaixo
        if key in omitted:
            continue
        canvas.setFont('Helvetica', size)
        canvas.drawString(x, y, (changes or {}).get(key, text))
    canvas.setFont('Helvetica', 5)
    for x, upper, lower in (
        (23, 'Itens de fatura', ''), (130, 'Unid.', ''), (180, 'Quant.', ''),
        (220, 'Preço unit (R$)', 'com tributos'), (266, 'Valor (R$)', ''),
        (315, 'PIS/', 'COFINS'), (357, 'ICMS', ''), (398, 'Tarifa', 'unit. (R$)'),
    ):
        canvas.drawString(x, 552, upper)
        canvas.drawString(x, 546, lower)
    for index, text in enumerate(pre_item_lines):
        canvas.drawString(23, 570 - index * 7, text)
    for index, values in enumerate(items):
        for x, value in zip((23, 130, 180, 220, 266, 315, 357, 398), values):
            canvas.drawString(x, 536 - 14 * index, value)
    canvas.drawString(23, 370, 'TOTAL')
    for index, values in enumerate(taxes):
        for x, value in zip((450, 487, 522, 560), values):
            canvas.drawString(x, 543 - 10 * index, value)
    if history:
        canvas.drawString(450, 474, 'HISTÓRICO DE CONSUMO / kWh')
        canvas.drawString(450, 466, 'CONSUMO FATURADO    Nº DIAS FAT.')
        rows = [(month, str(100 + i), '30') for i, month in enumerate(MONTHS)] if history is True else history
        for index, row in enumerate(rows):
            for x, value in zip((450, 500, 560), row):
                canvas.drawString(x, 453 - 7 * index, value)
    for index, text in enumerate((
        'PARA CADASTRO DE DÉBITO AUTOMÁTICO, UTILIZE O NÚMERO: 000000000',
        'Grupo de Tensao / Modalidade Tarifaria: B - CONVENCIONAL',
        'A qualquer tempo pode ser solicitado o cancelamento de valores não relacionados à prestação do serviço de',
        'energia elétrica, como convênios e doações.',
        'Periodos Band.Tarif.: Amarela:01/07-01/08',
    )):
        canvas.drawString(307, 260 - index * 8, text)
    if duplicate:
        canvas.setFont('Helvetica', 8)
        canvas.drawString(211, 594, duplicate)
    # Somente cabeçalhos visuais observados; no original são parte gráfica.
    canvas.setFont('Helvetica', 6)
    for x, y, text in (
        (210, 706, 'UNIDADE CONSUMIDORA'),
        (347, 733, 'Leitura anterior     Leitura atual       Nº de dias      Próxima Leitura'),
        (23, 632, 'REF: MÊS / ANO'), (115, 632, 'VENCIMENTO'), (210, 632, 'TOTAL A PAGAR'),
        (23, 351, 'Medidor     Grandezas     Leitura Anterior     Leitura Atual     Consumo kWh'),
    ):
        canvas.drawString(x, y, text)
    canvas.showPage()
    canvas.setFont('Helvetica', 7)
    canvas.drawString(204, 830, BLOCKS['header'][3])
    canvas.drawString(23, 708, 'CLIENTE FICTICIO PARA TESTES')
    canvas.drawString(490, 5, 'DANF3EA4B (V1.06)')
    canvas.save()
    return output.getvalue()


if __name__ == '__main__':
    Path(__file__).with_name('core_anon.pdf').write_bytes(make_pdf())
