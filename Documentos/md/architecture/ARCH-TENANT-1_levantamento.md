# ARCH-TENANT-1 — levantamento de exposição do identity map

Data: 2026-10-07. Snapshot analisado: HEAD `174eed74d246837588c7e2c61c1d30df037099c4`. As conclusões abaixo usam o tree commitado via `git show`/`git grep HEAD`; alterações locais foram ignoradas. Nenhum código, teste, model, migration, listener ou sessão foi alterado.

## Sumário executivo

O listener em `backend/extensions.py:21-38` adiciona `with_loader_criteria` a SELECTs ORM com `g.current_empresa_id`, mas um hit do identity map pode retornar uma instância sem executar SELECT. O teste em `backend/tests/security/test_tenant_identity_map.py:43-65` registra esse comportamento para Client A após alternar A→B.

No inventário estático de HEAD, não localizei getter PK-only de produção aplicado a classe TenantMixin. Chamadas de produção encontradas envolvem Empresa, User e Category (modelos sem TenantMixin), mais Pendencia somente em exemplo de docstring. A maioria dos acessos tenant por ID usa filtro explícito empresa_id. Existem mudanças de contexto intra-request em platform billing e webhook ASAAS, mas nos trechos encontrados não há objeto tenant carregado antes da troca; as consultas posteriores mantêm escopo explícito. Portanto: vulnerabilidade do mecanismo **demonstrada**, mas fluxo produtivo atual explorável por getter cru **não localizado**. Reuso em mesma Session por código futuro, jobs persistentes, relacionamentos ou APIs ORM é risco latente.

Recomendação preliminar: (1) helper tenant-scoped + regra CI que proíba getter PK-only cru em modelos tenant; (2) protótipo arquitetural de validação fail-closed da identidade residente ou unidade de trabalho separada por tenant; (3) limpeza de sessão como defesa adicional, não solução isolada. Mudança global de Session/listener exige aprovação humana e não foi feita.

## Método e inventário de acessos por PK

Comandos aplicados ao HEAD:

```text
git grep -n -E '\.query\.get\(|\.get_or_404\(|session\.get\(|db\.session\.get\(|\.session\.get\(|session\.query\([^)]*\)\.get\(' HEAD -- backend
git grep -n -E '\.(query\.get|session\.get|query\.get_or_404|get_or_404)\(' HEAD -- backend/routes backend/services backend/jobs backend/scripts backend/utils
git grep -n 'TenantMixin\|class (Client|UC|Usina|Fatura|FaturaConcessionaria|Document|Invitation|User)' HEAD -- backend/models
```

O primeiro comando encontrou, em produção, Empresa, User, Category e uma referência a Pendencia em docstring; referências diretas a Client/Fatura/FaturaConcessionaria são testes. O segundo não encontrou getter real de modelo tenant em rotas/services/jobs/scripts/utils nem get_or_404. A busca complementar por filter_by(id=...) encontrou os lookups tenant explícitos citados abaixo.

