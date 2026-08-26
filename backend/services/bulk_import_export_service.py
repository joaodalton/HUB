# backend/services/bulk_import_export_service.py
"""
Importacao/exportacao em massa (CSV pipe-delimited) para clientes, UCs e usinas.
"""
import csv as csv_mod
import io as io_mod
from datetime import date

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.plant import Plant
from services.log_service import LogService


def _csv_writer(rows, fieldnames):
    buf = io_mod.StringIO()
    w = csv_mod.DictWriter(buf, fieldnames=fieldnames, delimiter='|',
                           lineterminator='\n', extrasaction='ignore')
    w.writeheader()
    for row in rows:
        w.writerow(row)
    return buf.getvalue()


def _csv_to_rows(text):
    buf = io_mod.StringIO(text)
    reader = csv_mod.DictReader(buf, delimiter='|')
    return [dict(r) for r in reader]


def export_clients_csv(empresa_id):
    clients = Client.query.filter_by(empresa_id=empresa_id).all()
    rows = [{
        'nome': c.nome,
        'cpf': c.cpf,
        'email': c.email,
        'telefone': c.telefone or '',
        'concessionaria': c.concessionaria,
        'status': c.status,
        'data_nascimento': c.data_nascimento.isoformat() if c.data_nascimento else '',
    } for c in clients]
    return _csv_writer(rows, ['nome', 'cpf', 'email', 'telefone',
                              'concessionaria', 'status', 'data_nascimento'])


def export_ucs_csv(empresa_id):
    ucs = ConsumerUnit.query.filter_by(empresa_id=empresa_id).all()
    rows = [{
        'cliente_id': str(uc.client_id),
        'codigo': uc.codigo,
        'codigo_aneel': uc.codigo_aneel or '',
        'apelido': uc.apelido or '',
        'documento': uc.documento or '',
        'endereco': uc.endereco or '',
        'cep': uc.cep or '',
        'concessionaria': uc.concessionaria or '',
        'geracao_propria': str(uc.geracao_propria).lower(),
        'dia_emissao_fatura': str(uc.dia_emissao_fatura) if uc.dia_emissao_fatura else '',
        'consumo': str(uc.consumo) if uc.consumo is not None else '',
        'base_tarifaria': uc.base_tarifaria,
        'desconto': uc.desconto or '',
        'tipo_ligacao': uc.tipo_ligacao,
        'inicio_contrato': uc.inicio_contrato.isoformat() if uc.inicio_contrato else '',
        'termino_contrato': uc.termino_contrato.isoformat() if uc.termino_contrato else '',
        'carencia_meses': str(uc.carencia_meses) if uc.carencia_meses else '',
    } for uc in ucs]
    return _csv_writer(rows, [
        'cliente_id', 'codigo', 'codigo_aneel', 'apelido', 'documento',
        'endereco', 'cep', 'concessionaria', 'geracao_propria',
        'dia_emissao_fatura', 'consumo', 'base_tarifaria', 'desconto',
        'tipo_ligacao', 'inicio_contrato', 'termino_contrato', 'carencia_meses'
    ])


