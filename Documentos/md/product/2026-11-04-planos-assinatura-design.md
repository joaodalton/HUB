# Planos de assinatura do HUB + checkout público + self-signup pós-pagamento

## Intenção e porquê

O HUB cobra hoje a empresa-tenant pela própria assinatura manualmente
(`backend/scripts/criar_empresa.py`, convite enviado à mão). A rota
pública `/empresas/registro` está desativada de propósito
(`backend/routes/empresa_routes.py`) com o comentário explícito de que o
modelo futuro seria "link de convite enviado por e-mail após a compra,
criando empresa + owner juntos". Esta decisão formaliza esse modelo:
landing pública → checkout → pagamento confirmado (Asaas) → e-mail com
link → cliente cria a própria empresa.

Isso também fecha a pendência V1.5-B do `VISAO.md` ("decidir com o João
se abre self-signup conectado a cobrança/plano") e substitui o desenho
de trial da seção 6.5 (hoje "Starter com volume reduzido") por um plano
teste dedicado e secreto.

## Goals

- Catálogo com 3 planos principais comprováveis (Starter, Avançado,
  Enterprise) + 1 plano teste oculto (não aparece em nenhuma lista
  pública, não pode ser comprado).
- Cada plano tem franquia própria de usina/UC/usuário e, a partir do
  Avançado, libera funcionalidade extra (robô de leitura automática de
  AVA/boletos no Avançado; Enterprise fica com funcionalidade extra em
  aberto — ver Não resolvido).
- Excedente de usina/UC/usuário acima da franquia continua à la carte,
  self-service, dentro do app — reaproveita o desenho já existente na
  seção 6.4 do `VISAO.md` (aumento imediato e recalcula na hora;
  diminuição só no próximo ciclo, ciclo atual cobra valor cheio) e o
  `quota_service.py` / `LimiteContratado` já existentes. Esta entrega
  **não** reimplementa essa tela — só garante que o catálogo novo
  alimenta o que já existe.
- `cliente` deixa de ser recurso vendável/por plano: trava fixa de
  segurança (1000, igual para toda empresa, não ajustável), só para
  evitar abuso (ex.: criação em massa derrubando o servidor).
- Landing pública ganha página de checkout (fora do app, mesmo padrão
  estático da landing atual) por plano: formulário de pagamento via
  Asaas (boleto/pix/cartão).
- Webhook de pagamento confirmado (reaproveitando
  `platform_asaas_webhook_service.py`) gera um token de cadastro
  (hash + expiração, mesmo padrão de `Invitation`/`PasswordResetToken`,
  sem `TenantMixin` — a empresa ainda não existe) vinculado a
  email + plano comprado, e dispara e-mail para o endereço usado no
  pagamento com o link de cadastro.
- Link abre formulário público (nome da empresa, slug, senha do owner)
  que cria `Empresa` + `Assinatura` (status `ativa`, plano comprado) +
  `User` owner numa única transação, consumindo o token — equivalente ao
  que `criar_empresa.py` já faz manualmente, só que disparado pelo
  cliente.
- Tela interna de criação de empresa (admin/manual) ganha seletor de
  plano: sem plano, Starter, Avançado, Enterprise, teste.
- Plano teste: franquia 2 usinas / 50 ucs / 1 usuário, duração 14 dias,
  ao expirar vira somente-leitura — reaproveita o status `suspensa` já
  desenhado na seção 6.5 do `VISAO.md` (consulta liberada,
  criação/edição bloqueada), não apaga nem esconde dado.
- `VISAO.md` seção 6 atualizado: trial da 6.5 passa a referenciar o
  plano teste em vez de "Starter com volume reduzido"; `cliente` sai da
  lista de recursos à la carte na 6.1/6.3/6.4.

## Preços e franquias decididos

| Plano | Preço/mês | Usinas | UCs | Usuários | Extra |
|---|---|---|---|---|---|
| Starter | R$600 | 5 | 300 | 3 | — |
| Avançado | R$900 | 13 | 750 | 8 | robô de leitura automática de AVA/boletos |
| Enterprise | R$1200 | 19 | 1125 | 12 | em aberto (ver Não resolvido) |
| Teste (secreto) | não comprável | 2 | 50 | 1 | 14 dias, depois somente-leitura |

Excedente por unidade (fixo por ora, sem faixa degressiva): UC R$2,00 /
usina R$5,00 / usuário R$3,50.

Cliente: trava fixa de 1000 para toda empresa, independente de plano,
não ajustável nesta entrega.

Arredondamento de franquia (Avançado = 2,5× Starter; Enterprise = 1,5×
Avançado, aplicado sobre o valor bruto do Starter, não sobre o valor já
arredondado do Avançado): usina e usuário arredondados para cima quando
fracionários. Decisão do João, já confirmada.

## Non-goals

- Faixa de preço degressivo por volume de UC (ex.: 1–100 a um preço,
  101+ a outro) — fica para depois, catálogo atual usa preço fixo.
- Reimplementar a tela de ajuste de volume self-service (seção 6.4 do
  `VISAO.md`) — ela já está desenhada; esta entrega só garante que o
  catálogo novo (3 planos + teste) é compatível com o que existe.
- Prorata por dia no recálculo de valor — já decidido no VISAO que não
  há prorata.
- Upgrade/downgrade de tier (mudar de Starter pra Avançado, etc.) com
  todas as regras de cobrança associadas — fica fora desta entrega;
  catálogo precisa suportar múltiplos planos, mas o fluxo de troca de
  plano por uma empresa já ativa não é o foco aqui (hoje só existe
  criação nova).
- Decidir a funcionalidade extra do Enterprise.
- Qualquer mudança na automação dos robôs em si (V6.0) — aqui só o flag
  de catálogo que libera o Avançado.

## Anti-goals

- Nunca expor formulário de criação de empresa sem token válido vindo de
  pagamento confirmado — a rota pública `/empresas/registro` continua
  desativada tal como está; o novo endpoint de cadastro-via-token é uma
  rota nova, separada, que exige token válido e não-expirado.
- Nunca permitir compra do plano teste pela landing/checkout público —
  ele não aparece em nenhum catálogo consultável por rota pública.
- Nunca deixar a trava de `cliente` (1000) ser contornável por
  `LimiteContratado` — ela é hard-coded, não um recurso em
  `RECURSOS_VALIDOS` com excedente comprável.
- Nunca apagar ou esconder dado de empresa quando o plano teste expira
  ou quando a assinatura fica `suspensa` — sempre somente-leitura.

## Constraints

- Isolamento multi-tenant (`empresa_id`) é crítico — qualquer rota nova
  que toca `Empresa`/`Assinatura`/criação de `User` passa por
  `hub-security-reviewer` antes de aprovar (regra do `CLAUDE.md` do
  projeto).
- Checkout e formulário de cadastro-via-token rodam sem sessão
  autenticada (igual `Invitation`/`PasswordResetToken` hoje) — nunca
  usar `g.current_empresa_id` nesses caminhos.
- Token de cadastro é de uso único, expira (prazo a decidir — ver Não
  resolvido) e nunca é logado em texto puro (mesmo padrão de
  `token_hash` já usado).
- `criar_empresa.py` continua existindo para o caminho manual (empresa
  sem plano / teste / demo) — o fluxo novo não o substitui, convive com
  ele.
- Mudança em `backend/planos/catalogo.py` precisa manter compatibilidade
  com `quota_service.get_limite`/`verificar_cota` (que já leem
  `franquia` por `get_plano(...)['franquia']`) — não quebrar a leitura
  de `clientes` ali sem antes remover `clientes` de `RECURSOS_VALIDOS`
  e do `_CONTADORES`/enforcement correspondente, substituindo por
  checagem fixa de 1000.
- Build/teste obrigatórios antes de considerar pronto (`pytest` backend,
  `npm run build && npm test && npm run lint` frontend) — regra do
  `CLAUDE.md` do projeto.

## O que já foi decidido pelo João (não é escolha do builder)

- Nomes e preços dos 3 planos e do plano teste, franquias e regra de
  arredondamento (tabela acima).
- Preço de excedente fixo (UC/usina/usuário) definidos acima.
- Cliente sai da franquia por plano, trava fixa 1000.
- Plano teste: 14 dias, depois somente-leitura (reaproveita `suspensa`).
- Checkout é página pública solta, fora do app, mesmo padrão da landing.
- Pagamento via Asaas (boleto/pix/cartão), reaproveitando client/webhook
  já existentes (`platform_asaas_webhook_service.py`,
  `services/asaas_client.py`).
- Token de cadastro pós-pagamento segue o padrão `token_hash` +
  `expires_at` já usado por `Invitation`/`PasswordResetToken`.
- Ajuste de volume acima da franquia continua self-service dentro do
  app, não no checkout inicial (checkout só escolhe o plano-base).
- Tela interna de criação de empresa ganha os 5 planos no seletor
  (sem plano, Starter, Avançado, Enterprise, teste).

## Resolvido na revisão do builder-check

- **Pedido pendente pré-pagamento.** A empresa ainda não existe no
  momento do checkout, então precisa de uma entidade nova (`PedidoPlano`
  ou nome equivalente a critério do builder) criada no checkout, antes
  da confirmação: email, plano escolhido, id do customer/assinatura
  Asaas, status. O webhook de pagamento confirmado localiza esse
  registro via `externalReference` (mesmo campo que
  `platform_asaas_webhook_service.py` já lê) e só então gera o token de
  cadastro e dispara o e-mail. Sem `TenantMixin` (empresa não existe
  ainda), mesma linha de `Invitation`/`PasswordResetToken`.
- **Recorrência:** usa o objeto de assinatura recorrente nativo do
  Asaas — `Assinatura.asaas_subscription_id` já existe no model
  justamente pra isso, não é recobrança manual.
- **Empresas já existentes** (hoje `Assinatura.plano_chave='starter'`
  sem preço) continuam tratadas como equivalentes ao plano Starter
  (franquia/enforcement), mas **sem gerar cobrança/boleto** pra elas —
  são legado, não entram na cobrança recorrente nova. O builder decide o
  mecanismo mais simples pra marcar isso (ex.: flag `isento_cobranca` na
  `Assinatura` ou checagem por ausência de `asaas_subscription_id`).
- **Gatilho de expiração do trial/plano teste:** não existe cron/job
  agendado no projeto hoje pra isso. Fica a critério do builder criar um
  script agendado (mesmo padrão dos outros em `backend/scripts/`) que
  verifica `trial_expira_em` e aplica `suspensa` quando vencido — é
  infraestrutura nova, não só reuso de estado.

## Não resolvido (precisa de resposta do João antes do plano de implementação)

- Funcionalidade extra do Enterprise — por ora, o builder pode deixar um
  flag de catálogo reservado (ex.: `flags` vazio além de `robo_ava`) sem
  nenhuma feature nova atrás dele.
- Prazo de expiração do token de cadastro pós-pagamento (o convite de
  usuário comum usa 7 dias — segue o mesmo prazo por padrão, a menos que
  o João queira diferente).
- Campos exatos coletados no checkout (nome, CPF/CNPJ, telefone) para
  criar o cliente Asaas — o builder pode seguir os campos mínimos que
  `asaas_client.py` já exige hoje para outros fluxos de cobrança.
- O que acontece se o pagamento falhar ou o cliente abandonar o
  checkout sem pagar (sem ação — simplesmente nenhum token é gerado) —
  assumido como comportamento padrão, a confirmar.

## O que fica a critério do builder

- Nome exato dos campos/rotas novas, formato do token de cadastro na
  URL, estrutura de migration.
- Onde colocar a nova rota pública (`hub_platform` vs novo módulo) —
  seguir o padrão já usado por `platform_routes.py`.
- Texto do e-mail enviado (seguir padrão de `EmailTemplate` /
  `_enviar_email_convite`).
- Rounding exato (13/19 já decidido, mas qualquer outro arredondamento
  que apareça na implementação).
