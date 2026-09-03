# backend/services/rateio_formulario_service.py
"""
Monta a tabela de revisao do Formulario Copel de Rateio (Associacoes) a
partir das PlantConnection JA CONFIRMADAS de uma usina, e confere se cada UC
beneficiaria tem o Termo de Adesao anexado -- pre-requisito pra Sprint 4
(geracao do PDF) poder bloquear a geracao com seguranca.

Linha 1 da tabela e sempre a propria usina/associacao (UC ancora), 0% fixo --
decisao registrada com o Joao: nao existe campo de "UC ancora" separado,
a usina geradora sempre ocupa essa posicao.
"""
import unicodedata
from datetime import datetime

from flask import g

from extensions import db
from models.consumer_unit import PlantConnection
from models.document import Document
from models.empresa import Empresa
from models.pendencia import Pendencia
from models.plant import Plant
from services.pendencia_service import criar_pendencia_manual


def _normalizar(texto: str | None) -> str:
    if not texto:
        return ''
    sem_acento = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('ascii')
    return sem_acento.lower()


def buscar_termo_adesao(client_id: int | None, consumer_unit_id: int | None) -> Document | None:
    """Considera 'tem termo de adesao' se existir QUALQUER Document vinculado
    ao cliente OU a UC cujo nome OU categoria contenha 'termo' e 'adesao' --
    mesmo criterio (substring, sem acento) ja usado em automacao_service.py
    e documentRules.ts, pra nao introduzir uma segunda regra de matching."""
    if not client_id and not consumer_unit_id:
        return None

    query = Document.query
    if client_id and consumer_unit_id:
        query = query.filter(
            (Document.client_id == client_id) | (Document.consumer_unit_id == consumer_unit_id)
        )
    elif client_id:
        query = query.filter(Document.client_id == client_id)
    else:
        query = query.filter(Document.consumer_unit_id == consumer_unit_id)

    for documento in query.all():
        nome = _normalizar(documento.nome)
        categoria_nome = _normalizar(documento.category.nome) if documento.category else ''
        alvo = f'{nome} {categoria_nome}'
        if 'termo' in alvo and 'adesao' in alvo:
            return documento

    return None


def _tem_termo_adesao(client_id: int | None, consumer_unit_id: int | None) -> bool:
    return buscar_termo_adesao(client_id, consumer_unit_id) is not None


# Formulario oficial (paginas 1-2) so tem 24 linhas de beneficiarias -- passar
# disso nao cabe no PDF. Bloqueado explicitamente em vez de estourar silenciosamente
# na hora do overlay (Sprint 4).
MAX_LINHAS_BENEFICIARIAS = 24


