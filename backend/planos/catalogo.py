"""Catalogo de planos do HUB; edite este arquivo para alterar franquias."""

PLANOS = {
    'starter': {
        'nome': 'Starter',
        'franquia': {
            'usuarios': 10,
            'clientes': 1000,
            'ucs': 1000,
            'usinas': 10,
        },
        'flags': {
            'robo_ava': False,
            'robo_envio_rateio': False,
            'robo_protocolo': False,
        },
    },
}

PLANO_PADRAO = 'starter'


def get_plano(chave: str) -> dict:
    return PLANOS.get(chave, PLANOS[PLANO_PADRAO])
