"""Core documental observado no DANF3EA4B V1.06; sem interpretação comercial."""
from datetime import datetime
from decimal import Decimal
import re
import unicodedata

from .base import InvoiceParser
from .extraction import FullTextExtractor
from .item_matcher import ItemMatcher, ItemMatcherRule
from .schemas import ExtractedField, ExtractionIssue, ParsedInvoice, ParserIdentity


def _ascii(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c))


def _decimal(text):
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?', text):
        raise ValueError('Número documental inválido.')
    return Decimal(text.replace('.', '').replace(',', '.'))


def _date(text):
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', text):
        raise ValueError('Data documental inválida.')
    return datetime.strptime(text, '%d/%m/%Y').date()


def _reference(text):
    datetime.strptime(text, '%m/%Y')
    return text  # preserva mês/ano documental; normalização final é posterior


def _digits(text, length):
    value = re.sub(r'[ .\-/]', '', text)
    if not value.isascii() or not value.isdigit() or len(value) != length:
        raise ValueError('Identificador incompleto ou ilegível.')
    return value


def _field(name, candidates, convert=str, *, present=False, critical=False, source=None):
    """Candidatos distintos nunca são resolvidos pela ordem de extração."""
    values = []
    invalid = False
    for candidate in candidates:
        try:
            value = convert(candidate.strip())
            if value == '':
                raise ValueError('Valor vazio.')
            if value not in values:
                values.append(value)
        except (ValueError, ArithmeticError):
            invalid = True
    status = 'ambiguous' if len(values) > 1 or (values and invalid) else (
        'failed' if invalid or (present and not values) else 'found' if values else 'not_present'
    )
    issues = () if status == 'found' else (ExtractionIssue(
        f'COPEL_{status.upper()}', 'critical' if critical else 'warning',
        f'Campo documental {name}: {status}.', name,
    ),)
    return ExtractedField(
        status, values[0] if status == 'found' else None,
        Decimal('0.95') if status == 'found' else None,
        source=source or f'p1:{name}', warnings=issues,
    )


def _cpf_field(candidates, *, present, source):
    """CPF mascarado é ausência documental intencional, não erro de OCR."""
    values = [candidate.strip() for candidate in candidates if candidate.strip()]
    if values and all('*' in candidate and len(re.sub(r'\D', '', candidate)) < 11 for candidate in values):
        issue = ExtractionIssue('COPEL_CPF_MASKED', 'info',
                                'CPF apresentado mascarado; nenhum identificador foi reconstruído.',
                                'cpf_cnpj')
        return ExtractedField('not_present', source=source, warnings=(issue,))
    return _field('cpf_cnpj', values, lambda value: _digits(value, 11),
                  present=present, source=source)


