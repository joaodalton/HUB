"""Popula a empresa 'pedro-8fd9' com dados FALSOS para teste manual:
200 clientes, 250 UCs (parte dos clientes com mais de uma) e 20 usinas,
cada UC conectada a uma usina. Roda fora de request context, então o
filtro automático de tenant (extensions.py) não interfere -- empresa_id
é setado manualmente em cada linha.

Uso: python scripts/seed_pedro_fake_data.py
"""
import random
from datetime import date, timedelta
from decimal import Decimal

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models.empresa import Empresa
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.plant import Plant, MESES

EMPRESA_SLUG = 'pedro-8fd9'
N_CLIENTS = 200
N_UCS = 250
N_PLANTS = 20

random.seed(42)

NOMES = ['Ana', 'Bruno', 'Carla', 'Daniel', 'Eduarda', 'Felipe', 'Gabriela', 'Henrique',
         'Isabela', 'João', 'Larissa', 'Marcos', 'Natália', 'Otávio', 'Patrícia', 'Rafael',
         'Sabrina', 'Thiago', 'Valentina', 'William', 'Beatriz', 'Caio', 'Débora', 'Enzo',
         'Fernanda', 'Gustavo', 'Helena', 'Igor', 'Juliana', 'Kevin']
SOBRENOMES = ['Silva', 'Souza', 'Oliveira', 'Santos', 'Pereira', 'Costa', 'Rodrigues',
              'Almeida', 'Nascimento', 'Lima', 'Araújo', 'Fernandes', 'Carvalho', 'Gomes',
              'Martins', 'Rocha', 'Ribeiro', 'Alves', 'Monteiro', 'Cardoso']
CIDADES_UF = [('Curitiba', 'PR'), ('Londrina', 'PR'), ('Maringá', 'PR'), ('Ponta Grossa', 'PR'),
              ('Cascavel', 'PR'), ('Foz do Iguaçu', 'PR'), ('Guarapuava', 'PR'), ('Toledo', 'PR')]
RUAS = ['Rua das Flores', 'Av. Brasil', 'Rua XV de Novembro', 'Rua Marechal Deodoro',
        'Av. Sete de Setembro', 'Rua Paraná', 'Rua Santa Catarina', 'Av. Presidente Kennedy']
MARCAS_INVERSOR = ['Growatt', 'Fronius', 'Huawei', 'WEG', 'Deye', 'Sungrow']


