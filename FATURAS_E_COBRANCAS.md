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

## 3.1 Compatibilidade da Cobrança HUB

Nesta arquitetura, **Cobrança** é o conceito de domínio. Sua persistência física atual e futura é o model `Fatura`, na tabela `faturas` já existente.

- Não criar model ou tabela `Cobranca` paralela.
- `FaturaConcessionaria` será a entidade distinta, documental e imutável da fatura original emitida pela concessionária.
- `Fatura` poderá referenciar opcionalmente `fatura_concessionaria_id`; cobranças manuais legadas podem permanecer sem esse vínculo.
- Os campos de pagamento já existentes em `Fatura` permanecem a projeção técnica do provider até a evolução incremental para o contrato financeiro completo.

### Sprint B1 — emissão ASAAS

Implementação descrita em `FATURAS.md`, seção B1: intenção `Fatura` e UUID de
referência confirmados antes do efeito externo; unicidade do comando por empresa;
reserva atômica persistente no banco; retry retorna a intenção ou reconcilia via
`externalReference`. Ausência numa consulta após timeout não autoriza novo POST.
O workflow local (`status_interno`) não substitui o status remoto (`asaas_status`).
Legados não recebem referências, comandos, políticas nem significados retroativos.

O escopo B1 não implementa as entidades, versões explícitas, abstrações ou
automações das seções futuras deste documento. B2/webhook permanece etapa separada.

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

Endpoint legado por cliente (o fluxo atual da página de Faturas usa o upload por UC, descrito na seção UI-C1):

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
Extração da UC para vínculo automático (somente na rota sem cliente)
 ↓
Deduplicação
 ↓
DocumentService
 ↓
FaturaConcessionaria(recebida)
 ↓
ProcessingService
```

Na rota sem cliente, a extração da UC é necessária para escolher o cliente
com segurança, inclusive ao verificar duplicatas. Isso não substitui o
processamento/validação F7: os snapshots e o vínculo validado com a UC
continuam posteriores à preservação do PDF.

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
Parser específico
 ↓
ParsedInvoice
 ↓
InvoiceNormalizer
 ↓
InvoiceNormalized
 ↓
InvoiceValidator
```

### Framework confirmado na Sprint F3

- Contratos em `backend/services/invoice_parsers/schemas.py`, com dataclasses
  independentes de Flask/SQLAlchemy. `ExtractedField[T]` exige status explícito;
  `found` exige valor, `not_present`/`failed` não carregam valor e `ambiguous`
  pode guardar uma hipótese acompanhada de issues. Confiança é `Decimal` entre
  0 e 1 ou desconhecida (`None`); valores escalares rejeitam `float`.
- `ExtractionIssue` representa info/warning/critical com código, mensagem,
  caminho de campo opcional e metadata textual opcional. Warnings não lançam
  exceção; falhas técnicas de execução continuam lançando exceções no núcleo.
- `RawExtraction` suporta texto completo ou parcial, páginas efetivamente lidas,
  contagem total, metadata, palavras com coordenadas e tabelas por página.
  `None` em words/tables significa não extraído. Coordenadas podem usar float;
  valores documentais precisos usam Decimal. Nada é persistido automaticamente.
- `MinimalExtractor.extract(document: bytes)` reutiliza pypdf e extrai texto
  somente da primeira página, contagem total e Producer/Creator quando presentes.
  Ausência de texto gera warning técnico; não há OCR ou extração de tabelas.
- `InvoiceParser` declara `identity: ParserIdentity`, `can_parse(raw) -> bool`
  e `parse(document: bytes) -> ParsedInvoice`. A identidade centraliza nome e
  versão do parser e, quando aplicável, nome/versão do layout; é carregada em
  `ParsedInvoice.identity`. O service recusa resultado com identidade divergente.
- `ParserRegistry(parsers).select(raw)` retorna `ParserSelection`: exatamente
  um parser, ou nenhum com `LAYOUT_NOT_RECOGNIZED`/`AMBIGUOUS_LAYOUT`. Identidades
  duplicadas são erro de configuração. Não há desempate por ordem da lista.
  O registry padrão é vazio; parsers fake existem apenas em testes.
- `ParsedInvoice` contém metadata da origem e seções documentais de identificação
  fiscal, titular, classificação, leituras, resumo, itens, tributos, histórico,
  medidor, boleto original, avisos, energia e issues. Seções usam mapas de rótulo
  documental para ExtractedField; grupos repetidos usam tuplas de mapas. Chave
  omitida significa ainda não examinada, nunca confirmação de `not_present`.
  Não há campos financeiros inferidos, normalização ou serialização JSON nesta
  sprint; Decimal é preservado em memória (inclusive por `dataclasses.asdict`).
- `FaturaProcessingService(registry=None).process(fatura_id, document=pdf_bytes)`
  é uma entrada síncrona interna: exige tenant no contexto, consulta fatura e
  Documento nesse tenant e verifica SHA-256 contra o original da F2 antes de
  extrair. Recebe os bytes já obtidos pelo chamador; não baixa do Drive nem chama
  APIs externas. Retorna `ProcessingResult` com raw/parsed/issues ou erro
  estruturado sem conteúdo da exceção. Não é endpoint nem chamada automática
  no upload; o adaptador de obtenção do PDF permanece para integração futura.
- Status persistidos, versionamento histórico da extração e gravação dos dados
  ficam para F4. `parsed` é somente resultado em memória e não significa
  `status_extracao=extraida`. A F3 não grava nem `processando`, nem `erro`, nem
  `layout_nao_reconhecido`; esses dois últimos aparecem apenas no resultado.
  Um worker futuro precisa estabelecer contexto de empresa antes de chamar o
  serviço. Nenhuma fila, migration ou mudança de contrato HTTP foi introduzida.

### 13.1 Prioridade de extração

1. âncoras semânticas;
2. tabelas/cabeçalhos;
3. proximidade geométrica;
4. regex contextual;
5. coordenadas absolutas apenas como último recurso.

### Sprint F4 — Copel Core comprovado

`CopelDANF3EParser` implementa `InvoiceParser` com identidade centralizada:
`copel` / `1.0.0`, layout `danf3e` / `DANF3EA4B-V1.06`. O suporte é limitado
à versão observada, não a todo PDF da Copel.

Reconhecimento exige conjuntamente nome do emissor, CNPJ público
`04.368.898/0001-06`, `DANF3E - DOCUMENTO AUXILIAR DA`, título
`NOTA FISCAL ELETRÔNICA DE ENERGIA ELÉTRICA` e marcador `DANF3EA4B (V1.06)`.
Mantido o contrato booleano F3; ausência de qualquer âncora não seleciona Copel.
Nome isolado ou versão desconhecida não reconhecem o layout.

Campos testados em `ParsedInvoice`:

- `identificacao_fiscal`: concessionaria, codigo_uc (15 dígitos neste layout),
  competencia (texto documental `MM/AAAA`), numero_nota_fiscal, serie e
  chave_acesso (44 dígitos, sem validação fiscal/checksum nesta sprint).
- `resumo`: data_emissao, data_vencimento (`date`), consumo_kwh e
  valor_total_concessionaria (`Decimal`, sem arredondamento).
- `leituras[0]`: data_leitura_anterior, data_leitura_atual,
  data_proxima_leitura (`date`). Não são os índices numéricos do medidor.
- `titular`: nome, cpf_cnpj (somente label CPF observado), logradouro, numero,
  bairro, cidade, uf e cep. Complemento não é decomposto nesta sprint.
  O CPF da amostra está mascarado: retorna `failed`/warning, nunca preenche os
  dígitos escondidos. Remoção de pontuação de CPF legível foi testada somente
  com valor fictício. CNPJ de titular não foi observado nem declarado suportado.

Estratégia: `FullTextExtractor` genérico reutiliza pypdf em modo layout,
preservando colunas em `RawExtraction.page_texts` (tupla opcional adicionada ao
fim do contrato F3); não há OCR, extração de imagens, tabelas ou dependência
nova. `MinimalExtractor` continua somente com a primeira página e sem conhecimento
da Copel. O parser lê os blocos core da primeira página. Na amostra real os
cabeçalhos de UC, resumo e leituras são gráficos e não saem na camada textual:
nesses casos usa a estrutura contextual observada (UC isolada de 15 dígitos,
linha mês/ano-vencimento-total, linha de três datas e nº de dias), não coordenadas
absolutas. Para consumo, usa a linha `CONSUMO kWh TP` do medidor, nunca o histórico
ou a quantidade dos itens. Nome/endereço são delimitados pelas labels do titular,
excluindo endereço/CNPJ da distribuidora e dados bancários.

Cada campo carrega source e status. Candidatos distintos produzem `ambiguous`,
valor inválido/mascarado produz `failed`, ausência de label/estrutura observável
produz `not_present`. Cabeçalho gráfico perdido não permite distinguir sozinho
label ausente de valor invisível; esta limitação exige revisão das issues.
Confiança `0.95` indica conversão exata de candidato único na estrutura suportada;
é heurística, não probabilidade estatisticamente calibrada. Demais estados têm
confiança desconhecida. Identificação fiscal/UC/competência/total/vencimento/consumo
indisponíveis geram critical; campos opcionais indisponíveis geram warning.

`default_registry()` registra Copel. `ParserRegistry()` explicitamente vazio
continua disponível para compatibilidade/testes. O ProcessingService usa a
factory do registry sem importar/conhecer Copel; integra fatura tenant-scoped,
PDF fornecido pelo chamador, hash, extração mínima, seleção e ParsedInvoice.
Mantida a opção F3 de resultado em memória: sem commit/transição persistida,
sem `dados_brutos_extraidos` ou `dados_normalizados`. `parsed` não significa
validada nem autoriza cobrança; o consumidor precisa examinar issues. A F4
não requer persistência para este fluxo interno. O upload não dispara parser
automaticamente e não foi criado endpoint.

Evidência: uma fatura real privada, duas páginas, com core na primeira e
continuação cadastral na segunda. Não foi movida nem versionada. A fixture
`tests/fixtures/invoices/copel/core_anon.pdf` reconstrói geometria/blocos com dados
fictícios; não copia imagens, QR/PIX, códigos bancários ou metadata privada.
Expected JSON e gerador reproduzível acompanham o arquivo. Variações controladas
cobrem ausência, ilegibilidade, candidatos conflitantes e deslocamento dos blocos.
Elas não são uma segunda amostra real: robustez multi-layout, outros medidores,
UC de outro tamanho, fatura empresarial e OCR não foram validados.

Sem GD-I/GD-II, saldos, histórico completo, itens/tributos/tarifas avançados,
normalizer, matching, cálculo, emissão ou alteração de banco. STOP F4.

### Sprint F5 — extração documental profunda comprovada

Parser `copel/1.1.0`, mesmo layout `DANF3EA4B-V1.06`. Reutiliza os mapas de
`ExtractedField` já definidos em `ParsedInvoice`: não cria modelos SQLAlchemy,
InvoiceLineItem paralelo ou schema financeiro. `RawExtraction` e o extrator
genérico permanecem como na F4; F5 usa o texto por página com colunas preservadas.

- `itens`: descricao_original, descricao_normalizada (alias documental opcional),
  unidade, quantidade, preco_unitario_com_tributos, valor, pis_cofins_valor,
  icms_valor e tarifa_unitaria. Source inclui página, linha textual e coluna;
  confiança/status/issues ficam em cada campo. Colunas vazias são not_present,
  nunca zero. Base/alíquota não são atribuídas artificialmente a cada item.
- Colunas de tarifa observadas: **Preço unit (R$) com tributos** e **Tarifa unit.
  (R$)**. Ambas são preservadas separadamente como Decimal, incluindo seis casas.
  Não se afirma TE/TUSD ou tarifa sem impostos além do label documental, nem se
  escolhe tarifa comercial. PIS/COFINS agregado na linha não é separado por fórmula.
- `tributos`: três linhas do quadro fiscal — ICMS, COFINS, PIS — com tributo,
  base_calculo, aliquota e valor. Alíquota mantém a magnitude percentual escrita
  (ex.: `19%` vira `Decimal('19')`), não uma fração calculada. O sinal `%` e o fim
  da linha distinguem dados tributários dos cabeçalhos homônimos dos itens.
- `historico_consumo`: 13 linhas na amostra, com competencia, consumo_kwh e
  dias_faturados. Competência conserva o label `SET26`/equivalente, sem inferir
  século nem preencher meses ausentes. Valores/dias usam Decimal; dia ausente
  fica not_present sem consumir o mês seguinte.
- `medidor`: numero, grandeza, unidade, posto, leitura_anterior, leitura_atual,
  constante e consumo_kwh. `CONSUMO kWh TP` é o padrão observado. Consumo reutiliza
  o mesmo ExtractedField do resumo F4; índices/constante não recalculam consumo.
- `avisos`: instrução **PARA CADASTRO DE DÉBITO AUTOMÁTICO**, grupo/modalidade
  tarifária, mensagem regulatória sobre cancelamento de valores não relacionados
  ao serviço e períodos de bandeira tarifária. Texto documental, sem efeito em
  UC ou política comercial. A instrução de cadastro não prova débito ativo.

Matcher reutilizável em `item_matcher.py`: exact, prefix, contains, regex e
priority; prioridade maior vence e targets empatados permanecem candidatos
distintos. O parser preserva descricao_original e representa ambiguidade no
alias. As únicas regras de produção são exact, para labels efetivamente vistos:

- `ENERGIA ELET CONSUMO` → `energia_elet_consumo`;
- `ENERGIA ELET USO SISTEMA` → `energia_elet_uso_sistema`;
- `ENERGIA CONS. B.AMARELA` → `energia_cons_b_amarela`;
- `CONT ILUMIN PUBLICA MUNICIPIO` → `cont_ilumin_publica_municipio`.

