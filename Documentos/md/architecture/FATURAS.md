ADR — Financeiro V2.0 (Fatura via ASAAS)

## ARCH-PLATFORM-1 — fronteira ASAAS da plataforma

As cobranças B0–B3 em `Fatura` são das empresas contra seus clientes finais,
com `AsaasClient(empresa_id)`, `ApiCredential` por empresa e webhook tenant em
`/api/v1/webhooks/asaas`. O HUB como plataforma usa somente `PLATFORM_ASAAS_*`
e a nova entrada `/api/v1/webhooks/asaas/platform`. Eventos autenticados de
plataforma são recebidos em ledger próprio, sem payload completo e com unicidade
por ID. Reentrega idêntica não duplica. Referências tenant antigas `hub-<uuid>`
continuam no fluxo tenant; referências de plataforma, quando presentes, exigem
`hub-platform-`.

Esse recebimento não emite, concilia nem ativa assinatura SaaS. Preço, ciclo,
inadimplência e homologação externa permanecem por definir:
`SAAS_BILLING_READY=false`. `RESEND_API_KEY` e `EMAIL_FROM` continuam globais
para e-mail transacional do HUB, distintos de credencial `resend` por empresa.

## B2 — Webhook multi-tenant e ledger (2026-09-14)

Antes: token global, lookup `asaas_id.first()` sem resolver ambiguidade e apenas
sobrescrita de status, sem identidade persistente do evento. Agora a rota pública
delega ao `asaas_webhook_service`, sem chamar emissão ou criar pagamentos.

1. Valida envelope `id`, `event`, `payment.id` e referência opcional.
2. Lookup privado SQLAlchemy Core retorna somente ID, tenant e identificadores:
   prioriza a referência global B1, depois ID remoto com exatamente um candidato.
   Referência/ID contraditórios são recusados; referência antiga ausente no banco
   pode usar fallback por ID único. Nunca escolher arbitrariamente entre empresas.
3. Busca token cifrado do tenant encontrado em `ApiCredential` e compara com
   `secrets.compare_digest`. Não usa o token global nem API key como webhook token.
4. Estabelece tenant, insere o ledger e faz flush. A constraint única arbitra
   concorrentes. `IntegrityError` provoca rollback e consulta tenant-scoped do
   evento concluído; apenas mesmo alvo/tipo/ID é reconhecido como duplicata.
5. Bloqueia a Fatura para atualização (`FOR UPDATE` onde suportado), aplica status
   remoto/URLs presentes e grava `processed_at` no mesmo commit do ledger.
   Qualquer falha reverte ambos. O contexto anterior é restaurado ao sair.

Tabela `payment_webhook_events` / `PaymentWebhookEvent` herda `TenantMixin`:
tenant, Fatura FK, provider, ID/tipo de evento, ID/referência remotos, SHA-256 do
payload e timestamps. Não persiste payload completo, tokens ou dados pessoais
adicionais. Nenhum helper genérico de bypass, endpoint de ledger ou tabela Cobranca.

ASAAS declara IDs únicos de evento, preservados nas reentregas: por isso a
constraint é **provider + event_id**, sem tenant. O tenant continua obrigatório
para propriedade, autenticação e consultas. A transação evita marcar evento
concluído sem Fatura atualizada, ou atualizar Fatura sem evento durável.
Duplicatas autenticadas retornam 200 sem tocar timestamps nem executar `_aplicar`.
Side effects futuros de banco devem participar desta transação; efeitos externos
exigirão entrega durável própria. Nenhuma notificação/automações implementadas.

### Credenciais e ativação

- Usar o CRUD existente, provider `asaas`, nomes exatos `webhook_token_sandbox`
  e `webhook_token_producao`; valores devem coincidir com `authToken` configurado
  no ASAAS daquela empresa/ambiente. Usar segredos distintos por empresa/ambiente.
- API keys nomeadas `api_key_sandbox`/`api_key_producao` têm prioridade. API keys
  de nomes livres anteriores continuam fallback; tokens e chaves nomeadas do
  outro ambiente nunca são selecionados como API key.