def cpf_falso(seq: int) -> str:
    base = [int(d) for d in f'{seq:09d}']

    def dv(nums, peso_inicial):
        soma = sum(n * p for n, p in zip(nums, range(peso_inicial, 1, -1)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    d1 = dv(base, 10)
    d2 = dv(base + [d1], 11)
    digits = base + [d1, d2]
    s = ''.join(str(d) for d in digits)
    return f'{s[0:3]}.{s[3:6]}.{s[6:9]}-{s[9:11]}'


def nome_falso() -> str:
    return f'{random.choice(NOMES)} {random.choice(SOBRENOMES)}'


def email_falso(nome: str, seq: int) -> str:
    base = nome.lower().replace(' ', '.').replace('á', 'a').replace('ã', 'a').replace('é', 'e')
    return f'{base}{seq}@exemplo-teste.com'


def telefone_falso() -> str:
    return f'41{random.randint(90000, 99999)}{random.randint(1000, 9999)}'


def cep_falso() -> str:
    return f'{random.randint(80000, 87999)}-{random.randint(100, 999):03d}'


def data_nascimento_falsa() -> date:
    return date.today() - timedelta(days=random.randint(18 * 365, 70 * 365))


def criar_clientes(empresa_id: int) -> list[Client]:
    clientes = []
    for i in range(1, N_CLIENTS + 1):
        nome = nome_falso()
        cliente = Client(
            empresa_id=empresa_id,
            nome=nome,
            cpf=cpf_falso(i),
            email=email_falso(nome, i),
            telefone=telefone_falso(),
            concessionaria='Copel',
            status=random.choice(['Ativo', 'Esperando usina', 'Ativo', 'Ativo']),
            data_nascimento=data_nascimento_falsa(),
        )
        clientes.append(cliente)
    db.session.add_all(clientes)
    db.session.flush()
    return clientes


def criar_usinas(empresa_id: int) -> list[Plant]:
    usinas = []
    for i in range(1, N_PLANTS + 1):
        cidade, uf = random.choice(CIDADES_UF)
        kw_pico = Decimal(str(round(random.uniform(50, 1200), 2)))
        producao_base = float(kw_pico) * random.uniform(100, 140)
        usina = Plant(
            empresa_id=empresa_id,
            nome=f'Usina Solar {cidade} {i:02d}',
            uc=f'{random.randint(1000000, 9999999)}',
            kw_pico=kw_pico,
            status=random.choice(['Ativa', 'Ativa', 'Implantacao']),
            percentual_disponivel=random.randint(60, 100),
            marca_inversor=random.choice(MARCAS_INVERSOR),
            telefone_proprietario=telefone_falso(),
            email_proprietario=f'proprietario.usina{i}@exemplo-teste.com',
            cidade=cidade,
            uf=uf,
            endereco=f'{random.choice(RUAS)}, {random.randint(100, 2999)}',
            data_ativacao=date.today() - timedelta(days=random.randint(30, 900)),
            responsavel=nome_falso(),
            cep=cep_falso(),
            latitude=Decimal(str(round(random.uniform(-26.5, -23.0), 6))),
            longitude=Decimal(str(round(random.uniform(-54.0, -48.5), 6))),
            num_modulos=random.randint(80, 2000),
            potencia_modulo_w=Decimal(str(random.choice([450, 550, 600]))),
            reserva_percentual=Decimal(str(random.choice([0, 5, 10]))),
            dia_emissao_usina=random.randint(1, 28),
            concessionaria='Copel',
        )
        for mes in MESES:
            variacao = random.uniform(0.8, 1.2)
            setattr(usina, f'producao_{mes}', Decimal(str(round(producao_base * variacao, 2))))
        usinas.append(usina)
    db.session.add_all(usinas)
    db.session.flush()
    return usinas


def criar_ucs(empresa_id: int, clientes: list[Client], usinas: list[Plant]) -> None:
    # 1a UC de cada cliente garante os 200; as 50 restantes vao pra clientes
    # aleatorios (com repeticao), cobrindo o "alguns com mais de uma UC".
    atribuicoes = list(clientes)
    extras = random.sample(clientes, k=N_UCS - N_CLIENTS)
    atribuicoes.extend(extras)

    for idx, cliente in enumerate(atribuicoes, start=1):
        inicio = date.today() - timedelta(days=random.randint(30, 1000))
        uc = ConsumerUnit(
            empresa_id=empresa_id,
            client_id=cliente.id,
            codigo=f'{random.randint(1000000, 9999999)}',
            apelido=random.choice(['Casa', 'Comércio', 'Sítio', '']),
            documento=cliente.cpf,
            endereco=f'{random.choice(RUAS)}, {random.randint(10, 2999)}',
            cep=cep_falso(),
            concessionaria='Copel',
            geracao_propria=False,
            dia_emissao_fatura=random.randint(1, 28),
            consumo=Decimal(str(round(random.uniform(80, 900), 2))),
            base_tarifaria=random.choice(['B1', 'B2', 'B3']),
            desconto=f'{random.randint(10, 25)}%',
            tipo_ligacao=random.choice(['Monofasico', 'Bifasico', 'Trifasico']),
            inicio_contrato=inicio,
            carencia_meses=random.choice([0, 3, 6]),
            percentual_desconto_carencia=str(random.choice([0, 5, 10])),
            documentacao_completa=random.choice([True, True, False]),
            sem_pendencia_financeira=random.choice([True, False]),
            cliente_estrategico=random.random() < 0.1,
        )
        db.session.add(uc)
        db.session.flush()

        usina = random.choice(usinas)
        conexao = PlantConnection(
            empresa_id=empresa_id,
            consumer_unit_id=uc.id,
            plant_id=usina.id,
            percentual=Decimal(str(round(random.uniform(1, 25), 2))),
            percentual_manual=False,
        )
        db.session.add(conexao)


def main() -> None:
    app = create_app()
    with app.app_context():
        empresa = Empresa.query.filter_by(slug=EMPRESA_SLUG).first()
        if not empresa:
            raise SystemExit(f"Empresa com slug '{EMPRESA_SLUG}' não encontrada.")

        print(f'Empresa: {empresa.nome} (id={empresa.id})')
        clientes = criar_clientes(empresa.id)
        print(f'{len(clientes)} clientes criados.')
        usinas = criar_usinas(empresa.id)
        print(f'{len(usinas)} usinas criadas.')
        criar_ucs(empresa.id, clientes, usinas)
        db.session.commit()
        print(f'{N_UCS} UCs criadas e conectadas a usinas.')


if __name__ == '__main__':
    main()
