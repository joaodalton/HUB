from datetime import datetime

from extensions import TenantMixin, db


class FaturaConcessionaria(TenantMixin, db.Model):
    __tablename__ = 'faturas_concessionarias'
    __table_args__ = (
        db.UniqueConstraint(
            'empresa_id', 'arquivo_hash',
            name='uq_faturas_concessionarias_empresa_hash',
        ),
        db.Index('uq_faturas_concessionarias_id_empresa', 'id', 'empresa_id', unique=True),
        db.Index(
            'ix_faturas_concessionarias_empresa_chave',
            'empresa_id', 'chave_acesso',
        ),
        db.CheckConstraint(
            "status_extracao IN ('recebida', 'processando', 'extraida', "
            "'layout_nao_reconhecido', 'erro')",
            name='ck_faturas_concessionarias_status_extracao',
        ),
        db.CheckConstraint(
            "status_validacao IN ('pendente', 'valida', 'revisao_necessaria', "
            "'uc_nao_encontrada', 'uc_pertence_outro_cliente')",
            name='ck_faturas_concessionarias_status_validacao',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)

    concessionaria = db.Column(db.String(50), nullable=True)
    codigo_uc_extraido = db.Column(db.String(100), nullable=True)
    competencia = db.Column(db.String(7), nullable=True)
    numero_nota_fiscal = db.Column(db.String(100), nullable=True)
    serie_nota_fiscal = db.Column(db.String(50), nullable=True)
    chave_acesso = db.Column(db.String(64), nullable=True)
    arquivo_hash = db.Column(db.String(64), nullable=False)

    data_emissao = db.Column(db.Date, nullable=True)
    data_leitura_anterior = db.Column(db.Date, nullable=True)
    data_leitura_atual = db.Column(db.Date, nullable=True)
    data_proxima_leitura = db.Column(db.Date, nullable=True)
    data_vencimento = db.Column(db.Date, nullable=True)

    consumo_kwh = db.Column(db.Numeric(18, 6), nullable=True)
    energia_compensada_kwh = db.Column(db.Numeric(18, 6), nullable=True)
    injecao_gd1_kwh = db.Column(db.Numeric(18, 6), nullable=True)
    injecao_gd2_kwh = db.Column(db.Numeric(18, 6), nullable=True)
    saldo_creditos_kwh = db.Column(db.Numeric(18, 6), nullable=True)
    valor_total_concessionaria = db.Column(db.Numeric(18, 2), nullable=True)

    parser_name = db.Column(db.String(100), nullable=True)
    parser_version = db.Column(db.String(50), nullable=True)
    layout_name = db.Column(db.String(100), nullable=True)
    layout_version = db.Column(db.String(50), nullable=True)
    status_extracao = db.Column(db.String(30), nullable=False, default='recebida')
    status_validacao = db.Column(db.String(30), nullable=False, default='pendente')
    dados_brutos_extraidos = db.Column(db.JSON, nullable=True)
    dados_normalizados = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    client = db.relationship('Client')
    consumer_unit = db.relationship('ConsumerUnit')
    document = db.relationship('Document')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'clienteId': self.client_id,
            'ucId': self.consumer_unit_id,
            'documentoId': self.document_id,
            'concessionaria': self.concessionaria,
            'codigoUcExtraido': self.codigo_uc_extraido,
            'competencia': self.competencia,
            'numeroNotaFiscal': self.numero_nota_fiscal,
            'serieNotaFiscal': self.serie_nota_fiscal,
            'chaveAcesso': self.chave_acesso,
            'arquivoHash': self.arquivo_hash,
            'dataEmissao': self.data_emissao.isoformat() if self.data_emissao else None,
            'dataLeituraAnterior': self.data_leitura_anterior.isoformat() if self.data_leitura_anterior else None,
            'dataLeituraAtual': self.data_leitura_atual.isoformat() if self.data_leitura_atual else None,
            'dataProximaLeitura': self.data_proxima_leitura.isoformat() if self.data_proxima_leitura else None,
            'dataVencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'consumoKwh': str(self.consumo_kwh) if self.consumo_kwh is not None else None,
            'energiaCompensadaKwh': str(self.energia_compensada_kwh) if self.energia_compensada_kwh is not None else None,
            'injecaoGd1Kwh': str(self.injecao_gd1_kwh) if self.injecao_gd1_kwh is not None else None,
            'injecaoGd2Kwh': str(self.injecao_gd2_kwh) if self.injecao_gd2_kwh is not None else None,
            'saldoCreditosKwh': str(self.saldo_creditos_kwh) if self.saldo_creditos_kwh is not None else None,
            'valorTotalConcessionaria': str(self.valor_total_concessionaria) if self.valor_total_concessionaria is not None else None,
            'parserName': self.parser_name,
            'parserVersion': self.parser_version,
            'layoutName': self.layout_name,
            'layoutVersion': self.layout_version,
            'statusExtracao': self.status_extracao,
            'statusValidacao': self.status_validacao,
            'dadosBrutosExtraidos': self.dados_brutos_extraidos,
            'dadosNormalizados': self.dados_normalizados,
            'criadaEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadaEm': self.updated_at.isoformat() if self.updated_at else None,
        }
