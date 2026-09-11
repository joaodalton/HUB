# FATURAS_E_COBRANCAS.md

## 1. Objetivo

Este documento define a arquitetura oficial do módulo de **Faturas & Cobranças** do HUB.

O módulo cobre o fluxo completo:

```text
Upload da fatura da concessionária
        ↓
Validação do arquivo
        ↓
Deduplicação
        ↓
Armazenamento do PDF original
        ↓
Detecção da concessionária/layout
        ↓
Parser específico
        ↓
ParsedInvoice
        ↓
InvoiceNormalizer
        ↓
InvoiceNormalized
        ↓
Validação + vínculo Cliente/UC
        ↓
Resolução da regra de cobrança
        ↓
Motor de cálculo
        ↓
Política de faturamento
        ↓
Cobrança calculada
        ↓
Confirmação de emissão
        ↓
PaymentProvider
        ↓
ASAAS ou outro provider
        ↓
Webhook / conciliação
        ↓
Pendências / Agenda
        ↓
Envio ao cliente
```

A implementação é incremental. Nenhuma etapa posterior deve compensar silenciosamente um erro de uma etapa anterior.

---

## 2. Regras obrigatórias

1. Não remover funcionalidades existentes.
2. Não alterar comportamento existente sem necessidade.
3. Reutilizar componentes, services, models e padrões existentes antes de criar novos.
4. Seguir a arquitetura multi-tenant atual.
5. Não colocar lógica financeira diretamente em routes.
6. Não colocar lógica específica de uma concessionária no motor financeiro.
7. Não colocar lógica de ASAAS dentro do motor de cálculo.
8. Não armazenar credenciais hardcoded.
9. Toda cobrança deve ser auditável.
10. Cobranças emitidas nunca podem depender da configuração atual para reconstruir seu histórico.
11. Toda operação financeira externa deve ser idempotente.
12. Falha de parser, normalização ou matching nunca pode destruir o PDF original.
13. Nunca assumir defaults financeiros silenciosamente.
14. O PDF importado da concessionária é **imutável após a importação**.
15. Alterações posteriores acontecem na cobrança gerada pelo HUB, nunca no documento original.
16. Toda alteração relevante deve atualizar a documentação e o `PROGRESS.md`.

---

## 3. Separação de domínios

O módulo possui responsabilidades independentes:

```text
FATURA
O que a concessionária emitiu.

EXTRAÇÃO
O que foi lido do PDF.

NORMALIZAÇÃO
Como o HUB representa os dados extraídos.

CÁLCULO
Quanto o HUB deve cobrar.

FATURAMENTO
Como a cobrança será apresentada e vencida.

PAGAMENTO
Quem efetivamente gera a cobrança externa.

ENTREGA
Como a cobrança chega ao cliente.
```

Fluxo obrigatório:

```text
PDF
 ↓
Parser
 ↓
Normalizer
 ↓
InvoiceNormalized
 ↓
RuleResolver
 ↓
CalculationEngine
 ↓
BillingPolicy
 ↓
PaymentProvider
```

O fluxo inverso é proibido.

---

## 4. Cliente, UC e Fatura

A fatura é importada dentro da página do Cliente.

```text
Cliente
├── UCs
├── Faturas
├── Cobranças
├── Documentos
└── Configuração financeira
```

Endpoint preferencial:

```http
POST /api/v1/clients/{clientId}/invoices/upload
```

O contexto do upload já fornece:

- `empresa_id`
- `client_id`

O PDF fornece o código da UC.

O backend deve:

1. localizar a UC dentro do cliente informado;
2. validar se ela pertence ao mesmo tenant;
3. caso não encontre no cliente, verificar se a UC existe em outro cliente do mesmo tenant;
4. nunca trocar automaticamente o cliente da importação.

A fatura persiste explicitamente:

- `empresa_id`
- `client_id`
- `consumer_unit_id`

Regra de integridade:

```text
Fatura.client_id == Fatura.consumer_unit.client_id
```

