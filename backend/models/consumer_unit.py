# backend/models/consumer_unit.py
from datetime import datetime

from extensions import db


class ConsumerUnit(db.Model):
    __tablename__ = 'consumer_units'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    codigo = db.Column(db.String(30), nullable=False)
    codigo_aneel = db.Column(db.String(20), nullable=True)  # novo padrao nacional de 15 digitos (REN ANEEL 1.095/2024)
    apelido = db.Column(db.String(100), nullable=True, default='')
    documento = db.Column(db.String(20), nullable=True)  # CPF/CNPJ da UC -- pode ser diferente do cpf do Cliente (ex.: casa no CPF, empresa no CNPJ do mesmo titular)
    endereco = db.Column(db.String(255), nullable=True)
    cep = db.Column(db.String(10), nullable=True)
    concessionaria = db.Column(db.String(50), nullable=True)
    geracao_propria = db.Column(db.Boolean, nullable=False, default=False)
    dia_emissao_fatura = db.Column(db.Integer, nullable=True)  # dia do mes (1-31)
    consumo = db.Column(db.String(30), nullable=True, default='')
    base_tarifaria = db.Column(db.String(10), nullable=False, default='B1')
    desconto = db.Column(db.String(20), nullable=True, default='')
    tipo_ligacao = db.Column(db.String(20), nullable=False, default='Monofasico')
    inicio_contrato = db.Column(db.Date, nullable=True)
    termino_contrato = db.Column(db.Date, nullable=True)
    carencia_meses = db.Column(db.Integer, nullable=True)
    percentual_desconto_carencia = db.Column(db.String(10), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client', backref=db.backref('ucs', cascade='all, delete-orphan'))
    conexoes = db.relationship(
        'PlantConnection',
        back_populates='consumer_unit',
        cascade='all, delete-orphan'
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'clienteId': self.client_id,
            'clienteNome': self.client.nome if self.client else None,
            'codigo': self.codigo,
            'codigoAneel': self.codigo_aneel,
            'apelido': self.apelido,
            'documento': self.documento,
            'endereco': self.endereco,
            'cep': self.cep,
            'concessionaria': self.concessionaria,
            'geracaoPropria': self.geracao_propria,
            'diaEmissaoFatura': self.dia_emissao_fatura,
            'consumo': self.consumo,
            'baseTarifaria': self.base_tarifaria,
            'desconto': self.desconto,
            'tipoLigacao': self.tipo_ligacao,
            'inicioContrato': self.inicio_contrato.isoformat() if self.inicio_contrato else None,
            'terminoContrato': self.termino_contrato.isoformat() if self.termino_contrato else None,
            'carenciaMeses': self.carencia_meses,
            'percentualDescontoCarencia': self.percentual_desconto_carencia,
            'conexoes': [conexao.to_dict() for conexao in self.conexoes]
        }


class PlantConnection(db.Model):
    __tablename__ = 'plant_connections'

    id = db.Column(db.Integer, primary_key=True)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    percentual = db.Column(db.String(10), nullable=False, default='')

    consumer_unit = db.relationship('ConsumerUnit', back_populates='conexoes')
    plant = db.relationship('Plant', back_populates='connections')

    def to_dict(self) -> dict:
        return {
        "id": self.id,
        "plantId": self.plant_id,
        "usina": self.plant.nome if self.plant else "",
        "percentual": self.percentual,
    }