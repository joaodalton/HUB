"""Dados ANEEL versionados localmente; nunca consulta rede em runtime."""
from datetime import date
from decimal import Context, Decimal, localcontext
import json
from pathlib import Path

from flask import has_app_context


_DATA = Path(__file__).resolve().parents[1] / 'data' / 'regulatory_tariffs.json'


def _month(value):
    year, month = map(int, value.split('-'))
    return date(year, month, 1), date(year + (month == 12), month % 12 + 1, 1)


def _previous_month(value):
    return date(value.year - (value.month == 1), 12 if value.month == 1 else value.month - 1, 1)


class RegulatoryTariffRepository:
    def fio_b_tariffs(self):
        from services.fio_b_resolver import RegulatoryFioBTariff

        published_keys = set()
        if has_app_context():
            from models.regulatory_tariff import RegulatoryTariff
            rows = RegulatoryTariff.query.order_by(RegulatoryTariff.id).all()
            if rows:
                for row in rows:
                    record = self._record(RegulatoryFioBTariff, {
                        'distributor': row.distributor, 'official_distributor': row.official_distributor,
                        'component': row.component, 'base_tariff': row.base_tariff, 'subgroup': row.subgroup,
                        'modality': row.modality, 'tariff_class': row.tariff_class or None,
                        'tariff_subclass': row.tariff_subclass or None, 'tariff_detail': row.tariff_detail,
                        'tariff_period': row.tariff_period or None, 'source_value': row.source_value,
                        'source_unit': row.source_unit, 'valid_from': row.valid_from.isoformat(),
                        'valid_until': row.valid_until.isoformat(), 'source_reference': row.source_reference,
                        'source_url': row.source_url, 'version': row.source_version,
                        'unit_tariff': row.value_kwh,
                    })
                    if record is not None:
                        yield record
                        published_keys.add((row.official_distributor, row.valid_from.isoformat(), row.valid_until.isoformat(),
                                            row.subgroup, row.modality, row.tariff_class, row.tariff_subclass, row.tariff_period))
        payload = json.loads(_DATA.read_text(encoding='utf-8'))
        version = f"{payload['source']}:{payload['resource_id']}:{payload['resource_hash']}"
        for row in payload['tariffs']:
            if (row['component'], row['source_unit'], row['base_tariff'], row['tariff_detail']) != (
                    'TUSD_FIO_B', 'R$/MWh', 'Tarifa de Aplicação', 'SCEE'):
                continue
            raw = Decimal(row['source_value'])
            with localcontext(Context(prec=len(raw.as_tuple().digits) + 4)):
                unit_tariff = raw / Decimal(1000)
            key = (row['official_distributor'], row['valid_from'], row['valid_until'], row['subgroup'], row['modality'],
                   row['tariff_class'] or '', row['tariff_subclass'] or '', row['tariff_period'] or '')
            if key in published_keys:
                continue
            record = self._record(RegulatoryFioBTariff, {**row, 'version': version, 'unit_tariff': unit_tariff})
            if record is not None:
                yield record

    @staticmethod
    def _record(record_type, row):
        start, after = _month(row['valid_from'][:7])
        end, after_end = _month(row['valid_until'][:7])
        first_month = start if row['valid_from'] == start.isoformat() else after
        last_month = end if row['valid_until'] == (after_end - date.resolution).isoformat() else _previous_month(end)
        if first_month > last_month:
            return None
        return record_type(
            row['distributor'], first_month.strftime('%Y-%m'), last_month.strftime('%Y-%m'),
            row['subgroup'], row['modality'], Decimal(row['unit_tariff']), row['source_reference'], row['version'],
            row.get('tariff_class'), row.get('tariff_subclass'), row.get('tariff_period'),
            component=row['component'], unit='R$/kWh', source='ANEEL',
            source_value=Decimal(row['source_value']), source_unit=row['source_unit'],
            valid_from_date=row['valid_from'], valid_until_date=row['valid_until'],
            tariff_detail=row['tariff_detail'], base_tariff=row['base_tariff'],
            source_url=row['source_url'], official_distributor=row['official_distributor'],
        )