---

## 5. Imutabilidade da fatura

A fatura original da concessionária nunca deve ser modificada após importação.

Devem permanecer imutáveis:

- PDF original;
- hash do arquivo;
- chave fiscal;
- dados brutos extraídos daquele processamento;
- vínculo com o documento original;
- valores originalmente extraídos.

Se for necessário rodar um parser mais novo sobre a mesma fatura, criar um **novo registro/versionamento de extração**, sem sobrescrever silenciosamente os dados que serviram de base para uma cobrança histórica.

Uma cobrança já emitida ou paga nunca pode mudar porque um parser foi atualizado.

---

## 6. Deduplicação

### 6.1 Hash idêntico

Calcular SHA-256 antes do parsing.

Se o mesmo `empresa_id + arquivo_hash` já existir:

- não criar novo `Document`;
- não criar nova `FaturaConcessionaria`;
- não rodar parser;
- manter o registro mais antigo como referência;
- retornar resposta idempotente indicando duplicidade.

### 6.2 Mesma chave fiscal com hash diferente

Não tratar automaticamente como duplicidade descartável.

Pode representar:

- segunda via com conteúdo diferente;
- documento reemitido;
- documento retificado;
- alteração legítima da concessionária.

Comportamento:

- preservar o documento novo;
- não substituir o antigo;
- marcar para revisão;
- criar pendência de conflito documental;
- manter a fatura original já utilizada por cobranças históricas intacta.

### 6.3 Prioridade dos identificadores

1. `arquivo_hash`
2. `chave_acesso`
3. identificador fiscal confiável
4. UC + competência apenas como detecção de possível conflito

---

## 7. Débito automático

`ConsumerUnit.debito_automatico` deve ser a fonte oficial para definir a política de cobrança.

A informação deve ser prioritariamente **manual**, editada por usuário autorizado.

O parser pode detectar textos ou sinais no PDF relacionados a débito automático, porém:

- deve armazenar apenas como `hint`/aviso;
- nunca deve transformar isso automaticamente em `debito_automatico = true`.

Mesmo quando o PDF explicitamente indicar débito automático, o dado manual continua sendo a fonte de verdade até existir uma regra futura formal de sincronização.

---

## 8. Precisão numérica

Valores financeiros e tarifas devem utilizar `Decimal`.

### 8.1 Tarifas

Usar no banco, no mínimo:

```text
Numeric(18, 6)
```

ou precisão equivalente compatível com o schema atual.

Preservar seis casas decimais quando o documento fornecer seis casas.

### 8.2 Dinheiro

Valores finais monetários normalmente são apresentados com duas casas, porém cálculos intermediários devem preservar maior precisão.

### 8.3 Arredondamento

O parser **não arredonda**.

O normalizador preserva o valor encontrado.

A política de arredondamento pertence ao motor financeiro.

Não usar `float` para cálculos monetários.

---

## 9. Armazenamento do PDF

Fluxo obrigatório:

```text
Upload
 ↓
FileValidator
 ↓
SHA-256
 ↓
Deduplicação
 ↓
DocumentService
 ↓
FaturaConcessionaria(recebida)
 ↓
ProcessingService
```

O PDF deve ser preservado antes do parsing.

---

## 10. Segurança do upload

Validar no mínimo:

- extensão permitida;
- MIME;
- magic bytes `%PDF`;
- tamanho máximo;
- quantidade máxima de páginas;
- PDF corrompido;
- PDF criptografado;
- filename sanitizado;
- armazenamento com nome interno controlado pelo HUB.

Não confiar apenas na extensão.

A V1 pode adotar limites conservadores, por exemplo:

- 10 MB por arquivo;
- 10 páginas por fatura.

Esses limites devem ser configuráveis.

---

## 11. Identificação da concessionária

A validação "é PDF" e a validação "é uma fatura suportada" são diferentes.

Fluxo:

```text
PDF válido
 ↓
MinimalExtractor
 ↓
ParserRegistry
 ↓
Parser.can_parse()
```

Exemplo Copel:

- CNPJ da distribuidora;
- presença do marcador DANF3E;
- outros indicadores de layout necessários.

Não usar apenas uma string frágil.

---

## 12. Arquitetura do extrator

Estrutura provável:

```text
backend/services/invoices/
├── upload_service.py
├── processing_service.py
├── matching_service.py
├── normalization_service.py
├── validation_service.py
├── deduplication_service.py
└── schemas.py

backend/services/invoice_parsers/
├── __init__.py
├── base.py
├── registry.py
├── extraction.py
├── copel.py
└── mappings/
    └── copel_items.py
```

Adaptar os nomes à convenção já existente no repositório. Não criar diretórios duplicados se já houver estrutura equivalente.

---

## 13. Pipeline de extração

```text
FileValidator
 ↓
MinimalExtractor
 ↓
ParserRegistry
 ↓
CopelParser
 ↓
StructuredExtraction
 ↓
ParsedInvoice
 ↓
InvoiceNormalizer
 ↓
InvoiceNormalized
 ↓
InvoiceValidator
```

### 13.1 Prioridade de extração

1. âncoras semânticas;
2. tabelas/cabeçalhos;
3. proximidade geométrica;
4. regex contextual;
5. coordenadas absolutas apenas como último recurso.

---

## 14. Versionamento do parser

Toda extração deve registrar:

- `parser_name`
- `parser_version`
- `layout_name`
- `layout_version`

Exemplo:

```text
parser_name = copel
parser_version = 1.0.0
layout_name = danf3e
layout_version = 2026.1
```

---

## 15. ParsedInvoice

Representa aquilo que foi encontrado no documento, sem regra comercial.

Deve suportar:

- identificação;
- titular;
- classificação;
- leituras;
- resumo;
- itens da fatura;
- tributos;
- histórico de consumo;
- medidor;
- boleto original;
- avisos;
- energia;
- warnings;
- metadata da extração.

---

## 16. Status por campo

Um campo ausente não deve ser representado apenas por `null`.

Estados mínimos:

```text
found
not_present
failed
ambiguous
```

Exemplo:

```json
{
  "value": null,
  "status": "not_present"
}
```

é diferente de:

```json
{
  "value": null,
  "status": "failed"
}
```

---

## 17. Confiança por campo

Estrutura conceitual:

```json
{
  "value": "2026-09-10",
  "status": "found",
  "confidence": 0.99,
  "source": "anchor",
  "warnings": []
}
```

A confiança geral pode ser derivada dos campos críticos, mas não substitui a confiança individual.

---

## 18. Severidade

Problemas devem usar:

```text
info
warning
critical
```

Exemplos:

### info
- segunda via;
- informação opcional detectada.

### warning
- item novo ainda não mapeado;
- hint de débito automático vindo do PDF;
- pequena inconsistência entre leitura e consumo.

### critical
- valor total ausente;
- UC ausente;
- vencimento ausente quando obrigatório;
- chave fiscal inválida;
- campo exigido pela regra financeira ausente.

Um item desconhecido não deve automaticamente bloquear toda a fatura.

---

## 19. Status da fatura

Separar:

### `status_extracao`

```text
recebida
processando
extraida
layout_nao_reconhecido
erro
```

### `status_validacao`

```text
pendente
valida
revisao_necessaria
uc_nao_encontrada
uc_pertence_outro_cliente
```

---

## 20. GD-I, GD-II e energia compensada

São campos distintos e nunca devem ser agregados pelo extrator.

Manter separadamente:

- `energia_compensada_kwh`
- `injecao_gd1_kwh`
- `injecao_gd2_kwh`
- `saldo_creditos_kwh`

Sem amostra real de fatura beneficiária, não inventar rótulos de produção.

A Sprint específica de GD-I/GD-II só é concluída com fixtures reais anonimizadas e testes de regressão.

---

## 21. Tarifas do documento