Esses aliases descrevem labels, não categorias financeiras. Nenhum dos quatro
itens reais ficou sem alias. Desconhecidos são preservados com issue
`COPEL_ITEM_UNMAPPED` info e alias not_present; não bloqueiam o parser. Regras
regex são configuração interna de código, não expressões recebidas do PDF.

Limites das colunas são derivados de uma linha completa com unidade/valores,
mantendo a posição relativa das células vazias, sem coordenadas fixas de página.
Tabela sem referência suficiente retorna warning de estrutura não identificada.
Suporte comprovado é de linhas simples nas oito colunas observadas; descrições
quebradas em múltiplas linhas, colunas reordenadas, outras unidades/layouts e
tributos diferentes continuam sem comprovação. Confiança continua heurística.

Energia consumida é preservada nas linhas e no medidor, sem somar quantidades.
Não foram observados labels de energia injetada/compensada, crédito, saldo,
GD-I ou GD-II na amostra real. `energia` permanece sem números inferidos; esses
conceitos não são agregados nem classificados. Testes adversariais com labels
desconhecidos de injeção/compensação/crédito comprovam somente preservação de
linhas separadas, não suporte de extração a uma fatura GD. F6 dependerá de amostra
real apropriada e não foi iniciada.

Fixture F4 reconstruída foi expandida com valores fictícios, expected JSON,
gerador e revisão visual. Continua existindo apenas uma amostra real privada;
variações sintéticas não comprovam segundo layout. Processamento permanece em
memória, sem atualizar ConsumerUnit, fatura, status, banco, cobrança ou ASAAS.

---

### Sprint F6 — classificação energética documental PARTIAL

Parser `copel/1.2.0`; layout mantido `DANF3EA4B-V1.06`. Descoberta sustentada
por **uma amostra real**, revisada novamente nas duas páginas, visualmente e
pela camada textual. Nenhum dado pessoal foi copiado. Não houve pesquisa externa
para preencher lacunas. O PDF anônimo F4/F5 não foi modificado; somente seu
expected JSON foi ampliado com classificações dos dados já existentes.

| Label/bloco observado | Contexto/evidência | Classificação permitida |
|---|---|---|
| ENERGIA ELET CONSUMO | Linha dos itens, unidade kWh e quantidade | consumed; quantidade da linha, não consumo total inferido |
| ENERGIA ELET USO SISTEMA | Outra linha dos itens, com sua própria quantidade/tarifa | other; preservada sem equivalência com GD/compensação |
| ENERGIA CONS. B.AMARELA | Linha distinta dos itens, com quantidade/tarifa | other; preservada sem soma |
| CONSUMO kWh / TP | Quadro do medidor, coluna Consumo kWh | consumo documental do medidor, campo F4 reutilizado |
| HISTÓRICO DE CONSUMO / kWh; CONSUMO FATURADO | Quadro mensal | Histórico F5, não crédito energético |
| Grupo de Tensao / Modalidade Tarifaria: B - CONVENCIONAL | Informações complementares | Texto tarifário; não distingue modalidade GD |
| Ficha de Compensação | Rodapé do boleto bancário | Não é energia compensada |
| DÉBITO AUTOMÁTICO / instrução de cadastro | Avisos e publicidade no verso | Não prova modalidade GD nem autoriza mudar UC |

Os três labels dos itens têm evidência direta na tabela e confiança heurística
0.95 para correspondência exata, não probabilidade calibrada. Não há labels
inequívocos de GD-I/GD-II, injeção, compensação energética, crédito/saldo,
expiração, origem/destino energético, SCEE ou beneficiários de energia.
O verso contém informações gerais/canais e publicidade, não um demonstrativo GD.

Contrato aditivo, em memória:

- `ParsedInvoice.energy_components`: tupla de mapas de ExtractedField, no mesmo
  padrão de itens/tributos. Cada mapa contém `original_label`, `category`,
  `amount_kwh`, `unit`, `item_index`. Índice referencia `itens` para acessar
  quantidade/valor/tarifas originais; source/confidence/warnings ficam nos campos.
  Não se duplica o item inteiro nem se atribui origem/beneficiário sem evidência.
- `energy_matcher` reutiliza ItemMatcher com três regras **exact**, prioridade
  100, para os labels da tabela acima. Versão das regras pertence à identidade
  do parser. Nenhuma regra de produção de GD/injeção/crédito foi criada.
- Item em kWh sem regra comprovada permanece individual: categoria
  `ambiguous`, value `unclassified`, issue `COPEL_ENERGY_UNCLASSIFIED` info.
  Empates do matcher preservam status ambiguous e issue, sem escolher candidato.
  Outros itens permanecem íntegros em `itens`, mesmo fora de energy_components.
- Unidade ausente/incompatível de label reconhecido: `amount_kwh=failed`,
  issue `COPEL_ENERGY_UNIT_UNSUPPORTED` warning, sem converter unidade; a
  quantidade original permanece no item. Quantidade ilegível/ausente mantém
  failed/not_present e issues F5. Decimal e precisão originais são preservados.
- `energia.consumo_kwh` reutiliza o ExtractedField do medidor/resumo; nunca é
  soma nem escolha comercial entre quantidades dos itens.
- `energia.gd1_kwh`, `gd2_kwh`, `energia_injetada_kwh`,
  `energia_compensada_kwh`, `saldo_creditos_kwh`: distintos, sem valor,
  `not_present` acompanhado de `COPEL_ENERGY_NOT_SUPPORTED` info. Significa
  **nenhum campo identificado no escopo comprovado**, não ausência de GD na
  instalação nem suporte a reconhecer todos os labels possíveis. Esses campos
  são estrutura reservada; o parser 1.2.0 não os preenche. GD não é assumido como
  sinônimo de injeção (os nomes conceituais futuros da seção 20 não são aliases).

Sem soma, reconstrução de saldo, normalizer, banco/SQLAlchemy, lookup de UC,
modalidade cadastrada, cálculo, ASAAS ou mudança do débito automático. Registry,
ProcessingService e RawExtraction permanecem intactos. Sem contrato HTTP novo.

**Faltam para concluir F6:** documentos reais com distinção explícita de GD-I
e GD-II, incluindo contexto/legenda, valores e unidades; casos documentais de
energia injetada versus compensada; demonstrativo de saldo anterior/utilizado/
acumulado/atual e expiração (competência/unidade); linhas múltiplas com origem
ou beneficiário quando existentes. Uma única nova amostra pode comprovar vários
casos, mas nenhum é declarado suportado antes da inspeção e regressão anônima.
Testes adversariais em memória comprovam somente recusa de inferência e
preservação, não constituem amostras reais GD. Robustez multi-layout segue não
validada. **PARTIAL; F7 não iniciada.**

#### Atualização documental C5.3A.1 — GD real por evento

Três faturas Copel reais privadas, mantidas fora do versionamento, ampliam a
evidência do mesmo layout DANF3EA4B-V1.06. Fixtures estruturadas sanitizadas
preservam somente labels, quantidades, componentes, classificação, mês e tarifas.

Agora estão comprovados documentalmente:

- `ENERGIA INJETADA` própria/local, separada de `ENERGIA INJ. OUC MPT`;
- OUC, MPT, TE/TUSD, GD-I, GD-II e meses de origem distintos;
- múltiplos eventos válidos na mesma fatura;
- bandeira de consumo e bandeira de injeção em linhas separadas;
- demonstrativo de saldo SCEE no documento, sem transformar o texto em cálculo;
- `tarifa_unitaria` distinta de `preco_unitario_com_tributos`.

O parser Copel 1.3.0 classifica esses itens e conserva `ExtractedField`, origem e
precisão. A representação textual observada `TUS` no componente GD-II é normalizada
para TUSD somente no parser e apenas nesse contexto documental comprovado. Números
negativos são quantidades documentais válidas; TE e TUSD com a mesma identidade
representam uma quantidade física única pelo valor absoluto.

Na cobrança compartilhada, somente eventos normalizados como `OUTRA_UC` e
`MESMO_POSTO` compõem `energia_compensada_cobravel_kwh`. A energia local permanece
em `InvoiceNormalized.energy_components` para auditoria, mas não é somada à OUC.
Eventos GD-I e GD-II, ou meses diferentes, permanecem separados. Duplicidade na
mesma identidade ou quantidades TE/TUSD divergentes continuam bloqueando o evento.
GD-III e OPT permanecem fora deste suporte.

F6 continua **PARTIAL**: a prova cobre os três documentos inspecionados, não todos
os layouts Copel, e a extração canônica completa de saldo/expiração ainda não foi
generalizada. Esta atualização não aplica regra comercial nem inicia C5.3B.

### Sprint F7 — contrato canônico, validação e primeira persistência

`InvoiceNormalizer` e `InvoiceNormalized` ficam em
`services/invoice_normalization_service.py`; `InvoiceValidator`,
`InvoiceValidationResult` e `UCMatchCandidate` em `invoice_validation_service.py`.
Ambas as camadas são independentes de Flask/SQLAlchemy e de regras financeiras.
`ParsedInvoice` continua sendo o contrato documental do parser, sem referências
internas. O parser Copel não mudou de versão/layout nesta sprint.

**InvoiceNormalized:** identidade do parser/layout; empresa_id/client_id do
contexto de upload; consumer_unit_id somente após matching; `campos` como mapa
canônico de ExtractedField; itens_documentais, tariffs_documented, tributos,
historico_consumo, medidor, energy_components, avisos, source_metadata,
status_normalizacao e issues. A cópia é independente dos mapas mutáveis do
ParsedInvoice. Nenhum campo é convertido para float.

Chaves de `campos`:

- Identificação/fiscal: concessionaria, codigo_uc_documental, uc_numero,
  numero_nota_fiscal, serie_nota_fiscal, chave_acesso, mes_referencia.
- Datas: data_emissao, data_leitura, data_leitura_anterior,
  data_proxima_leitura, data_vencimento.
- Energia: consumo_kwh, gd1_kwh, gd2_kwh, injecao_gdi_kwh, injecao_gdii_kwh,
  energia_injetada_kwh, energia_compensada_kwh, saldo_credito_kwh.
- Valores documentais: valor_total_concessionaria, saldo_credito_valor,
  multa, juros, tarifa_base, descontos_aplicados.
- Titular/endereço: nome, cpf_cnpj, logradouro, numero, complemento, bairro,
  cidade, uf, cep.

Equivalências comprovadas: codigo_uc → codigo_uc_documental, serie →
serie_nota_fiscal, competencia MM/AAAA → mes_referencia AAAA-MM,
data_leitura_atual → data_leitura, saldo_creditos_kwh → saldo_credito_kwh.
GD-I/GD-II não são convertidos em injeção: gd1_kwh/gd2_kwh preservam a semântica
F6; somente campos explicitamente denominados injecao_gd1_kwh/injecao_gd2_kwh
poderão alimentar os aliases de injeção, quando existir suporte documental.
Hoje todos permanecem null. Código UC não perde zeros, não é convertido para
inteiro nem presumido como número cadastral: uc_numero vem do matching.

Datas já extraídas permanecem date; texto ISO vira date, datetime vira sua
data. UF é padronizada em maiúsculas e validada; CPF/CNPJ e CEP legíveis ficam
em dígitos. Máscaras/formatos inválidos não são reparados por inferência.
Campo omitido pelo parser ganha not_present + FIELD_NOT_EXAMINED; ausência
examinada, failed, ambiguous e avisos de não suporte F6 são preservados.
Zero documentado continua Decimal zero, nunca substituto de ausência.
Múltiplos registros de leitura não escolhem o primeiro: campos canônicos ficam
ambiguous. Histórico mantém competência curta documental, lacunas e fontes,
sem inferir século. Componentes energéticos e referências de item não colapsam.

`tariffs_documented` preserva as duas colunas documentais por item com seu
item_index; não escolhe uma delas. tarifa_base, multa, juros e descontos só
podem vir de campos documentais explicitamente equivalentes, nunca de fórmula.
O parser atual não os fornece. Normalização não calcula totais/tributos/saldos.

**Política de validação:** o mínimo segue o Core F4 já marcado critical,
acrescido do emissor reconhecido pelo Registry: concessionaria, UC documental,
competência, número/série/chave fiscal, vencimento, consumo e valor total.
Todos exigem found e tipo/formato adequado. Consumo/total devem ser Decimal
finito não negativo (zero explícito é aceito); chave exige 44 dígitos, sem
introduzir checksum fiscal não validado pela F4. Competência exige AAAA-MM.
Emissão/leituras/titular/endereço são recomendados; itens/tarifas/tributos/
histórico/medidor complementar/GD e créditos são opcionais nesta validação
documental. Ausência opcional não invalida nem habilita cálculo futuro.

Issues críticas existentes ou campos obrigatórios inválidos causam revisão.
Warnings de CPF mascarado e suporte GD ausente não bloqueiam por si só.
status_normalizacao registra falhas/ambiguidades de campos canônicos; não
substitui status_validacao. Valida significa documento core + matching aceitos,
**não aprovação para cobrança**. O futuro contrato financeiro deverá exigir
os campos específicos de cada regra sem usar zeros silenciosos.

O validator recebe candidatos, não busca banco nem modifica entidades:

- Sem UC documental legível/contexto de matching: revisao_necessaria.
- Código legível e zero candidatas no tenant: uc_nao_encontrada.
- Mais de uma candidata (inclusive códigos iguais em duas UCs): revisão,
  sem desempate por `.first()`.
- Uma candidata de outro Client: uc_pertence_outro_cliente, sem associação.
- Uma candidata do Client original: match aceito; demais issues determinam
  valida ou revisao_necessaria. consumer_unit_id pode ser associado com match
  correto mesmo quando outro campo documental exigir revisão.
- Candidatos de outro tenant são rejeitados como contexto inválido. Resultado
  contém status/issues, consumer_unit_id/uc_numero quando match aceito; warnings
  e critical_errors são projeções das issues.

