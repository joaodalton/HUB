"""Mescla os Termos de Adesão reais em PDF; o formulário é XLSX."""
import io

from pypdf import PdfReader, PdfWriter

from services.drive_service import get_drive_service
from services.rateio_formulario_service import buscar_termo_adesao, montar_tabela_formulario, verificar_termos_adesao


class DriveUnavailableError(RuntimeError):
    pass


def gerar_termos_adesao_pdf(plant_id: int) -> bytes:
    tabela = montar_tabela_formulario(plant_id)
    if round(sum(float(linha.get('percentual') or 0) for linha in tabela['linhas']), 2) > 100:
        raise ValueError('Soma dos percentuais excede 100%. Ajuste antes de gerar.')
    verificacao = verificar_termos_adesao(plant_id)
    if not verificacao['ok']:
        nomes = ', '.join(item['nome'] for item in verificacao['faltando'])
        raise ValueError(f'Termo de Adesão faltando para: {nomes}. Geração bloqueada.')
    writer = PdfWriter()
    for linha in tabela['linhas']:
        documento = buscar_termo_adesao(linha['clienteId'], linha['ucId'])
        if not documento or documento.storage_provider != 'google_drive':
            raise ValueError(f'Termo de Adesão de {linha["nome"]} não está disponível no Google Drive.')
        try:
            paginas = PdfReader(io.BytesIO(get_drive_service().download_file(documento.storage_ref))).pages
        except Exception as exc:
            raise DriveUnavailableError(f'Não foi possível baixar o Termo de Adesão de {linha["nome"]}.') from exc
        if not paginas:
            raise ValueError(f'Termo de Adesão de {linha["nome"]} não é um PDF válido.')
        for pagina in paginas:
            writer.add_page(pagina)
    if not writer.pages:
        raise ValueError('Nenhum Termo de Adesão válido (PDF) encontrado para mesclar.')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
