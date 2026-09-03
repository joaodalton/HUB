ADR — Financeiro V2.0 (Fatura via ASAAS)
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
| `/faturas` | POST | Emissão manual: `clienteId`, `ucId`, `valor`, `mesVencimento`, `competencia`. Valida tenant (`_client()`/`_uc()`). Chama ASAAS; só grava `Fatura` se sucesso (nunca registro órfão sem `asaas_id`). `origem='manual'`, `criado_por_id=g.current_user.id`. |
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

**Testes obrigatórios a partir da etapa 3:** isolamento tenant (padrão `test_tenant_service_lookups.py`). A partir da etapa 4: falha da ASAAS não deve gravar registro órfão — é o ponto mais frágil (única chamada de saída que grava dado financeiro).