**ProcessingService:** `process(id, document=bytes, persist=True)` agora faz
pipeline completo. Resolve Fatura/Documento/Client na empresa autenticada,
verifica hash original e busca UC por igualdade exata em ConsumerUnit.codigo,
sempre com empresa_id. Não usa apelido, CPF, fuzzy matching, modalidade ou
débito automático. Não altera ConsumerUnit nem Client. `persist=False` mantém
diagnóstico completo em memória, inclusive em extração já persistida.

Hash continua identificando arquivo e deduplicação F2; chave identifica
documento fiscal. Outra fatura do mesmo tenant com chave igual/hash diferente
gera FISCAL_KEY_DIFFERENT_HASH e revisão, sem apagar/mesclar arquivos nem
modificar a extração anterior. Chave de outra empresa não gera conflito.

Uma transação grava identidade, snapshot integral do ParsedInvoice,
`dados_normalizados={invoice: InvoiceNormalized, validation: resultado}`,
campos estruturais de identificação/datas e vínculo UC permitido. Valores
Decimal são strings exatas nos JSON; date/datetime são ISO, enums são seus
valores, estruturas aninhadas são recursivas; float/tipos não suportados são
rejeitados. **Colunas Numeric F1 não são preenchidas pela F7:** suas escalas
18,2/18,6 não preservam necessariamente toda precisão documental. Snapshot
JSON é a fonte canônica; não arredondar silenciosamente para preencher colunas.
Nenhuma migration/schema físico novo.

Extração concluída grava extraida independentemente de valida/revisão/conflito
de UC. Layout desconhecido grava layout_nao_reconhecido/pendente; ambiguidade
de Registry grava erro/pendente. Falha técnica causa rollback integral e
resultado erro redigido, **mantendo os status anteriores no banco**, sem
snapshot parcial ou associação pendente. Não há processando persistido entre
etapas nem chamadas externas. O serviço é dono da transação; chamador deve
fornecer sessão dedicada/sem alterações pendentes (dirty/new/deleted rejeitados)
e não trazer alterações previamente flushadas de outra operação.

**Reprocessamento:** enquanto não houver histórico versionado, persistência é
recusada se houver snapshot, identidade de parser/layout, identificação/vínculo
extraído prévio ou status extraida/processando. Bloqueia também antes de existir
cobrança, portanto não sobrescreve silenciosamente uma extração usada por ela.
Falhas sem snapshot e layouts desconhecidos podem ser tentados novamente.
PostgreSQL serializa a checagem fiscal por lock de empresa e protege candidatas
UC por lock; atualização final usa compare-and-swap tenant/hash/updated_at e
ausência de snapshots. Perda de corrida causa rollback, não overwrite. Testes
locais SQLite comprovam CAS obsoleto/rollback; concorrência real PostgreSQL F7
não foi homologada nesta entrega.

F6 permanece PARTIAL, uma amostra real, sem novas regex/fixtures GD. F7 não
dispara upload/processamento automaticamente nem cria endpoint, fila, cálculo,
ASAAS, Pendências, Agenda ou frontend. STOP antes de C0/C1.

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

### STORAGE-1 — PDF original privado

`FaturaConcessionaria.document_id` continua obrigatório e aponta para o único
`Document` que guarda `storage_provider/storage_ref`. O hash SHA-256 permanece
somente em `FaturaConcessionaria.arquivo_hash`. Novos PDFs de fatura são gravados
em R2 privado (`s3`) em produção e localmente em desenvolvimento; o nome físico
é UUID sob prefixo da empresa e não contém dados cadastrais. Upload valida
tipo, 10 MiB, 10 páginas, integridade, UC/tenant e duplicidade antes de criar
o objeto. Falha de commit tenta remover apenas a chave nova desta tentativa.

Downloads tenant/admin autenticados verificam `faturas.read`, vínculo com o
Document da mesma empresa e hash antes de servir o PDF com nome amigável.
Referências `google_drive` e `local` antigas continuam legíveis, sem migração
ou exclusão do original. O provider genérico não conhece entidades de negócio.
`R2_READY` exige validação posterior de bucket privado/configuração/leitura real;
testes S3 simulados não comprovam essa operação externa.


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

### Sprint F1 — fundação persistente

`FaturaConcessionaria` foi criada em `faturas_concessionarias` como entidade
tenant-aware distinta de `Fatura`. `client_id` e `document_id` são obrigatórios;
`consumer_unit_id` permanece nulo até o matching futuro, pois o registro nasce
como `recebida` antes da extração. Não há endpoint ou edição genérica nesta fase.

O par `empresa_id + arquivo_hash` é único. `empresa_id + chave_acesso` possui
índice não exclusivo: mesma chave fiscal com hash diferente continua permitida
para revisão futura. Campos de energia usam `Numeric(18,6)`, o valor total usa
`Numeric(18,2)` e os dados brutos/normalizados seguem o `JSON` já usado pelo HUB.
O downgrade vazio é reversível; com registros, bloqueia a remoção da fonte.
`Fatura` ainda não referencia essa entidade — o vínculo opcional será adicionado
somente quando o fluxo financeiro realmente o consumir.

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

### Sprint C1 — persistência do perfil comercial

`GrupoRegraCobranca`/`grupos_regra_cobranca` é o perfil comercial reutilizável,
tenant-aware, sem vínculo com Empresa/Cliente/UC além do tenant proprietário.
Ele persiste os mesmos valores de `CalculationMethod`, `TariffSource`,
`DiscountType`, `TariffBasis`, `BillingMode` e `DueDateBasis` definidos na C0;
não existe segundo conjunto de enums. `energy_component_index` completa a
invariante C0 quando a base é `documented_component`.

Tarifas, desconto, juros e multa usam `Numeric(18,6)` e são serializados como
texto. Fonte manual exige tarifa; desde C4.1 a tarifa empresa pode coexistir com fonte de fatura. Desconto
`none` exige valor nulo; os demais exigem valor. NaN/infinito são rejeitados,
offset aceita ambos os sinais e nenhum limite comercial arbitrário foi criado.
Desde UI-C1, `tarifa_fixa_com_desconto` admite também `none`/null no grupo para
não repetir o desconto cadastrado na UC. Na execução operacional C5.5, o
percentual `ConsumerUnit.desconto` validado (0–100) substitui o desconto do
grupo nos métodos compatíveis; vazio significa sem desconto. Valor legado
inválido bloqueia a execução para revisão, sem estimativa. `tarifa_especifica`
continua sem desconto adicional. `tarifa_fixa_com_desconto` segue configurável,
mas não executável.
Percentuais legados do grupo são preservados e a migration não os reescreve.

Na UI-C1, a página `/regras-cobranca` lista perfis comerciais e usa o vínculo
ativo `company` como regra padrão efetiva. Se ele não existir, um usuário com
permissão de escrita pode seguir a criação guiada: escolher método e tarifa,
salvar o perfil e confirmar o vínculo padrão. Nenhuma tarifa ou desconto é
preenchido por suposição. UCs podem herdar a regra do cliente/empresa, escolher
uma regra direta ou criar uma específica em página completa; a volta usa apenas
o ID numérico da UC. Editar uma regra herdada não cria vínculo direto. Mudanças
atingem novas execuções, não snapshots anteriores. Perfis com método ou
modificadores não executáveis são sinalizados no editor.

Em `/faturas`, o botão "Enviar PDF" fica ao lado de "Emitir cobrança" e não pede
cliente. O upload `POST /billing-calculations/invoices/upload` extrai a UC do PDF
e vincula a fatura ao cliente da única UC com código documental igual a `codigo`
na empresa autenticada. Código ausente/ilegível, layout sem
parser, UC inexistente ou múltiplas UCs correspondentes impedem o armazenamento;
não há escolha arbitrária de cliente. O vínculo validado com a UC e os snapshots
continuam exclusivos do processamento F7; o upload não os antecipa. A rota
legada `POST /clients/<id>/invoices/upload` permanece compatível. Se o mesmo PDF
legado já estiver vinculado a outro cliente, o upload automático retorna conflito
sem alterar o registro imutável. A seção lista
os documentos por `GET /billing-calculations/invoices`, tenant-scoped. Para
administrador da plataforma, exige empresa explicitamente selecionada e usa
as rotas administrativas por empresa. PDFs e cobranças ASAAS permanecem
separados: enviar PDF não emite cobrança nem executa automaticamente o motor.

`revision` começa em 1 e incrementa somente quando a configuração financeira
relevante muda. Nome, descrição, ativação e marcação de padrão não reescrevem
essa revisão. Uma empresa pode não ter padrão. Quando existir, o banco permite
no máximo um grupo simultaneamente ativo e `padrao`, por índice único parcial
compatível com PostgreSQL e SQLite. Nenhum perfil é criado pela migration.

Desativação usa `ativo=false`; não há DELETE. O downgrade vazio é reversível e
é bloqueado se houver perfis persistidos. Nesta fase:

```text
GrupoRegraCobranca != RegraCobrancaAssignment
GrupoRegraCobranca != regra resolvida/executada
GrupoRegraCobranca != cálculo ou cobrança emitida
```

C1 não implementa assignment, precedência, RuleResolver, estratégia,
BillingPolicy, snapshot em Fatura, cálculo, emissão ASAAS ou frontend.
`padrao` é apenas uma indicação administrativa do perfil: não substitui um
assignment explícito de escopo Empresa e não participa da resolução futura.

---

## 27. RegraCobrancaAssignment

Separa a regra de quem usa a regra.

Escopos:

```text
company
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

### Sprint C2 — persistência do assignment explícito

`RegraCobrancaAssignment`/`regra_cobranca_assignments` associa um
`GrupoRegraCobranca` a exatamente um target da empresa: o próprio escopo
`company`, um `Client` ou uma `ConsumerUnit`. O tenant sempre vem do contexto;
grupo e target são consultados na mesma empresa. O assignment de UC não duplica
`client_id`: o futuro C3 poderá alcançar o cliente pelo relacionamento da UC.

O banco aplica `CHECK` para as três combinações válidas de target e índices
únicos parciais para permitir no máximo um assignment ativo por empresa, por
Client e por UC. Os índices possuem predicados PostgreSQL e SQLite. Troca de
regra desativa a linha anterior e insere a nova linha ativa na mesma transação;
não há hard delete nem reescrita do histórico inativo.

Novo assignment ativo não pode apontar para grupo inativo. Se um grupo já
associado for desativado depois, o assignment é preservado sem efeito automático;
C3 bloqueia a resolução com `inactive_rule_assigned`. A C2 não aplica precedência,
fallback ou `ResolvedBillingRule`.

```text
GrupoRegraCobranca
        ↓
RegraCobrancaAssignment
        ↓
[RuleResolver futuro]
```

`GrupoRegraCobranca.padrao` é metadado administrativo e não cria, substitui ou
sincroniza assignment `company`.

---

## 28. Resolvedor de regra — Sprint C3

Serviço interno `services/billing_rule_resolver.py`:
`RuleResolver().resolve(client_id=..., consumer_unit_id=None)` retorna o DTO C0
`ResolvedBillingRule` ou lança `RuleResolutionError`, com atributo `code` estável.
A empresa vem exclusivamente de `g.current_empresa_id`, estabelecido pela
autenticação ou pelo chamador interno autorizado. Não há endpoint novo.

A precedência é **consumer_unit > client > company**. O resolver consulta
targets exatos pelo `find_for_target` de C2, somente assignments ativos, e para
no primeiro encontrado. Sem UC informada, começa por Client. Um assignment
inativo é ignorado, sem reativação. O vencedor fornece uma regra completa;
nenhum campo é mesclado com regras inferiores. `padrao` ≠ fallback de resolução:
somente assignment explícito `company` pode fornecer o fallback da empresa.

Antes da busca, valida IDs positivos, contexto tenant e existência de Client/UC
na empresa. UC informada deve pertencer ao Client informado; IDs nunca são
corrigidos automaticamente. Grupo é buscado pelo lookup C1 com tenant explícito,
sem navegar por relacionamento que possa alcançar grupo de outra empresa.

| Código | Significado |
|---|---|
| `no_rule_configured` | Nenhum assignment ativo em qualquer nível; grupo padrão isolado não resolve. |
| `inactive_rule_assigned` | Primeiro assignment ativo aponta para grupo inativo; bloqueia sem fallback inferior. |
| `invalid_context` | Tenant/IDs inválidos, UC de outro Client ou sessão com alterações pendentes. |
| `assignment_inconsistent` | Múltiplos assignments ativos no target, grupo ausente/no tenant errado ou incompatível com DTO C0. |
| `target_not_found` | Client/UC inexistente ou pertencente a outro tenant, indistinguíveis ao chamador. |

Falhas técnicas do banco permanecem exceções técnicas, sem conversão em ausência
de regra. Esses bloqueios de domínio não são respostas HTTP nem códigos 500.

Mapping: id/nome/revision do grupo viram rule_id/rule_name/rule_version
(`revision` convertido em string conforme C0). source_scope usa BillingRuleScope;
source_id é o ID da UC, Client ou Empresa vencedora, nunca o assignment.
metadata contém `assignment_id` textual. Todos os parâmetros comerciais,
inclusive energy_component_index, são copiados integralmente do grupo; Decimal
e None permanecem intactos, sem valores inventados ou arredondamento.

Operação somente de leitura: sessão limpa obrigatória e autoflush desabilitado;
não há commit, rollback, mutações, snapshot de Fatura ou chamadas externas.
Os lookups C1/C2 aceitam `refresh=True` para renovar objetos já carregados;
chamadas existentes mantêm o comportamento padrão. No máximo três consultas
de assignment por target, sem carregar a coleção da empresa (até oito SELECTs
no caminho UC → Client → Company com validações e grupo).

A resolução reflete os dados visíveis na transação do chamador; não trava
configuração contra edições concorrentes nem persiste snapshot. Garantia de
atomicidade entre resolução, cálculo e emissão pertence à integração futura.
Nada de tarifa documental, estratégia, cálculo, BillingPolicy ou C4 nesta entrega.

---

## 29. Estratégias de cálculo

### Sprint C0 — contratos implementados, sem motor executável

Contratos em `backend/services/billing_calculation_contracts.py`, com dataclasses
e ABCs, sem SQLAlchemy, models, provider, persistência ou fórmulas. Dependem apenas
do contrato documental F7 e reutilizam `json_safe`; o parser não importa financeiro.

```text
InvoiceNormalized (fatos) + ResolvedBillingRule (configuração) + BillingCalculationContext
                                  ↓
                       BillingCalculationEngine (ABC)
                                  ↓
                       BillingCalculationResult
