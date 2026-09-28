"""Validation at manual registration boundaries; existing rows remain untouched."""
import re


def normalize_name(value):
    name = str(value or '').strip()
    if not name or len(name) > 200:
        raise ValueError('Nome deve conter de 1 a 200 caracteres.')
    return name


def normalize_phone(value):
    raw = str(value or '').strip()
    if not re.fullmatch(r'\+?[0-9\s().-]+', raw):
        raise ValueError('Telefone invalido.')
    digits = re.sub(r'\D', '', raw)
    if raw.startswith('+55'):
        digits = digits[2:]
    if len(digits) == 11 and digits[2] == '9' and int(digits[:2]) >= 11:
        return digits
    if len(digits) == 10 and int(digits[:2]) >= 11:
        return digits
    raise ValueError('Telefone invalido.')


def _document(value, length, label):
    raw = str(value or '').strip()
    if not re.fullmatch(r'[0-9\s./-]+', raw):
        raise ValueError(f'{label} invalido.')
    digits = re.sub(r'\D', '', raw)
    if len(digits) != length or len(set(digits)) == 1:
        raise ValueError(f'{label} invalido.')
    return digits


def normalize_cpf(value):
    digits = _document(value, 11, 'CPF')
    for size in (9, 10):
        check = (sum(int(digits[i]) * (size + 1 - i) for i in range(size)) * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[size]):
            raise ValueError('CPF invalido.')
    return digits


def normalize_cnpj(value):
    digits = _document(value, 14, 'CNPJ')
    for size, weights in ((12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
                          (13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))):
        rest = sum(int(digits[i]) * weights[i] for i in range(size)) % 11
        if (0 if rest < 2 else 11 - rest) != int(digits[size]):
            raise ValueError('CNPJ invalido.')
    return digits


def normalize_document(value):
    digits = re.sub(r'\D', '', str(value or ''))
    return normalize_cpf(value) if len(digits) == 11 else normalize_cnpj(value)
