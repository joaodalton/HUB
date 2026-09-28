"""Importação manual e transacional do CSV oficial de componentes ANEEL."""
import csv
import hashlib
import io
import json
import tempfile
from datetime import date, datetime, timedelta
from decimal import Context, Decimal, InvalidOperation, localcontext
from pathlib import Path

from flask import g
from sqlalchemy.exc import IntegrityError

from config import Config
from services.aneel_ckan_client import AneelCkanClient, REQUIRED_COLUMNS
from extensions import db
from models.regulatory_tariff import RegulatoryTariff, RegulatoryTariffImport, RegulatoryTariffPreview


MAX_BYTES = Config.REGULATORY_TARIFF_MAX_BYTES
TTL_MINUTES = Config.REGULATORY_TARIFF_PREVIEW_TTL_MINUTES
CHUNK_BYTES = 64 * 1024
TEMP_PREFIX = 'regulatory-tariff-'
ACTIVE_TEMP_PATHS = set()


class UploadTooLarge(ValueError):
    pass
ANEEL_PORTAL = 'https://dadosabertos.aneel.gov.br/dataset/componentes-tarifarias'
REQUIRED = set(REQUIRED_COLUMNS)


def create_preview(file_storage, source_url: str | None, source_version: str | None) -> dict:
    path, filename, digest = _file(file_storage)
    try:
        source_url = _source_url(source_url)
        if source_version is not None and len(source_version.strip()) > 255:
            raise ValueError('Versão da fonte excede o limite permitido.')
        ACTIVE_TEMP_PATHS.add(path.resolve())
        plan, summary = _plan(_rows(path), source_url, source_version or digest)
        status = 'ready' if summary['validos'] and not summary['conflitos'] and not summary['rejeitados'] else 'invalid'
        preview = RegulatoryTariffPreview(
            created_by_id=g.current_user.id, file_name=filename, file_hash=digest,
            source_url=source_url, source_version=source_version or digest,
            plan=plan, summary=summary, status=status,
            expires_at=datetime.utcnow() + timedelta(minutes=TTL_MINUTES),
        )
        db.session.add(preview); db.session.commit()
        return _preview_dict(preview)
    finally:
        ACTIVE_TEMP_PATHS.discard(path.resolve())
        _remove_temp(path)


def fetch_copel_fio_b(year: int):
    client = AneelCkanClient(api_url=Config.ANEEL_CKAN_API_URL,
                             timeout_seconds=Config.ANEEL_CKAN_TIMEOUT_SECONDS,
                             token=Config.ANEEL_CKAN_TOKEN)
    return client.copel_fio_b(year, Config.REGULATORY_TARIFF_MAX_ROWS)


def create_ckan_preview(distributor: str, year: int) -> dict:
    if distributor != 'COPEL-DIS':
        raise ValueError('Distribuidora ANEEL não suportada para sincronização.')
    rows, source = fetch_copel_fio_b(year)
    source_url = _source_url(source.get('source_url'))
    source_version = str(source.get('source_version') or source['resource_id'])[:255]
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    plan, summary = _plan(iter(rows), source_url, source_version)
    summary['ckan'] = {'resourceId': source['resource_id'], 'generatedAt': source.get('generated_at'),
                       'filters': source.get('filters', {}), 'found': len(rows)}
    preview = RegulatoryTariffPreview(
        created_by_id=g.current_user.id, file_name=f'componentes-tarifarias-{year}.ckan.json',
        file_hash=hashlib.sha256(payload).hexdigest(), source_url=source_url, source_version=source_version,
        plan=plan, summary=summary,
        status='ready' if summary['validos'] and not summary['conflitos'] and not summary['rejeitados'] else 'invalid',
        expires_at=datetime.utcnow() + timedelta(minutes=TTL_MINUTES),
    )
    db.session.add(preview); db.session.commit()
    return _preview_dict(preview)


