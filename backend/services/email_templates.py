# backend/services/email_templates.py
"""
Templates de e-mail transacional -- HTML simples inline (sem engine de
template, coerente com o resto do backend, que nao usa Jinja pra API).
Cada funcao retorna (subject, html, text). Adicionar novos templates aqui,
nao espalhar HTML solto pelos services.
"""


def password_reset_email(nome: str, reset_link: str) -> tuple[str, str, str]:
    subject = 'Redefinição de senha — HUB'

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #1e293b;">
      <h2 style="color: #f0713a;">Redefinir senha</h2>
      <p>Olá, {nome or 'tudo bem'}.</p>
      <p>Recebemos um pedido para redefinir a senha da sua conta no HUB. Clique no botão abaixo para escolher uma nova senha:</p>
      <p style="margin: 24px 0;">
        <a href="{reset_link}" style="background: #f0713a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">Redefinir senha</a>
      </p>
      <p style="color: #64748b; font-size: 13px;">Se você não pediu isso, pode ignorar este e-mail com segurança. Este link expira em 1 hora.</p>
    </div>
    """.strip()

    text = (
        f'Olá, {nome or "tudo bem"}.\n\n'
        'Recebemos um pedido para redefinir a senha da sua conta no HUB.\n'
        f'Acesse o link abaixo para escolher uma nova senha (expira em 1 hora):\n{reset_link}\n\n'
        'Se você não pediu isso, pode ignorar este e-mail.'
    )

    return subject, html, text