O extrator deve capturar todas as tarifas existentes na fatura, preservando a precisão.

O extrator não decide qual tarifa será usada comercialmente.

O motor financeiro terá:

```text
fonte_tarifa = fatura
```

ou:

```text
fonte_tarifa = manual
tarifa_override = ...
```

---

## 22. Item mapping

Não limitar a um `dict[str, str]`.

Estrutura preparada para:

- exact;
- prefix;
- contains;
- regex;
- priority.

Isso evita colisões principalmente entre GD-I e GD-II.

---

## 23. Invariantes úteis

Usar somente validações de alto valor:

- chave de acesso tem formato esperado;
- competência válida;
- vencimento válido;
- consumo >= 0;
- valor total >= 0;
- UC pertence ao cliente;
- leitura atual >= leitura anterior;
- consumo do medidor aproximadamente coerente com leituras, quando aplicável.

Inconsistências não devem corrigir automaticamente os dados.

---

## 24. Fixtures e regression tests

Diretório sugerido:

```text
backend/tests/fixtures/invoices/
```

Exemplos:

```text
copel_danf3e_consumidor_comum.pdf
copel_danf3e_gd1.pdf
copel_danf3e_gd2.pdf
copel_danf3e_gd1_gd2.pdf
copel_danf3e_debito_automatico.pdf
copel_danf3e_segunda_via.pdf
copel_danf3e_item_desconhecido.pdf
copel_layout_invalido.pdf
```

Cada fixture deve possuir saída esperada equivalente.

O teste executa:

```text
PDF
 ↓
Parser
 ↓
Normalizer
 ↓
resultado
 ↓
expected.json
```

Uma mudança de parser que quebre um layout anterior deve falhar nos testes.

---

## 25. Model `FaturaConcessionaria`

Campos de consulta/operação sugeridos:

- `id`
- `empresa_id`
- `client_id`
- `consumer_unit_id`
- `document_id`
- `concessionaria`
- `codigo_uc_extraido`
- `competencia`
- `numero_nota_fiscal`
- `serie_nota_fiscal`
- `chave_acesso`
- `arquivo_hash`
- `data_emissao`
- `data_leitura_anterior`
- `data_leitura_atual`
- `data_proxima_leitura`
- `data_vencimento`
- `consumo_kwh`
- `energia_compensada_kwh`
- `injecao_gd1_kwh`
- `injecao_gd2_kwh`
- `saldo_creditos_kwh`
- `valor_total_concessionaria`
- `dados_brutos_extraidos`
- `dados_normalizados`
- `parser_name`
- `parser_version`
- `layout_name`
- `layout_version`
- `status_extracao`
- `status_validacao`
- timestamps

Dados pouco consultados devem permanecer em JSON em vez de virar dezenas de colunas.

---

# MOTOR DE COBRANÇA

## 26. GrupoRegraCobranca

Representa um perfil reutilizável.

Exemplos:

- Padrão
- Associação 20%
- Cliente antigo
- Contrato especial
- GD-II específico

Campos conceituais:

- `id`
- `empresa_id`
- `nome`
- `descricao`
- `ativo`
- `is_default`
- `metodo_calculo`
- `fonte_tarifa`
- `tarifa_override`
- `tipo_desconto`
- `desconto_valor`
- `base_tarifaria`
- `modo_cobranca`
- `vencimento_base`
- `vencimento_offset_dias`
- `juros_percentual_mes`
- `multa_percentual`
- timestamps

A exibição da fatura original para o cliente **não é configurável na regra padrão**: a fatura da concessionária deve sempre ficar disponível para o cliente consultar.

---

## 27. RegraCobrancaAssignment

Separa a regra de quem usa a regra.

Escopos:

```text
global
client
consumer_unit
```

Precedência:

```text
UC
 ↓
Cliente
 ↓
Global
```

Constraints obrigatórias devem impedir mais de uma regra ativa no mesmo escopo para o mesmo alvo.

---

