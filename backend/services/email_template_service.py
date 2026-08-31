# backend/services/email_template_service.py
"""
CRUD + renderização dos templates de e-mail editáveis pela tela de
Configurações > E-mails. Templates ficam no banco (EmailTemplate); o
conteúdo em email_template_defaults.py só serve de seed inicial e de
"Restaurar padrão".

Renderização é deliberadamente simples (decisão registrada: campos de texto
com variáveis {{var}}, sem HTML livre -- reduz risco de quebrar o layout do
e-mail por edição acidental). A variável "link" ganha tratamento especial:
quando aparece sozinha numa linha, vira um botão estilizado no HTML (senão,
vira um link normal); no texto simples, é sempre a URL crua.

SEGURANÇA:
- Os valores das variáveis são escapeados com html.escape() antes de
  serem inseridos no HTML, prevenindo XSS via dados do usuário.
- O corpo do template NÃO deve conter tags <script> ou atributos
  de evento (onload, onclick, etc.) -- esses são bloqueados na
  atualização via update_template() para prevenir que um admin
  mal-intencionado injete JavaScript no e-mail.
- O HTML gerado não é executado no navegador do destinatário como
  página web -- é apenas o body de um e-mail HTML. Contudo, alguns
  clientes de e-mail executam JavaScript, então a sanitização é
  importante mesmo para e-mails.
"""
from html import escape
import re

from extensions import db
from models.email_template import EmailTemplate
from services.email_template_defaults import DEFAULT_TEMPLATES
from services.log_service import LogService

_BUTTON_COLOR = '#f0713a'

# Padrões para detectar conteúdo potencialmente perigoso em templates
_DANGEROUS_TAG_PATTERN = re.compile(
    r'<\s*script\b|<\s*/script\s*>|on\w+\s*=\s*["\'][^"\']*["\']|on\w+\s*=\s*\S',
    re.IGNORECASE
)


def _contem_conteudo_proibido(texto: str) -> bool:
    """
    Verifica se o texto contém tags ou atributos que podem permitir XSS
    em clientes de e-mail que executam JavaScript.

    Returns:
        True se encontrar conteúdo proibido, False caso contrário.
    """
    return bool(_DANGEROUS_TAG_PATTERN.search(texto))


def ensure_seeded() -> None:
    """Cria no banco qualquer template padrão que ainda não exista. Chamado
    sob demanda (não no boot da app) -- não precisa de migration de dado,
    o próprio uso normal (tela ou envio de e-mail) semeia sozinho."""
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
    """
    Atualiza um template existente com validação de segurança.

    Args:
        chave: identificador do template
        assunto: novo assunto (ou vazio para manter o atual)
        corpo: novo corpo (ou vazio para manter o atual)

    Returns:
        dict com o template atualizado, ou None se o template não existir

    Raises:
        ValueError: se o corpo contiver tags ou atributos proibidos (XSS)
    """
    ensure_seeded()
    template = EmailTemplate.query.filter_by(chave=chave).first()

    if not template:
        return None

    # Validação de segurança: bloqueia tags <script> e atributos de evento
    if _contem_conteudo_proibido(corpo):
        raise ValueError(
            'Corpo do template contém conteúdo não permitido (script ou atributos de evento). '
            'Links e HTML básico (p, a, strong, em, ul, li, table) são permitidos, '
            'mas tags <script> e atributos on* (onclick, onload, etc.) são bloqueados '
            'para prevenir XSS em clientes de e-mail.'
        )

    # Validação de assunto: bloqueia conteúdo perigoso também
    if _contem_conteudo_proibido(assunto):
        raise ValueError(
            'Assunto do template contém conteúdo não permitido (script ou atributos de evento).'
        )

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
    """
    Retorna (assunto, html, text) prontos para email_service.send_email.
    None se o template não existir (chamador decide o que fazer).

    SEGURANÇA: Todos os valores de variáveis são escapeados com html.escape()
    antes de serem inseridos no HTML, prevenindo injeção de código via dados
    de variáveis (plausível em cenários onde variáveis vêm de fontes externas
    ou de usuários não confiáveis).
    """
    ensure_seeded()
    template = EmailTemplate.query.filter_by(chave=chave).first()

    if not template:
        return None

    assunto = template.assunto
    texto = template.corpo
    for nome_var, valor in variaveis.items():
        placeholder = f'{{{{{nome_var}}}}}'
        assunto = assunto.replace(placeholder, escape(str(valor)))
        texto = texto.replace(placeholder, escape(str(valor)))

    html = _renderizar_html(template.corpo, variaveis)
    return assunto, html, texto


def renderizar_para_empresa(empresa_id: int, chave: str, variaveis: dict) -> tuple[str, str, str] | None:
    """Adaptador de compatibilidade: convite/reset preferem o template do tenant."""
    from services.message_template_service import render_email_for_empresa
    return render_email_for_empresa(empresa_id, chave, variaveis) or renderizar(chave, variaveis)


def _renderizar_html(corpo: str, variaveis: dict) -> str:
    """
    Converte o corpo do template (texto com placeholders) em HTML.

    SEGURANÇA:
    - Todos os valores de variáveis são escapeados antes de inserção
    - O botão de link usa escape tanto no href quanto no texto
    - Links normais também são escapeados
    """
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
