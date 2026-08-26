# backend/utils/lista_exclusao.py
"""
Lista de frases para confirmação de exclusão crítica (empresas).

Rotaciona entre tentativas: a cada nova chamada a frase muda, até o
usuário digitar exatamente a palavra-chave em maiúsculas ou cancele.
"""

PHRASES: list[str] = [
    "confirmar",
    "excluir",
    "deletar",
    "apagar",
    "concordo",
    "afirmativo",
]