| Modelo/grupo | Localização / filtro | Classificação |
|---|---|---|
| Client, ConsumerUnit, Plant, Document, Fatura, FaturaConcessionaria, LogEntry, Pendencia e demais TenantMixin | Nenhum getter PK-only produtivo localizado. Exemplos filtrados: `client_service.py:11-12`, `uc_service.py:16-18`, `plant_service.py:9`, `document_service.py:20-22`, `fatura_service.py:95,183`, `asaas_webhook_service.py:105`, `billing_calculation_service.py:148`. | Nenhum uso cru encontrado; exemplos com empresa_id explícito estão protegidos no SELECT. Listener cobre SELECT em `extensions.py:26-38`; não protege hit de identity map. |
| Empresa | `platform_routes.py:59`; `billing_calculation_routes.py:272`; `auth_service.py:30`; `empresa_service.py:267,288`; `invitation_service.py:85,153`; `rateio_formulario_service.py:94`; `utils/auth.py:200,212`. | Empresa não herda TenantMixin (`models/empresa.py`; imports do app em `app.py:39`); lookup global esperado, não é exposição de entidade tenant. |
| User | `utils/auth.py:81,152,190`; `password_reset_service.py:88`. | User não usa TenantMixin por desenho (`models/user.py:9-12`); necessário para autenticação antes do tenant. Há usos separados com filtro empresa_id em `user_service.py:63,108`. |
| Category | `document_service.py:47,164`. | Category não usa TenantMixin (`models/category.py`); lookup global. Associação ao documento deve ser validada em seu próprio fluxo. |
| Invitation | `scripts/criar_empresa.py:67` usa `query.filter_by(id=...).one()`, não getter ORM; modelo explicitamente sem TenantMixin (`models/invitation.py:9-12`). Serviço lista/obtém convite por `id` + empresa (`invitation_service.py:112`). | Global/não tenant-scoped por desenho; script consulta convite criado na execução. |
| PasswordResetToken | Nenhum getter direto encontrado; `User.query.get(reset.user_id)` em `password_reset_service.py:88`. | Token e User são não tenant-scoped. |
| Pendencia | `Pendencia.query.get` só no exemplo documentado em `security_middleware.py:135-145`; nenhum uso do decorator encontrado. | Não executável conforme busca de referências; risco se copiado para produção. |
| Fatura/FaturaConcessionaria em testes | `db.session.get` em `test_asaas_webhook.py:137,146,150,159,253`; outros casos em testes billing/upload. | Somente testes. Repro de Client em `test_tenant_identity_map.py:43-73`. |

TenantMixin existe em vários models além da lista resumida na VISAO; fonte usada para classificar foi cada model do HEAD e `extensions.py`, não a lista histórica da visão.

## Mapa de contexto e ciclo da Session

**Request normal.** Middleware instala `before_request` e, após auth, define `g.current_empresa_id = user.empresa_id` (`utils/auth.py:177-201`). Fora handlers especiais, não encontrei outra atribuição produtiva. `g` é escopo da requisição Flask; assim, contexto normal permanece fixo após middleware.

**Ciclo SQLAlchemy.** `app.py:11-31` chama `db.init_app(app)` e não registra teardown próprio; requirements declara Flask-SQLAlchemy. Não há `db.session.remove/close/expunge_all` em teardown de produção. A afirmação de Session scoped removida no teardown do app context é comportamento da extensão (inferência do uso padrão), não customização local comprovada. Uso web padrão liga app context à requisição. CLI scripts abrem app context (`scripts/criar_empresa.py:37-39`; migração também usa app context), com Session limitada ao comando/contexto. Não foi achado job scheduler/task registrado no backend.

**Platform admin.** Middleware parte do tenant do usuário; para platform admin valida cookie `hub_platform_view`, consulta Empresa e define tenant selecionado (`utils/auth.py:198-225`). `platform_routes.entrar_na_empresa` valida Empresa, atribui `g.current_empresa_id` e emite cookie para requests seguintes (`platform_routes.py:56-82`). `sair` remove cookie; não troca contexto da requisição atual (`platform_routes.py:86-101`). Não encontrei troca de A para B dentro do mesmo request por essa UI.

**Platform billing.** `platform_billing_calculation_routes.before_request` valida usuário, `is_platform_admin`, existência da empresa na URL e então atribui o contexto (`billing_calculation_routes.py:266-274`). Auth antes consultou User/Empresa, não entidade TenantMixin. Queries seguintes observadas filtram empresa explicitamente (`:279`; serviço `billing_calculation_service.py:148`). Troca intra-request existe, objeto tenant pré-carregado nessa request não foi localizado.

**Webhook ASAAS.** Rota pública chama `processar_webhook` (`routes/fatura_routes.py:68-74`). Serviço resolve fatura/credencial via Core SQL; depois define tenant, adiciona ledger, consulta Fatura com `id` + `empresa_id`, commita e restaura contexto anterior em `finally` (`asaas_webhook_service.py:34-66,71-121`). Um pagamento por chamada; não foi encontrado loop multi-empresa.

