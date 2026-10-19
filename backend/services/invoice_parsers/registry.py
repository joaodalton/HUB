from dataclasses import dataclass
from typing import Iterable

from .base import InvoiceParser
from .schemas import ExtractionIssue, IssueSeverity, RawExtraction


@dataclass(frozen=True)
class ParserSelection:
    parser: InvoiceParser | None
    issues: tuple[ExtractionIssue, ...] = ()


class ParserRegistry:
    def __init__(self, parsers: Iterable[InvoiceParser] = ()):
        # Lista explícita; default_registry define os parsers de produção.
        self.parsers = tuple(parsers)
        identities = [parser.identity for parser in self.parsers]
        if len(set(identities)) != len(identities):
            raise ValueError('Identidade de parser duplicada no registry.')

    def select(self, raw: RawExtraction) -> ParserSelection:
        matches = []
        for parser in self.parsers:
            claimed = parser.can_parse(raw)
            if not isinstance(claimed, bool):
                raise TypeError('can_parse deve retornar bool.')
            if claimed:
                matches.append(parser)
        if len(matches) == 1:
            return ParserSelection(matches[0])
        if not matches:
            return ParserSelection(None, (ExtractionIssue(
                'LAYOUT_NOT_RECOGNIZED', IssueSeverity.WARNING,
                'Nenhum parser reconheceu o documento.',
            ),))
        return ParserSelection(None, (ExtractionIssue(
            'AMBIGUOUS_LAYOUT', IssueSeverity.CRITICAL,
            'Mais de um parser reconheceu o documento.',
        ),))


def default_registry() -> ParserRegistry:
    from .copel import CopelDANF3EParser

    return ParserRegistry((CopelDANF3EParser(),))
