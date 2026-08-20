# comandos/mapear.py
"""
Gera o mapa de dependencias do codigo (backend + frontend) automaticamente,
a partir dos imports reais dos arquivos -- nao e escrito na mao, e sempre
bate com o codigo de verdade porque roda de novo toda vez que
'python hub.py iniciar' e chamado (ver iniciar.py). Escreve dentro de
ARCHITECTURE.md, entre os marcadores MAPA-AUTO:INICIO / MAPA-AUTO:FIM --
nunca mexe no resto do arquivo (a parte escrita a mao continua preservada).
Se os marcadores ainda nao existirem no arquivo, sao criados sozinhos no
final na primeira execucao.

Falha aqui NUNCA deve impedir o HUB de iniciar -- por isso iniciar.py chama
mapear() dentro de um try/except e so avisa no console, nao aborta o start.

Limitacao conhecida: so mapeia arquivos DENTRO das pastas de dominio
(routes/services/models/utils no backend; pages/components/services/hooks/
layouts no frontend). Arquivos soltos na raiz de src/ (ex.: dom.ts, main.ts)
e imports de bibliotecas externas (flask, react, etc.) ficam de fora de
proposito -- o objetivo e mostrar SO as conexoes entre codigo nosso.
"""
import ast
import re
from pathlib import Path

from comandos.process_utils import BASE_DIR

BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_SRC = BASE_DIR / "frontend" / "src"
ARCHITECTURE_FILE = BASE_DIR / "ARCHITECTURE.md"

MARK_INICIO = "<!-- MAPA-AUTO:INICIO -->"
MARK_FIM = "<!-- MAPA-AUTO:FIM -->"

# Pastas do backend que contam como "codigo nosso" -- import de fora dessas
# (flask, sqlalchemy, etc.) e ignorado no mapa, so polui sem ajudar.
BACKEND_PACOTES = {"routes", "services", "models", "utils", "database"}

FRONTEND_PASTAS = {"pages", "components", "services", "hooks", "layouts"}

IMPORT_TS_RE = re.compile(r"from\s+['\"](\.[^'\"]+)['\"]")


def mapear() -> None:
    bloco = (
        f"{MARK_INICIO}\n"
        "> Gerado automaticamente por `python hub.py iniciar` "
        "(`comandos/mapear.py`) -- nao editar esta secao na mao, "
        "a proxima execucao sobrescreve.\n\n"
        "### Backend (imports reais entre routes / services / models / utils)\n\n"
        "```mermaid\n"
        f"{_mapear_backend()}\n"
        "```\n\n"
        "### Frontend (imports reais entre pages / components / services / hooks / layouts)\n\n"
        "```mermaid\n"
        f"{_mapear_frontend()}\n"
        "```\n"
        f"{MARK_FIM}"
    )
    _atualizar_architecture(bloco)


def _mapear_backend() -> str:
    edges: set[tuple[str, str]] = set()
    nodes_por_pasta: dict[str, set[str]] = {pasta: set() for pasta in BACKEND_PACOTES}
    nodes_por_pasta["raiz"] = set()

    arquivos = list(BACKEND_DIR.glob("*.py"))
    for pasta in BACKEND_PACOTES:
        arquivos += list((BACKEND_DIR / pasta).glob("*.py"))

    for arquivo in arquivos:
        if arquivo.name == "__init__.py":
            continue

        modulo_origem = _modulo_backend(arquivo)
        pasta_origem = modulo_origem.split(".")[0] if "." in modulo_origem else "raiz"
        nodes_por_pasta.setdefault(pasta_origem, set()).add(modulo_origem)

        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(arvore):
            alvo = None
            if isinstance(node, ast.ImportFrom) and node.module:
                alvo = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    alvo = alias.name
                    break

            if not alvo:
                continue

            pacote_alvo = alvo.split(".")[0]
            e_pacote_nosso = pacote_alvo in BACKEND_PACOTES
            e_arquivo_raiz_nosso = (BACKEND_DIR / f"{alvo}.py").exists()

            if not (e_pacote_nosso or e_arquivo_raiz_nosso):
                continue

            pasta_alvo = pacote_alvo if e_pacote_nosso else "raiz"
            nodes_por_pasta.setdefault(pasta_alvo, set()).add(alvo)
            edges.add((modulo_origem, alvo))

    return _montar_mermaid(nodes_por_pasta, edges)


def _modulo_backend(arquivo: Path) -> str:
    relativo = arquivo.relative_to(BACKEND_DIR).with_suffix("")
    return ".".join(relativo.parts)


def _mapear_frontend() -> str:
    edges: set[tuple[str, str]] = set()
    nodes_por_pasta: dict[str, set[str]] = {pasta: set() for pasta in FRONTEND_PASTAS}

    arquivos = [
        arquivo
        for pasta in FRONTEND_PASTAS
        for arquivo in (FRONTEND_SRC / pasta).glob("*.ts")
    ]

    for arquivo in arquivos:
        origem = _modulo_frontend(arquivo)
        nodes_por_pasta.setdefault(arquivo.parent.name, set()).add(origem)

        try:
            texto = arquivo.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for caminho_relativo in IMPORT_TS_RE.findall(texto):
            alvo_path = (arquivo.parent / caminho_relativo).resolve()

            try:
                alvo_relativo = alvo_path.relative_to(FRONTEND_SRC)
            except ValueError:
                continue

            partes = alvo_relativo.parts
            if not partes or partes[0] not in FRONTEND_PASTAS:
                continue

            alvo_modulo = "/".join(partes)
            nodes_por_pasta.setdefault(partes[0], set()).add(alvo_modulo)
            edges.add((origem, alvo_modulo))

    return _montar_mermaid(nodes_por_pasta, edges)


def _modulo_frontend(arquivo: Path) -> str:
    relativo = arquivo.relative_to(FRONTEND_SRC).with_suffix("")
    return "/".join(relativo.parts)


def _montar_mermaid(nodes_por_pasta: dict[str, set[str]], edges: set[tuple[str, str]]) -> str:
    linhas = ["graph TD"]

    for pasta, nomes in sorted(nodes_por_pasta.items()):
        if not nomes:
            continue
        linhas.append(f'  subgraph {_slug(pasta)}["{pasta}"]')
        for nome in sorted(nomes):
            linhas.append(f'    {_slug(nome)}["{nome}"]')
        linhas.append("  end")

    for origem, alvo in sorted(edges):
        linhas.append(f"  {_slug(origem)} --> {_slug(alvo)}")

    return "\n".join(linhas)


def _slug(texto: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", texto)


def _atualizar_architecture(bloco_novo: str) -> None:
    if not ARCHITECTURE_FILE.exists():
        ARCHITECTURE_FILE.write_text(bloco_novo + "\n", encoding="utf-8")
        return

    conteudo = ARCHITECTURE_FILE.read_text(encoding="utf-8")

    if MARK_INICIO in conteudo and MARK_FIM in conteudo:
        antes = conteudo.split(MARK_INICIO)[0]
        depois = conteudo.split(MARK_FIM)[1]
        novo_conteudo = f"{antes}{bloco_novo}{depois}"
    else:
        novo_conteudo = f"{conteudo.rstrip()}\n\n{bloco_novo}\n"

    ARCHITECTURE_FILE.write_text(novo_conteudo, encoding="utf-8")