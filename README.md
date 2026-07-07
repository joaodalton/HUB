# APP HUB - Operacao solar

Organiza documentos, clientes, UCs e usinas em uma interface unica para operacao.

## Estrutura

```text
backend/
  app.py
  config.py
  routes/
  services/
  database/
  models/
  utils/

frontend/
  src/
    pages/
    components/
    layouts/
    hooks/
    services/
    styles/
```

## Configuracao

O projeto usa variaveis de ambiente para deixar credenciais, portas e URLs fora do codigo.

Arquivos locais:

```text
backend/.env
frontend/.env
```

Modelo de referencia:

```text
.env.example
```

Coloque o `credentials.json` da Service Account dentro da pasta `backend/`. Esse arquivo nao deve ser enviado ao GitHub.

## Como rodar

### Backend Python

```bash
cd backend
venv\Scripts\python.exe app.py
```

Se ainda nao tiver criado o ambiente virtual:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

O backend roda em:

```text
http://localhost:8000
```

### Frontend TypeScript

Na primeira vez:

```bash
cd frontend
npm install
npm run dev
```

Depois, no dia a dia:

```bash
cd frontend
npm run dev
```

O frontend roda em:

```text
http://127.0.0.1:5173
```

## Validacao

```bash
cd frontend
npm run build
```

```bash
cd backend
venv\Scripts\python.exe -c "from app import app; print(app.url_map)"
```

## Funcionalidades atuais

- Buscar documentos e pastas no Google Drive.
- Filtrar resultados por tudo, pastas, imagens em PDF e termo de adesao.
- Reservar documentos para uso.
- Abrir documentos reservados.
- Baixar documentos reservados em ZIP.
- Visualizar tela de Clientes com dashboard e listagem.
- Cadastrar e editar clientes em popup.
- Excluir clientes com confirmacao.
- Anexar, renomear e baixar documentos do cliente quando o arquivo foi anexado pela interface.
- Cadastrar concessionaria do cliente. Por enquanto a lista possui `Copel`, preparada no codigo para receber novas opcoes.
- Visualizar tela de Usinas com dashboard e listagem.
- Cadastrar, editar e excluir usinas com confirmacao.
- Gerenciar Configuracoes com bloco de Banco de dados.
- Configurar contas Google Drive operacionais, SQL futuro, cor principal e logotipo local.
- Visualizar rascunho inicial da Agenda operacional em formato de calendario.

## Navegacao

- Documentos: busca e reserva de arquivos do Google Drive.
- Clientes: tabela com nome, UC, usina, consumo e status.
- Usinas: tabela com nome, UC, media de geracao e status.
- Configuracoes: parametros do app e Banco de dados.
- Agenda: calendario inicial para futuros lembretes de boleto, vencimento e contratos.

Na tela de Clientes, o botao "Novo cliente" abre um popup de cadastro com nome, CPF, email obrigatorios, concessionaria e anexos. Tambem e possivel adicionar UCs ja no cadastro do novo cliente. Ao clicar em um cliente existente, o popup abre em duas partes: dados do cliente na esquerda e UCs vinculadas na direita.

Na area de UCs, cada cliente pode ter mais de uma unidade consumidora. Cada UC aparece em acordeao para manter o popup compacto. Ao abrir a UC, ficam disponiveis codigo, subnome, consumo, base tarifaria, desconto, tipo de ligacao e conexoes com usinas. A base tarifaria usa uma lista fechada com `A1`, `A2`, `A3`, `A3a`, `AS`, `B1`, `B2`, `B3` e `B4`, com ajuda por tooltip. A lista de conexao mostra apenas usinas com percentual disponivel acima de 0%, permitindo informar quantos por cento daquela UC serao conectados em cada usina.

Nesta fase, os cadastros de clientes e os anexos adicionados pela interface ficam salvos no `localStorage` do navegador, usando a chave `hub.operations.v1`. Isso evita perder dados ao atualizar a pagina, mas ainda nao e armazenamento definitivo nem compartilhado entre maquinas. Anexos antigos/mockados que nao possuem conteudo salvo aparecem na lista, mas nao podem ser baixados ate existirem no backend. A proxima etapa de dados deve ligar esse service ao backend, primeiro usando Google Drive como fonte operacional e depois SQL em servidor.

O Google Drive saiu da barra lateral como item separado e agora fica dentro de Configuracoes > Banco de dados. Por enquanto ele e a fonte operacional inicial, mas a tela ja comunica a futura migracao para SQL em servidor.

Na tela de Usinas, e possivel cadastrar nome, UC, kW pico, status e porcentagem disponivel para rateio. O cadastro usa popup, permite edicao pela linha da tabela e exclusao com confirmacao.

Em Configuracoes, a aba Banco de dados organiza contas Google Drive, conta ativa e campos de SQL futuro. Credenciais reais, URLs sensiveis e chaves continuam fora do frontend e devem permanecer em variaveis de ambiente no backend. A aba Aparencia salva cor principal e logotipo PNG/JPG no armazenamento local do navegador.

## Proximas fases

A arquitetura ja separa rotas, servicos, modelos, paginas, componentes, layout, hooks e services para receber:

- Clientes
- UCs
- Usinas
- Documentos
- Configuracoes
- Pendencias
- Dashboard inteligente
- Agenda operacional

Modelo futuro planejado: um cliente pode ter varias UCs, cada UC pode ser conectada a varias usinas e documentos podem ser anexados ao perfil de cada cliente.

## Instalavel .exe

A refatoracao manteve frontend e backend separados para permitir uma futura versao desktop instalavel. O caminho recomendado para a proxima etapa e empacotar a interface com Electron ou Tauri e iniciar o backend Python junto do aplicativo, sem exigir que o usuario abra o navegador manualmente.
