# backend/utils/crypto.py
"""
Criptografia simetrica para dados sensiveis salvos no banco (hoje: refresh
token do Google OAuth em GoogleAccount). A chave nunca e hardcoded -- vem de
SECRET_ENCRYPTION_KEY no .env. Sem a variavel configurada, falha alto e claro
em vez de salvar o token em texto puro.
"""
from cryptography.fernet import Fernet, InvalidToken

from config import Config


def _get_cipher() -> Fernet:
    key = Config.SECRET_ENCRYPTION_KEY

    if not key:
        raise RuntimeError(
            'SECRET_ENCRYPTION_KEY nao configurada no .env. Gere uma com: '
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    return Fernet(key.encode())


def encrypt_value(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None

    return _get_cipher().encrypt(raw_value.encode()).decode()


def decrypt_value(encrypted_value: str | None) -> str | None:
    if encrypted_value is None:
        return None

    try:
        return _get_cipher().decrypt(encrypted_value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError('Nao foi possivel descriptografar o valor (chave errada ou dado corrompido).') from exc