def export_plants_csv(empresa_id):
    plants = Plant.query.filter_by(empresa_id=empresa_id).all()
    rows = [{
        'nome': p.nome,
        'uc': p.uc,
        'kw_pico': str(p.kw_pico),
        'status': p.status,
        'marca_inversor': p.marca_inversor or '',
        'telefone_proprietario': p.telefone_proprietario or '',
        'email_proprietario': p.email_proprietario or '',
        'cidade': p.cidade or '',
        'uf': p.uf or '',
        'endereco': p.endereco or '',
        'data_ativacao': p.data_ativacao.isoformat() if p.data_ativacao else '',
        'responsavel': p.responsavel or '',
        'cep': p.cep or '',
        'latitude': str(p.latitude) if p.latitude is not None else '',
        'longitude': str(p.longitude) if p.longitude is not None else '',
        'num_modulos': str(p.num_modulos) if p.num_modulos else '',
        'potencia_modulo_w': str(p.potencia_modulo_w) if p.potencia_modulo_w else '',
        'producao_jan': str(p.producao_jan),
        'producao_fev': str(p.producao_fev),
        'producao_mar': str(p.producao_mar),
        'producao_abr': str(p.producao_abr),
        'producao_mai': str(p.producao_mai),
        'producao_jun': str(p.producao_jun),
        'producao_jul': str(p.producao_jul),
        'producao_ago': str(p.producao_ago),
        'producao_set': str(p.producao_set),
        'producao_out': str(p.producao_out),
        'producao_nov': str(p.producao_nov),
        'producao_dez': str(p.producao_dez),
        'reserva_percentual': str(p.reserva_percentual),
        'producao_media_manual': str(p.producao_media_manual) if p.producao_media_manual else '',
        'dia_emissao_usina': str(p.dia_emissao_usina) if p.dia_emissao_usina else '',
        'is_coringa': str(p.is_coringa).lower(),
        'concessionaria': p.concessionaria or '',
    } for p in plants]
    return _csv_writer(rows, [
        'nome', 'uc', 'kw_pico', 'status', 'marca_inversor',
        'telefone_proprietario', 'email_proprietario', 'cidade', 'uf',
        'endereco', 'data_ativacao', 'responsavel', 'cep', 'latitude',
        'longitude', 'num_modulos', 'potencia_modulo_w',
        'producao_jan', 'producao_fev', 'producao_mar', 'producao_abr',
        'producao_mai', 'producao_jun', 'producao_jul', 'producao_ago',
        'producao_set', 'producao_out', 'producao_nov', 'producao_dez',
        'reserva_percentual', 'producao_media_manual', 'dia_emissao_usina',
        'is_coringa', 'concessionaria'
    ])


def _pBool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('true', '1', 'sim', 'yes')


