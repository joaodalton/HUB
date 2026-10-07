# Inventário técnico de dados

Data do levantamento: 2026-10-05. Baseado nos models, services e rotas atuais do repositório. A coluna “Finalidade técnica” descreve apenas a função implementada observável; não determina finalidade legal, base legal ou papel LGPD. Quando o código não comprova algo, consta `PENDING_REVIEW`.

## Classificação interna

`PUBLIC`, `INTERNAL`, `PERSONAL`, `SENSITIVE` e `SECRET` são categorias operacionais internas. Não equivalem às categorias legais da LGPD e não determinam, por si só, tratamento jurídico.

| Categoria | Uso interno |
|---|---|
| PUBLIC | Informação destinada à divulgação pública, quando aplicável. |
| INTERNAL | Dados operacionais/administrativos sem indicação de acesso público. |
| PERSONAL | Informação que identifica ou pode identificar pessoa natural. |
| SENSITIVE | Rótulo interno para conteúdo de alto impacto ou que exige cuidado reforçado; não afirma dado pessoal sensível na acepção legal. |
| SECRET | Credenciais, tokens, hashes de autenticação ou segredos de infraestrutura. |

## Inventário por entidade e grupo de campos

O compartilhamento externo abaixo indica somente caminho explícito no código, não prova de que uma instância esteja ativa ou de que uma transmissão tenha ocorrido. `PENDING_REVIEW` significa que essa confirmação não pode ser feita pelo repositório.

