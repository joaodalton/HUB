# Redesenho de Faturas e Financeiro — design

Data: 2026-11-09. Mockup aprovado: `.superpowers/brainstorm/28169-1794260788/content/telas-v1.html`.

## Por quê

O fluxo fatura → boleto → pagamento já existe no backend, mas quem opera não
consegue usá-lo com conforto. Queixas do usuário, nas palavras dele:

- falta botão de gerar boleto e de deletar fatura;
- nenhuma ação avisa que terminou;
- quando dá erro, nada diz o que errou ou o que faltou;
- a organização das telas e das informações não agrada.

Além disso, não há prova de que o extrator lê e separa corretamente injeção
GD I e GD II em um PDF completo.

## Objetivo

Uma pessoa importa PDFs da Copel de qualquer tela, vê cada um extraído e
vinculado ao cliente (ou o motivo exato de não ter sido), abre o Financeiro,
clica em "Gerar boleto" e recebe na hora o download e o link de pagamento.
Quando o cliente paga, a fatura aparece como "Pago" e surge a pendência de
pagar a concessionária.

## Fora de escopo

- Novo parser, nova concessionária, mudança no motor de cálculo.
- Mudança no webhook ASAAS além do que for preciso para exibir o resultado.
- Envio do boleto ao cliente (e-mail/WhatsApp).
- Sino/central de notificações persistente. Notificação = toast.
- O dashboard atual de recebido/pendente e repasse por usina: sai da tela
  Financeiro (ver "Decisões minhas").

## Anti-objetivos

- Erro genérico ("Falha ao processar"). Todo erro nomeia o campo ou a causa.
- Ação sem retorno visível.
- Cliente de outra empresa aparecendo em qualquer lista (isolamento por
  `empresa_id` é obrigatório; passa por `hub-security-reviewer`).
- Arquitetura paralela: reutilizar os endpoints e serviços existentes.

## O que já existe (reutilizar)

- Upload com extração e vínculo automáticos: `POST /api/v1/billing-calculations/invoices/upload`
  (`fatura_concessionaria_upload_service.upload_invoice`, chama `FaturaProcessingService.process`).
- Lista paginada de PDFs importados com filtros: `GET .../invoices` (`_invoices`).
- Download do PDF: `GET .../invoices/<id>/download`.
- Cálculo: `POST .../invoices/<id>/execute`.
- Gerar boleto: `POST .../invoices/<id>/gerar-boleto` (`gerar_boleto_concessionaria` → `emitir` → ASAAS).
  Erros já tipados: `INVOICE_DATA_INCOMPLETE` (com `details.missing`), `BILLING_CALCULATION_REQUIRED`, `EMISSAO_PENDENTE`.
- Deletar: `DELETE .../invoices/<id>`, recusa com `INVOICE_HAS_CALCULATION`.
- Webhook ASAAS: marca `asaas_status='received'` e cria pendência `pagar_concessionaria`.
- Parser Copel 1.3.0 com GD-I/GD-II; gerador de fixture `backend/tests/fixtures/invoices/copel/build_fixture.py`.
- Modo de cobrança `auto/unificada/separada` em `GrupoRegraCobranca` (§32 de `FATURAS_E_COBRANCAS.md`).
- Frontend: `FaturasPage.ts`, `FinanceiroPage.ts`, `ConcessionariaInvoicesPanel.ts` (botão de upload), `Toast.ts`, `Header.ts`, `BillingRulesPage.ts`.

## Decidido pelo usuário

### Tela Faturas (`/faturas`)

Só PDFs importados. Botão "Importar faturas (PDF)" e uma tabela, uma linha por PDF:

| Coluna | Conteúdo |
|---|---|
| Competência | MM/AAAA |
| Cliente / UC | nome + código da UC; "Sem vínculo" + UC lida no PDF quando não vinculou |
| Usina | usina(s) da UC |
| Extração | Extraída / Erro; no erro, o motivo escrito na linha |
| GD I, GD II | kWh injetados de cada tipo, "—" quando não há |
| Valor Copel | valor total da concessionária |
| Boleto | Sem boleto / Aguardando pagamento / Pago |
| Ações | PDF; Boleto e Link quando há boleto; Deletar quando não há; Reprocessar quando houve erro |

Filtros: busca, status, usina.

