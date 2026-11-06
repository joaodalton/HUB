"""Transição GD-II da Lei 14.300, art. 27; resolução local, sem consulta externa."""
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, localcontext
import re

from services.invoice_compensation import CompensacaoNormalizada, EnergyStatus
from services.invoice_normalization_service import InvoiceNormalized, json_safe
from services.invoice_parsers.schemas import ExtractedField


REGULATORY_BASIS = 'Lei 14.300/2022, art. 27; versão 2023-2028'
TRANSITION_RATES = {2023: Decimal('.15'), 2024: Decimal('.30'), 2025: Decimal('.45'),
                    2026: Decimal('.60'), 2027: Decimal('.75'), 2028: Decimal('.90')}


def _month(value):
    return isinstance(value, str) and re.fullmatch(r'(?!0000)[0-9]{4}-(0[1-9]|1[0-2])', value)


def _number(value):
    return isinstance(value, Decimal) and value.is_finite() and value >= 0


def _document_value(field):
    if (isinstance(field, ExtractedField) and field.status == 'found'
            and isinstance(field.source, str) and field.source.strip()):
        return field.value
    return None


@dataclass(frozen=True)
class RegulatoryFioBTariff:
    """Registro já importado/validado; nenhuma tabela padrão ou tarifa implícita."""
    distributor: str
    valid_from: str
    valid_to: str
    subgroup: str
    modality: str
    unit_tariff: Decimal
    reference: str
    version: str
    tariff_class: str | None = None
    tariff_subclass: str | None = None
    tariff_period: str | None = None
    component: str = 'TUSD_FIO_B'
    unit: str = 'R$/kWh'
    source: str = 'ANEEL'
    source_value: Decimal | None = None
    source_unit: str | None = None
    valid_from_date: str | None = None
    valid_until_date: str | None = None
    tariff_detail: str | None = None
    base_tariff: str | None = None
    source_url: str | None = None
    official_distributor: str | None = None

    def __post_init__(self):
        if not _number(self.unit_tariff):
            raise ValueError('TUSD Fio B exige Decimal finito não negativo em R$/kWh.')
        if not _month(self.valid_from) or not _month(self.valid_to) or self.valid_from > self.valid_to:
            raise ValueError('Vigência exige intervalo YYYY-MM válido.')
        for name in ('distributor', 'subgroup', 'modality', 'reference', 'version'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError('Tarifa regulatória exige identificação e versão explícitas.')
        for name in ('tariff_class', 'tariff_subclass', 'tariff_period'):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError('Dimensão tarifária deve ser texto ou None.')
        if self.component != 'TUSD_FIO_B' or self.unit != 'R$/kWh' or not self.source.strip():
            raise ValueError('Registro regulatório exige componente, unidade e fonte explícitos.')
        if self.source_value is not None and not _number(self.source_value):
            raise ValueError('Valor-fonte regulatório exige Decimal finito não negativo.')
        for name in ('source_unit', 'valid_from_date', 'valid_until_date', 'tariff_detail',
                     'base_tariff', 'source_url', 'official_distributor'):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError('Metadado regulatório deve ser texto ou None.')
        if (self.valid_from_date is None) != (self.valid_until_date is None):
            raise ValueError('Vigência diária regulatória exige início e fim.')
        if self.valid_from_date is not None:
            try:
                valid_from_date = date.fromisoformat(self.valid_from_date)
                valid_until_date = date.fromisoformat(self.valid_until_date)
            except (TypeError, ValueError):
                raise ValueError('Vigência diária regulatória inválida.') from None
            if valid_from_date > valid_until_date:
                raise ValueError('Vigência diária regulatória inválida.')


@dataclass(frozen=True)
class FioBResolution:
    event: CompensacaoNormalizada | None
    status: str
    applicable: bool | None
    gd_classification: str | None
    competencia: str | None
    energy_kwh: Decimal | None = None
    tusd_fio_b_unit_tariff: Decimal | None = None
    tariff_source: str | None = None
    transition_rate: Decimal | None = None
    amount: Decimal | None = None
    regulatory_basis: str = REGULATORY_BASIS
    evidence: tuple = ()

    def __post_init__(self):
        if self.status not in ('RESOLVED', 'NOT_APPLICABLE', 'UNSUPPORTED', 'MISSING_DATA', 'AMBIGUOUS'):
            raise ValueError('Estado Fio B inválido.')
        for value in (self.energy_kwh, self.tusd_fio_b_unit_tariff, self.transition_rate, self.amount):
            if value is not None and not _number(value):
                raise ValueError('Componente Fio B exige Decimal não negativo ou None.')
        if self.status == 'RESOLVED':
            if (self.event is None or self.event.status != EnergyStatus.VALID
                    or self.gd_classification != 'GD_II' or self.applicable is not True
                    or any(value is None for value in (self.energy_kwh, self.tusd_fio_b_unit_tariff,
                                                      self.transition_rate, self.amount))
                    or self.tariff_source not in ('DOCUMENT', 'REGULATORY') or not self.evidence):
                raise ValueError('Fio B resolvido exige evento, tarifa, regra e evidência.')
        elif self.amount is not None:
            raise ValueError('Fio B não resolvido não fornece valor monetário.')

    def to_dict(self):
        return json_safe(self)


class FioBResolver:
    def resolve(self, invoice: InvoiceNormalized, *, regulatory_tariffs=()):
        if not isinstance(invoice, InvoiceNormalized):
            raise TypeError('Fio B exige InvoiceNormalized.')
        tariffs = tuple(regulatory_tariffs)
        if not tariffs:
            tariffs = None
        elif any(not isinstance(row, RegulatoryFioBTariff) for row in tariffs):
            raise TypeError('Tabela Fio B exige registros regulatórios tipados.')
        energy = invoice.billing_energy_input
        events = tuple(e for e in energy.compensacoes if e.cobravel_ouc_mpt) if energy else ()
        if not events:
            return (FioBResolution(None, 'MISSING_DATA', None, None,
                                   energy.competencia if energy else None),)
        return tuple(self._event(invoice, event, tariffs) for event in events)

    def _event(self, invoice, event, tariffs):
        month = invoice.billing_energy_input.competencia
        gd = event.classificacao_gd
        common = dict(event=event, applicable=gd == 'GD_II' if gd != 'UNKNOWN' else None,
                      gd_classification=gd, competencia=month, energy_kwh=event.quantidade_kwh)
        if gd == 'GD_I':
            return FioBResolution(status='NOT_APPLICABLE', regulatory_basis='Lei 14.300/2022, art. 26', **common)
        if gd == 'GD_III':
            return FioBResolution(status='UNSUPPORTED', **common)
        if gd != 'GD_II' or not _month(month):
            return FioBResolution(status='MISSING_DATA', **common)
        rate = TRANSITION_RATES.get(int(month[:4]))
        if rate is None:
            return FioBResolution(status='UNSUPPORTED', **common)
        common['transition_rate'] = rate
        if event.status != EnergyStatus.VALID or invoice.billing_energy_input.status != EnergyStatus.VALID:
            status = 'AMBIGUOUS' if event.status == EnergyStatus.AMBIGUOUS else 'MISSING_DATA'
            return FioBResolution(status=status, **common)
        tariff, source, evidence, status = self._tariff(invoice, event, tariffs, month)
        if status != 'RESOLVED':
            return FioBResolution(status=status, evidence=evidence, **common)
        numbers = (event.quantidade_kwh, tariff, rate)
        precision = sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in numbers) + 12
        with localcontext(Context(prec=precision)):
            amount = event.quantidade_kwh * tariff * rate
        return FioBResolution(status='RESOLVED', tusd_fio_b_unit_tariff=tariff,
            tariff_source=source, amount=amount, evidence=evidence, **common)

    @staticmethod
    def _tariff(invoice, event, tariffs, month):
        # Campo novo e explícito no item TUSD; tarifa_unitaria é TUSD total e não serve.
        documents = []
        for component in event.componentes:
            field = component.documento.get('tusd_fio_b_unit_tariff')
            if component.tipo != 'TUSD' or field is None:
                continue
            index = _document_value(component.energy_evidence.get('item_index'))
            linked = (type(index) is int and 0 <= index < len(invoice.itens_documentais)
                      and invoice.itens_documentais[index].get('tusd_fio_b_unit_tariff') == field)
            documents.append((field, linked, index))
        if documents:
            evidence = tuple({'field': field, 'item_index': index} for field, _, index in documents)
            if len(documents) != 1 or any(field.status == 'ambiguous' for field, _, _ in documents):
                return None, None, evidence, 'AMBIGUOUS'
            field, linked, _ = documents[0]
            value = _document_value(field)
            if linked and _number(value):
                return value, 'DOCUMENT', evidence, 'RESOLVED'
        else:
            evidence = ()
        if tariffs is None:
            from services.regulatory_tariff_repository import RegulatoryTariffRepository
            tariffs = tuple(RegulatoryTariffRepository().fio_b_tariffs())
        matches = tuple(row for row in tariffs if row.valid_from <= month <= row.valid_to and all(
            expected is None or _document_value(invoice.campos.get(name)) == expected
            for name, expected in (
                ('concessionaria', row.distributor), ('subgrupo_tarifario', row.subgroup),
                ('modalidade_tarifaria', row.modality), ('classe_tarifaria', row.tariff_class),
                ('subclasse_tarifaria', row.tariff_subclass), ('posto_tarifario', row.tariff_period))))
        if len(matches) != 1:
            return None, None, evidence + matches, 'AMBIGUOUS' if matches else 'MISSING_DATA'
        return matches[0].unit_tariff, 'REGULATORY', evidence + matches, 'RESOLVED'