def confirm(preview_id: int) -> dict | None:
    preview = RegulatoryTariffPreview.query.filter_by(id=preview_id, created_by_id=g.current_user.id).first()
    if preview is None:
        return None
    if preview.status != 'ready' or preview.expires_at < datetime.utcnow() or preview.consumed_at:
        raise ValueError('Prévia indisponível, expirada ou já confirmada.')
    rows = tuple(_from_plan(row) for row in preview.plan)
    try:
        imported = RegulatoryTariffImport(created_by_id=g.current_user.id, file_name=preview.file_name,
            file_hash=preview.file_hash, source_url=preview.source_url, source_version=preview.source_version,
            status='completed', summary=preview.summary, completed_at=datetime.utcnow())
        db.session.add(imported); db.session.flush()
        created = unchanged = 0
        pending = []
        for row in rows:
            existing = _existing(row)
            if existing is not None:
                if not _same(existing, row):
                    raise ValueError('Conflito tarifário detectado após a prévia; envie nova prévia.')
                unchanged += 1; continue
            tariff = RegulatoryTariff(import_id=imported.id, file_hash=preview.file_hash,
                source_url=preview.source_url, source_version=preview.source_version, **row)
            db.session.add(tariff); pending.append(tariff)
            created += 1
            if len(pending) == 500:
                db.session.flush()
                for item in pending: db.session.expunge(item)
                pending.clear()
        if pending:
            db.session.flush()
            for item in pending: db.session.expunge(item)
        preview.consumed_at = datetime.utcnow(); preview.status = 'consumed'
        imported.summary = {**preview.summary, 'created': created, 'unchanged': unchanged}
        db.session.commit()
        return {'importId': imported.id, 'created': created, 'unchanged': unchanged,
                'sourceVersion': imported.source_version, 'coverage': _coverage()}
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Conflito tarifário detectado; gere uma nova prévia.') from exc
    except Exception:
        db.session.rollback()
        raise


def status() -> dict:
    latest = RegulatoryTariffImport.query.order_by(RegulatoryTariffImport.completed_at.desc()).first()
    count = RegulatoryTariff.query.count()
    return {
        'status': 'updated' if latest else 'missing', 'records': count, 'coverage': _coverage(),
        'lastImport': None if latest is None else {
            'id': latest.id, 'completedAt': latest.completed_at.isoformat() if latest.completed_at else None,
            'sourceVersion': latest.source_version, 'records': latest.summary.get('created', 0) + latest.summary.get('unchanged', 0),
            'createdById': latest.created_by_id,
        },
    }


def _file(file_storage):
    if file_storage is None or not (file_storage.filename or '').lower().endswith('.csv'):
        raise ValueError('Envie um arquivo CSV oficial da ANEEL.')
    if len(file_storage.filename) > 255:
        raise ValueError('Nome do arquivo excede o limite permitido.')
    path, digest = _copy_to_temp(file_storage.stream)
    return path, file_storage.filename, digest


