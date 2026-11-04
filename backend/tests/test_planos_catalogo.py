from decimal import Decimal
from planos.catalogo import PLANOS, PRECO_EXCEDENTE, get_plano

def test_tres_planos_principais_mais_teste():
    assert set(PLANOS) == {'starter', 'avancado', 'enterprise', 'teste'}

def test_franquia_starter():
    assert get_plano('starter')['franquia'] == {'usuarios': 3, 'ucs': 300, 'usinas': 5}

def test_franquia_avancado():
    assert get_plano('avancado')['franquia'] == {'usuarios': 8, 'ucs': 750, 'usinas': 13}

def test_franquia_enterprise():
    assert get_plano('enterprise')['franquia'] == {'usuarios': 12, 'ucs': 1125, 'usinas': 19}

def test_franquia_teste():
    assert get_plano('teste')['franquia'] == {'usuarios': 1, 'ucs': 50, 'usinas': 2}

def test_plano_teste_nao_tem_preco_e_nao_e_compravel():
    assert get_plano('teste')['preco'] is None
    assert get_plano('teste')['comprável'] is False

def test_precos_planos_principais():
    assert get_plano('starter')['preco'] == Decimal('600')
    assert get_plano('avancado')['preco'] == Decimal('900')
    assert get_plano('enterprise')['preco'] == Decimal('1200')

def test_avancado_libera_robo_ava_starter_nao():
    assert get_plano('starter')['flags']['robo_ava'] is False
    assert get_plano('avancado')['flags']['robo_ava'] is True

def test_preco_excedente_fixo():
    assert PRECO_EXCEDENTE == {'usina': Decimal('5'), 'uc': Decimal('2'), 'usuario': Decimal('3.5')}

def test_nenhum_plano_tem_franquia_de_cliente():
    for chave, plano in PLANOS.items():
        assert 'clientes' not in plano['franquia'], chave