- Menor evolução compatível B1: ambiente ainda segue a URL da instalação
  (`api-sandbox.asaas.com` → sandbox; `api.asaas.com`/`www.asaas.com` → produção).
  Ambientes simultâneos por empresa/troca de conta permanecem futuros. Não trocar
  URL/conta enquanto existirem cobranças/intencões dependentes do ambiente anterior.
- `ASAAS_WEBHOOK_TOKEN` fica sem uso no webhook. Antes de ativar B2, cadastrar os
  tokens por empresa; não há fallback global nem migração automática de segredos.
- Testar webhook token no HUB verifica apenas cifra local (`dry-run`). Homologar
  entrega real separadamente; a UI existente informa os nomes, sem nova tela.

### Estados e limites

Eventos aceitos: `PAYMENT_CREATED`, `PAYMENT_UPDATED`, `PAYMENT_CONFIRMED`,
`PAYMENT_RECEIVED`, `PAYMENT_OVERDUE`, `PAYMENT_DELETED`, `PAYMENT_RESTORED`,
`PAYMENT_REFUNDED`, `PAYMENT_PARTIALLY_REFUNDED`, `PAYMENT_RECEIVED_IN_CASH_UNDONE`,
`PAYMENT_BANK_SLIP_CANCELLED`, `PAYMENT_BANK_SLIP_VIEWED`, `PAYMENT_CHECKOUT_VIEWED`.
Usar `payment.status`: PENDING→pending; RECEIVED/CONFIRMED/RECEIVED_IN_CASH→received;
OVERDUE→overdue; REFUNDED→refunded. PAYMENT_DELETED→canceled (evento formal,
não um status remoto inventado). Cancelamento do registro de boleto na CIP **não**
significa exclusão da cobrança. Evento/status não suportado retorna 422 sem commit;
não converter silenciosamente chargeback/risco/reembolso em progresso para pending.
Configurar apenas o conjunto necessário no ASAAS e monitorar respostas não-2xx.

`status_interno`, chave/reserva de emissão, `asaas_id` e referência B1 não mudam.
Webhook pode localizar intenção pendente pela referência e atualizar o espelho;
conclusão da emissão ainda exige a reconciliação validada B1. Nenhum overdue local.
Não há ordenação temporal entre eventos **distintos**: configurar entrega sequencial
no provider e homologar eventos atrasados. Idempotência por ID não garante ordem.

Migration `k5e0f4a9b7c1` após B1: cria somente ledger/índices, sem alterar Fatura
ou dados legados. Upgrade e downgrade vazio testados; downgrade com ledger não
vazio bloqueia antes de apagar auditoria (mesma política de preservação B1).
Aplicar migration antes de iniciar leitores B2, com escritores antigos parados.
Não executar código antigo de webhook após ativação B2, pois ignora o ledger.