| Entidade / dados | Finalidade técnica | Categoria | Persistência | Empresa / tenant | Compartilhamento externo | Observação |
|---|---|---|---|---|---|---|
| User: nome, e-mail, hash de senha, papel, estado e indicador de administrador de plataforma | Login, sessão e autorização | PERSONAL; SECRET para hash/material de autenticação | Banco relacional, model `User` | `empresa_id` existe; User não herda `TenantMixin` para permitir localizar identidade antes do contexto de empresa | E-mail é usado nos fluxos de convite/reset; Resend só tenta envio se configurado (`backend/services/email_service.py`). Uso efetivo: PENDING_REVIEW | `backend/models/user.py`; senha não é persistida em texto puro. |
| Empresa: nome, razão social, CNPJ, e-mail, telefone, status, slug e referências a documentos empresariais | Cadastro e identificação da empresa | INTERNAL; PERSONAL quando identificar pessoa natural | Banco relacional, model `Empresa` | Registro raiz da empresa; model não herda `TenantMixin` | PENDING_REVIEW | `backend/models/empresa.py`. |
| Client: nome, CPF, e-mail e telefone | Cadastro e consulta de clientes | PERSONAL | Banco relacional, model `Client` | `TenantMixin`, com `empresa_id` | PENDING_REVIEW | `backend/models/client.py`; não presumir envio desses campos a fornecedores. |
| ConsumerUnit (UC): código, concessionária, apelido e vínculo a cliente | Identificação da unidade para fluxos operacionais e documentais | INTERNAL; PERSONAL quando associado a titular pessoa natural | Banco relacional, model `ConsumerUnit` | `TenantMixin`, com `empresa_id` | Existem integrações de concessionária configuráveis; transmissão desses campos: PENDING_REVIEW | `backend/models/consumer_unit.py`. |
| UC: documento CPF/CNPJ, endereço e CEP | Cadastro e correspondência documental da unidade | PERSONAL quando ligado a pessoa natural; caso contrário INTERNAL | Banco relacional, campos `documento`, `endereco`, `cep` de `ConsumerUnit` | `TenantMixin`, com `empresa_id` | PENDING_REVIEW | O comentário do model afirma que o documento da UC pode divergir do CPF do cliente. `backend/models/consumer_unit.py`. |
| UC: consumo, geração própria, desconto e demais parâmetros operacionais | Cadastro e cálculo operacional da unidade | INTERNAL; PERSONAL quando associado a pessoa natural | Banco relacional, model `ConsumerUnit` | `TenantMixin`, com `empresa_id` | PENDING_REVIEW | `consumo` e `geracao_propria` em `backend/models/consumer_unit.py`. |
| Plant / Usina: dados cadastrais/operacionais, endereço/CEP e contato do proprietário quando informado | Cadastro e gestão de usinas | INTERNAL; PERSONAL para dados de contato identificáveis | Banco relacional, model `Plant` | `TenantMixin`, com `empresa_id` | PENDING_REVIEW | `backend/models/plant.py`. |
| Fatura: cliente, UC, competência, concessionária, valor, vencimento, estado, referência de pagamento/ASAAS | Criar e acompanhar cobrança | INTERNAL; PERSONAL quando ligada a pessoa natural | Banco relacional, model `Fatura` | `TenantMixin`, com `empresa_id` | `backend/services/asaas_client.py` possui chamadas HTTP de cobrança; dados enviados por chamada/ambiente: PENDING_REVIEW | `backend/models/fatura.py`; cliente e referências externas estão em campos do model. |
| FaturaConcessionaria: consumo, energia compensada/injetada, leituras, datas, valores, dados brutos/normalizados e hash | Receber, processar, validar e relacionar fatura documental | INTERNAL; PERSONAL quando vinculada a cliente/titular pessoa natural | Banco relacional, model `FaturaConcessionaria` | `TenantMixin`, com `empresa_id` | PENDING_REVIEW | `backend/models/fatura_concessionaria.py`; grupos de campos listados conforme colunas do model. |
| PDF da fatura e arquivos associados a Document | Upload, processamento, consulta e download de documentos | PERSONAL; SENSITIVE como rótulo interno por possível conteúdo identificador/financeiro | Metadados em `Document`/`FaturaConcessionaria`; bytes no provider selecionado/configurado | Models tenant-scoped | Google Drive possui adapter; storage S3/local possui adapter. Provider usado em cada operação e dados efetivamente enviados: PENDING_REVIEW | `backend/models/document.py`, `backend/services/drive_service.py`, `backend/services/object_storage.py`; configuração de storage em `backend/config.py`. |
| Document: metadados, categoria, relações de domínio, referências/chaves do objeto | Catalogar e relacionar documentos do HUB | INTERNAL; PERSONAL conforme conteúdo/documento | Banco relacional, model `Document`; arquivo externo/local conforme provider | `TenantMixin`, com `empresa_id` | Caminhos Drive/object storage existem; execução real: PENDING_REVIEW | `backend/models/document.py`, `backend/services/document_service.py`. |
| LogEntry: ator, empresa, ação, entidade/ID, mensagem, metadados e data | Auditoria e diagnóstico de operações | INTERNAL; PERSONAL quando identifica usuário | Banco relacional, model `LogEntry` | `TenantMixin`; alguns eventos recebem empresa explicitamente | Sentry é inicializado condicionalmente; envio de cada dado/log: PENDING_REVIEW | `backend/models/log_entry.py`, `backend/services/log_service.py`, `backend/app.py`. |
| BillingCalculationSnapshot (o nome da classe no código): fingerprint, snapshot de regra/entrada, resultado, valor e data | Persistir entrada/regra/resultado do cálculo de cobrança | INTERNAL; PERSONAL se ligada a UC/cliente | Banco relacional, JSON e valores do model | `TenantMixin`, com `empresa_id` | PENDING_REVIEW | `backend/models/calculo_cobranca.py`. |
| Assinatura: estado e referências de assinatura/plano/cobrança | Persistir estado de assinatura usado pela aplicação | INTERNAL; PERSONAL se associada a pessoa natural | Banco relacional, model `Assinatura` | Não herda `TenantMixin` conforme model atual | PENDING_REVIEW | `backend/models/assinatura.py`; não presumir que represente aceite legal. |
| Invitation: e-mail, papel, empresa, hash de token, validade, autor, estado e datas | Convidar usuário e aceitar convite | PERSONAL (e-mail); SECRET (hash do token) | Banco relacional, model `Invitation`; token cru não é coluna persistida | Tem `empresa_id`, sem `TenantMixin`; service faz filtro explícito | Serviço chama `send_email`; tentativa depende da chave Resend (`backend/services/invitation_service.py`, `backend/services/email_service.py`). Entrega efetiva: PENDING_REVIEW | `backend/models/invitation.py`; validade configurada como 7 dias em `backend/services/invitation_service.py`. |
| PasswordResetToken: user_id, hash, validade, usado e data de criação | Recuperar acesso à conta | SECRET; associado a identidade PERSONAL | Banco relacional, model `PasswordResetToken`; token cru entregue no link e não armazenado pelo model | Sem `TenantMixin`; ligado a `User` | Serviço chama `send_email`; tentativa depende da chave Resend. Entrega efetiva: PENDING_REVIEW | `backend/models/password_reset_token.py`, `backend/services/password_reset_service.py`; TTL configurado em 60 minutos. |
| LegalAcceptance: versão, usuário, instante e IP de aceite | PENDING_REVIEW | PENDING_REVIEW | Não foi localizado model/tabela/serviço equivalente no código atual | PENDING_REVIEW | PENDING_REVIEW | `LegalAcceptance` não foi encontrado no código atual; não considerar aceite persistido implementado. |

## Limites

- A presença de campo/model não prova que esteja preenchido, transmitido, nem qual seja sua finalidade legal ou base legal.
- Conteúdo de arquivos pode incluir dados que o esquema de metadados não enumera.
- Classificação legal, controlador/operador, bases legais, avisos aos titulares, direitos e retenção jurídica permanecem `PENDING_REVIEW`.