**Imports, scripts, testes.** `import_service.py:124,186` consulta por empresa e chama `expire_all`; isso não é proteção geral contra identity map. Scripts encontrados criam uma empresa por execução ou fazem migração; não há evidência de loop ORM alternando tenants na mesma Session. Testes frequentemente definem g e removem Session em teardown; o repro sintético alterna tenant com a mesma sessão (`test_tenant_identity_map.py:43-73`).

## Exposição: atual versus latente

**Alcançável no mecanismo:** se uma classe TenantMixin já está no identity map e ocorre `Session.get`/`Query.get` pela mesma chave depois de trocar tenant, ORM pode retornar instância sem SELECT e o listener não é invocado. O repro mostra precisamente esse padrão para Client A sob contexto B (`test_tenant_identity_map.py:43-65`). SELECT filtrado por id+empresa é controle e retorna None (`:66-73`).

**Produção no HEAD:** não localizei sequência completa de preload tenant A → troca para B → getter PK-only em rota/service/job. Platform billing e ASAAS mudam contexto, mas os trechos observados não pré-carregam entidade tenant e consultas seguintes filtram empresa. Conclusão é ausência de caminho encontrado pela busca, não prova matemática de inexistência.

**Latente:** sessão mantida em job iterando tenants; novo getter cru; objeto retido em variável/cache e consumido após troca; lazy relationship ou coleção previamente carregada; `refresh(obj)` sob contexto novo; `merge(detached)` reinserindo estado. O inventário não encontrou uso produtivo de `merge`/`refresh`; relações precisam de teste. Vazamento de leitura é potencial. Escrita cross-tenant é **HIPÓTESE condicionada** a código mutar/commitar objeto retornado; não demonstrada pelo repro atual.

## Alternativas

Esforço relativo: P pequeno, M médio, G grande.

| Alternativa | Cobertura | Lacunas / risco de regressão | Esforço e validação |
|---|---|---|---|
| a. Expirar/limpar Session ao trocar contexto | Descarta/expira identidades para forçar consulta e abrange troca platform/webhook/jobs se centralizado. | `expire_all` pode manter identidade e refresh sem escopo; remove pode descartar trabalho, desanexar objetos ou quebrar lazy loads. Esquecimento de chamada deixa buraco. | M. Testar A→B, dirty/new/deleted, transações, relações, rotas platform e erro/sucesso webhook. Defesa auxiliar, não solução única. |
| b. Validar empresa_id de objeto retornado por wrapper/evento | Fail closed em lookup de objeto tenant; centralização pode cobrir sessão/ORM. | Wrapper não alcança getters crus não migrados nem referências retidas; evento precisa comprovar disparo no cache hit e em relationship/refresh/merge. Pode alterar None/404 para exceção e adicionar consultas. | M–G. Testar Query.get, Session.get, cache hit, refresh, merge, lazy/eager, objeto dirty, sem tenant e retorno 404 sem revelar existência. Mudança de evento é global. |
| c. Forçar SELECT/populate_existing | SELECT reexecutado e listener aplica critério; padrão pontual já existe em `billing_calculation_service.py:148`. | `Session.get` pode continuar retornando cache sem opção; não protege referências retidas, merge/Core, nem é solução global sem afetar consultas. Pode sobrescrever estado dirty e aumentar custo. | M–G. Testar cache-hit + SQL, mudanças não flushadas, loaders e impacto de queries/performance. |
| d. Helper tenant-scoped + banir getter cru | Usa filtro id+empresa padrão; AST/lint detecta regressão; compatível com padrões atuais. | Não protege instâncias já retidas, relacionamentos carregados ou APIs de sessão fora do helper. | M. Testar duas empresas, helper retorna None, lint contra aliases/Query.get/Session.get em TenantMixin, allowlist de classes globais. |
| e. Session separada por tenant | Identity maps isolados por unidade de trabalho/tenant; especialmente adequada a jobs. | Mudança global de Session/Flask-SQLAlchemy, transações, relacionamentos, objetos detached e todo fluxo auth/platform/webhook; alto risco. | G. Aprovação arquitetural. Testar requests paralelos, tenant A→B, platform, webhook, jobs, relações, transações e suíte completa. |
| f. Guard no boundary de resolução de identidade | Interceptar lookup da identidade sem trocar toda arquitetura; potencial defesa central. | Eventos podem não disparar em cache hit; API interna incerta; falsa sensação de segurança afeta ORM global. | G. Prova de conceito isolada, demonstrar interceptação do cache hit, relações, refresh, merge e falha fechada antes de adotar. |
| g. Unidade de trabalho por tenant + revisão/CI | Evita alternância de contexto na sessão; check de código e testes mantêm filtros explícitos. | Mitiga disciplina, mas não corrige semântica de identidade nem protege contra bug novo. | P–M. Testes sequenciais multi-tenant, regra CI contra getters crus, revisão de jobs/webhooks. |

