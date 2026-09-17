from abc import ABC, abstractmethod

from .schemas import ParsedInvoice, ParserIdentity, RawExtraction


class InvoiceParser(ABC):
    @property
    @abstractmethod
    def identity(self) -> ParserIdentity:
        """Uma declaração de nome/versão por parser e layout."""

    @abstractmethod
    def can_parse(self, raw: RawExtraction) -> bool:
        """Identifica usando apenas os dados mínimos, sem I/O externo."""

    @abstractmethod
    def parse(self, document: bytes) -> ParsedInvoice:
        """Lê o PDF original somente após seleção; sem banco ou regra comercial."""