## 28. Resolvedor de regra

Entrada:

- UC;
- cliente;
- tenant.

Saída:

- grupo aplicado;
- origem (`consumer_unit`, `client`, `global`);
- assignment;
- parâmetros efetivos.

Sem regra resolvida:

```text
billing_rule_not_found
```

Bloquear cálculo.

---

## 29. Estratégias de cálculo

O motor deve utilizar estratégia, não uma coleção de booleanos incompatíveis.

Estratégias previstas:

- `energia_compensada`
- `economia_gerada`
- `valor_total_fatura`
- `tarifa_fixa`

Implementar somente as fórmulas formalmente definidas e testadas.

---

## 30. Resultado do cálculo

Criar estrutura equivalente a `BillingCalculationResult`.

Deve conter:

- versão do motor;
- regra usada;
- energia considerada;
- GD-I;
- GD-II;
- energia compensada;
- tarifa e fonte;
- valor base;
- descontos;
- adicionais;
- valor HUB;
- warnings;
- memória completa do cálculo.

---

## 31. Snapshot

Toda cobrança persiste:

- `regra_snapshot`;
- `memoria_calculo`.

Alterar `GrupoRegraCobranca` futuramente nunca altera uma cobrança antiga.

---

# POLÍTICA DE FATURAMENTO

## 32. Modo de cobrança

Valores:

```text
auto
unificada
separada
```

### `auto`

```text
ConsumerUnit.debito_automatico = true
→ separada

ConsumerUnit.debito_automatico = false
→ unificada
```

Overrides explícitos de `unificada` ou `separada` prevalecem sobre `auto`.

Caso seja forçada `unificada` em UC marcada manualmente como débito automático, gerar warning:

```text
AUTO_DEBIT_WITH_FORCED_UNIFIED_BILLING
```

---

## 33. Cobrança separada

```text
valor_total = valor_hub
```

O valor da concessionária permanece apenas como referência.

---

## 34. Cobrança unificada

```text
valor_total = valor_concessionaria + valor_hub
```

A memória de cálculo deve manter os dois componentes separados.

---

## 35. Fatura da concessionária sempre disponível

A regra padrão do HUB é:

> Toda cobrança deve disponibilizar a fatura original da concessionária ao cliente.

Isso vale para cobrança unificada e separada.

V1 não precisa mesclar o PDF da concessionária com o boleto do provider.

Na experiência do cliente devem existir:

- link/ação para pagamento da cobrança HUB;
- link/ação para visualizar a fatura original.

Na cobrança separada, nunca aplicar texto "NÃO PAGAR A CONCESSIONÁRIA" automaticamente.

---

## 36. Vencimento

Estrutura:

- `vencimento_base`
- `vencimento_offset_dias`

Bases previstas:

- vencimento da concessionária;
- emissão da concessionária;
- leitura;
- data de geração da cobrança.

Se a base exigida não existir, bloquear cálculo da data.

---

## 37. Juros e multa

Fazem parte da política de faturamento, não do provider.

Campos V1:

- `juros_percentual_mes`
- `multa_percentual`

O provider apenas converte esses valores para seu payload.

---

# COBRANÇA

## 38. Model `Cobranca`

Campos conceituais:

- `id`
- `empresa_id`
- `client_id`
- `consumer_unit_id`
- `fatura_concessionaria_id`
- `competencia`
- `grupo_regra_id`
- `assignment_id`
- `regra_snapshot`
- `memoria_calculo`
- `modo_cobranca`
- `valor_hub`
- `valor_concessionaria`
- `valor_total`
- `vencimento`
- `juros_percentual_mes`
- `multa_percentual`
- `status`
- `versao`
- `substitui_cobranca_id`
- `payment_provider`
- `external_payment_id`
- `external_reference`
- `invoice_url`
- `pago_em`
- timestamps

---

## 39. Estados da cobrança

Estados previstos:

```text
calculada
aguardando_emissao
emitida
paga
vencida
cancelada
substituida
erro_calculo
erro_emissao
```