def _pFloat(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _pInt(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _pDate(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        parts = str(v).strip().split('-')
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        pass
    return None


def import_clients_from_csv(empresa_id, text):
    rows = _csv_to_rows(text)
    ok, fails = 0, []
    for idx, row in enumerate(rows, start=2):
        try:
            nome = (row.get('nome') or '').strip()
            cpf = (row.get('cpf') or '').strip()
            email = (row.get('email') or '').strip()
            if not nome or not cpf or not email:
                raise ValueError('nome/cpf/email vazios')
            telefone = (row.get('telefone') or '').strip() or None
            concessionaria = (row.get('concessionaria') or 'Copel').strip() or 'Copel'
            data_nascimento = _pDate(row.get('data_nascimento'))
            client = Client(
                empresa_id=empresa_id, nome=nome, cpf=cpf, email=email,
                telefone=telefone, concessionaria=concessionaria,
                data_nascimento=data_nascimento,
            )
            db.session.add(client)
            db.session.flush()
            ok += 1
        except Exception as exc:
            db.session.rollback()
            fails.append({'linha': idx, 'erro': str(exc)})
    db.session.commit()
    LogService.info(
        acao='bulk_clients_import',
        mensagem=f'Importados {ok} clientes, {len(fails)} falha(s)',
        entidade='Client',
        metadados={'empresa_id': empresa_id, 'importados': ok, 'falhas': len(fails)},
    )
    return {'importados': ok, 'falhas': fails}


def import_ucs_from_csv(empresa_id, text):
    rows = _csv_to_rows(text)
    ok, fails = 0, []
    for idx, row in enumerate(rows, start=2):
        try:
            cliente_id = _pInt(row.get('cliente_id'))
            if not cliente_id:
                raise ValueError('cliente_id vazio')
            client = Client.query.get(cliente_id)
            if not client or client.empresa_id != empresa_id:
                raise ValueError(f'cliente_id={cliente_id} nao encontrado')
            codigo = (row.get('codigo') or '').strip()
            if not codigo:
                raise ValueError('codigo vazio')
            uc = ConsumerUnit(
                empresa_id=empresa_id, client_id=cliente_id, codigo=codigo,
                codigo_aneel=(row.get('codigo_aneel') or '').strip() or None,
                apelido=(row.get('apelido') or '').strip() or '',
                documento=(row.get('documento') or '').strip() or None,
                endereco=(row.get('endereco') or '').strip() or None,
                cep=(row.get('cep') or '').strip() or None,
                concessionaria=(row.get('concessionaria') or '').strip() or None,
                geracao_propria=_pBool(row.get('geracao_propria')),
                base_tarifaria=(row.get('base_tarifaria') or 'B1').strip() or 'B1',
                desconto=(row.get('desconto') or '').strip() or None,
            )
            consumo = _pFloat(row.get('consumo'))
            if consumo is not None:
                uc.consumo = consumo
            tl = (row.get('tipo_ligacao') or 'Monofasico').strip()
            if tl not in ('Monofasico', 'Bifasico', 'Trifasico'):
                raise ValueError(f'tipo_ligacao invalido: {tl}')
            uc.tipo_ligacao = tl
            uc.dia_emissao_fatura = _pInt(row.get('dia_emissao_fatura'))
            uc.inicio_contrato = _pDate(row.get('inicio_contrato'))
            uc.termino_contrato = _pDate(row.get('termino_contrato'))
            uc.carencia_meses = _pInt(row.get('carencia_meses'))
            db.session.add(uc)
            db.session.flush()
            ok += 1
        except Exception as exc:
            db.session.rollback()
            fails.append({'linha': idx, 'erro': str(exc)})
    db.session.commit()
    LogService.info(
        acao='bulk_ucs_import',
        mensagem=f'Importadas {ok} UCs, {len(fails)} falha(s)',
        entidade='ConsumerUnit',
        metadados={'empresa_id': empresa_id, 'importados': ok, 'falhas': len(fails)},
    )
    return {'importados': ok, 'falhas': fails}


def import_plants_from_csv(empresa_id, text):
    rows = _csv_to_rows(text)
    ok, fails = 0, []
    for idx, row in enumerate(rows, start=2):
        try:
            nome = (row.get('nome') or '').strip()
            uc_codigo = (row.get('uc') or '').strip()
            if not nome or not uc_codigo:
                raise ValueError('nome/uc vazios')
            kw_pico = _pFloat(row.get('kw_pico'))
            if kw_pico is None or kw_pico <= 0:
                raise ValueError('kw_pico invalido')
            plant = Plant(
                empresa_id=empresa_id, nome=nome, uc=uc_codigo, kw_pico=kw_pico,
                status=(row.get('status') or 'Implantacao').strip() or 'Implantacao',
            )
            plant.marca_inversor = (row.get('marca_inversor') or '').strip() or None
            plant.telefone_proprietario = (row.get('telefone_proprietario') or '').strip() or None
            plant.email_proprietario = (row.get('email_proprietario') or '').strip() or None
            plant.cidade = (row.get('cidade') or '').strip() or None
            plant.uf = (row.get('uf') or '').strip() or None
            plant.endereco = (row.get('endereco') or '').strip() or None
            plant.data_ativacao = _pDate(row.get('data_ativacao'))
            plant.responsavel = (row.get('responsavel') or '').strip() or None
            plant.cep = (row.get('cep') or '').strip() or None
            plant.latitude = _pFloat(row.get('latitude'))
            plant.longitude = _pFloat(row.get('longitude'))
            plant.num_modulos = _pInt(row.get('num_modulos'))
            plant.potencia_modulo_w = _pFloat(row.get('potencia_modulo_w'))
            for mes in ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
                        'jul', 'ago', 'set', 'out', 'nov', 'dez']:
                v = _pFloat(row.get(f'producao_{mes}'))
                if v is not None:
                    setattr(plant, f'producao_{mes}', v)
            plant.reserva_percentual = _pFloat(row.get('reserva_percentual')) or 0
            plant.producao_media_manual = _pFloat(row.get('producao_media_manual'))
            plant.dia_emissao_usina = _pInt(row.get('dia_emissao_usina'))
            plant.is_coringa = _pBool(row.get('is_coringa'))
            plant.concessionaria = (row.get('concessionaria') or '').strip() or None
            db.session.add(plant)
            db.session.flush()
            ok += 1
        except Exception as exc:
            db.session.rollback()
            fails.append({'linha': idx, 'erro': str(exc)})
    db.session.commit()
    LogService.info(
        acao='bulk_plants_import',
        mensagem=f'Importadas {ok} usinas, {len(fails)} falha(s)',
        entidade='Plant',
        metadados={'empresa_id': empresa_id, 'importados': ok, 'falhas': len(fails)},
    )
    return {'importados': ok, 'falhas': fails}