Referências oficiais: [envelope, header e reentregas](https://docs.asaas.com/docs/webhooks-events),
[unicidade do evento](https://docs.asaas.com/docs/how-to-implement-idempotence-in-webhooks),
[tipos de evento](https://docs.asaas.com/docs/payment-events),
[campos/status do payment](https://docs.asaas.com/reference/retrieve-a-single-payment).
Homologação ASAAS Sandbox real e concorrência PostgreSQL ainda pendentes; testes
locais não usaram credenciais reais nem criaram cobranças externas.

## B3 — Homologação (2026-09-14) — PARTIAL

O PostgreSQL de desenvolvimento chegou de h2b7c1d9e4f6 ao head
k5e0f4a9b7c1 e confirmou as constraints/índices B1/B2. Concorrência real
contra PostgreSQL, mas com cliente ASAAS simulado, confirmou uma intenção/POST
para dois comandos equivalentes e um ledger/efeito para duas entregas do mesmo
evento. O alvo estava sem Faturas legadas antes do upgrade; sua compatibilidade
continua comprovada pela suíte SQLite. Dados B3 efêmeros foram removidos depois
da prova.

Não havia ApiCredential(provider='asaas') no banco de desenvolvimento, nem
endpoint público de homologação. Portanto emissão, retry, reconciliação por
externalReference, entrega externa e isolamento entre duas credenciais reais
Sandbox estão bloqueados. Para retomar: empresa(s) de teste, API key e
webhook_token_sandbox distintos por empresa, URL pública não produtiva e
webhook ASAAS Sandbox configurado com entrega SEQUENTIALLY.

A documentação ASAAS atual confirma externalReference como filtro de listagem
e entrega ordenada somente no modo sequencial. O HUB não ordena eventos
distintos: RECEIVED seguido de PENDING pode regredir o espelho; B2 protege
somente reentregas do mesmo event_id. Tratar ordenação como follow-up, não
alterar nesta sprint.

O ambiente permanece global por instalação via ASAAS_API_BASE_URL; API keys e
tokens são por empresa, mas a escolha Sandbox/produção não. A dívida pertence
ao follow-up D2 de ambiente ASAAS por empresa.

## B1 — Emissão idempotente (2026-09-14)

`FaturaService.emitir()` continua a única fronteira de emissão. `Fatura` é a
persistência da Cobrança HUB; não há tabela `Cobranca` adicional.

- A intenção `aguardando_emissao`, a chave do comando e a referência UUID são
  confirmadas no banco **antes** de qualquer chamada ASAAS.
- Comando equivalente = empresa + cliente + UC + competência + valor normalizado
  a centavos + vencimento. O hash `emission_key` tem unicidade por empresa;
  `external_reference` tem unicidade global e nunca é recalculada.
- `UPDATE ... WHERE emissao_iniciada_em IS NULL AND asaas_id IS NULL`, com tenant,
  reserva atomicamente a emissão. O commit da reserva precede o efeito externo.
  Não existe lock em memória nem expiração que permita outro POST durante timeout.
- `payment_customer_id` registra o destinatário remoto antes do POST para validar
  o resultado da reconciliação. Não se recalcula pagamento a partir do cadastro atual.
- Sucesso grava `asaas_id`, URLs, status remoto e `status_interno='emitida'`.
- Retry retorna a mesma intenção concluída ou consulta o ASAAS por referência.
  Referência, customer, valor, vencimento, BOLETO e status precisam corresponder.
  Resposta malformada, múltiplos resultados ou divergência bloqueiam a conclusão.
- Erro de customer anterior a `/payments` libera a reserva, pois esse caminho
  comprova que não houve POST de pagamento. Após iniciar `/payments`, qualquer
  erro (inclusive 4xx/5xx), timeout ou queda de processo conserva a reserva.
- Resultado vazio no GET após uma tentativa **não prova ausência definitiva**:
  retorna `409 EMISSAO_PENDENTE` com `faturaId`; não há reenvio automático.
- Falha no commit final mantém a referência durável. O mesmo POST de HUB ou a
  ação existente de sincronizar pode concluir a persistência por reconciliação.

`status_interno` distingue workflow (`aguardando_emissao`, `emitida`,
`erro_emissao`, `cancelada`) de `asaas_status`. Para preservar o contrato antigo,
`asaas_status` conserva o default `pending`; sem `asaas_id`, isso não significa
boleto emitido nem status remoto confirmado. Resumo de cobranças só conta IDs remotos.

Legados permanecem legíveis, com novos campos nulos e valores/histórico intactos.
A garantia de retry usa comandos registrados a partir de B1; não se inventa uma
chave para emissões anteriores. Repetir um comando B1 já cancelado também recupera
seu registro; uma nova versão explícita não faz parte desta sprint.

Migration: `j4d9e3f8a6b0`, após `i3c8d2e7f5a9`. Upgrade preserva dados;
downgrade funciona com banco vazio/legado, mas bloqueia antes do DDL se houver
intenção B1, para não apagar o diário de emissão. Aplicar com escritores parados;
não executar código antigo após emitir sob B1.

Limites operacionais: queda depois da reserva e antes do POST pode exigir
conciliação manual, assim como rejeição definitiva do provider. Não limpar a
reserva nem alterar valor/vencimento para contornar um resultado ambíguo. Manter
a mesma conta/ambiente ASAAS para reconciliar; a gestão de troca de conta é futura.
O cadastro remoto de customer ainda pode duplicar se o próprio `/customers`
sofrer timeout; isso não libera dois pagamentos do mesmo comando.

Referência do provider: [GET /payments por externalReference](https://docs.asaas.com/reference/listar-cobrancas)
e [criação de cobrança](https://docs.asaas.com/reference/criar-nova-cobranca).
O ASAAS documenta a referência como busca, não como uma constraint de unicidade.
> Documentos relacionados: [[VISAO]] · [[API_CONTRACTS]] · [[PENDENCIAS]] · [[AGENTS]]
> Formato: compacto, Ctrl+F-friendly. Não é spec narrativa — é checklist executável.

## Princípio (não quebrar)
Único service de emissão, dois chamadores:
```
manual (form)     ──┐
                     ├──► FaturaService.emitir() ──► AsaasClient ──► Fatura (espelho local)
automação (futuro) ──┘
```
Rotas/models/integração NUNCA sabem se quem chamou foi humano ou robô. Robô é chamador novo do mesmo service — nunca reescreve o service.

Fonte de verdade do status = ASAAS (via webhook), não data local. Não calcular "vencido" comparando data no HUB.

## 1. asaas_client.py (novo, isolado)
- `backend/services/asaas_client.py`
- Funções: `criar_cobranca(payload)->dict`, `consultar_cobranca(asaas_id)->dict`, `cancelar_cobranca(asaas_id)->bool`
- Credencial: reaproveita `ApiCredential` (`provider='asaas'`, já existe, já criptografado por empresa) — **nenhuma tela nova**.
- Sem credencial configurada → falha controlada (400/503), nunca crash, nunca silencioso (diferente de `email_service.py`).
- Timeout curto, sem retry automático nesta fase.
- Padrão lazy-init igual `drive_service.py` (nada inicializa no import).

## 2. Model Fatura (novo)
`backend/models/fatura.py` + migration, `TenantMixin`.

| Campo | Tipo | Nota |
|---|---|---|
| empresa_id | FK Empresa | TenantMixin |
| client_id | FK Client, obrigatório | |
| consumer_unit_id | FK ConsumerUnit, obrigatório | 1 boleto por UC |
| concessionaria | string | livre, igual Client/Plant |
| competencia | string YYYY-MM | |
| valor | Numeric(10,2) | valor enviado na emissão (auditável) |
| mes_vencimento | date | |
| origem | string `manual`\|`automatica` | quem preencheu os dados, não quem emitiu (tudo emite via ASAAS) |
| asaas_id | string, único por empresa, indexado | correlação c/ webhook |
| asaas_status | string `pending`\|`received`\|`overdue`\|`canceled`\|`refunded` | espelho, confirmar nomes na doc ASAAS atual |
| boleto_url | string | link hospedado pela ASAAS (não é Document/Drive) |
| linha_digitavel / codigo_barras | string, opcional | pro envio (seção 6) |
| criado_por_id | FK User, opcional | nulo se origem=automatica |
| enviado_em | datetime, opcional | |
| created_at/updated_at | datetime | |

**Removido do desenho anterior:** `document_id`, `paga_em` calculado, status por comparação de data. **Sem PUT** (boleto emitido é imutável — cancela e reemite).

## 3. Sincronização de status
- **(A) Webhook ASAAS** — `POST /webhooks/asaas`, pública, precisa entrar em `public_paths` de `utils/auth.py` (mesmo grupo de `/oauth/google/callback`). Validar autenticidade (assinatura/token — checar doc ASAAS). Implementar já na 1ª entrega.
- **(B) Polling manual** — `POST /faturas/<id>/sincronizar` chama `consultar_cobranca()` sob demanda (mesmo padrão de `POST /pendencias/verificar`). Fallback, não bloqueante.

## 4. Rotas — `/api/v1/faturas`

| Rota | Método | Lógica |
|---|---|---|
| `/faturas` | POST | Emissão manual idempotente: `clienteId`, `ucId`, `valor`, `mesVencimento`, `competencia`. Valida tenant/ator, confirma a intenção local e sua referência antes do ASAAS; retry recupera/reconcilia a mesma intenção. `asaas_id` pode ser nulo; ver B1 acima. |
| `/faturas?clienteId=&ucId=&status=&competencia=` | GET | Lista local, não consulta ASAAS a cada request |
| `/faturas/<id>` | GET | Detalhe local |
| `/faturas/<id>/sincronizar` | POST | Força consulta pontual, atualiza `asaas_status` |
| `/faturas/<id>/cancelar` | POST | Chama ASAAS, atualiza status. Não é DELETE (auditoria) |
| `/faturas/<id>/enviar` | POST | Ver seção 6 |
| `/faturas/resumo` | GET | Cards por `asaas_status`, mesmo padrão `GET /pendencias/resumo` |
| `/webhooks/asaas` | POST, pública | Recebe callback (seção 3) |

**Removido:** `PUT /faturas/<id>`, `/marcar-paga`, `/reabrir` (status é exclusivo da ASAAS agora).

## 5. Permissões
`faturas.create` restrito a `owner`/`admin`/`financial` (dinheiro real sendo movimentado). `operator` só `faturas.read`. Mesmo padrão de `require_role('owner','admin')` de `email_template_routes.py`.

## 6. Envio ao cliente
- **E-mail:** novo `MessageTemplate` `chave='boleto_emitido'`, canal `email`. Reaproveita `render_email_for_empresa()` (já usado por `password_reset_service.py`/`invitation_service.py`). Variáveis: `nome`, `link=boleto_url`, `valor`, `vencimento`. Zero código novo de envio (`email_service.py` existente).
- **WhatsApp:** rota já aceita canal, mas retorna "canal indisponível" até V1.5-C decidir provedor. **Não implementar envio WhatsApp agora.**

## 7. Motor de automação (extensão de `automacao_service.py`)
- Lembrete de vencimento: cálculo por data (`mes_vencimento` a N dias, `asaas_status='pending'`) — independe de webhook.
- Boleto vencido: reativo — dispara quando webhook muda `asaas_status='overdue'`, não por job comparando datas. Evita pendência fantasma (cliente pagou no mesmo dia).
- `Pendencia.fatura_id` opcional, mesmo padrão de `client_id`/`uc_id`/`plant_id`/`document_id`.

## 8. Fora de escopo nesta entrega
- Upload manual de PDF de boleto (não existe mais — boleto é sempre resposta da API)
- Importação em massa de fatura da concessionária → isso vira, no futuro, só **mais um chamador** de `FaturaService.emitir()`, não uma rota nova

## 9. Ordem de implementação
1. Confirmar `provider='asaas'` já existe em `PROVIDERS_VALIDOS` (`api_credential_service.py`) — checar, sem mudança esperada
2. `asaas_client.py` isolado, testável com mock (sem rota ainda)
3. Migration + `models/fatura.py`
4. `POST /faturas` + `GET /faturas` + `GET /faturas/<id>` (sem webhook, status = o que veio na criação)
5. `POST /webhooks/asaas` (sincronização real)
6. `POST /faturas/<id>/cancelar`, `/sincronizar`, `/resumo`
7. `FaturasPage.ts` + aba Financeiro em `ClientDetailView.ts`
8. `POST /faturas/<id>/enviar` (e-mail via `MessageTemplate`)
9. Extensão de `automacao_service.py` (lembrete + vencido reativo)
10. *(fase separada, gate por regra de negócio ainda não definida)* import de fatura concessionária → `FaturaService.emitir()`

**Testes obrigatórios:** isolamento tenant, concorrência de sessões independentes,
retry normal, timeout, reconciliação, falha de commit e migrations. Falha ASAAS
preserva a intenção local recuperável, sem declarar emissão falsa nem repetir POST cegamente.
