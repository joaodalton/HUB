"""Correspondência de descrições; não contém categorias ou regras comerciais."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ItemMatcherRule:
    mode: str
    pattern: str
    target: str
    priority: int = 0

    def __post_init__(self):
        if self.mode not in ('exact', 'prefix', 'contains', 'regex'):
            raise ValueError('Modo de correspondência inválido.')
        if not self.pattern or not self.target:
            raise ValueError('Pattern e target são obrigatórios.')
        if self.mode == 'regex':
            re.compile(self.pattern)

    def matches(self, description: str) -> bool:
        if self.mode == 'exact':
            return description == self.pattern
        if self.mode == 'prefix':
            return description.startswith(self.pattern)
        if self.mode == 'contains':
            return self.pattern in description
        return re.search(self.pattern, description) is not None


class ItemMatcher:
    def __init__(self, rules):
        self.rules = tuple(rules)

    def match(self, description: str) -> tuple[str, ...]:
        matches = [rule for rule in self.rules if rule.matches(description)]
        if not matches:
            return ()
        priority = max(rule.priority for rule in matches)
        # Empate entre targets diferentes fica explícito para o consumidor.
        return tuple(sorted({rule.target for rule in matches if rule.priority == priority}))
