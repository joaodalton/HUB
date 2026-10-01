# Análise Técnica — Sistema de Loading do HUB

## Componente Loading.ts

**Arquivo:** `frontend/src/components/Loading.ts`

Exporta duas funções:

- `createLoading(): HTMLElement` — cria um `<div class="global-loading" hidden>` com `textContent = "Carregando..."`, guarda a referência em `loadingState.element` (módulo singleton) e retorna o elemento. O elemento começa hidden.
- `setGlobalLoading(isLoading: boolean): void` — oposta `element.hidden = !isLoading`.
  - Quando `isLoading = true`: inicia timeout de 2s que auto-esconde o loading (fallback se a página esqueceu `hide()`). Se já existia timeout ativo, cancela antes de criar um novo.
  - Quando `isLoading = false`: cancela o timeout (se existir) e não dispara auto-hide.

Estado é mantido em módulo-closure:
```ts
const loadingState = {
  element: null as HTMLElement | null,
  timeoutId: null as ReturnType<typeof setTimeout> | null
};
```
Isso significa que há **um único elemento de loading por sessão** (não por componente, não por contexto React). O `createLoading` deve ser chamado antes de qualquer `setGlobalLoading`, senão a função retorna cedo.

## Como o Loading é injetado no DOM — BaseLayout.ts

**Arquivo:** `frontend/src/layouts/BaseLayout.ts`

A linha crítica é a 25:
```ts
shell.append(overlay, body, createLoading(), createToastContainer());
```

- `createBaseLayout(...)` é a função que monta o shell da aplicação.
- Dentro dela, `createLoading()` é chamado **uma única vez** por instância de layout.
- O elemento retornado é imediatamente anexado ao `shell` (que é um `<div class="app-shell">`).
- O `shell` é retornado e deve ser inserido no DOM pelo caller (provavelmente substituição do root do SPA).

Ordem no DOM (dentro do shell): `sidebar-overlay` → `app-body` (sidebar + main) → `global-loading` → `toast-container`.

O loading fica **acima do conteúdo** (posição fixa, `top: 20px; right: 20px`), mas abaixo do toast (`z-index: 200`) e do drawer overlay (`z-index: 1000`).

Note que `createLoading()` registra o elemento em `loadingState.element`. Se o layout for recriado (navegação), o elemento antigo será removido do DOM (GC) e o novo será registrado.

## CSS — shared.css

**Arquivo:** `frontend/src/styles/shared.css`, linhas 148–173.

```css
.global-loading {
  position: fixed;
  top: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 16px;
  font-size: 12px;
  color: var(--text-dim);
  z-index: 150;
  box-shadow: var(--shadow-md);
}
```

- Posição fixa no canto superior direito.
- `z-index: 150` — abaixo do toast (200) e do drawer (1000), acima do conteúdo.
- Não depende de `:not([hidden])` para exibição. A alternância é feita via atributo `hidden` do HTML, que é respeitado pelo CSS (o `display: flex` não se aplica a elementos `hidden`).
- O spinner é feito com `::before` + animação `spin`.

**Conclusão CSS:** Não há regra que sobrepossa `hidden`. O CSS está correto.

## Criação única vs recriação

- O `createLoading()` é chamado uma vez por `createBaseLayout()`.
- Se o app SPA recria o layout a cada navegação (substituindo o root via `replaceChildren`/innerHTML), então o loading é **recriado a cada navegação**.
- Isso é **correto**: o elemento antigo sai do DOM, o novo é registrado em `loadingState.element`.
- Se houvesse múltiplos layouts simultâneos (ex: modais com layout próprio), haveria conflito — mas o HUB parece usar um único layout principal.

**Vantagem:** singleton de módulo evita múltiplos loadings sobrepostos.
**Risco:** se uma página chamar `loading.show()` antes que o layout tenha terminado de montar e registrar o elemento, a chamada é ignorada silenciosamente (retorno antecipado em `if (!loadingState.element) return`). Mas isso é edge case raro — quarta chamada no init homologada.

## Padrão de uso nas páginas

Todas as páginas que usam loading seguem o mesmo padrão:

```ts
const loading = useGlobalLoading();
// ...
async function loadX() {
  loading.show();
  try {
    // operação
  } finally {
    loading.hide();
  }
}
```

Exemplos verificados:
- `AgendaPage.ts`: `loading.show()` antes do `try`, `loading.hide()` no `finally` (linhas 35, 38). Também usado em `saveComposer` (linhas 140, 152) e `cancelEvent` (linha 165 — ver linha final).
- `BillingRuleEditorPage.ts`: `loading.show()`/`loading.hide()` balanceados em `load()` (linhas 80, 91) e no save (linhas 282, 319).

Todas as amostras inspecionadas têm `show`/`hide` balanceados em `try/finally`.

## Possíveis causas do loading não sumir

1. **Falta de `hide()` no `finally`** em algum novo código — mas o padrão é consistente.
2. **Timeout de 2s atuando** — o loading aparece e some após 2s se o `hide()` não for chamado. Isso pode confundir o usuário ("por que sumiu só?").
3. **Chamadas aninhadas de loading** — se `show()` é chamado antes que uma operação anterior termine (ex: load agendamento interno dentro de save), o loading pode piscar. O código atual não previne reentrância.
4. **Elemento perdido** — se o layout é recriado durante uma operação assíncrona (navegação rápida), o `loadingState.element` pode apontar para elemento desconexão e o hide não surtir efeito visual. Mas o elemento novo seria registrado no novo layout.

## Recomendação

1. **Adicionar proteção de reentrância:** o `setGlobalLoading` deveria ignorar `show()` se já estiver em loading, e `hide()` se já estiver oculto. Atualmente não há verificação — o estado é apenas o atributo `hidden` do elemento, sem lógica de mutex. Uma simples guarda `if (isLoading && !loadingState.element.hidden) { ... }` evitaria efeitos visuais indesejados.
2. **Logging melhora:** os console.logs existentes ajudam na depuração; manter.
3. **Timeout configurável:** se a operação legítima levar mais de 2s, o timeout de segurança esconderá o loading prematuramente. Considerar aumentar ou tornar configurável, ou remover o timeout e exigir `hide()` em todos os caminhos.
4. **Verificar se há operações sem `finally`:** revisar novas páginas/code paths que usem `loading.show()` sem `finally` correspondente — é a causa mais provável de "loading que não some".
