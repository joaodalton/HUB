from io import BytesIO

from pypdf import PdfReader

from .schemas import ExtractionIssue, IssueSeverity, RawExtraction


class MinimalExtractor:
    def extract(self, document: bytes) -> RawExtraction:
        """Recebe bytes já validados pela F2; não extrai tabelas, palavras ou OCR."""
        reader = PdfReader(BytesIO(document), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise ValueError('PDF deve estar desprotegido e conter páginas.')
        text = reader.pages[0].extract_text() or ''
        metadata = {
            key: str(value) for key, value in (reader.metadata or {}).items()
            if key in ('/Producer', '/Creator')
        }
        warnings = ()
        if not text.strip():
            warnings = (ExtractionIssue(
                'NO_TEXT_ON_FIRST_PAGE', IssueSeverity.WARNING,
                'Primeira página sem texto extraível; OCR não executado.',
            ),)
        return RawExtraction(
            text=text, page_count=len(reader.pages), extracted_pages=(1,),
            metadata=metadata, warnings=warnings,
        )


class FullTextExtractor:
    def extract(self, document: bytes) -> RawExtraction:
        """Texto por página preservando colunas, sem OCR ou acesso externo."""
        reader = PdfReader(BytesIO(document), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise ValueError('PDF deve estar desprotegido e conter páginas.')
        pages = tuple(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
        return RawExtraction(
            text='\n\f\n'.join(pages), page_count=len(pages),
            extracted_pages=tuple(range(1, len(pages) + 1)), page_texts=pages,
        )