class CopelDANF3EParser(InvoiceParser):
    identity = ParserIdentity('copel', '1.3.0', 'danf3e', 'DANF3EA4B-V1.06')
    item_matcher = ItemMatcher((
        ItemMatcherRule('exact', 'ENERGIA ELET CONSUMO', 'energia_elet_consumo', 100),
        ItemMatcherRule('exact', 'ENERGIA ELET USO SISTEMA', 'energia_elet_uso_sistema', 100),
        ItemMatcherRule('prefix', 'ENERGIA INJETADA ', 'energia_injetada', 100),
        ItemMatcherRule('prefix', 'ENERGIA INJ. OUC MPT ', 'energia_inj_ouc_mpt', 100),
        ItemMatcherRule('prefix', 'ENERGIA CONS. B.AMARELA', 'energia_cons_b_amarela', 100),
        ItemMatcherRule('exact', 'ENERGIA INJ. BAND. AMARELA TE', 'energia_inj_band_amarela_te', 100),
        ItemMatcherRule('exact', 'CONT ILUMIN PUBLICA MUNICIPIO', 'cont_ilumin_publica_municipio', 100),
    ))
    energy_matcher = ItemMatcher((
        ItemMatcherRule('exact', 'ENERGIA ELET CONSUMO', 'consumed', 100),
        ItemMatcherRule('exact', 'ENERGIA ELET USO SISTEMA', 'other', 100),
        ItemMatcherRule('prefix', 'ENERGIA INJETADA ', 'injected', 100),
        ItemMatcherRule('prefix', 'ENERGIA INJ. OUC MPT ', 'compensated', 100),
        ItemMatcherRule('prefix', 'ENERGIA CONS. B.AMARELA', 'other', 100),
        ItemMatcherRule('exact', 'ENERGIA INJ. BAND. AMARELA TE', 'other', 100),
    ))
    energy_event_patterns = (
        (re.compile(r'^ENERGIA INJETADA (?P<component>TE|TUSD) (?P<month>\d{2}/\d{4})\s*(?P<gd>GDI-I)$'),
         'energia_injetada'),
        (re.compile(r'^ENERGIA INJ\. OUC MPT (?P<component>TE|TUSD|TUS) (?P<month>\d{2}/\d{4})\s*(?P<gd>GDI-I|GDII-II|GDIII-III)$'),
         'energia_inj_ouc_mpt'),
    )

    def can_parse(self, raw):
        text = _ascii(raw.text).upper()
        return all(anchor in text for anchor in (
            'COPEL DISTRIBUICAO', '04.368.898/0001-06',
            'DANF3E - DOCUMENTO AUXILIAR DA',
            'NOTA FISCAL ELETRONICA DE ENERGIA ELETRICA',
            'DANF3EA4B (V1.06)',
        ))

    def parse(self, document):
        raw = FullTextExtractor().extract(document)
        text = raw.page_texts[0]
        if not self.can_parse(raw):
            raise ValueError('Layout Copel não suportado.')
        # Recorta antes dos itens/histórico/boleto; evita capturar dados do banco
        # ou o endereço da distribuidora no cabeçalho.
        core = text.split('ENERGIA ELET CONSUMO', 1)[0]
        summary = re.findall(r'^\s*(\d{2}/\d{4})\s+(\S+)\s+R\$\s*(\S+)\s*$', core, re.M)
        fiscal_lines = re.findall(r'NOTA FISCAL No\.[^\n]*', core)
        fiscal = [_ascii(line) for line in fiscal_lines]
        number = [m.group(1) for line in fiscal if (m := re.search(r'No\.\s*(.*?)\s*-\s*SERIE', line))]
        series = [m.group(1) for line in fiscal if (m := re.search(r'SERIE\s*(.*?)\s*/\s*DATA', line))]
        issued = [m.group(1) for line in fiscal if (m := re.search(r'EMISSAO:\s*(\S*)', line))]
        keys = re.findall(r'(?<!Consulte )Chave de Acesso[ \t]*\n([^\n]*)', core)
        # No PDF observado estes cabeçalhos são gráficos, não texto. A linha
        # isolada de 15 dígitos e os três valores do resumo são âncoras estruturais.
        uc = re.findall(r'(?<!\S)(?:\d{12}|\d{15})(?!\S)', core)
        identification = {
            'concessionaria': _field('concessionaria', ['Copel'], source='p1:emissor/CNPJ/DANF3E'),
            'codigo_uc': _field('codigo_uc', uc, critical=True,
                                source='p1:bloco superior/unidade consumidora'),
            'competencia': _field('competencia', [row[0] for row in summary], _reference,
                                  present='R$' in core, critical=True, source='p1:linha mês/ano-vencimento-total'),
            'numero_nota_fiscal': _field('numero_nota_fiscal', number,
                                        lambda v: _digits(v, len(v)),
                                        present=bool(fiscal), critical=True, source='p1:NOTA FISCAL No.'),
            'serie': _field('serie', series, lambda v: _digits(v, len(v)),
                            present=bool(fiscal), critical=True, source='p1:SÉRIE'),
            'chave_acesso': _field('chave_acesso', keys, lambda v: _digits(v, 44),
                                   present=bool(re.search(r'(?<!Consulte )Chave de Acesso[ \t]*$', core, re.M)),
                                   critical=True, source='p1:Chave de Acesso'),
        }
        dates = re.findall(r'^\s*(\S+/\S+/\S+)\s+(\S+/\S+/\S+)\s+\d+\s+(\S+/\S+/\S+)\s*$', core, re.M)
        readings = {
            name: _field(name, [row[index] for row in dates], _date,
                         source='p1:linha leitura anterior/atual/nº dias/próxima')
            for index, name in enumerate(('data_leitura_anterior', 'data_leitura_atual', 'data_proxima_leitura'))
        }
        # Consumo do medidor, não quantidade dos itens nem histórico mensal.
        consumption = re.findall(
            r'^\s*\d+\s+CONSUMO\s+kWh\s+TP\s+\S+\s+\S+\s+\S+\s+(\S+)\s*$', text, re.M,
        )
        result_summary = {
            'data_emissao': _field('data_emissao', issued, _date, present=bool(fiscal), source='p1:DATA DE EMISSÃO'),
            'data_vencimento': _field('data_vencimento', [row[1] for row in summary], _date,
                                      present=bool(summary), critical=True, source='p1:linha mês/ano-vencimento-total'),
            'valor_total_concessionaria': _field('valor_total_concessionaria', [row[2] for row in summary],
                                                _decimal, present='R$' in core, critical=True,
                                                source='p1:linha mês/ano-vencimento-total'),
            'consumo_kwh': _field('consumo_kwh', consumption, _decimal,
                                  present=bool(re.search(r'CONSUMO\s+kWh\s+TP', text)),
                                  critical=True, source='p1:medidor/CONSUMO kWh TP/Consumo kWh'),
        }
        # Mantém a grafia original do titular. Colunas separadas por >=2 espaços
        # não pertencem ao endereço (UC/fiscal à direita na mesma altura).
        personal = _ascii(core[core.find('Nome:'):]) if 'Nome:' in core else ''

        def labelled(label):
            values = []
            for value in re.findall(re.escape(label) + r'([^\n]*)', personal):
                # A UC fica em coluna lateral na mesma linha do endereço; alguns
                # extratores reduzem o espaçamento, mas o identificador tem 15 dígitos.
                values.append(re.sub(r'(?:\s+)?\d{15}\s*$', '', re.split(r'\s{2,}', value.strip())[0]))
            return values

        addresses = labelled('Endereco:')
        address_parts = [re.fullmatch(
            r'(?P<logradouro>.*?),\s*(?P<numero>[^\s,]+)(?:\s+-\s*(?P<complemento>.*?))?', value
        ) for value in addresses]
        towns = re.findall(r'Cidade:\s*(.*?)\s*-\s*Estado:\s*([A-Z]{2})', personal)
        taxpayer = labelled('CPF:')
        holder = {
            'nome': _field('nome', labelled('Nome:'), present='Nome:' in core, source='p1:Nome:'),
            'cpf_cnpj': _cpf_field(taxpayer, present='CPF:' in personal,
                                   source='p1:CPF: (pode estar mascarado)'),
            'logradouro': _field('logradouro', [m['logradouro'] if m else '' for m in address_parts],
                                 present=bool(addresses), source='p1:Endereco:'),
            'numero': _field('numero', [m['numero'] if m else '' for m in address_parts],
                             present=bool(addresses), source='p1:Endereco:/numero'),
            'complemento': _field('complemento', [m['complemento'] if m else '' for m in address_parts],
                                  source='p1:Endereco:/complemento'),
            'bairro': _field('bairro', re.findall(r'^\s*-\s+([^\n]+)', personal, re.M), source='p1:continuação Endereço:'),
            'cidade': _field('cidade', [row[0] for row in towns], present='Cidade:' in personal, source='p1:Cidade:'),
            'uf': _field('uf', [row[1] for row in towns], present='Estado:' in personal, source='p1:Estado:'),
            'cep': _field('cep', labelled('CEP:'), lambda v: _digits(v, 8), present='CEP:' in personal, source='p1:CEP: do titular'),
        }
        classification_line = re.findall(
            r'Grupo de Tensao / Modalidade Tarifaria:[ \t]*([^\s-]+)[ \t]*-[ \t]*([^\n]+)', _ascii(text))
        residential_classification = re.findall(
            r'^[ \t]*(B1) (Residencial) / (Residencial)(?=[ \t]{2,}|[ \t]*$)', core, re.M)
        classification = {
            'grupo_tarifario': _field('grupo_tarifario', [row[0] for row in classification_line],
                                      source='p1:Grupo de Tensao / Modalidade Tarifaria'),
            'modalidade_tarifaria': _field('modalidade_tarifaria', [row[1] for row in classification_line],
                                           source='p1:Grupo de Tensao / Modalidade Tarifaria'),
            # Somente o contexto B1 Residencial foi comprovado nesta amostra.
            'subgrupo_tarifario': _field('subgrupo_tarifario',
                [row[0] for row in residential_classification],
                source='p1:classificacao residencial'),
            'classe_tarifaria': _field('classe_tarifaria', [row[1] for row in residential_classification],
                                        source='p1:classificacao residencial'),
            'subclasse_tarifaria': _field('subclasse_tarifaria', [row[2] for row in residential_classification],
                                           source='p1:classificacao residencial'),
        }
        fields = (*identification.values(), *readings.values(), *result_summary.values(),
                  *holder.values(), *classification.values())
        issues = tuple(issue for value in fields for issue in value.warnings)
        items, taxes, history, meter, notices, deep_issues = self._deep(text, result_summary['consumo_kwh'])
        components, energy, energy_issues = self._energy(items, result_summary['consumo_kwh'])
        compensation_supported = any(
            component['category'].status == 'found' and component['category'].value == 'compensated'
            for component in components
        )
        return ParsedInvoice(
            identity=self.identity, source_metadata={'page_count': str(raw.page_count), 'core_page': '1'},
            identificacao_fiscal=identification, titular=holder, leituras=(readings,),
            resumo=result_summary, itens=items, tributos=taxes, classificacao=classification,
            historico_consumo=history, medidor=meter, avisos=notices,
            energy_components=components, energia=energy,
            compensation_supported=compensation_supported,
            issues=issues + deep_issues + energy_issues,
        )

    def _energy(self, items, consumption):
        components, issues = [], []
        for index, item in enumerate(items):
            label, unit = item['descricao_original'], item['unidade']
            targets = self.energy_matcher.match(label.value or '')
            if not targets and unit.value != 'kWh':
                continue  # demais itens continuam íntegros em ParsedInvoice.itens
            source = label.source
            category = _field('category', targets, source=source)
            if not targets:
                issue = ExtractionIssue('COPEL_ENERGY_UNCLASSIFIED', 'info',
                                        'Linha em kWh preservada sem categoria comprovada.',
                                        f'itens.{index}')
                category = ExtractedField('ambiguous', 'unclassified', source=source, warnings=(issue,))
            amount = item['quantidade']
            if unit.value != 'kWh':
                issue = ExtractionIssue('COPEL_ENERGY_UNIT_UNSUPPORTED', 'warning',
                                        'Unidade ausente ou incompatível com kWh; quantidade original preservada.',
                                        f'itens.{index}.unidade')
                amount = ExtractedField('failed', source=amount.source, warnings=(issue,))
            component = {
                'original_label': label, 'category': category,
                'amount_kwh': amount, 'unit': unit,
                'item_index': ExtractedField('found', index, source=source),
            }
            for pattern, context in self.energy_event_patterns:
                match = pattern.fullmatch(label.value or '')
                if match is None:
                    continue
                gd = {'GDI-I': 'GD_I', 'GDII-II': 'GD_II', 'GDIII-III': 'GD_III'}[match['gd']]
                month, year = match['month'].split('/')
                component.update({
                    'tariff_component': _field('tariff_component', [
                        'TUSD' if match['component'] == 'TUS' else match['component']], source=source),
                    'gd_classification': _field('gd_classification', [gd], source=source),
                    'credit_month': _field('credit_month', [f'{year}-{month}'], source=source),
                    'compensation_context': _field('compensation_context', [context], source=source),
                })
                if context == 'energia_inj_ouc_mpt':
                    component.update({
                        'origin': _field('origin', ['OUC'], source=source),
                        'period': _field('period', ['MPT'], source=source),
                    })
                break
            components.append(component)
            issues.extend(category.warnings)
            # Quantidade ilegível já tem sua issue F5; não duplicá-la.
            if amount is not item['quantidade']:
                issues.extend(amount.warnings)
        energy = {'consumo_kwh': consumption}  # medidor, não soma de itens
        for name in ('gd1_kwh', 'gd2_kwh', 'energia_injetada_kwh',
                     'energia_compensada_kwh', 'saldo_creditos_kwh'):
            issue = ExtractionIssue('COPEL_ENERGY_NOT_SUPPORTED', 'info',
                                    'Sem label comprovado na amostra de referência; não comprova ausência na instalação.',
                                    f'energia.{name}')
            energy[name] = ExtractedField('not_present', source=f'escopo documental suportado: {self.identity.layout_version}',
                                         warnings=(issue,))
            issues.append(issue)
        return tuple(components), energy, tuple(issues)

    def _deep(self, text, consumption):
        lines = text.splitlines()
        items, taxes, history, notices, issues = [], [], [], [], []
        meter = {}
        # Os cabeçalhos são gráficos no original. Aprende limites das colunas
        # na linha completa observada; não usa coordenadas absolutas da página.
        candidates = [i for i, line in enumerate(lines) if re.search(r' {2,}(?:kWh|UN) {2,}', line)]
        reference = next((i for i in candidates if len(re.split(r' {2,}', lines[i].strip())) >= 8), None)
        if reference is not None:
            cells = list(re.finditer(r'\S(?:.*?\S)?(?= {2,}|$)', lines[reference]))
            if len(cells) >= 8:
                bounds = [cells[0].start()] + [
                    (cells[i - 1].end() + cells[i].start()) // 2 for i in range(1, 8)
                ] + [(cells[7].end() + cells[8].start()) // 2 if len(cells) > 8 else cells[7].end() + 8]
                names = ('descricao_original', 'unidade', 'quantidade', 'preco_unitario_com_tributos',
                         'valor', 'pis_cofins_valor', 'icms_valor', 'tarifa_unitaria')
                for line_no in range(reference, len(lines)):
                    line = lines[line_no]
                    description = line[bounds[0]:bounds[1]].strip()
                    if description == 'TOTAL' or re.search(r'\bCONSUMO\s+kWh\s+TP\b', line):
                        break
                    if not description:
                        continue
                    values = [line[bounds[i]:bounds[i + 1]].strip() for i in range(8)]
                    if values[0].startswith('ENERGIA ') and values[1].endswith('kWh') and values[1] != 'kWh':
                        values[0] += values[1][:-3].strip()
                        values[1] = 'kWh'
                    # A tabela só aceita as unidades documentais observadas; texto
                    # de "Segunda Via"/histórico não pode virar item financeiro.
                    if values[1] and values[1] not in ('kWh', 'UN'):
                        continue
                    optional_lighting = values[0] == 'CONT ILUMIN PUBLICA MUNICIPIO' and values[1] == 'UN'
                    row = {}
                    for index, (name, value) in enumerate(zip(names, values)):
                        source = f'p1:itens/linha {line_no + 1}/coluna {name}'
                        if optional_lighting and name in ('quantidade', 'tarifa_unitaria') and not value:
                            row[name] = ExtractedField('not_present', source=source)
                        else:
                            row[name] = _field(f'itens.{len(items)}.{name}', [value] if value else [],
                                               str if index < 2 else _decimal, source=source)
                    targets = self.item_matcher.match(values[0])
                    row['descricao_normalizada'] = _field('descricao_normalizada', targets,
                                                          source='matcher documental')
                    if not targets:
                        issues.append(ExtractionIssue('COPEL_ITEM_UNMAPPED', 'info',
                                                      'Descrição preservada sem mapeamento.', f'itens.{len(items)}'))
                    items.append(row)
            else:
                issues.append(ExtractionIssue('COPEL_ITEM_COLUMNS_UNREADABLE', 'warning',
                                              'Não foi possível delimitar colunas dos itens.', 'itens'))
        else:
            issues.append(ExtractionIssue('COPEL_ITEMS_NOT_IDENTIFIED', 'warning',
                                          'Estrutura de itens não identificada.', 'itens'))

        for match in re.finditer(r'\b(ICMS|COFINS|PIS)[ \t]+(\S+)[ \t]+(\S+%)[ \t]+(\S+)[ \t]*$', text, re.M):
            taxes.append({
                name: _field(f'tributos.{len(taxes)}.{name}', [value.removesuffix('%') if index == 2 else value],
                             str if index == 0 else _decimal,
                             source=f'p1:quadro tributos/{match[1]}/{name}')
                for index, (name, value) in enumerate(zip(('tributo', 'base_calculo', 'aliquota', 'valor'), match.groups()))
            })
        history_text = text.split('HISTÓRICO DE CONSUMO / kWh', 1)
        if len(history_text) == 2:
            for match in re.finditer(r'\b((?:JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\d{2})[ \t]+(\S+)(?:[ \t]+(\S+))?[ \t]*$', history_text[1], re.M):
                history.append({
                    name: _field(f'historico.{len(history)}.{name}', [value] if value else [], str if index == 0 else _decimal,
                                 source=f'p1:HISTÓRICO DE CONSUMO/{name}')
                    for index, (name, value) in enumerate(zip(('competencia', 'consumo_kwh', 'dias_faturados'), match.groups()))
                })
        matches = list(re.finditer(r'^\s*(\d+)\s+(CONSUMO)\s+(kWh)\s+(TP)\s+(\S+)\s+(\S+)\s+(\S+)\s+\S+\s*$', text, re.M))
        for index, name in enumerate(('numero', 'grandeza', 'unidade', 'posto', 'leitura_anterior', 'leitura_atual', 'constante')):
            meter[name] = _field(f'medidor.{name}', [m[index + 1] for m in matches], str if index < 4 else _decimal,
                                 source=f'p1:medidor/CONSUMO kWh TP/{name}')
        meter['consumo_kwh'] = consumption  # mesma fonte do resumo F4, sem recálculo
        for line in lines:
            clean = line.strip()
            if clean.startswith(('PARA CADASTRO DE DÉBITO AUTOMÁTICO,', 'Grupo de Tensao / Modalidade Tarifaria:',
                                 'Periodos Band.Tarif.:')):
                notices.append(_field('aviso', [clean], source='p1:informações complementares'))
        regulatory = re.search(r'A qualquer tempo pode ser solicitado.*?energia elétrica, como convênios e doações\.', text, re.S)
        if regulatory:
            notices.append(_field('aviso', [' '.join(regulatory[0].split())], source='p1:mensagem regulatória'))
        for row in (*items, *taxes, *history, meter):
            issues.extend(issue for value in row.values() for issue in value.warnings)
        return tuple(items), tuple(taxes), tuple(history), meter, tuple(notices), tuple(issues)