---

## 40. Nova versão de cobrança

Se já existir cobrança para a mesma fatura/competência e o usuário solicitar uma nova:

Frontend deve mostrar:

```text
Já existe uma cobrança para esta fatura.

[Cancelar] [Confirmar nova versão]
```

### Ao cancelar

Nenhuma alteração.

### Ao confirmar

#### Se a cobrança antiga ainda não foi emitida
Pode ser marcada como `substituida` e a nova versão é criada.

#### Se a cobrança antiga foi emitida
Não fazer hard delete.

1. tentar cancelar no provider quando permitido;
2. marcar a cobrança antiga como `substituida` ou `cancelada`;
3. preservar snapshot e histórico;
4. criar nova cobrança com `versao + 1`;
5. preencher `substitui_cobranca_id`.

#### Se a cobrança antiga já foi paga
Não substituir silenciosamente.

Bloquear o fluxo simples e exigir processo financeiro específico de estorno/ajuste.

**Nunca apagar hard-delete uma cobrança emitida/paga**, pois isso destruiria auditoria.

---

## 41. Idempotência e concorrência

A checagem em código não é suficiente.

Implementar proteção no banco e na transação para impedir duas cobranças ativas equivalentes.

Usar:

- constraint/índice apropriado;
- transação;
- lock quando necessário;
- checagem amigável em Python.

A implementação deve permitir versões explícitas, sem permitir duplicidade acidental.

---

# PAYMENT PROVIDER

## 42. Abstração

Estrutura conceitual:

```text
PaymentProvider
├── ensure_customer()
├── create_payment()
├── get_payment()
└── cancel_payment()
```

O domínio nunca deve importar lógica ASAAS diretamente no motor financeiro.

---

## 43. ExternalPaymentCustomer

Uma associação por:

```text
empresa_id + client_id + provider
```

para reutilizar o mesmo customer externo em múltiplas competências.

---

## 44. Credenciais ASAAS

Existem dois segredos diferentes por ambiente:

- API key;
- webhook token.

E dois ambientes:

- sandbox;
- produção.

Reutilizar `ApiCredential` se seu schema atual suportar `provider + nome`.

Nomes possíveis:

```text
api_key_sandbox
webhook_token_sandbox
api_key_producao
webhook_token_producao
```

Criar configuração explícita por empresa para indicar o ambiente ativo.

Não colocar ambiente no `GrupoRegraCobranca`.

---

## 45. Emissão

Separar:

```text
CALCULAR
```

de:

```text
EMITIR
```

Uma cobrança `calculada` não chama API externa.

A emissão só ocorre por comando explícito ou automação futura autorizada.

---

## 46. Webhook ASAAS e multi-tenant

A rota é pública e não possui cookie de sessão.

Fluxo obrigatório:

```text
Webhook
 ↓
extrair external_payment_id / externalReference
 ↓
consulta controlada de Cobranca sem filtro automático de tenant
 ↓
resolver empresa_id
 ↓
carregar webhook_token do ambiente ativo daquela empresa
 ↓
comparar token com secrets.compare_digest()
 ↓
estabelecer contexto do tenant
 ↓
processar evento
```

Essa consulta sem tenant filter deve ser encapsulada e restrita exclusivamente ao serviço de webhook.

Não criar um bypass genérico disponível ao resto da aplicação.

---

## 47. Idempotência do webhook

Registrar eventos externos ou mecanismo equivalente.

Chave preferencial:

```text
provider + event_id
```

Evento repetido:

- responder sucesso;
- não repetir efeito.

---

# EXPERIÊNCIA DO CLIENTE

## 48. Página de Faturas

Dentro do cliente:

- competência;
- UC;
- concessionária;
- vencimento;
- valor concessionária;
- status de extração;
- status de validação;
- status da cobrança.

Ações conforme permissão:

- importar;
- visualizar PDF;
- ver dados extraídos;
- revisar;
- calcular cobrança;
- criar nova versão;
- emitir;
- abrir pagamento.