```

`BillingPolicy` decidirá estrutura/vencimento da cobrança; `PaymentProvider`
será responsável pela emissão externa. Nenhum dos dois foi implementado na C0.
O motor não recebe ConsumerUnit/Client/Fatura SQLAlchemy e não decide AUTO.

Enums C0:

| Contrato | Valores |
|---|---|
| BillingRuleScope | company, client, consumer_unit |
| CalculationMethod | energia_compensada, economia_gerada, valor_total_fatura, tarifa_fixa (legado), tarifa_fixa_com_desconto, tarifa_especifica, energia_recebida |
| TariffSource | invoice, manual |
| DiscountType | percentage, fixed, none |
| TariffBasis | consumed, compensated, gd1, gd2, documented_component |
| BillingMode | auto, unified, separate |
| DueDateBasis | invoice_due_date, invoice_issue_date, reading_date, calculation_date |
| BillingIssueSeverity | info, warning, critical |

`company` representa o escopo global **da empresa** das seções 27/28, nunca uma
regra compartilhada entre tenants. `source_id` é o ID da empresa/Cliente/UC desse
escopo, não o ID de assignment. Precedência UC > Cliente > Empresa é implementada
no serviço C3 da seção 28. `unified/separate` representam os conceitos
unificada/separada da seção 32. Não houve alteração de API/model legado.

As bases de vencimento seguem a seção 36: vencimento, emissão, leitura e data
de geração. `calculation_date` reserva a referência temporal desse último caso;
a futura BillingPolicy precisará fixar explicitamente qual instante de geração
usar, sem presumir que cálculo e emissão ocorreram no mesmo dia. Não se calcula
vencimento nem se adiciona reference_month, que não estava definido na seção 36.
Offset é inteiro com sinal (negativo/zero/positivo), sem ajuste de calendário.

`BillingCalculationContext`: empresa_id, client_id, consumer_unit_id,
fatura_concessionaria_id (inteiros positivos), competencia YYYY-MM e
calculation_timestamp opcional explícito. Não chama now(), não consulta cadastro
e não confirma ownership de IDs. O futuro chamador/resolver deverá estabelecer
contexto autorizado e coerente antes de executar estratégias.

`ResolvedBillingRule`: rule_id/name/version, source_scope/id, calculation_method,
tariff_source/manual_tariff, discount_type/value, tariff_basis,
energy_component_index opcional, billing_mode, due_date_basis/offset_days,
monthly_interest, fine_percentage e metadata textual. Não é model nem resultado
de uma resolução implementada. Política de faturamento é transportada para
snapshot, mas não deve ser interpretada pelas estratégias matemáticas.

Validações estruturais: enums fechados; IDs positivos; nome/versão não vazios;
Decimal finito sem coerção de string/int/float; fonte manual exige manual_tariff;
desconto percentage/fixed exige discount_value; offset exige inteiro (bool não
é inteiro aceito). Metadata exige strings. Não há defaults financeiros zero.
Precisão de seis ou mais casas é preservada, sem quantize/arredondamento.
Faixas comerciais de percentuais/valores, compatibilidade entre método/base e
interpretação de valores redundantes ainda exigem definição antes do cálculo.

`documented_component` exige índice inteiro não negativo explícito em
InvoiceNormalized.energy_components; outras bases não aceitam esse índice.
É somente referência configurada, não seleção executada: existência, unidade,
status/confiança e suporte deverão ser validados pelo motor futuro. Enumerar
GD-I/GD-II/compensação não torna esses dados disponíveis. A F6 permanece PARTIAL.
O campo legado ConsumerUnit.base_tarifaria (ex.: B1) é outra classificação, não
foi reinterpretado como TariffBasis. Desconto textual legado e fórmulas do
Rateio também não foram incorporados ao motor de cobrança.

`BillingRuleSnapshot(rule)` captura imediatamente toda a regra em JSON textual
imutável, com Decimal como string e enum como valor. Alterar metadata da regra
ou o dicionário devolvido por `snapshot.to_dict()` não altera essa captura.
Rule version é explícita; não há grupo/assignment/tabela de snapshots na C0.

`BillingCalculationResult`: context + rule_snapshot, calculation_version,
energy_base_kwh, consumo_kwh, gd1_kwh, gd2_kwh, energia_compensada_kwh,
tariff_value, gross_base, discount_amount, additions_amount, hub_amount,
issues e calculation_memory. Todos os números começam None, nunca zero;
nenhuma soma, desconto ou valor final é produzido pela C0. A serialização
`result.to_dict()` projeta rule_id/name/source_scope, tariff_source/basis e
fatura_concessionaria_id/competencia a partir do snapshot/contexto, evitando
identidades redundantes contraditórias. Inclui snapshot como objeto JSON e
warnings como projeção das issues. Versão única: CALCULATION_ENGINE_VERSION=1.0.
Este é o versionamento inicial do contrato, não alegação de motor funcional.

`calculation_memory` é um mapa auditável aninhado, validado como serializável e
copiado ao construir o resultado. Pode guardar método, referências, passos e
valores documentais/futuros resultados; C0 não gera esses passos. Serializer
reutilizado da F7 preserva Decimal textual exato, datas ISO, enums, null e DTOs
aninhados; rejeita float/tipos incompatíveis. Não há conversão Decimal → float.

`BillingCalculationIssue` é distinto de ExtractionIssue: código, severity,
mensagem e campo opcional. Resultado recusa issues de extração nesse slot;
estratégias futuras poderão traduzi-las explicitamente, sem acoplar parser ao
financeiro. Códigos operacionais ainda não são emitidos pela C0.

`BillingCalculationEngine.calculate(*, invoice, rule, context)` é abstrato,
tipado para InvoiceNormalized/ResolvedBillingRule/BillingCalculationContext e
retorno BillingCalculationResult. `BillingCalculationStrategy` herda esse
contrato e exige `method: CalculationMethod`. Não há estratégia concreta,
registry, fallback com valor fictício ou engine instanciável na C0.

**Decisões ainda abertas:** fórmulas dos quatro métodos (principalmente o que
constitui economia_gerada e tarifa_fixa); seleção inequívoca de tarifa documental;
limites/compatibilidades comerciais de desconto/juros/multa; requisitos de dados
por estratégia; arredondamento e calendário; referência temporal da geração.
Nomear métodos não define suas fórmulas. Nenhum deles executa cálculo agora.
Sem C1/CRUD/migrations/RuleResolver/BillingPolicy/Fatura/ASAAS/frontend. STOP C0.

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

## 38. Cobrança, persistida por `Fatura`

Os campos abaixo são conceituais da Cobrança e devem ser adicionados incrementalmente ao model `Fatura`; não criam uma segunda entidade persistida.

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

Implementado em B2: tokens cifrados por empresa/ambiente nos nomes abaixo,
reutilizando `ApiCredential`. Para preservar B1, o ambiente ativo ainda é o da
URL ASAAS da instalação; seleção explícita independente por empresa permanece
evolução futura. Não há fallback para `ASAAS_WEBHOOK_TOKEN` global. API keys
nomeadas têm prioridade e tokens nunca podem ser selecionados como API key.

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

Homologação B3 confirmou que a implementação B1/B2 ainda seleciona ambiente
pela URL global da instalação. API key e token continuam corretamente por
empresa, mas Sandbox e produção simultâneos por tenant permanecem dívida do
follow-up D2 de ambiente ASAAS por empresa; não refatorar esta seleção durante
B3.

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

Implementado em B2 no `asaas_webhook_service`: lookup Core privado e mínimo da
Fatura por referência B1 ou ID remoto não ambíguo, seguido de autenticação do
tenant proprietário. Contexto tenant só é estabelecido após token válido e é
restaurado ao sair. Identificadores conflitantes/não encontrados/ambíguos recebem
resposta genérica, sem revelar empresa. Nenhuma alteração à fronteira de emissão.

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

Implementado em B2: `PaymentWebhookEvent` / `payment_webhook_events`, com
`TenantMixin`, FK da Fatura e unicidade `(provider,event_id)` porque o ASAAS
documenta IDs únicos preservados nas reentregas. Inserção, atualização da Fatura
e `processed_at` têm commit único; a constraint e o tratamento de IntegrityError
serializam duplicatas concorrentes. Auditoria guarda hash, não payload completo.
Não confundir deduplicação com ordenação entre eventos diferentes. Detalhes,
estados aceitos e limites operacionais em `FATURAS.md`, seção B2.

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

### Sprint UI-F2 — acompanhamento unificado

A listagem usa `FaturaConcessionaria` como linha principal, com filtros e
paginação no backend antes de apresentar cliente, UC, todos os vínculos de
usina comprovados, competência, valor e vencimento documentais, processamento
e pendências abertas. A cobrança `Fatura`/ASAAS mantém seu próprio estado e
valor. Como ainda não há chave persistida entre os dois tipos de fatura,
cobranças da mesma UC e competência são mostradas apenas como contexto,
inclusive quando houver zero ou várias. Isso não comprova que uma cobrança
foi calculada a partir daquele PDF.

O upload continua a identificar UC e cliente no backend sem seleção manual.
O PDF original só terá ações de acesso quando o backend fornecer uma URL
autorizada; o identificador do documento e um arquivo temporário não são URLs
de acesso. O boleto ASAAS usa somente a URL retornada pela API de cobrança.
Pendências F6.1 abertas aparecem como aviso operacional, sem inferir erro de
qualquer fatura sem compensação.

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

Implementado como persistência explícita por target:

```text
GrupoRegraCobranca → RegraCobrancaAssignment → [RuleResolver futuro]
```

com constraints de escopo e unicidade ativa por `company`, Client e UC.

`RegraCobrancaAssignment` define onde um `GrupoRegraCobranca` se aplica. O
assignment de escopo Empresa continua explícito mesmo quando existir grupo
`padrao`; a C3 resolve exclusivamente assignments explícitos.

A C2 não implementa a precedência `consumer_unit > client > company`; ela
somente armazena e consulta targets exatos. Também não cria cálculo, snapshot,
BillingPolicy, Fatura ou integração ASAAS.

---

## Sprint C3 — RuleResolver

Implementado conforme seção 28: consumer_unit > client > company, somente
assignments explícitos; `padrao` é administrativo. Grupo inativo bloqueia,
ausência total produz `no_rule_configured`. DTO C0, leitura tenant-safe, sem
mistura de campos ou cálculo. STOP antes de C4.

---

## Sprint C4 — Fonte de tarifa

> Registro histórico C4. A responsabilidade manual descrita abaixo foi substituída
> pela separação documental/comercial da C4.1. O estado vigente está na próxima seção.

**PARTIAL — estrutura implementada; seleção comercial invoice depende de decisão.**

`services/tariff_selector.py` expõe
`TariffSelector.select(invoice: InvoiceNormalized, rule: ResolvedBillingRule)`.
É puro, sem banco, SQLAlchemy, PDF, parser, provider ou cálculo. O contrato C0,
o RuleResolver e os models não mudaram; não há endpoint ou migration.

`TariffSelectionResult` contém value (Decimal ou None), source, basis,
document_label/reference, confidence, issues e candidates. `warnings` é projeção
das issues de severidade warning. Issues reutilizam BillingCalculationIssue.
Cada candidato preserva status, Decimal, label original, caminho do item/campo,
nome do campo, source documental e confidence. Candidatos não são tarifas aprovadas;
no resultado invoice bloqueado, value/label/reference/confidence de seleção ficam
None, enquanto a evidência de cada candidato permanece disponível.

| Fonte/base | Comportamento C4 |
|---|---|
| `manual` | Usa exclusivamente manual_tariff, preservando Decimal e precisão; nenhuma tarifa documental é consultada. |
| `invoice` + `consumed` | Filtra componentes com category found=consumed, unidade kWh, quantidade legível e item_index válido. Não interpreta descrições nem soma componentes. |
| `invoice` + `documented_component` | energy_component_index referencia energy_components; seu item_index referencia itens_documentais. Valida referência/unidade/quantidade, sem usar posição como escolha comercial. |
| `invoice` + `compensated`, `gd1`, `gd2` | unsupported_tariff_basis: F6 ainda não comprovou essas categorias. Não substitui por consumo ou zero. |

Fonte manual só seleciona um parâmetro; não afirma que existe energia GD ou que
a fatura satisfaz os requisitos de uma estratégia futura. Confidence manual é
desconhecida (None), sem probabilidade inventada. Zero explícito é preservado;
ausência nunca vira zero. C0 já recusa manual_tariff ausente; a defesa do selector
também produz manual_tariff_missing ou invalid_manual_tariff para DTO adulterado.

Fonte invoice lê apenas tariffs_documented e suas referências normalizadas.
Nunca utiliza manual_tariff, tarifa_base sem contrato ou divisão valor/kWh.
Não arredonda nem aplica desconto. Categorias ambíguas geram ambiguous_tariff_basis;
referências inválidas, invalid_document_reference; base sem componente legível,
required_invoice_data_missing. Tarifa ausente gera document_tariff_missing;
campo ilegível gera unreadable_document_tariff; ambiguidade documental ou múltiplos
candidatos gera ambiguous_document_tariff. Não colapsa tarifas iguais nem escolhe
primeira/maior/menor. Warnings dos campos documentais são preservados como issues.

**Decisão comercial pendente:** os contratos atuais não determinam se usar
`tarifa_unitaria` ou `preco_unitario_com_tributos`. TariffBasis expressa base
energética, não representação tributária. O label Tarifa unit. (R$) tampouco
comprova sozinho "sem tributos", TE ou TUSD. C4 não declara nenhuma coluna como
tarifa correta do HUB e não adiciona configuração comercial silenciosa.
Toda seleção invoice permanece bloqueada com value=None; após análise de uma
base suportada, emite tariff_representation_required, inclusive se só uma coluna
estiver disponível. A disponibilidade não define a política de tributos.

Para concluir C4, definir explicitamente a representação documental comercial e
onde essa escolha deve ser configurada/versionada. Então implementar e testar o
caminho invoice bem-sucedido conforme essa decisão. O teste de sucesso invoice
e o aceite integral da sprint permanecem pendentes; testes de diagnóstico e
bloqueio não os substituem. Nenhuma extensão de C0/model/API foi antecipada.
F6 continua PARTIAL, sem novas amostras GD. **STOP antes de C5.**

---

## Sprint C4.1 — Modelo tarifário e opções de cobrança

> Registro histórico. C4.2 substitui a política de datas absolutas e formaliza
> bloqueios e estados por método; a seção C4.2 abaixo é o contrato vigente.

**PARTIAL para liberação de C5; arquitetura implementada, decisões de execução pendentes.**
Classificação tarifária ≠ tarifa concessionária ≠ tarifa empresa ≠ método de cálculo
≠ modificadores. Não há fórmula, engine concreto, snapshot em Fatura ou cobrança.

| Responsabilidade | Representação vigente |
|---|---|
| Classificação | InvoiceNormalized.campos: grupo_tarifario, subgrupo_tarifario, modalidade_tarifaria; ExtractedField textual com origem/status. |
| Referência concessionária | TariffSelectionResult.value / concessionaria_reference_tariff_kwh, exclusivamente documental, Decimal ou None com issues/candidatos. |
| Tarifa empresa | TariffConfiguration.company_tariff; coluna manual_tariff preservada; Numeric(18,6). |
| Tarifa horária comercial | TariffConfiguration.tariff_hfp / tariff_hp, Numeric(18,6) nullable. |
| Método principal | CalculationMethod, único método por regra, sem executar fórmula. |
| Modificadores | BillingModifiers e GracePeriod, distintos das condições de vencimento/juros/multa. |

Parser Copel 1.3.0 extrai grupo/modalidade da linha documental
`Grupo de Tensao / Modalidade Tarifaria: B - CONVENCIONAL` e subgrupo do contexto
`B1 Residencial / Residencial`, comprovados na fixture existente. Ausência permanece
null; não usa o default cadastral da UC. Nenhuma tabela A/B de preços ou inferência
de subgrupo é criada. Outros subgrupos exigem evidência de layout para extração.
Normalizer somente transporta classificação; não escolhe tarifa comercial.

### Matriz de configuração

| Configuração | Semântica e limite |
|---|---|
| energia_compensada | Método padrão legado; dados GD ainda limitados pela F6. |
| economia_gerada | Método legado, fórmula futura ainda precisa de definição. |
| valor_total_fatura | Desconto sobre total da concessionária, sem considerar compensação. Nenhum desconto aplicado agora. |
| tarifa_fixa | Legado preservado, sem transformar regras existentes em tarifa_fixa_com_desconto. |
| tarifa_fixa_com_desconto | Exige tarifa empresa; desconto percentual explícito legado ou none/null no grupo. Sem execução no C5. |
| tarifa_especifica | Exige tarifa empresa; não cria bloqueio nem interpretação jurídica. |
| energia_recebida | Método configurável; não exige tarifa nova por inferência. Definição quantitativa/fórmula pendentes. |
| exclude_pis_cofins | Excluir valores documentais quando a estratégia os utilizar; não subtrai nada agora. |
| icms_policy=exclude | **SEM ICMS**, conforme esclarecimento do usuário. null = não configurado. Não infere tarifa líquida nem fórmula tributária. |
| exclude_tariff_flag | Futura preferência por base sem bandeira quando comprovada; ausência requer warning/bloqueio a definir, nunca reconstrução silenciosa. |
| grace_period | enabled, without_discount, start/end explícitos ou ambos null; habilitado sem datas indica definição temporal pendente. |
| recurring_additional_cost | Valor fixo recorrente Decimal, separado de multa/juros/tarifa/desconto; não aplicado. |
| tariff_hfp / tariff_hp | Tarifas horárias da empresa. HP null preservado; possibilidade futura de usar HFP em HP foi documentada, não executada. |

Carência aceita intervalo explícito, início ≤ fim, somente quando habilitada;
nenhuma data é derivada de criação do grupo, contrato ou UC. Ainda é necessário
definir origem temporal automática e inclusão dos limites antes de cálculo.
Valores null não equivalem a zero/false. Nenhuma configuração é imposta a legados.

### Integração, auditoria e compatibilidade

C1 recebe objetos tariffConfiguration e billingModifiers, com PATCH parcial,
validação estrutural e alias manualTariff/companyTariff sem duplicação persistida.
API_CONTRACTS.md documenta chaves, tipos e requisitos. TariffSource invoice/manual
é preservado por compatibilidade; não estabelece uma escolha global entre tarifas
comercial e documental. A estratégia futura poderá usar energia × tarifa empresa
e registrar referência da concessionária separadamente para comparação.

C3 mantém consumer_unit > client > company, assignments explícitos, padrao ≠ fallback,
tenant e bloqueios inalterados. Transporta DTOs comerciais completos. Revision
inclui todos os parâmetros novos; descrições e PATCH idêntico não incrementam.
BillingRuleSnapshot inclui método, tarifas, modificadores, carência e revision como
rule_version, sem persistir snapshot em Fatura.

Migration `o9c4e8f1a3b5` adiciona dez campos nullable e CHECKs na tabela existente;
C1/C2 não são reescritas. Upgrade preserva valores, revisão e assignments antigos.
Downgrade só remove a extensão se nenhuma configuração C4.1 for perdida e os dados
couberem no contrato C1 anterior; caso contrário bloqueia antes de remover campos.

### TariffSelector revisado e decisões antes de C5

Selector não lê manual_tariff/TariffConfiguration; seu source é sempre invoice.
TariffBasis filtra os mesmos candidatos documentais de C4. Não acessa banco, PDF
ou SQLAlchemy. Não aplica ICMS, PIS/COFINS, bandeira, carência, descontos ou fórmulas.
TariffSelectionResult conserva ambas as colunas documentais, labels, referências,
Decimal e issues, mas **value continua None** sem critério comprovado para referência.
tariff_representation_required continua explícito; campo único também não autoriza
seleção. Não foi criado enum/configuração comercial tariff_representation.

Antes de C5: aprovar qual evidência/representação define a referência da
concessionária; definir fórmulas e energia elegível por método; definir origem e
limites da carência e o bloqueio/warning quando faltarem dados tributários/bandeira.
ICMS já está semanticamente resolvido como exclusão; disponibilidade documental e
como aplicar a exclusão continuam dependências da futura estratégia. F6 segue PARTIAL
sem amostras GD reais. Não interpretar aviso operacional como regra legal automática.
**Recomendação: manter C5 parada até as decisões necessárias à estratégia escolhida.**

---

## Sprint C4.2 — Contratos fechados e bloqueios explícitos para C5

### Decisão de produto confirmada — composição da referência Copel

Esta decisão substitui, **para a identidade Copel 1.3.0 / danf3e /
DANF3EA4B-V1.06**, o bloqueio de representação descrito nas entregas anteriores.
Referência concessionária = tarifa_unitaria da linha ENERGIA ELET CONSUMO +
tarifa_unitaria da linha ENERGIA ELET USO SISTEMA, ambas R$/kWh. Nunca somar
valor monetário das linhas nem preco_unitario_com_tributos. Não dividir valor/kWh.

TariffSelector possui mapa de composições por identidade documental comprovada,
fora do motor financeiro. Usa descricao_normalizada, unidade e item_index do
InvoiceNormalized, sem reparsear PDF/labels. Outra concessionária/layout exige
seu próprio contrato comprovado; não herda a composição Copel. A referência é
independente de TariffBasis comercial: não comprova GD nem energia elegível.

Os dois componentes obrigatórios são preservados em TariffSelectionResult.components
(Decimal, status, label original, referência de item/campo, origem e confiança).
CalculationMemory.concessionaria_reference_components transporta suas evidências.
A soma usa contexto Decimal dimensionado para precisão exata, sem arredondamento.
Ausente/failed/sem unidade kWh ou origem válida → concessionaire_tariff_components_missing;
ambiguous/duplicidade/referência ambígua → concessionaire_tariff_ambiguous.
Qualquer bloqueio impede a soma. Zero explícito é válido; ausência não vira zero.
Componentes válidos parciais permanecem auditáveis, mas não constituem referência.

Para identidades sem composição aprovada permanece tariff_reference_representation_required.
company_tariff segue parâmetro independente da empresa. Composição documental não
aplica desconto, ICMS, PIS/COFINS, bandeira, carência nem calcula cobrança. Não define
automaticamente base líquida/SEM ICMS. **C5 não iniciada.**

**PARTIAL global.** O núcleo de valor_total_fatura está READY_TO_IMPLEMENT;
isso não libera métodos ou modificadores cuja semântica/dados continuem pendentes.
Esta sprint não implementa fórmulas, strategy, engine, BillingPolicy ou emissão.

### Política de carência reutilizável e dados do target

`GracePeriod` contém somente enabled, without_discount e duration_months.
A unidade meses segue o vocabulário existente de `ConsumerUnit.carencia_meses`;
isso não define origem, limite inclusivo, mês civil versus ciclo de fatura ou
prorrata. Duração nullable: ausência continua configuração pendente. Não há
herança automática entre carencia_meses da UC e duration_months do grupo.

Fontes investigadas: ConsumerUnit.inicio_contrato/termino_contrato são datas
contratuais; created_at é cadastro; sem_usina_desde é ausência de vínculo com
usina; Plant.data_ativacao é ativação da usina, não da instalação beneficiária.
Nenhuma foi documentada como início operacional da carência dessa UC. Não criar
campo duplicado nem reutilizar uma data por conveniência. Produto deve confirmar
se inicio_contrato é a origem adequada ou definir dado operacional específico do
target. Até então, carência habilitada exige definição temporal e não é executável.
ConsumerUnit.percentual_desconto_carencia também não sobrepõe a política da regra.

Datas C4.1 grace_start/grace_end ficam fisicamente preservadas apenas como legado
de transição. Novas datas são rejeitadas pela API. O resolver bloqueia perfil com
datas antigas usando `grace_policy_migration_required`, sem cair para outro escopo.
Operador deve revisar, remover explicitamente ambas e configurar a política; não
há conversão de intervalo em duração, limpeza na migration ou atribuição a UCs.
DTO/snapshot ativo não inclui essas datas. Versões antigas da aplicação ainda
podem gravar no schema expandido, mas essas regras serão bloqueadas pela C4.2.

**Sem desconto durante carência:** regra conceitual confirmada é desconto
comercial efetivo = 0, mantendo os demais componentes do método. Porém a frase
"apenas com o valor da fatura da concessionária" também admite substituir a base
pela fatura inteira, comportamento diferente. A documentação anterior não resolve
essa divergência. **BLOCKED_BY_BUSINESS_DECISION para carência** até produto
confirmar que se mantém a strategy normal ou aprovar explicitamente a substituição.
Não codificar nenhum dos caminhos como fallback. Registrar desconto original,
efetivo e estado/origem da carência na memória futura.

### Ausência documental: sempre bloqueio, nunca zero reconstruído

| Requisito solicitado pela strategy/modificador | Código crítico |
|---|---|
| PIS/COFINS excluídos, tributos não identificados | required_tax_data_missing |
| Base sem bandeira solicitada, indisponível | base_tariff_without_flag_missing |
| SEM ICMS exige decomposição indisponível | required_icms_data_missing |
| Energia exigida não comprovada | required_energy_data_missing |
| Referência necessária para identidade sem composição aprovada | tariff_reference_representation_required |
| Componentes Copel obrigatórios ausentes/falhos | concessionaire_tariff_components_missing |
| Componentes Copel duplicados/ambíguos | concessionaire_tariff_ambiguous |

CalculationBlockCode formaliza os identificadores. `required_document_value`
valida apenas pré-condição Decimal/origem, devolvendo BillingCalculationIssue
critical para ausência; não calcula, não extrai nem decide compatibilidade.
Chamador só entrega valores found/documentalmente confiáveis; falha, ambiguidade,
unidade incompatível e campo não comprovado são ausência para esse contrato.
PIS e COFINS exigem comprovação individual, não basta encontrar um dos tributos.
Zero explicitamente documentado é aceito; None nunca vira zero. Não há divisão
valor/kWh, subtração tributária ou reconstrução de tarifa nesta camada.

### Matriz CalculationMethod × requisitos × compatibilidade

Os estados são de **prontidão para implementar**, não de cálculo executável hoje.
Todos os resultados financeiros continuam sem cálculo em C4.2.

| Método | Dados obrigatórios conhecidos | Tarifa/energia | Desconto | Modificadores compatíveis/pendentes | Estado |
|---|---|---|---|---|---|
| valor_total_fatura | InvoiceNormalized.campos.valor_total_concessionaria found, Decimal e origem | Não exige tarifa empresa, referência concessionária ou energia | Sobre o total; tipo/valor vêm da regra | Adicional após base/desconto definido. Carência e exclusões tributárias/bandeira ainda dependem de compatibilidade | READY_TO_IMPLEMENT para núcleo sem modificadores pendentes |
| tarifa_fixa_com_desconto | company_tariff; falta definir energia elegível/documento e como consumir desconto da UC neste método | E_elegível × tarifa empresa | Percentual legado do grupo ou none/null; este método ainda não executa | Adicional posterior definido; demais dependem da definição da base | BLOCKED_BY_BUSINESS_DECISION: energia elegível e desconto da UC neste método |
| tarifa_especifica | company_tariff; falta definir qual energia multiplica | Tarifa empresa; energia não definida | Nenhum desconto inferido pelo nome do método; interação com desconto configurado pendente | Adicional posterior definido; demais pendentes | BLOCKED_BY_BUSINESS_DECISION |
| energia_recebida | Campo documental confiável de energia recebida; ainda não comprovado em InvoiceNormalized/F6 | Não substituir por consumo, GD ou injeção; composição tarifária ainda pendente | Não definido | Compatibilidade depende da fórmula; adicional permanece separado | BLOCKED_BY_DOCUMENT_DATA; fórmula também BLOCKED_BY_BUSINESS_DECISION |
| energia_compensada | Energia compensada documental; seleção GD-I/GD-II ainda não definida | Não somar GDs, inferir energia ou escolher tarifa pelo nome | Não formalizado | Adicional separado; compatibilidade restante pendente | BLOCKED_BY_BUSINESS_DECISION e BLOCKED_BY_DOCUMENT_DATA (F6) |
| economia_gerada | Base/comparação para economia ainda não definidas | Necessidade de referência/tarifa depende da fórmula aprovada | Não formalizado | Pendente; não equiparar economia a desconto | BLOCKED_BY_BUSINESS_DECISION |
| tarifa_fixa (legado) | Sem fórmula formal suficiente | Não converter para tarifa_fixa_com_desconto/especifica | Não formalizado | Pendente | BLOCKED_BY_BUSINESS_DECISION |

Formulação **conceitual**, sem execução:

- valor_total_fatura: base = total documental da concessionária; subtotal = base
  menos desconto comercial sobre essa base. Se percentual: desconto = base × p/100;
  se fixo: desconto = valor monetário configurado; se none: sem desconto. Energia
  compensada não participa. Não inventar clamp, arredondamento ou limites comerciais.
- tarifa_fixa_com_desconto: subtotal = E_elegível × [tarifa_empresa × (1 − p/100)].
  A expressão não autoriza escolher E_elegível: produto ainda deve defini-la.
- tarifa_especifica: E_a_definir × tarifa_empresa é somente estrutura conceitual;
  não escolhe energia, desconto ou demais ajustes.
- Demais métodos: nenhum algoritmo financeiro formalmente autorizado. A revisão
  das seções 20/29/C0 encontrou nomes e dados, não fórmulas aprovadas.

CalculationMethod é fórmula principal. BillingModifiers não vira enum de método.
Configuração estrutural aceita em C1 não implica combinação pronta para execução.
Exclusões PIS/COFINS/ICMS/bandeira dependem de compatibilidade com a base aprovada
e de dados adequados; quando solicitadas e faltarem dados, os códigos acima são
bloqueios críticos, não warnings que autorizam seguir. Havendo dados, ainda não
se pode inventar fórmula/decomposição para aplicá-las. Sem ICMS é decisão fechada;
o algoritmo de exclusão e quais componentes atingir ainda exigem definição.

**Adicional recorrente:** componente fixo adicionado depois da base/desconto da
strategy. Não sofre desconto por inferência, não é tarifa, juros ou multa. Durante
carência, sua posição/componente permanece; nenhuma soma é executada aqui.

### HP/HFP e referência concessionária

HFP deve estar configurada para o modo horário. HP é opcional: null permite à
strategy futura usar a mesma tarifa HFP para HP, somente quando houver energia
HP/HFP documentalmente confiável. C4.2 não copia valor, escolhe modo horário ou
calcula. Sem dados por horário: required_energy_data_missing. O campo company_tariff
não é declarado fallback de HFP nem recebe automaticamente valor documental.

company_tariff/manual_tariff = tarifa comercial da empresa, aliases compatíveis.
Tarifa da concessionária é referência separada, não base comercial automática.
TariffSelector compõe a referência Copel conforme decisão acima. Para identidades
sem contrato aprovado retorna tariff_reference_representation_required, mesmo com
uma única coluna disponível. Estratégias que
não precisam dessa referência não devem chamar o selector como gate obrigatório
nem copiar esse bloqueio para seu resultado. Referência ausente pode permanecer
None na memória de uma cobrança baseada só na tarifa empresa.

### Contrato de auditoria futura

CalculationMemory tipada foi adicionada ao BillingCalculationResult; mapas legados
continuam aceitos. Nenhum campo monetário ganha zero/default calculado.

| Informação | Campo de auditoria |
|---|---|
| Método, revisão e parâmetros originais | rule_snapshot.calculation_method/rule_version/tariff_configuration/billing_modifiers |
| Energia usada | energy_base_kwh no resultado; calculation_memory.energy_source/energy_reference |
| Tarifa empresa efetivamente usada | calculation_memory.company_tariff_used |
| Referência concessionária | concessionaria_reference_tariff/concessionaria_reference_source |
| PIS/COFINS, ICMS, bandeira | *_treatment e *_amount na memória |
| Desconto configurado/original/efetivo | snapshot.discount_type/discount_value; memória.original_discount_amount; resultado.discount_amount |
| Carência avaliada | memória.grace_state/grace_start/grace_source; data exclusiva do target com origem auditável |
| Adicional recorrente | memória.recurring_additional_cost, separado de additions_amount agregado |
| Base e valor final | resultado.gross_base/hub_amount |

Tratamentos: not_evaluated/applied/excluded/not_applicable/blocked. Carência:
not_evaluated/active/inactive/not_applicable/blocked. Valores são dados fornecidos
pela execução futura, nunca calculados pelo DTO. Não persistir snapshot em Fatura.

### Migração e decisão final

Migration nova p0d5f9a2b4c6 acrescenta grace_duration_months nullable com CHECK de
duração positiva e habilitação. Não modifica migrations anteriores, datas legadas,
revisão existente ou registros UC. Downgrade bloqueia se houver duração configurada,
para não perder política comercial. Revision incrementa ao mudar duração ou limpar
datas via API. Nenhuma ação automática de migração de negócio é executada.

**Produto ainda decide:** energia elegível e fórmulas pendentes; origem/calendário
da carência e interpretação da frase operacional; compatibilidade e decomposição
de exclusões; composição da referência para outros layouts; limites e arredondamento
nas etapas próprias. **C5 não iniciada. PARTIAL global; núcleo valor_total_fatura
READY_TO_IMPLEMENT com os limites acima.**

---

## Sprint C4.3 — Compensação canônica e entrada energética

**PARTIAL global; regras físicas implementadas, F6 ainda sem comprovação GD real.**
BillingEngine nunca lê linhas Copel diretamente. Fluxo obrigatório:
ParsedInvoice → InvoiceNormalizer → compensações normalizadas →
energia_compensada_cobravel_kwh → BillingEngine futuro. Sem cálculo comercial.

### A) NORMALIZATION RULES — fixas, não configuráveis

`invoice_compensation.py` usa somente categorias/metadados estruturados de
ParsedInvoice.energy_components. Não lê regex, descrições, PDF ou regra comercial.
Parser declara compensation_supported=true somente com suporte comprovado;
default false produz UNSUPPORTED. Copel 1.3.0 continua false, sem regex GD nova.

| Campo estruturado (ExtractedField com source) | Semântica |
|---|---|
| category | compensated = abatimento físico na beneficiária; injected/consumed/other não entram |
| tariff_component | TE ou TUSD, já reconhecido documentalmente |
| amount_kwh / unit | Decimal original finito e unidade kWh confiável |
| item_index | Referência exata à linha original; não é chave de agrupamento |
| origin | MUC → MESMA_UC; OUC → OUTRA_UC; ausente → None |
| period | MPT → MESMO_POSTO; OPT → OUTRO_POSTO; ausente → None |
| gd_classification | GD_I/GD_II/GD_III/UNKNOWN; ausente → UNKNOWN, sem inferência |
| credit_month | YYYY-MM ou None; nunca substituído pela competência da fatura |
| compensation_context | Contexto documental comprovado que associa TE/TUSD do mesmo evento; obrigatório |

Chave: origem + posto + GD + mês de origem + contexto documental. Não usar
descrição nem quantidade como identidade. Contexto diferencia eventos com os
mesmos demais atributos e é compartilhado pelo par TE/TUSD. Sua extração exige
evidência de layout; não inventar um contexto constante para juntar todas as linhas.

CompensacaoNormalizada contém origem, posto, classificacao_gd, mes_origem,
contexto_documental, quantidade_kwh, componentes, source, confidence, status e
issues. Componentes são tupla auditável com tipo TE/TUSD, quantidade_original_kwh,
tarifa_r_kwh, valor_r, documento original (inclusive impostos) e energy_evidence.
A tupla preserva duplicidades inválidas para revisão, sem sobrescrever evidências.

TE=-1000 e TUSD=-1000 → um evento de 1000 kWh, preservando -1000 nos dois
componentes. Junho TE/TUSD=400 + julho TE/TUSD=600 → dois eventos, total 1000.
GD/origem/posto classificam; não multiplicam quantidade. Magnitude e soma usam
Decimal exato, sem arredondamento, divisão valor/tarifa ou reconstrução energética.
UNKNOWN pode acompanhar quantidade física comprovada; isso não autoriza uma
strategy que exija enquadramento GD específico. VALID energético não aprova método comercial.

### B) COMMERCIAL RULES — configuráveis em GrupoRegraCobranca

Método, tarifa empresa, HP/HFP, descontos, modificadores, carência e adicional
continuam em ResolvedBillingRule. Não participam da normalização de quantidade.
Nenhuma configuração comercial pode duplicar TE/TUSD ou usar saldo/planejamento
como compensação real. Referência tarifária Copel permanece a composição aprovada
em C4.2; TariffSelector não determina kWh. Não há engine/strategy concreta.

### C) SAFETY RULES — bloqueiam inferências perigosas

| Condição | Resultado |
|---|---|
| TE/TUSD divergentes | DIVERGENCIA_COMPONENTES_COMPENSACAO; AMBIGUOUS; quantidade None |
| Mesmo componente duplicado | COMPENSACAO_COMPONENTE_DUPLICADO; AMBIGUOUS, sem dedupe por texto/quantidade |
| Linha reutilizada | COMPENSACAO_REFERENCIA_DUPLICADA; total bloqueado |
| Identidade/categoria indefinida | AMBIGUOUS; não agrupar por conveniência |
| Par TE/TUSD incompleto | MISSING; não inferir a partir de componente isolado |
| Quantidade/unidade não confiável, inclusive kW | Não cria quantidade válida; bloqueia evento/total |
| Sem eventos com suporte declarado | MISSING, nunca zero |
| Parser sem suporte comprovado | UNSUPPORTED, nunca zero |

Par completo é proteção conservadora desta versão; evento composto por uma única
linha requer contrato/evidência próprios. Qualquer evento inválido bloqueia o
total inteiro: não liberar subtotal silencioso, mesmo havendo eventos válidos.
Compensações e evidências permanecem disponíveis para revisão.

Saldo, injeção da geradora, consumo registrado da rede, rateio esperado, custo de
disponibilidade, demanda kW e ajustes financeiros não alimentam o campo canônico.
Saldo 3500 + compensação 1000 → cobrável 1000. Planejado 2000 versus real 1650 →
cobrável 1650; não calculamos divergência de rateio. Imposto e tarifa não adicionam
kWh. Não há FIFO, expiração, projeções, rateio ou equivalência consumo total/rede.

### BillingEnergyInput e integração F7

InvoiceNormalized.billing_energy_input contém energia_compensada_cobravel_kwh,
compensacoes, status VALID/AMBIGUOUS/MISSING/UNSUPPORTED, issues, identidade do
parser, competência da fatura e fatura_concessionaria_id. ID vem da fatura já
validada pelo tenant na F7, nunca do PDF. Somente VALID fornece Decimal não
negativo e total conferido contra eventos válidos. require_valid() bloqueia outros
estados com required_energy_data_missing. InvoiceNormalized antigo sem esse campo
continua construível por compatibilidade, mas ausência não autoriza cálculo.

Normalizer marca revisao_necessaria quando há suporte declarado e dados inválidos.
O gate energético é independente da validação documental: F7 documentalmente
válida não significa compensação comercial VALID. F7 persiste a estrutura via
json_safe nos snapshots existentes, sem migration, sem preencher colunas comerciais
e sem reprocessar registros anteriores. Nenhum endpoint novo.

Testes unitários/normalizer sintéticos comprovam as regras físicas, não layouts GD.
A fixture Copel existente continua UNSUPPORTED para compensação. Pendências para
C5 global: amostras/extração GD reais, fórmulas/energia elegível e decisões C4.2
de carência e modificadores. **C5 não iniciada.**

---

## Sprint C5.1 — Energia compensada implementada

Esta decisão substitui o bloqueio comercial histórico da linha energia_compensada
na matriz C4.2. C5.1 termina em BillingCalculationResult; C5 global continua PARTIAL.
O suporte documental real F6 continua PARTIAL: o parser Copel atual não produz
entrada energética VALID. Testes sintéticos comprovam o cálculo, não extração GD.

`services/billing_calculation_engine.py` implementa o engine concreto e a única
CompensatedEnergyBillingStrategy, reutilizando as ABCs/DTOs C0. Assinatura mantida:
`calculate(*, invoice: InvoiceNormalized, rule: ResolvedBillingRule, context)`.
Invoice transporta BillingEnergyInput; não se duplica esse dado no contexto.
Engine seleciona método; strategy valida entrada/configuração e calcula.
Não há banco, Flask, consulta de regra, parser, PDF, provider ou persistência.

### Fórmula e precisão

```text
E = invoice.billing_energy_input.require_valid()
T = rule.tariff_configuration.company_tariff (= manual_tariff)
P = discount_value na escala 0..100, se percentage; 0 se none
gross_base = E × T
discount_amount = gross_base × (P / 100)
net_amount_before_rounding = gross_base - discount_amount
effective_company_tariff = T × (1 - P / 100)
hub_amount = net_amount_before_rounding em centavos, ROUND_HALF_UP
```

Somente hub_amount é arredondado. Bruto, desconto, energia e tarifas permanecem
exatos, inclusive na serialização Decimal textual; bruto/desconto podem ter mais
de duas casas. Não subtrair versões arredondadas para reproduzir o líquido.
Contexto Decimal local dimensionado pelos operandos, independente da precisão e
rounding globais. Não havia helper financeiro central: quantize de FaturaService
é validação legada com contexto implícito, não política reutilizável do motor.

Não se usa tarifa concessionária, total da fatura, saldo, consumo, injeção, demanda
ou rateio. TariffSource e TariffBasis legados permanecem no snapshot e não desviam
a energia canônica nem substituem company_tariff. Nenhuma seleção GD específica
é executada por esta strategy. Não há interpretação de componentes/labels Copel.

### Validações e escopo

- require_valid bloqueia AMBIGUOUS/MISSING/UNSUPPORTED; ausência nunca vira zero.
  Energia e tarifa devem ser Decimal finito não negativo. Zero explícito é válido.
- Desconto none exige valor null; percentage exige 0..100 inclusivos. Fixed retorna
  unsupported_discount_type. Faixa validada na execução, sem alterar regras antigas.
- HP/HFP configurados, exclusões tributárias/bandeira ativas, carência habilitada
  ou adicional configurado (inclusive zero) bloqueiam com unsupported_billing_configuration.
  Ausência/false não ativa modificadores; tratamentos permanecem not_evaluated.
- Outros métodos retornam unsupported_calculation_method, sem fallback.
- Falhas de domínio usam BillingCalculationError.code: invalid_context,
  required_energy_data_missing, invalid_energy_input, invalid_company_tariff,
  invalid_discount e os códigos unsupported acima. Nenhum resultado monetário é
  retornado nesses casos. Ausência de tarifa também é invalid_company_tariff.
- Contexto deve corresponder aos IDs da invoice, target de origem da regra,
  competência e ID da fonte energética. Isso verifica coerência de DTOs, não
  substitui autorização/tenant do chamador e RuleResolver C3.
- BillingMode, vencimento, juros e multa são apenas transportados no snapshot.
  Nenhuma política de cobrança é executada.

### Resultado e memória

Reutilizados energy_base_kwh/energia_compensada_kwh, tariff_value (empresa),
gross_base, discount_amount, hub_amount e calculation_version=1.0. Método/revision
permanecem no BillingRuleSnapshot imutável, independente da metadata original.
CalculationMemory registra energy_source/reference, company_tariff_used,
discount_percentage, effective_company_tariff, net_amount_before_rounding e
monetary_rounding. Contexto preserva IDs/competência; nenhum timestamp é gerado.
Demais componentes não avaliados permanecem null/not_evaluated, sem valores fictícios.
Resultado, memória e snapshot são determinísticos. Sem migration ou novo endpoint.

Somente energia_compensada está implementada. economia_gerada, valor_total_fatura,
tarifa_fixa, tarifa_fixa_com_desconto, tarifa_especifica e energia_recebida continuam
sem strategy concreta. Modificadores, BillingPolicy, Fatura e ASAAS ficam fora da
C5.1; nenhuma próxima sprint é iniciada automaticamente.

## Sprint C5 — Estratégias

### Sprint C5.2 — Tarifa fixa e tarifa específica

A decisão C5.2 define os métodos tarifa_fixa e tarifa_especifica e substitui
seus bloqueios comerciais históricos da matriz C4.2. C5 global continua PARTIAL.
O mesmo BillingCalculationEngine seleciona CompensatedEnergyBillingStrategy,
EstrategiaTarifaFixa ou EstrategiaTarifaEspecifica. Permanecem no mesmo módulo,
com validações/aritmética compartilhadas; não existe outro motor ou diretório.

**Parâmetro tarifário:** a estrutura existente possui um único parâmetro manual
por regra, TariffConfiguration.company_tariff, persistido em manual_tariff e
exposto como companyTariff/manualTariff. O método dá a semântica desse parâmetro:

| Método | Papel da tarifa manual configurada | Desconto |
|---|---|---|
| energia_compensada | Tarifa comercial C5.1 | Sem alteração: none ou percentual 0..100 |
| tarifa_fixa | Tarifa fixa em R$/kWh | none ou percentual 0..100 |
| tarifa_especifica | Tarifa específica em R$/kWh | Não participa, mesmo configurado |

Não foram criados campos/aliases tarifa_fixa e tarifa_especifica: não existem
três valores concorrentes na regra atual. Trata-se de reutilização explícita do
parâmetro do método, **não fallback** para outra tarifa. Tarifa concessionária,
cheia e de compensação não são consultadas. Parâmetro ausente bloqueia; zero
explícito permanece válido. Decimal negativo/não finito bloqueia. A específica
já exige tarifa no construtor C0; o motor também mantém defesa para DTO inválido.

```text
E = BillingEnergyInput.require_valid()
T = tarifa manual do método
tarifa_fixa: bruto=E×T; desconto=bruto×P/100; líquido_exato=bruto−desconto
tarifa_especifica: bruto=E×T; desconto=0; líquido_exato=bruto
líquido_final = ROUND_HALF_UP(líquido_exato, 2 casas)
```

Somente o líquido final arredonda; bruto, desconto e tarifa efetiva preservam
precisão integral. Fixa aceita percentuais 0..100; desconto fixed continua
unsupported_discount_type. Específica ignora desconto compartilhado de qualquer
tipo aceito estruturalmente pelo DTO, sem validar/aplicar faixa de percentual
que não participa da fórmula. O desconto configurado permanece no snapshot.

**Memória:** campos C5.1 preservados (tarifa usada, energia no resultado, bruto,
abatimento, tarifa efetiva, líquido antes/depois de rounding e fonte/competência).
Novo campo opcional `desconto_aplicado`: específica=false e
discount_percentage=null, sem percentual fictício; fixa=true quando configurado
percentage (inclusive 0%), false para none. Na C5.1 permanece null por
compatibilidade com sua memória anterior. Tarifa efetiva da específica é T.
Método/revision/configuração original ficam no snapshot independente/imutável.

AMBIGUOUS/MISSING/UNSUPPORTED e energia ausente/negativa bloqueiam ambos os
métodos, sem abs/zero substituto. Modificadores, HP/HFP e adicional configurados
continuam bloqueados. Não há PDF, linhas/componentes documentais, consulta ao
banco, seleção tarifária documental, cobrança unificada ou persistência.
tarifa_fixa_com_desconto permanece enum distinto e não implementado: não é alias
automático de tarifa_fixa. valor_total_fatura/economia_gerada/energia_recebida
também permanecem unsupported_calculation_method. Nenhuma migration.

Os cenários energéticos novos são sintéticos. F6 permanece PARTIAL; não houve
mudança no parser/normalizer, nem evidência adicional de extração GD real.
Nenhuma etapa C5.3/C5.4/BillingPolicy/Fatura/ASAAS foi iniciada.

Implementar estratégias formalmente aprovadas.

---

## Sprint C5.3A — Resolução tarifária documental

**DONE no contrato documental; C5.3 e C5 global permanecem PARTIAL.** A fronteira
implementada é exclusivamente:

```text
InvoiceNormalized
↓
DocumentTariffResolver
↓
ResolvedDocumentTariffs
```

`services/document_tariff_resolver.py` é puro e recebe apenas
`InvoiceNormalized`. Não acessa SQLAlchemy, Flask, tenant global, RuleResolver,
tarifa comercial, BillingCalculationEngine, Fatura ou provider. O resultado não
foi acoplado a `InvoiceNormalized` nem persistido; C5.3B decidirá como combinar
esta evidência com `ResolvedBillingRule`.

`ResolvedDocumentTariff` separa `kind` (`full` ou `compensation`), `value`
Decimal/null, `with_taxes`, `includes_flag`, índices dos itens de origem,
confiança mínima das fontes, status `VALID|AMBIGUOUS|MISSING|UNSUPPORTED`, issues
e evidências documentais. Cada evidência preserva status, valor, label, caminho,
campo, source, confidence e warnings do `ExtractedField`. Resultado não VALID
nunca fornece valor; ausência não vira zero nem fallback.

A C5.3A.1 adiciona `ResolvedCompensationTariffEvent` e
`ResolvedDocumentTariffs.compensation_tariff_events`. Cada evento reutiliza
`CompensacaoNormalizada` como identidade e acrescenta tarifas TE/TUSD, soma exata,
bandeira/tributação documentais, índices, confiança, status, issues e evidências.
Não existe `CompensationIdentity` paralelo.

### Tarifa cheia

Para Copel 1.3.0/danf3e/DANF3EA4B-V1.06, o resolver reutiliza a composição C4.2:
`tarifa_unitaria` de `energia_elet_consumo` + `energia_elet_uso_sistema`. A
classificação vem do matcher já executado pelo parser; o resolver não reinterpreta
texto. Soma somente R$/kWh, com `Decimal` exato e sem arredondamento. Total da
linha, quantidade e `preco_unitario_com_tributos` não alimentam o valor. Falta de
TE/TUSD equivalente, referência inválida ou duplicidade bloqueiam a tarifa.

### Tarifa de compensação

O resolver reutiliza os eventos e componentes TE/TUSD já normalizados em
`BillingEnergyInput`. Somente identidades `OUTRA_UC + MESMO_POSTO` são cobráveis;
`ENERGIA INJETADA` local permanece auditável e fora do total OUC. Cada identidade
com par TE/TUSD completo produz um evento independente, por isso GD-I, GD-II e
meses diferentes podem coexistir como `VALID`.

Um único evento pode alimentar o `compensation_tariff` escalar. Múltiplos eventos
só mantêm esse scalar quando TE, TUSD, bandeira e tributação são semanticamente
iguais. Se as tarifas diferirem, o scalar fica null e os eventos continuam VALID,
com `TARIFA_COMPENSACAO_ESCALAR_INAPLICAVEL`. Nunca há média, ponderação ou escolha
do primeiro/último/maior/menor. Duplicidade na mesma identidade, par incompleto ou
divergência de quantidade TE/TUSD permanece AMBIGUOUS/MISSING; GD-III permanece
UNSUPPORTED. Evento ausente não copia a tarifa cheia.

### Bandeira e tributos

Uma linha separada já classificada como bandeira permite `includes_flag=false`
para a tarifa correspondente; ausência de prova mantém null. Classificação de bandeira
ambígua mantém null com `BANDEIRA_AMBIGUA`. Quando todos os componentes escolhidos
possuem também a variante explícita `preco_unitario_com_tributos`, a
`tarifa_unitaria` selecionada é registrada como `with_taxes=false`; ausência da
variante mantém null, nunca false implícito. Nenhum ICMS, PIS/COFINS ou bandeira é
calculado, removido ou aplicado.

Tarifa documental ≠ tarifa comercial. Resolução documental ≠ seleção comercial.
`tarifa_base`, grupo/subgrupo/modalidade e parâmetros companyTariff/manualTariff/
tariff_hfp/tariff_hp nunca inventam valor. A seleção comercial é descrita na C5.3B
abaixo. PIS/COFINS, Fio B, carência, BillingPolicy, Fatura e ASAAS não foram
iniciados. Zero migration.

## Sprint C5.3B — Seleção comercial de tarifa por evento

**DONE na seleção; C5 global permanece PARTIAL.** A fronteira implementada é:

```text
ResolvedDocumentTariffs + ResolvedBillingRule
↓
CommercialTariffSelector
↓
SelectedCommercialTariff[]
```

`services/commercial_tariff_selector.py` é puro e produz uma seleção imutável
para cada `ResolvedCompensationTariffEvent`. Cada resultado preserva o evento,
a origem (`configured_fixed`, `configured_specific`, `document_full` ou
`document_compensation`), a tarifa selecionada, ambas as referências documentais,
`includes_flag`, `with_taxes`, status, issues e `BillingRuleSnapshot`. Não há
acesso a PDF, parser, SQLAlchemy, Flask, filesystem, provider ou persistência.

`tarifa_fixa` e `tarifa_especifica` usam somente
`TariffConfiguration.company_tariff`; a evidência documental permanece apenas
para auditoria. Para `energia_compensada` documental, `icms_policy=exclude`
seleciona a tarifa de compensação do próprio evento e `icms_policy=null`
seleciona a tarifa cheia resolvida. ICMS é apenas critério de escolha: nenhum
valor tributário é calculado ou deduzido. Esse ramo exige `tariff_source=invoice`;
uma regra manual C5.1 não é reinterpretada silenciosamente como documental.

A política de bandeira é tri-state. `exclude_tariff_flag=true` exige
`includes_flag=false`; false exige true; null não restringe. Evidência null
bloqueia quando a regra exige variante, inclusive para tarifa configurada cuja
composição de bandeira não está documentada. `with_taxes` é somente transportado
e nunca aciona dedução.

Múltiplos eventos geram múltiplas seleções e preservam quantidade, GD e mês de
origem. Não existe média, escolha do primeiro/último/maior/menor nem fallback
entre tarifa cheia e de compensação. Evento não VALID bloqueia sua seleção.
O `BillingCalculationEngine` C5.1/C5.2 permanece inalterado: cálculo monetário
por evento e agregação são etapas posteriores. PIS/COFINS, Fio B, carência,
economia, valor total, HP/HFP, BillingPolicy, Fatura e ASAAS continuam fora;
C5.4 não foi iniciada. Zero migration.

---

## Sprint C5.4 — Componentes documentais e Fio B (DONE em 2026-09-24)

A ordem comercial é tarifa selecionada → energia × tarifa → desconto →
PIS/COFINS → GD-II/Fio B → valor líquido. Toda operação usa Decimal; somente
o valor final recebe ROUND_HALF_UP em duas casas. Deduções superiores ao valor
pós-desconto limitam a cobrança a zero, com issue
`DEDUCOES_SUPERAM_VALOR_COBRAVEL`; não criam crédito financeiro.

`CommercialDeductionResolver` recebe a fatura normalizada, a regra resolvida e
evidências explícitas `DocumentDeductionEvidence`. Cada evidência identifica
PIS ou COFINS, evento `CompensacaoNormalizada`, fatura/competência,
valor monetário `ExtractedField` e origem documental. O resultado conserva
evidências, confiança, issues, status e totais separados. Esse contrato não
constitui prova documental: o produtor precisa demonstrar o vínculo real do
valor com a compensação. As fixtures positivas são somente testes sintéticos.

`exclude_pis_cofins=true` exige evidência de PIS e COFINS por evento cobrável.
`exclude_gdii_fio_b=true` exige resolução canônica de Fio B do evento GD-II.
False/null desativam a respectiva dedução, com zero legítimo. Ativação sem
evidência bloqueia o resultado monetário com MISSING/UNSUPPORTED; candidatos
concorrentes são AMBIGUOUS. Não existe fallback para zero, tarifa ou outro evento.

`exclude_gdii_fio_b` existe **somente em memória** em `BillingModifiers`,
`BillingRuleSnapshot` e auditoria. Não há coluna, configuração persistida,
alteração da API pública nem migration. Regras provenientes do banco continuam
com esse modificador null nesta etapa.

O engine aceita seleções comerciais por evento, valida contexto, cobertura e
snapshot, calcula os produtos e o desconto, resolve e aplica as deduções. A
memória conserva seleções/eventos, bruto, desconto, pós-desconto, PIS, COFINS,
Fio B, pós-PIS/COFINS, líquido antes do arredondamento e resolução documental.
Uma dedução específica de GD-II permanece vinculada ao próprio evento.
Os caminhos configurados C5.1/C5.2 continuam disponíveis sem exigir tarifa
documental para substituir a configuração comercial.

### Limites documentais confirmados

Na inspeção local, os três PDFs GD privados estão nomeados `ref2026-08.pdf`,
`ref2026-09.pdf` e `ref2026-09 (1).pdf`. O quadro tributário contém PIS/COFINS
agregados, sem vínculo comprovado com a parcela de compensação cobrável.
Não se deduz o total integral nem se rateia por consumo/compensação. Nenhuma
linha explícita de Fio B foi comprovada; os itens não classificados observados
são bônus Itaipu, multa, juros e acréscimo moratório. GD-II não implica valor
financeiro de Fio B, e a diferença de TUSD GD-I/GD-II não é dedução autorizada.
O parser Copel apenas passou a preservar classe/subclasse Residencial já presentes
na linha B1 observada; ele não infere Fio B documental.

### Complemento implementado em 2026-09-23

O quadro fiscal já chega integralmente de F5 ao `InvoiceNormalized.tributos`:
tributo, base_calculo, aliquota e valor. A memória `document_taxes` agora preserva
PIS/PASEP e COFINS com origem DOCUMENT, base/alíquota/valor e evidência original,
sem alíquota fixa, cálculo, rateio ou uso de outra fatura. Valor ausente permanece
null/MISSING_DATA, zero documental é distinto, duplicidades são AMBIGUOUS.
Base/alíquota ausentes permanecem null mesmo com valor documental válido.
Esses totais fiscais não são a dedução da compensação: o vínculo exigido no
contrato anterior permanece, com valores de dedução em campos separados.

`FioBResolver` isola regra versionada da Lei 14.300/2022 art. 27, resolução
tarifária local e cálculo exato por evento. Reutiliza a classificação C4.3:
GD I → NOT_APPLICABLE (art. 26); GD III → UNSUPPORTED; UNKNOWN → MISSING_DATA.
Para GD II, a competência da fatura determina 2023=.15, 2024=.30, 2025=.45,
2026=.60, 2027=.75, 2028=.90; 2029+ e anos anteriores retornam UNSUPPORTED.
Mês de origem do crédito e data do servidor não alteram o percentual.

A tarifa segue prioridade documental → regulatória versionada → MISSING_DATA.
O campo estruturado `tusd_fio_b_unit_tariff` precisa estar no item TUSD do evento
e ser idêntico à evidência no item original. Não é `tarifa_unitaria` (TUSD total).
Sem esse campo, `RegulatoryTariffRepository` carrega primeiro os registros tipados
`RegulatoryFioBTariff` publicados na base regulatória; o dataset local versionado
é somente fallback de compatibilidade fora do contexto da aplicação. Registros
fornecidos pelo chamador continuam aceitos para uso já validado. Eles exigem referência/versão,
distribuidora, vigência mensal, subgrupo, modalidade e,
quando aplicáveis, classe/subclasse/posto. Correspondência exata; múltiplos
candidatos ou documento ambíguo bloqueiam. Campo documental inválido ou sem
vínculo não substitui um registro regulatório válido e permanece auditável.

O registro real publicado usado na prova C5.4.4 é COPEL-DIS, componente `TUSD_FioB`, Tarifa de Aplicação,
B1 Convencional, classe/subclasse Residencial, detalhe SCEE, da ANEEL Componentes
Tarifárias 2026: Resolução Homologatória nº 3.592, de 23/06/2026, valor original
`214.53560037400001 R$/MWh`, vigência 24/06/2026–23/06/2027. A importação CKAN
`id=1` publicou 53 registros, sem duplicação, do recurso
`e8717aa8-2521-453f-bf16-fbb9a16eea39`, versão `2026-09-17T15:31:25.510600`.
O registro publicado preserva URL, id do recurso, referência, valor e unidade originais;
o repositório converte por `Decimal(1000)` para R$/kWh. Como a competência da
cobrança é mensal, somente 2026-07–2027-05 ficam integralmente cobertos. Meses
parciais retornam MISSING_DATA; nunca se escolhe a tarifa mais recente. A futura
atualização adicionará registros validados ao dataset ou importador controlado;
o cálculo permanece sem acesso de rede.
O parser atual não produz o novo campo sem comprovação de layout.

```text
Fio B = kWh canônico do evento GD II × TUSD Fio B (R$/kWh) × transição
1000 × 0.21453560037400001 × 0.60 = 128.721360224400006000
```

TE/TUSD continuam um único volume; eventos GD I não entram na soma Fio B.
Não há arredondamento intermediário. A memória `fio_b_components` registra
status/applicabilidade/GD/competência/kWh/tarifa/origem/taxa/valor/base regulatória
e evidência. Nenhum estado não resolvido usa zero como valor do componente.
O total financeiro de uma dedução desativada ou exclusivamente GD I é zero
aritmético, enquanto seus componentes mantêm null/NOT_APPLICABLE.
Somente o modificador explícito ativa dedução; false/null preservam o cálculo
anterior. O contrato parcial de valor monetário GDII_FIO_B isolado deixa de
autorizar dedução sem tarifa/transição; o tipo GDII_FIO_B foi removido de
DocumentDeductionEvidence. PIS/COFINS vinculados agora exigem origem DOCUMENT e
item fiscal com tributo/base/alíquota/valor e identidade estruturada do evento
(origem/posto/GD/contexto/mês) conferidos documentalmente. Um item com `valor`
isolado não autoriza dedução. A auditoria conserva esse quadro em `document_tax`.

O teste integrado usa competência 2026-09, 1000 kWh canônicos e a tarifa ANEEL
real: `1000 × 0.21453560037400001 × .60 = 128.721360224400006000` de Fio B.
Com tarifa comercial 0.90 R$/kWh e desconto de 20%, o engine chega a 591.28 após
o ROUND_HALF_UP, preservando toda a auditoria regulatória. A fixture de energia
permanece sintética; a tarifa, sua vigência e referência são oficiais/versionadas.

**C5.4 DONE:** há caminho local auditável DOCUMENT → REGULATORY → MISSING_DATA,
sem valor inventado ou fallback para zero. PIS/COFINS globais continuam apenas
auditáveis e só deduzem com o vínculo documental já estabelecido. GD III, 2029+,
importação automática ANEEL e configuração persistida Fio B não são implementados.
C5/F6 permanecem PARTIAL por seus demais itens. C5.5 não foi iniciada.

### C5.5 — orquestração e diagnóstico financeiro (PARTIAL)

O fluxo usa a fatura da concessionária já processada, regra resolvida, seleção
tarifária e o motor C5 existente para criar uma tentativa append-only e, quando
válida, um snapshot financeiro imutável. A ordem permanece valor base, desconto,
PIS/COFINS comprovados, Fio B, piso zero e ROUND_HALF_UP. A interface administrativa
mostra as etapas e a memória retornadas pelo backend, sem recalcular valores e sem
emitir ASAAS. Snapshots PostgreSQL bloqueiam UPDATE/DELETE por trigger; a prova
direta aguarda `TEST_POSTGRES_BILLING_URL` em banco isolado `test_*`.

#### C5.5-D — laboratório técnico isolado

O laboratório é exclusivamente de platform admin e processa PDF Copel em memória,
sem empresa fictícia, cadastro, fatura operacional ou snapshot financeiro. Exibe
extração, normalização, compensações e etapas técnicas; não presume regra, tarifa,
desconto ou cobrança. Arquivos não são persistidos e o timeout configura apenas a
espera HTTP; simulação financeira e histórico técnico persistido permanecem fora
do escopo.

O resultado distingue sucesso de extração, qualidade da normalização e
elegibilidade para cobrança GD. Sem par documental confiável de compensação, a
elegibilidade fica bloqueada e consumo não é convertido. A tabela de itens inicia
somente em uma linha com todas as colunas delimitadas; texto de segunda via ou
histórico não forma item financeiro. CPF mascarado é ausência informativa, sem
reconstrução, e campos opcionais de iluminação pública não produzem warning.

#### F6.1 — pendência de compensação GD não comprovada

No fluxo operacional, uma UC exatamente validada cria pendência `Operacional` de
origem `GD_COMPENSATION_UNVERIFIED` somente quando uma usina conectada está `Ativa`
e ativada até a competência da fatura, mas a energia compensada não é comprovada.
A pendência preserva fatura, competência, UC, cliente, blocker e usinas candidatas;
com uma única usina aplicável ela é vinculada a ela, com várias não há atribuição
artificial. A chave única por empresa/fatura/origem torna o evento idempotente e o
log interno é emitido somente na criação. Sem vínculo, ativação comprovada ou UC
validada não há pendência. O laboratório isolado não consulta nem grava pendências.

O modelo atual não possui início/fim por `PlantConnection`, tampouco notificação
interna por usuário; por isso a expectativa é deliberadamente conservadora e a
Pendência/listagem existente é o aviso interno disponível. Não há envio externo.

### C5.4.1 — atualização manual da base tarifária ANEEL

O administrador de plataforma abre Configurações → Banco de Dados → Base tarifária
ANEEL, segue o link para o portal oficial, baixa o CSV de Componentes Tarifárias,
envia o arquivo, revisa a prévia e confirma. O HUB não baixa, raspa ou consulta a
ANEEL durante a cobrança. A prévia valida UTF-8, schema oficial e exclusivamente
`TUSD_FioB` de Tarifa de Aplicação/SCEE; ela guarda hash, ator e expiração no banco
e não publica qualquer linha. A confirmação é única por prévia e transacional.

Cada linha publicada preserva distribuidora, dimensões, valor/unidade original,
R$/kWh normalizado em Decimal, vigência diária, referência, URL, versão e hash do
arquivo. Registros idênticos são mantidos; uma chave natural com conteúdo divergente
é conflito e nunca sobrescreve histórico. O repositório regulatório prefere a base
publicada; se ela estiver vazia, o comportamento anterior continua explícito.

**Publicação comprovada:** a primeira importação real foi confirmada em 2026-09-24
e seus 53 registros permanecem visíveis ao reabrir o status da base. O CSV continua
como alternativa administrativa, sem afetar a cobrança em runtime.

### C5.4.3 — sincronização manual pela API CKAN

Além do CSV alternativo, o administrador de plataforma pode criar a mesma prévia pela API CKAN oficial. O backend descobre o recurso anual ativo de Componentes Tarifárias pelos metadados do dataset e consulta somente COPEL-DIS/TUSD_FioB/Tarifa de Aplicação/SCEE/R$/MWh. A resposta é normalizada para o mesmo plano, inclusive a vírgula decimal oficial, preservando valor/unidade de origem e convertendo para R$/kWh somente no repositório. A consulta registra ator, recurso, versão/geração, filtros, totais e conflitos no resumo da prévia; confirmação continua explícita e transacional. Não há HTTP durante o cálculo Fio B nem publicação automática.

#### CSV ANEEL temporário de até 100 MiB

O limite exclusivo do CSV ANEEL é `REGULATORY_TARIFF_MAX_BYTES=104857600`
(100 MiB). PDFs de faturas mantêm seu limite próprio. O upload é copiado em
chunks para `REGULATORY_TARIFF_TEMP_DIR` (ou temporário privado do sistema),
com nome aleatório e SHA-256 incremental; o parser CSV lê o arquivo em streaming.
Após persistir o plano e o relatório necessários à confirmação, o CSV é removido
em `finally`, inclusive em falha. `flask purge-regulatory-tariff-previews` remove
previews expiradas e temporários órfãos antigos de forma idempotente. O CSV nunca
é gravado no PostgreSQL, logs ou Git.

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