Aspectos transversais: auth precisa manter User global (não tenant); platform admin troca contexto por cookie/URL; jobs/imports devem ser um tenant por unidade de trabalho; billing já filtra explicitamente e tem populate_existing pontual; relacionamentos lazy/eager, refresh/merge precisam estar no plano. Helper tende a gerar lookup PK+tenant indexado; validação adicional pode exigir SELECT; populate_existing aumenta queries. Qualquer opção global precisa preservar contratos RBAC/404 e transações.

## Recomendação preliminar, testes e critérios de pronto

Recomendo combinação em fases, sem escolher ainda a mecânica global:

1. Fase de contenção: helper tenant-scoped para PK e teste/AST no CI que proíba getter PK-only em TenantMixin, permitindo explicitamente User/Empresa/Category quando aplicável.
2. Fase arquitetural: prototipar validação fail-closed da identidade residente (b) versus Session/unidade de trabalho separada por tenant (e). Não adotar `populate_existing` global como correção única. `expire/remove` pode complementar após definir destino de alterações pendentes.
3. Cobertura obrigatória para instâncias já retidas, lazy/eager relationships, `refresh`, `merge`, leitura e mutação.

Para tornar `test_tenant_identity_map.py` verde: em duas empresas, carregar Client A no tenant A; trocar para B; `Client.query.get(id)` e `db.session.get(Client,id)` devem retornar None ou falhar com resposta segura, nunca A; manter SELECT explícito filtrado como controle. Adicionar cenários de refresh/merge e relacionamentos; mutação + commit deve ser negada. Testar platform enter/use/exit, URL platform billing, usuário comum, webhook success/failure e imports/jobs sequenciais. Testar lint AST contra getters crus. Rodar suíte backend completa.

Pronto quando os dois expected failures forem verdes; nenhum objeto/relacionamento/refresh/merge atravessar tenant; tentativa de escrita for bloqueada; regra automatizada impedir regressão; platform/auth/billing/webhook/jobs preservarem contratos, transações e 404; sem estado pendente descartado; desempenho avaliado; revisão arquitetural independente feita.

## Riscos e perguntas abertas

1. **HIPÓTESE a confirmar em runtime da versão exata:** listener não executa em cache hit de `Session.get`; comportamento está reproduzido por teste marcado expectedFailure, mas esta etapa não rodou teste em worktree limpo.
2. Mismatch deve retornar None/404 ou lançar exceção interna? Não pode revelar existência da PK em outro tenant.
3. Ao trocar contexto com trabalho pendente: proibir, flush, commit, rollback ou encerrar unidade de trabalho? Requer decisão de transação.
4. Confirmar por busca AST no momento da implementação APIs `refresh`, `merge` e relacionamentos, além da busca textual aqui.
5. Conclusões cobrem apenas HEAD `174eed7`; execução externa/runtime e alterações locais foram excluídos.
6. VISAO lista nomes tenant históricos/resumidos; classificação deste levantamento veio dos modelos efetivos e do mixin no HEAD.
