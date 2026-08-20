# backend/services/email_template_defaults.py
"""
Conteudo padrao de cada template -- usado pra popular email_templates na
primeira vez (seed automatico, ver ensure_seeded() em email_template_service.py)
e como fallback do botao "Restaurar padrao" na tela. Mudar o texto que o
cliente recebe e feito pela tela (o banco sempre manda), nao aqui.
"""

DEFAULT_TEMPLATES = {
    'password_reset': {
        'nome': 'Redefinição de senha',
        'assunto': 'Redefinição de senha — HUB',
        'corpo': (
            'Olá, {{nome}}.\n\n'
            'Recebemos um pedido para redefinir a senha da sua conta no HUB.\n\n'
            '{{link}}\n\n'
            'Se você não pediu isso, pode ignorar este e-mail com segurança. '
            'Este link expira em 1 hora.'
        ),
        'variaveis_disponiveis': 'nome,link'
    },
    'convite': {
        'nome': 'Convite de acesso',
        'assunto': 'Você foi convidado para o HUB',
        'corpo': (
            'Olá!\n\n'
            'Você foi convidado para acessar o HUB como {{papel}} da empresa {{empresa}}.\n\n'
            '{{link}}\n\n'
            'Este link expira em 7 dias.'
        ),
        'variaveis_disponiveis': 'papel,empresa,link'
    }
}