def _temp_dir(value=None):
    path = Path(value or Config.REGULATORY_TARIFF_TEMP_DIR or Path(tempfile.gettempdir()) / 'hub-regulatory-tariffs')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _copy_to_temp(stream, temp_dir=None):
    folder = _temp_dir(temp_dir)
    handle = tempfile.NamedTemporaryFile(mode='xb', prefix=TEMP_PREFIX, suffix='.csv', dir=folder, delete=False)
    path = Path(handle.name)
    digest = hashlib.sha256(); size = 0
    try:
        with handle:
            while chunk := stream.read(CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise UploadTooLarge(f'Arquivo vazio ou maior que {MAX_BYTES // (1024 * 1024)} MiB.')
                digest.update(chunk); handle.write(chunk)
        if not size:
            raise ValueError('Arquivo vazio ou maior que 100 MiB.')
        return path, digest.hexdigest()
    except Exception:
        _remove_temp(path)
        raise


def _remove_temp(path):
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def purge_temporary_files(now=None, temp_dir=None):
    now = now or datetime.utcnow()
    cutoff = (now - timedelta(minutes=TTL_MINUTES + 5)).timestamp()
    removed = 0
    for path in _temp_dir(temp_dir).glob(f'{TEMP_PREFIX}*'):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                if path.resolve() not in ACTIVE_TEMP_PATHS:
                    path.unlink(); removed += 1
        except OSError:
            continue
    return removed


def purge_expired_previews(now=None):
    now = now or datetime.utcnow()
    removed = RegulatoryTariffPreview.query.filter(RegulatoryTariffPreview.expires_at < now).delete(
        synchronize_session=False)
    db.session.commit()
    return {'previews': removed, 'files': purge_temporary_files(now)}


def _source_url(value):
    url = (value or ANEEL_PORTAL).strip()
    if not url.startswith('https://dadosabertos.aneel.gov.br/'):
        raise ValueError('A fonte deve ser uma URL HTTPS oficial da ANEEL.')
    if len(url) > 1000:
        raise ValueError('URL da fonte excede o limite permitido.')
    return url


def _rows(path):
    def stream_rows():
        try:
            with Path(path).open('rb') as binary, io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as text:
                sample = text.read(8192); text.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=',;')
                reader = csv.DictReader(text, dialect=dialect)
                fields = reader.fieldnames or ()
                if len(fields) != len(set(fields)) or not REQUIRED.issubset(set(fields)):
                    missing = sorted(REQUIRED - set(fields))
                    raise ValueError('UNSUPPORTED_SOURCE_SCHEMA: colunas ANEEL ausentes: ' + ', '.join(missing))
                found = False
                for count, row in enumerate(reader, 1):
                    if count > Config.REGULATORY_TARIFF_MAX_ROWS:
                        raise ValueError('CSV ANEEL excede o limite de linhas.')
                    found = True
                    if None in row:
                        raise ValueError('Linha CSV possui quantidade de colunas inválida.')
                    yield row
                if not found:
                    raise ValueError('CSV ANEEL sem linhas.')
        except UnicodeDecodeError as exc:
            raise ValueError('CSV ANEEL deve usar UTF-8.') from exc
        except csv.Error as exc:
            raise ValueError('CSV ANEEL inválido ou sem delimitador reconhecido.') from exc
    return stream_rows()


def _plan(rows, source_url, source_version):
    plan, display, seen = [], [], set()
    summary = {'validos': 0, 'ignorados': 0, 'duplicados': 0, 'conflitos': 0, 'rejeitados': 0, 'linhas': []}
    for line, source in enumerate(rows, 2):
        try:
            row = _normalize(source)
        except ValueError as exc:
            summary['rejeitados'] += 1; summary['linhas'].append({'linha': line, 'situacao': 'rejeitada', 'motivo': str(exc)}); continue
        if row is None:
            summary['ignorados'] += 1; continue
        key = _key(row)
        if key in seen:
            summary['duplicados'] += 1; summary['linhas'].append({'linha': line, 'situacao': 'duplicada', 'motivo': 'Chave natural repetida no arquivo.'}); continue
        seen.add(key)
        existing = _existing(row)
        if (existing and not _same(existing, row)) or (not existing and _overlap(row)):
            summary['conflitos'] += 1; state = 'conflito'; reason = 'Mesmo período e dimensões com valor ou fonte divergente.'
        else:
            summary['validos'] += 1; state = 'mantida' if existing else 'nova'; reason = None; plan.append(_stored_row(row))
        display.append({**_public_row(row), 'linha': line, 'situacao': state, 'motivo': reason})
    summary['linhas'] = (summary['linhas'] + display)[:100]
    if not plan and not summary['conflitos']:
        summary['rejeitados'] += 1
        summary['linhas'].append({'linha': None, 'situacao': 'rejeitada', 'motivo': 'MISSING_COMPONENT: nenhuma linha TUSD_FioB aplicável.'})
    return plan, summary


