"""Catalogo de planos do HUB; edite este arquivo para alterar franquias."""
from decimal import Decimal

PLANOS = {
    'starter': {
        'nome': 'Starter',
        'preco': Decimal('600'),
        'comprável': True,
        'franquia': {'usuarios': 3, 'ucs': 300, 'usinas': 5},
        'flags': {
            'robo_ava': False,
            'robo_envio_rateio': False,
            'robo_protocolo': False,
        },
    },
    'avancado': {
        'nome': 'Avançado',
        'preco': Decimal('900'),
        'comprável': True,
        'franquia': {'usuarios': 8, 'ucs': 750, 'usinas': 13},
        'flags': {
            'robo_ava': True,
            'robo_envio_rateio': False,
            'robo_protocolo': False,
        },
    },
    'enterprise': {
        'nome': 'Enterprise',
        'preco': Decimal('1200'),
        'comprável': True,
        'franquia': {'usuarios': 12, 'ucs': 1125, 'usinas': 19},
        'flags': {
            'robo_ava': False,
            'robo_envio_rateio': False,
            'robo_protocolo': False,
        },
    },
    'teste': {
        'nome': 'Teste',
        'preco': None,
        'comprável': False,
        'franquia': {'usuarios': 1, 'ucs': 50, 'usinas': 2},
        'flags': {
            'robo_ava': False,
            'robo_envio_rateio': False,
            'robo_protocolo': False,
        },
    },
}

PRECO_EXCEDENTE = {
    'usina': Decimal('5'),
    'uc': Decimal('2'),
    'usuario': Decimal('3.5'),
}

PLANO_PADRAO = 'starter'


def get_plano(chave: str) -> dict:
    return PLANOS.get(chave, PLANOS[PLANO_PADRAO])