### Tela Financeiro (`/financeiro`)

Só clientes com fatura vinculada e **sem boleto gerado**, agrupados por usina.
Cabeçalho do grupo: nome da usina e quantos aguardam boleto. Linha: cliente/UC,
competência, valor Copel, valor a cobrar, tipo (Unificada/Separada), botão
"Gerar boleto" e, ao lado dele, um botão pequeno que leva à configuração da
regra de cobrança.

Quando o valor não pôde ser calculado, a linha mostra o motivo no lugar do valor
(ex.: "cliente sem regra de cobrança") e "Gerar boleto" fica desabilitado.

### Gerar boleto

Um clique chama o ASAAS. Em sucesso: toast e um painel com "Baixar boleto",
"Copiar link de pagamento" e, **somente na cobrança unificada**, "Fatura Copel
(PDF)". Na separada a fatura da concessionária **não** é oferecida junto do
boleto. Isto substitui a §35 de `FATURAS_E_COBRANCAS.md` (atualizar a doc).

Depois de gerado, o cliente some do Financeiro; boleto e link ficam na linha
dele em Faturas.

### Pagamento

Webhook ASAAS confirma → linha em Faturas mostra "Pago" → pendência "Pagar
concessionária" criada para aquele cliente (já implementado; garantir que a tela
reflete).

### Importar de qualquer tela

Botão de importar fatura disponível em todas as telas autenticadas.

### Feedback

Toda ação (importar, reprocessar, deletar, gerar boleto) termina com toast de
sucesso ou erro. Erro diz o que falhou e o que faltou. Importação em lote
resume: quantas vincularam, quantas falharam; o motivo fica em cada linha.

### Faturas de teste GD

Estender `build_fixture.py` (editar o existente) para gerar três PDFs fictícios
no layout Copel DANF3EA4B-V1.06: (1) só injeção GD I, (2) só GD II, (3) GD I e
GD II juntas. Cada um com `expected.json` e teste que verifica extração e a
separação/organização dos componentes (GD I e GD II nunca somados nem trocados).
Os PDFs devem servir também para upload manual na tela.

## Decisões minhas (não ditas pelo usuário — conferir)

1. **Deletar** é permitido enquanto não existir boleto (`Fatura`) não cancelado para a fatura. Hoje `delete_invoice` recusa quando há qualquer cálculo (`INVOICE_HAS_CALCULATION`); passa a recusar só quando há boleto, e a exclusão remove junto execuções/snapshots de cálculo e pendências abertas daquela fatura. Deletar pede confirmação.
2. **Reprocessar** roda de novo o parser sobre o PDF já armazenado (sem novo upload, mesmo registro e mesmo `document_id`). Permitido somente sem boleto e quando `status_extracao` ∈ {`erro`, `layout_nao_reconhecido`} ou `status_validacao` ∈ {`uc_nao_encontrada`, `uc_pertence_outro_cliente`, `revisao_necessaria`}. Caso de uso principal: cadastrar a UC que faltava e reprocessar. Sucesso fecha as pendências de erro de processamento abertas daquela fatura.
3. **Cálculo automático**: no upload/reprocessamento, logo após vínculo válido, o cálculo roda de forma síncrona; falha de cálculo não desfaz o upload. "Gerar boleto" **recalcula antes de emitir**, usando a regra atual, e emite com esse valor; vencimento vem da fatura. Sem digitação. Faturas antigas já vinculadas e sem cálculo aparecem no Financeiro com "Não calculado" e um botão "Calcular" (endpoint `execute` existente); sem backfill.
3a. **Motivos na linha do Financeiro**: fatura vinculada e válida entra na lista mesmo quando não dá para emitir; a linha fica desabilitada e mostra o motivo (sem regra de cobrança, vencimento ausente, valor ausente, cálculo bloqueado + causa). Fatura sem vínculo ou com erro de extração não entra no Financeiro, só em Faturas.
3b. **Boleto cancelado/estornado** não conta como boleto: a fatura volta ao Financeiro e pode ser deletada.
3c. **Financeiro sem paginação**: lista todas as pendentes de boleto, agrupadas por usina.
3d. **Modo gravado na emissão**: o modo resolvido (unificada/separada) é gravado na `Fatura` no momento da emissão (coluna aditiva, migration reversível, se ainda não houver onde ler). O painel e a linha em Faturas usam esse valor gravado, nunca a regra atual. Boletos antigos sem modo gravado: não oferecer a fatura Copel junto.
3e. **Permissões**: as já usadas pelo backend — listas com `billing_calculations.read`/`faturas.read`; importar, reprocessar, deletar, calcular e gerar boleto com `faturas.create`/`billing_calculations.execute`. Nenhuma permissão nova.
4. **Botão global de importar** fica no `Header`, visível a quem tem permissão de emitir (`owner`, `admin`, `financial`). Aceita vários PDFs; não pede cliente — o vínculo é sempre automático pela UC lida no PDF. Fora da tela Faturas, o toast de conclusão traz um atalho "Ver em Faturas"; na tela Faturas, a lista recarrega.
5. **Botão de regra** abre a regra de cobrança do cliente/UC daquela linha, reutilizando a tela/seção existente.
6. **Dashboard antigo** do Financeiro (recebido/pendente por cliente, repasse por usina, listas de pendências) é removido da tela; o endpoint `GET /financeiro/dashboard` permanece. Pendências continuam na página Pendências.
7. **UC em mais de uma usina** aparece em cada grupo de usina a que pertence; UC sem usina vai num grupo "Sem usina".
8. **Mensagens de erro** são traduzidas no frontend a partir dos códigos/issues que o backend já devolve; onde o backend só devolve texto genérico, passar a devolver código + campos faltantes.
9. **"Pago" aparece ao recarregar a lista**; sem atualização em tempo real.
10. Fixtures GD usam dados fictícios e o mesmo método de reconstrução do `core_anon.pdf`.