def _normalize(source):
    if any(value is None for name, value in source.items() if name is not None):
        raise ValueError('Linha CSV incompleta.')
    if any(isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) for value in source.values()):
        raise ValueError('Fórmulas não são permitidas no CSV ANEEL.')
    if source['DscComponenteTarifario'].strip() != 'TUSD_FioB':
        return None
    if source['DscBaseTarifaria'].strip() != 'Tarifa de Aplicação' or source['DscDetalheConsumidor'].strip() != 'SCEE':
        raise ValueError('Componente Fio B sem Tarifa de Aplicação/SCEE.')
    if source['DscUnidade'].strip() != 'R$/MWh':
        raise ValueError('Unidade TUSD_FioB não suportada.')
    try:
        value = source['VlrComponenteTarifario'].strip()
        if value.count(',') == 1 and '.' not in value:
            value = value.replace(',', '.')
        raw = Decimal(value)
        start, end = date.fromisoformat(source['DatInicioVigencia']), date.fromisoformat(source['DatFimVigencia'])
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Valor ou vigência ANEEL inválidos.') from exc
    if not raw.is_finite() or raw < 0 or start > end:
        raise ValueError('Valor ou vigência ANEEL inválidos.')
    with localcontext(Context(prec=len(raw.as_tuple().digits) + 4)):
        kwh = raw / Decimal(1000)
    period = source['DscPostoTarifario'].strip()
    return {'official_distributor': source['SigNomeAgente'].strip(), 'distributor': _distributor(source['SigNomeAgente']),
            'component': 'TUSD_FIO_B', 'base_tariff': 'Tarifa de Aplicação', 'subgroup': source['DscSubGrupoTarifario'].strip(),
            'modality': source['DscModalidadeTarifaria'].strip().upper(), 'tariff_class': _optional(source['DscClasseConsumidor']) or '',
            'tariff_subclass': _optional(source['DscSubClasseConsumidor']) or '', 'tariff_detail': 'SCEE',
            'tariff_period': '' if period == 'Não se aplica' else (_optional(period) or ''), 'source_value': raw,
            'source_unit': 'R$/MWh', 'value_kwh': kwh, 'valid_from': start, 'valid_until': end,
            'source_reference': source['DscResolucaoHomologatoria'].strip()}


def _distributor(value):
    return {'COPEL-DIS': 'Copel'}.get(value.strip(), value.strip())


def _optional(value):
    result = value.strip()
    return result or None


def _key(row):
    return tuple(row[name] for name in ('official_distributor', 'component', 'base_tariff', 'subgroup', 'modality',
        'tariff_class', 'tariff_subclass', 'tariff_detail', 'tariff_period', 'valid_from', 'valid_until'))


def _existing(row):
    return RegulatoryTariff.query.filter_by(**dict(zip(
        ('official_distributor', 'component', 'base_tariff', 'subgroup', 'modality', 'tariff_class',
         'tariff_subclass', 'tariff_detail', 'tariff_period', 'valid_from', 'valid_until'), _key(row)))).first()


def _overlap(row):
    fields = ('official_distributor', 'component', 'base_tariff', 'subgroup', 'modality', 'tariff_class',
              'tariff_subclass', 'tariff_detail', 'tariff_period')
    return RegulatoryTariff.query.filter_by(**{field: row[field] for field in fields}).filter(
        RegulatoryTariff.valid_from <= row['valid_until'], RegulatoryTariff.valid_until >= row['valid_from']).first()


def _same(record, row):
    return (record.source_value == row['source_value'] and record.source_unit == row['source_unit']
            and record.source_reference == row['source_reference'])


def _coverage():
    values = db.session.query(db.func.min(RegulatoryTariff.valid_from), db.func.max(RegulatoryTariff.valid_until)).one()
    return {'from': values[0].isoformat() if values[0] else None, 'until': values[1].isoformat() if values[1] else None}


def _public_row(row):
    return {**row, 'source_value': str(row['source_value']), 'value_kwh': str(row['value_kwh']),
            'valid_from': row['valid_from'].isoformat(), 'valid_until': row['valid_until'].isoformat()}


def _stored_row(row):
    return _public_row(row)


def _from_plan(row):
    return {**row, 'source_value': Decimal(row['source_value']), 'value_kwh': Decimal(row['value_kwh']),
            'valid_from': date.fromisoformat(row['valid_from']), 'valid_until': date.fromisoformat(row['valid_until'])}


def _preview_dict(preview):
    return {'previewId': preview.id, 'expiresAt': preview.expires_at.isoformat(), 'status': preview.status,
            **preview.summary, 'sourceVersion': preview.source_version}
