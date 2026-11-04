"""Isenta assinaturas legadas da cobranca nova e trava a franquia antiga.

Toda Assinatura com plano_chave='starter' criada antes da reforma de planos
tinha uma franquia maior (10 usinas / 1000 ucs / 10 usuarios) do que o novo
catalogo 'starter' (5 usinas / 300 ucs / 3 usuarios). Este script marca essas
assinaturas como isentas de cobranca e cria LimiteContratado travando a
franquia antiga, para que o efetivo da empresa nunca encolha.

Uso (dentro de backend/, com o ambiente virtual ativo):
    python scripts/migrar_assinaturas_legadas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from extensions import db
from models.assinatura import Assinatura
from models.limite_contratado import LimiteContratado

FRANQUIA_ANTIGA_STARTER = {'usuarios': 10, 'ucs': 1000, 'usinas': 10}


def main() -> None:
    app = create_app()
    with app.app_context():
        # asaas_subscription_id IS NULL distingue legado de um starter pago novo
        # (concluir_cadastro sempre grava asaas_subscription_id) -- sem essa
        # condicao, re-rodar o script depois desta feature marcaria clientes
        # pagantes como isentos e travaria a franquia antiga (errada) neles.
        assinaturas = Assinatura.query.filter_by(
            plano_chave='starter', isento_cobranca=False, asaas_subscription_id=None,
        ).all()
        for assinatura in assinaturas:
            assinatura.isento_cobranca = True
            for recurso, quantidade in FRANQUIA_ANTIGA_STARTER.items():
                existente = LimiteContratado.query.filter_by(
                    empresa_id=assinatura.empresa_id, recurso=recurso,
                ).first()
                if existente is None:
                    db.session.add(LimiteContratado(
                        empresa_id=assinatura.empresa_id,
                        recurso=recurso,
                        quantidade_contratada=quantidade,
                    ))
        db.session.commit()
        print(f'{len(assinaturas)} assinatura(s) legada(s) isenta(s) de cobranca.')
        db.session.remove()
        db.engine.dispose()


if __name__ == '__main__':
    main()