## Ajustes descobertos ao planejar (conferir)

11. **PDF de UC não cadastrada não é salvo.** O modelo exige cliente em toda fatura; em vez de linha "Sem vínculo" na tabela (como no mockup), a importação mostra um resultado por arquivo com o motivo ("UC X não está cadastrada... Cadastre a UC e importe de novo"). Linhas com erro em Faturas ficam para falhas pós-vínculo (campos não lidos etc.).
12. **Modo `auto` precisa de um campo novo.** `ConsumerUnit.debito_automatico` não existe; é criado (padrão: não) com checkbox no cadastro da UC. `auto` + débito automático → separada; senão unificada.
13. **Valor do boleto unificado** = valor HUB + valor da fatura Copel; separado = só valor HUB. Hoje a emissão cobra só o valor HUB em qualquer modo.
14. **Pendência "Pagar concessionária"** só nasce para boleto unificado (ou antigo, sem modo gravado). No separado o cliente paga a Copel direto.
15. **Download e link** são guardados separados (`boleto_url` = PDF do boleto, `invoice_url` = página de pagamento ASAAS).
16. **Cobrança manual** (modal "nova cobrança" da tela Faturas, sem PDF) sai da interface; o endpoint permanece.
17. **Emissão interrompida** (ASAAS não respondeu): a linha continua no Financeiro com "Retomar emissão", que reusa o valor original — nunca gera segundo boleto.

## Restrições

- Flask + SQLAlchemy; frontend TypeScript vanilla + Vite, sem framework; arquivos < 500 linhas.
- Toda consulta filtra por empresa autenticada; testes de tenancy com duas empresas.
- Mudança de contrato atualiza `Documentos/md/architecture/API_CONTRACTS.md`; entrega registrada em `PROGRESS.md`.
- Mudanças financeiras incluem testes de cálculo e de erro.
- Sem dependência nova. Sem migration destrutiva.
- Chamadas reais ao ASAAS só no ambiente configurado da empresa; testes usam cliente simulado.
- Validação final: suíte backend, `npm run build`, `npm test`, `npm run lint`.

## Deixado ao construtor

- Se a lista do Financeiro é endpoint novo ou filtro/formato novo sobre `GET .../invoices` (`statusCobranca=sem_cobranca`).
- De onde ler GD I/GD II por fatura para a tabela (colunas `injecao_gd1_kwh/gd2_kwh` ou `dados_normalizados`).
- Onde o modo unificada/separada resolvido é lido para a linha e para o painel pós-boleto.
- Divisão em arquivos/componentes, textos i18n, estilos seguindo o visual atual do HUB.
- Ordem das entregas.
