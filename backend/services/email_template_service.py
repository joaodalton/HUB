# backend/services/email_template_service.py
"""
CRUD + renderizacao dos templates de e-mail editaveis pela tela de
Configuracoes > E-mails. Templates ficam no banco (EmailTemplate); o
conteudo em email_template_defaults.py so serve de seed inicial e de
"Restaurar padrao".

Renderizacao e deliberadamente simples (decisao registrada: campos de texto
com variaveis {{var}}, sem HTML livre -- reduz risco de quebrar o layout do
e-mail por edicao acidental). A variavel "link" ganha tratamento especial:
quando aparece sozinha numa linha, vira um botao estilizado no HTML (senao,
vira um link normal); no texto simples, e sempre a URL crua.
"""
from html import escape

from extensions import db
from models.email_template import EmailTemplate
from services.email_template_defaults import DEFAULT_TEMPLATES
from services.log_service import LogService

_BUTTON_COLOR = '#f0713a'


def ensure_seeded() -> None:
    """Cria no banco qualquer template padrao que ainda nao exista. Chamado
    sob demanda (nao no boot da app) -- nao precisa de migration de dado,
    o proprio uso normal (tela ou envio de e-mail) semeia sozinho."""
    existentes = {t.chave for t in EmailTemplate.query.all()}

    for chave, dados in DEFAULT_TEMPLATES.items():
        if chave in existentes:
            continue

        db.session.add(EmailTemplate(
            chave=chave,
            nome=dados['nome'],
            assunto=dados['assunto'],
            corpo=dados['corpo'],
            variaveis_disponiveis=dados['variaveis_disponiveis']
        ))

    db.session.commit()


def list_templates() -> list[dict]:
    ensure_seeded()
    templates = EmailTemplate.query.order_by(EmailTemplate.nome).all()
    return [t.to_dict() for t in templates]


def get_template(chave: str) -> dict | None:
    ensure_seeded()
    template = EmailTemplate.query.filter_by(chave=chave).first()
    return template.to_dict() if template else None


def update_template(chave: str, assunto: str, corpo: str) -> dict | None:
    ensure_seeded()
    template = EmailTemplate.query.filter_by(chave=chave).first()

    if not template:
        return None

    template.assunto = (assunto or '').strip() or template.assunto
    template.corpo = corpo or template.corpo
    db.session.commit()

    LogService.info(acao='email_template_update', mensagem=f'Template de e-mail "{chave}" atualizado', entidade='EmailTemplate')
    return template.to_dict()


def restaurar_padrao(chave: str) -> dict | None:
    if chave not in DEFAULT_TEMPLATES:
        return None

    ensure_seeded()
    template = EmailTemplate.query.filter_by(chave=chave).first()

    if not template:
        return None

    padrao = DEFAULT_TEMPLATES[chave]
    template.assunto = padrao['assunto']
    template.corpo = padrao['corpo']
    db.session.commit()

    LogService.info(acao='email_template_restore', mensagem=f'Template de e-mail "{chave}" restaurado ao padrão', entidade='EmailTemplate')
    return template.to_dict()


def renderizar(chave: str, variaveis: dict) -> tuple[str, str, str] | None:
    """Retorna (assunto, html, text) prontos pra email_service.send_email.
    None se o template nao existir (chamador decide o que fazer)."""
    ensure_seeded()
    template = EmailTemplate.query.filter_by(chave=chave).first()

    if not template:
        return None

    assunto = template.assunto
    texto = template.corpo
    for nome_var, valor in variaveis.items():
        placeholder = f'{{{{{nome_var}}}}}'
        assunto = assunto.replace(placeholder, str(valor))
        texto = texto.replace(placeholder, str(valor))

    html = _renderizar_html(template.corpo, variaveis)
    return assunto, html, texto


def _renderizar_html(corpo: str, variaveis: dict) -> str:
    link = variaveis.get('link')
    linhas_html: list[str] = []

    for linha in corpo.split('\n'):
        if link and linha.strip() == '{{link}}':
            linhas_html.append(
                f'<p style="margin: 24px 0;">'
                f'<a href="{escape(str(link))}" style="background:{_BUTTON_COLOR};color:#fff;'
                f'padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600;'
                f'display:inline-block;">Acessar</a></p>'
            )
            continue

        linha_tratada = linha
        for nome_var, valor in variaveis.items():
            valor_str = str(valor)
            substituto = (
                f'<a href="{escape(valor_str)}">{escape(valor_str)}</a>'
                if nome_var == 'link'
                else escape(valor_str)
            )
            linha_tratada = linha_tratada.replace(f'{{{{{nome_var}}}}}', substituto)

        if linha_tratada.strip():
            linhas_html.append(f'<p>{linha_tratada}</p>')

    corpo_html = ''.join(linhas_html)
    return f'<div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #1e293b;">{corpo_html}</div>'