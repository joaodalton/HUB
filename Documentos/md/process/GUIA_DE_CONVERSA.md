# Guia de conversa com o Claude

Três etapas. Sempre nessa ordem: planejamento → implementação → verificação.

## 1. Planejamento

Pede escopo claro antes de qualquer código. Usa quando o pedido é vago ou pode ter mais de um jeito de entender.

```
Quero [o que você quer]. Antes de codar: esclarece o escopo comigo —
o que "pronto" significa, o que fica fora, e restrições que eu não
disse mas provavelmente existem. Se tiver mais de uma leitura possível,
mostra as opções lado a lado. Depois, monta um plano com passo a passo,
cada passo com uma verificação (teste, comando), e espera meu ok antes
de implementar.
```

Ele te devolve perguntas ou um plano — você confirma ou ajusta, só depois libera pra codar.

## 2. Implementação

Depois do plano aprovado. Se for várias tarefas sem relação entre si, pede pra rodar em paralelo:

```
Implementa o plano aprovado. Se houver tarefas independentes (sem
depender uma da outra, sem tocar nos mesmos arquivos), roda em paralelo;
senão, uma por vez. Commita só depois de cada verificação passar.
```

Pra forçar paralelo explicitamente (várias tarefas já claras, sem plano prévio):

```
Roda em paralelo: [tarefa A], [tarefa B], [tarefa C]. Elas não dependem
uma da outra e não tocam nos mesmos arquivos.
```

Pra tarefa simples e sem ambiguidade (ajuste pequeno, bug óbvio), pode pular a etapa 1 e pedir direto:

```
Corrige [o bug]: [descrição]. Mostra o diff e o teste que comprova
que corrigiu antes de commitar.
```

## 3. Verificação

Depois que o código está pronto, antes de considerar terminado:

```
/code-review high
```

ou, pra revisão mais pesada (vários especialistas, na nuvem):

```
/code-review ultra
```

Ele te devolve achados ordenados por gravidade (crítico → baixo). Se vier vazio, também é resultado válido — significa que nada sobrou depois da revisão.

## Resumo

| Etapa | Quando usar | Frase-chave |
|---|---|---|
| Planejamento | Pedido vago, mais de uma leitura possível | "antes de codar, esclarece o escopo" |
| Implementação | Plano já aprovado, ou bug simples e claro | "implementa o plano" / "corrige X" |
| Verificação | Código pronto, antes de considerar terminado | `/code-review` |

Não precisa citar nome de skill ou ferramenta — a frase certa já guia o Claude pra etapa certa.