---

## 49. Regra do Cliente e da UC

Cliente pode:

- herdar regra global;
- apontar para grupo específico.

UC pode:

- herdar cliente;
- apontar para grupo específico.

A interface deve mostrar a regra efetiva e sua origem.

---

# PENDÊNCIAS E AGENDA

## 50. Pendências

Criar/reutilizar regras para:

- UC não encontrada;
- UC pertence a outro cliente;
- conflito de mesma chave fiscal com arquivo diferente;
- layout desconhecido;
- falha de parser;
- revisão crítica;
- fatura válida sem cobrança;
- erro de cálculo;
- erro de emissão;
- cobrança vencida.

Resolver automaticamente quando a condição deixar de existir.

---

## 51. Agenda

A Agenda deve consumir dados derivados de:

- vencimento da concessionária;
- vencimento HUB;
- prazo de emissão;
- cobrança vencida;
- pendências relevantes.

Não duplicar lógica de negócio na Agenda.

---

# ENVIO AO CLIENTE

## 52. Notification Provider

Somente após a cobrança persistida.

O serviço de envio nunca recalcula valores.

Deve consumir:

- cliente;
- cobrança persistida;
- valor;
- vencimento;
- invoice URL;
- fatura original.

Canais futuros:

- e-mail;
- WhatsApp.

Registrar histórico de entrega quando necessário.

---

# SPRINTS

## Sprint F0 — Descoberta

Inspecionar antes de editar:

- Client
- ConsumerUnit
- Document
- Category
- TenantMixin
- ApiCredential
- permission_service
- automacao_service
- document_service
- upload atual
- request limits
- migrations
- infraestrutura de testes
- convenções de nomenclatura
- serviços existentes de integração

Entregar relatório curto.

---

## Sprint F1 — Fundação da fatura

Implementar:

- `FaturaConcessionaria`;
- relacionamentos;
- status;
- índices;
- constraints;
- migration;
- serialização.

Sem parser e sem financeiro.

---

## Sprint F2 — Upload seguro

Implementar:

- endpoint no Cliente;
- validação de PDF;
- SHA-256;
- deduplicação por hash;
- armazenamento do `Document`;
- registro da fatura recebida.

---

## Sprint F3 — Framework do extrator

Implementar:

- ExtractedField;
- ParsedInvoice;
- RawExtraction;
- MinimalExtractor;
- Parser interface;
- ParserRegistry;
- versionamento;
- warnings/errors.

---

## Sprint F4 — Copel DANF3E Core

Extrair:

- concessionária;
- UC;
- competência;
- emissão;
- vencimento;
- valor total;
- chave de acesso;
- leituras;
- consumo.

---

## Sprint F5 — Copel DANF3E Deep

Adicionar:

- itens;
- tributos;
- tarifas;
- histórico;
- medidor;
- classificação;
- avisos;
- dados bancários relevantes.

---

## Sprint F6 — GD-I / GD-II

Só iniciar com amostra real.

Implementar e testar separadamente:

- GD-I;
- GD-II;
- energia compensada;
- saldo de créditos.

---

## Sprint F7 — Normalizer + Validator

Fechar:

```text
ParsedInvoice
 ↓
InvoiceNormalized
```

Adicionar:

- confidence;
- field status;
- warnings;
- critical;
- invariants;
- matching Cliente/UC.

STOP: validar manualmente fixtures.

---

## Sprint C0 — Contrato financeiro

Congelar o schema `InvoiceNormalized` consumido pelo financeiro.

---

## Sprint C1 — GrupoRegraCobranca

Criar perfil reutilizável.

---

## Sprint C2 — Assignments

Implementar:

```text
UC → Cliente → Global
```

com constraints de unicidade.

---

## Sprint C3 — RuleResolver

Resolver regra efetiva sem defaults silenciosos.

---

## Sprint C4 — Fonte de tarifa

Implementar:

- tarifa da fatura;
- tarifa manual override.

---

## Sprint C5 — Estratégias

Implementar estratégias formalmente aprovadas.

---

## Sprint C6 — BillingCalculationResult

Memória de cálculo + snapshot.

STOP: validar cálculos manualmente.

---

## Sprint P0 — Cobranca

Criar entidade financeira.

---

## Sprint P1 — Snapshot

Persistir regra aplicada e memória do cálculo.

---

## Sprint P2 — BillingPolicy

Implementar:

- auto;
- unificada;
- separada;
- débito automático manual como fonte oficial.

---

## Sprint P3 — Vencimento

Implementar base + offset.

---

## Sprint P4 — Juros e multa

Implementar política interna.

---

## Sprint P5 — API calcular cobrança

Sem provider.

STOP: validar cobrança manualmente.

---

## Sprint D0 — PaymentProvider

Criar abstração.

---

## Sprint D1 — ExternalPaymentCustomer

Persistir associação de customer externo.

---

## Sprint D2 — Credenciais e ambiente ASAAS

Implementar sandbox/produção e dois segredos.

---

## Sprint D3 — ASAAS Provider

Implementar integração.

---

## Sprint D4 — Emissão

Implementar emissão idempotente e criação de nova versão mediante confirmação.

---

## Sprint D5 — Webhook multi-tenant

Implementar resolução segura do tenant e `secrets.compare_digest`.

---

## Sprint D6 — Idempotência de webhook

Garantir eventos únicos.

STOP: validar sandbox.

---

## Sprint E0 — Experiência de pagamento

Usar `invoice_url` do provider e disponibilizar sempre a fatura original como documento separado.

---

## Sprint E1 — Faturas do Cliente

Finalizar UI operacional.

---

## Sprint E2 — Regra do Cliente

UI para herança/override.

---

## Sprint E3 — Override da UC

UI de regra efetiva da UC.

---

## Sprint F8/F9 — Pendências e Agenda

Integrar fluxos operacionais.

---

## Sprint G0-G3 — Envio

E-mail/WhatsApp e histórico.

---

## Sprint H — Automação

Somente depois de o fluxo manual estar estável.

Fluxo automatizável:

```text
Fatura válida
 ↓
resolver regra
 ↓
calcular
 ↓
validar
 ↓
emitir
 ↓
enviar
```

---

# CRITÉRIOS DE ACEITE GERAIS

O módulo só é considerado arquiteturalmente correto se:

- parser não conhece SQLAlchemy diretamente;
- parser não conhece motor financeiro;
- motor financeiro não conhece ASAAS;
- ASAAS não decide regra de negócio;
- fatura original é imutável;
- GD-I e GD-II permanecem separados;
- valores financeiros usam Decimal;
- tarifas preservam pelo menos seis casas decimais;
- cobrança histórica possui snapshot;
- cobrança histórica possui memória de cálculo;
- regra resolve UC → Cliente → Global;
- cobrança automática respeita débito automático manual;
- fatura original fica sempre disponível ao cliente;
- duplicidade de hash é descartada idempotentemente;
- mesma chave fiscal + hash diferente gera revisão, não overwrite;
- nova versão de cobrança exige confirmação;
- cobrança emitida/paga nunca sofre hard delete;
- emissão é protegida contra concorrência;
- webhook resolve tenant de forma explícita;
- webhook usa comparação constant-time;
- sandbox e produção são separados;
- tenant A nunca acessa dados do tenant B;
- testes de regressão existem para parsers;
- documentação e PROGRESS.md são atualizados por sprint.

---

# NOMENCLATURA

Documentação, UI e conceitos de produto devem permanecer em português.

No código, o Codex deve seguir a convenção já existente no HUB. Não fazer renomeação massiva apenas para padronizar idioma. Se o projeto já utiliza identifiers em inglês, continuar o padrão local do arquivo/módulo. Consistência arquitetural é mais importante que traduzir nomes existentes.