def montar_tabela_formulario(plant_id: int) -> dict:
    """Retorna os dados completos pro formulario Copel: geradora/ancora (campos
    de topo -- SEMPRE a propria usina, ver decisao com o Joao) + linhas das
    beneficiarias (so essas entram na tabela -- o formulario oficial NAO tem
    linha pra geradora dentro da tabela, e um campo de texto separado no topo
    da pagina 1). termoAdesaoOk calculado por linha -- a tela de revisao usa
    isso pra mostrar aviso inline antes mesmo de tentar gerar o PDF."""
    plant = Plant.query.filter_by(id=plant_id, empresa_id=g.current_empresa_id).first()
    if not plant:
        raise ValueError('Usina nao encontrada.')

    empresa = Empresa.query.get(g.current_empresa_id)
    if not empresa:
        raise ValueError('Empresa nao encontrada.')

    conexoes = PlantConnection.query.filter_by(plant_id=plant.id).all()

    # Ordenacao alfabetica pelo nome do cliente titular -- mesma ordem que a
    # Sprint 4 usa pra mesclar os PDFs de Termo de Adesao.
    conexoes_ordenadas = sorted(
        conexoes,
        key=lambda c: _normalizar(c.consumer_unit.client.nome) if c.consumer_unit and c.consumer_unit.client else ''
    )

    linhas = []
    for ordem, conexao in enumerate(conexoes_ordenadas, start=1):
        uc = conexao.consumer_unit
        cliente = uc.client if uc else None

        linhas.append({
            'ordem': ordem,
            'nome': cliente.nome if cliente else '(cliente nao encontrado)',
            # documento da UC (uc.documento) tem prioridade sobre o CPF do
            # cliente -- ver comentario em models/consumer_unit.py: a UC pode
            # estar em CPF/CNPJ diferente do titular cadastrado no Cliente.
            'documento': (uc.documento if uc and uc.documento else (cliente.cpf if cliente else None)),
            # codigo (nao codigoAneel) -- e o identificador que a Copel usa
            # hoje nas telas/atendimento. Se precisar trocar pra codigoAneel,
            # e so essa linha.
            'ucIdentificacao': uc.codigo if uc else None,
            'percentual': float(conexao.percentual or 0),
            'termoAdesaoOk': _tem_termo_adesao(cliente.id if cliente else None, uc.id if uc else None),
            'clienteId': cliente.id if cliente else None,
            'ucId': uc.id if uc else None
        })

    soma_percentual = round(sum(linha['percentual'] for linha in linhas), 2)

    return {
        'plantId': plant.id,
        'plantNome': plant.nome,
        'ucGeradora': plant.uc,
        'ucAncora': plant.uc,  # ancora = a propria usina, sempre (decisao com o Joao)
        'empresaNome': empresa.razao_social or empresa.nome,
        'empresaCnpj': empresa.cnpj,
        'empresaEmail': empresa.email,
        'documentoCnpjOk': empresa.documento_cnpj_id is not None,
        'documentoEstatutoOk': empresa.documento_estatuto_id is not None,
        'linhas': linhas,
        'somaPercentual': soma_percentual,
        'excedeLimiteLinhas': len(linhas) > MAX_LINHAS_BENEFICIARIAS
    }


def verificar_termos_adesao(plant_id: int, registrar_pendencia: bool = False) -> dict:
    """Roda a mesma checagem de montar_tabela_formulario, mas so devolve
    quem esta faltando -- e, se faltar algo, ja cria a Pendencia urgente
    (categoria 'Documentos', prioridade 'critica' -- o sistema nao tem uma
    categoria chamada 'Urgente' hoje, prioridade e o campo que carrega essa
    urgencia). Usado pela geracao do PDF (Sprint 4) pra bloquear ANTES de
    gastar tempo montando o formulario."""
    tabela = montar_tabela_formulario(plant_id)

    faltando = [linha for linha in tabela['linhas'] if not linha['termoAdesaoOk']]

    pendencia = Pendencia.query.filter_by(
        plant_id=plant_id,
        categoria='Documentos',
        origem='Automacao',
        status='aberta'
    ).filter(
        Pendencia.titulo.like('Termo de adesão faltando para gerar formulário Copel%')
    ).first()

    if not faltando:
        if registrar_pendencia and pendencia:
            pendencia.status = 'resolvida'
            pendencia.resolved_at = datetime.utcnow()
            db.session.commit()
        return {'ok': True, 'faltando': []}

    nomes = ', '.join(linha['nome'] for linha in faltando)

    dados_pendencia = {
        'categoria': 'Documentos',
        'origem': 'Automacao',
        'titulo': f'Termo de adesão faltando para gerar formulário Copel — {tabela["plantNome"]}',
        'descricao': (
            f'Não é possível gerar o formulário de rateio da usina "{tabela["plantNome"]}" '
            f'porque as seguintes UCs beneficiárias não têm Termo de Adesão anexado: {nomes}.'
        ),
        'prioridade': 'critica',
        'usinaId': plant_id,
        'metadados': {
            'regra': 'rateio_termo_adesao',
            'plantId': plant_id,
            'ucsFaltando': [
                {'clienteId': linha['clienteId'], 'ucId': linha['ucId'], 'nome': linha['nome']}
                for linha in faltando
            ]
        }
    }

    if registrar_pendencia:
        if pendencia:
            pendencia.titulo = dados_pendencia['titulo']
            pendencia.descricao = dados_pendencia['descricao']
            pendencia.prioridade = 'critica'
            pendencia.metadados = dados_pendencia['metadados']
            db.session.commit()
        else:
            criar_pendencia_manual(dados_pendencia)

    return {
        'ok': False,
        'faltando': [
            {'clienteId': linha['clienteId'], 'ucId': linha['ucId'], 'nome': linha['nome']}
            for linha in faltando
        ]
    }
