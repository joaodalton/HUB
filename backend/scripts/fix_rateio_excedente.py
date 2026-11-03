"""
Corrige usinas cuja soma de PlantConnection.percentual passou de 100% --
dado de teste gerado por scripts/seed_pedro_fake_data.py antes da correcao
do gerador (empresa_id=60, "pedro-8fd9"). Re-escala proporcionalmente os
percentuais existentes de cada usina afetada pra que a soma fique em 100%
exatos, sem remover nenhuma conexao.

Roda tudo numa transacao e so comita depois de confirmar que nenhuma usina
ficou acima de 100%.

USO (de dentro de backend/, com o venv ativado):
    python scripts/fix_rateio_excedente.py
"""
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from extensions import db
from models.consumer_unit import PlantConnection
from sqlalchemy import func

CEM = Decimal('100.00')
EMPRESA_ID = 60  # dado de teste da seed de scripts/seed_pedro_fake_data.py


def usinas_excedentes():
    """plant_id -> soma de percentual, so as que passam de 100%."""
    somas = (
        db.session.query(PlantConnection.plant_id, func.sum(PlantConnection.percentual))
        .filter(PlantConnection.empresa_id == EMPRESA_ID)
        .group_by(PlantConnection.plant_id)
        .having(func.sum(PlantConnection.percentual) > CEM)
        .all()
    )
    return {plant_id: soma for plant_id, soma in somas}


def rescalar_usina(plant_id: int, soma_atual: Decimal) -> None:
    conexoes = (
        PlantConnection.query.filter_by(plant_id=plant_id)
        .order_by(PlantConnection.percentual.desc())
        .all()
    )
    novos = [
        (conexao.percentual * CEM / soma_atual).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        for conexao in conexoes
    ]
    ajuste = CEM - sum(novos)
    novos[0] += ajuste  # maior valor fecha a soma exata (evita 99.98/100.02)
    for conexao, novo_percentual in zip(conexoes, novos):
        conexao.percentual = novo_percentual


def main() -> None:
    app = create_app()
    with app.app_context():
        afetadas = usinas_excedentes()
        if not afetadas:
            print('Nenhuma usina acima de 100%.')
            return

        print(f'{len(afetadas)} usina(s) acima de 100%: {sorted(afetadas)}')
        for plant_id, soma_atual in afetadas.items():
            rescalar_usina(plant_id, soma_atual)
        db.session.flush()

        restantes = usinas_excedentes()
        if restantes:
            db.session.rollback()
            raise SystemExit(f'Ainda acima de 100% apos reescalar: {sorted(restantes)} -- abortado.')

        db.session.commit()
        print(f'Corrigidas {len(afetadas)} usina(s): {sorted(afetadas)}.')


if __name__ == '__main__':
    main()
