# backend/models/plant.py
from datetime import datetime
from decimal import Decimal

from extensions import db

MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


class Plant(db.Model):
    __tablename__ = 'plants'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    uc = db.Column(db.String(30), nullable=False)
    kw_pico = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Implantacao')
    percentual_disponivel = db.Column(db.Integer, nullable=False, default=0)  # fallback manual -- ver percentual_disponivel_efetivo()
    marca_inversor = db.Column(db.String(100), nullable=True)
    telefone_proprietario = db.Column(db.String(20), nullable=True)
    email_proprietario = db.Column(db.String(150), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    data_ativacao = db.Column(db.Date, nullable=True)
    responsavel = db.Column(db.String(150), nullable=True)

    # --- Campos do motor de rateio ---
    cep = db.Column(db.String(10), nullable=True)
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    num_modulos = db.Column(db.Integer, nullable=True)
    potencia_modulo_w = db.Column(db.Numeric(8, 2), nullable=True)

    producao_jan = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_fev = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_mar = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_abr = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_mai = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_jun = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_jul = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_ago = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_set = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_out = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_nov = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    producao_dez = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    reserva_percentual = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    dia_emissao_usina = db.Column(db.Integer, nullable=True)
    is_coringa = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connections = db.relationship(
        'PlantConnection',
        back_populates='plant',
        cascade='all, delete-orphan'
    )

    def producao_mensal(self) -> dict:
        return {mes: float(getattr(self, f'producao_{mes}') or 0) for mes in MESES}

    def tem_producao_cadastrada(self) -> bool:
        return any(getattr(self, f'producao_{mes}') for mes in MESES)

    def producao_media(self) -> float | None:
        """Média dos meses PREENCHIDOS (>0), não soma/12 -- assim cadastro
        parcial (só 3 meses, por exemplo) não fica artificialmente baixo."""
        valores = [float(getattr(self, f'producao_{mes}')) for mes in MESES if getattr(self, f'producao_{mes}')]
        if not valores:
            return None
        return sum(valores) / len(valores)

    def percentual_disponivel_efetivo(self) -> tuple[float, bool]:
        """Retorna (percentual, e_manual). Se houver produção cadastrada, o
        percentual é CALCULADO (100 - reserva) e o campo antigo vira só
        histórico/fallback. Sem produção, continua 100% manual (campo antigo)."""
        if self.tem_producao_cadastrada():
            reserva = float(self.reserva_percentual or 0)
            return round(max(0.0, 100 - reserva), 2), False
        return float(self.percentual_disponivel or 0), True

    def to_dict(self) -> dict:
        percentual_efetivo, e_manual = self.percentual_disponivel_efetivo()

        return {
            'id': self.id,
            'nome': self.nome,
            'uc': self.uc,
            'kwPico': float(self.kw_pico),
            'mediaGeracao': f'{self.kw_pico} kWp',
            'status': self.status,
            'percentualDisponivel': percentual_efetivo,
            'percentualManual': e_manual,
            'marcaInversor': self.marca_inversor,
            'telefoneProprietario': self.telefone_proprietario,
            'emailProprietario': self.email_proprietario,
            'cidade': self.cidade,
            'uf': self.uf,
            'endereco': self.endereco,
            'dataAtivacao': self.data_ativacao.isoformat() if self.data_ativacao else None,
            'responsavel': self.responsavel,
            'cep': self.cep,
            'latitude': float(self.latitude) if self.latitude is not None else None,
            'longitude': float(self.longitude) if self.longitude is not None else None,
            'numModulos': self.num_modulos,
            'potenciaModuloW': float(self.potencia_modulo_w) if self.potencia_modulo_w is not None else None,
            'producaoMensal': self.producao_mensal(),
            'producaoMedia': self.producao_media(),
            'reservaPercentual': float(self.reserva_percentual or 0),
            'diaEmissaoUsina': self.dia_emissao_usina,
            'isCoringa': self.is_coringa
        }