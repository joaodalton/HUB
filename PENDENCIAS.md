PENDENCIAS.md

Especificação operacional do motor de pendências do HUB

HUB V1.5
Operacional
1. Objetivo

O Motor de Pendências do HUB tem como objetivo controlar, priorizar, notificar e acompanhar todas as ações operacionais, cadastrais, financeiras e sistêmicas necessárias para o funcionamento da operação de energia compartilhada.

O sistema deve permitir:

- criação automática de pendências
- criação manual de pendências
- conclusão automática baseada em regras
- acompanhamento por prazo
- escalonamento por atraso
- visualização em agenda
- notificações em tempo real
- preparação para automações futuras e leitura inteligente de documentos (IA/OCR)

2. Conceitos principais

Pendência

Algo que precisa ser feito, validado, enviado, atualizado ou vinculado.

Evento

Algo que aconteceu e deve ficar registrado na linha do tempo operacional.

Agenda

Visão temporal de pendências com prazo, eventos e cobranças futuras.

Alerta

Sinalização visual de prioridade, atraso ou erro operacional.

3. Estrutura da pendência

Todos os tipos de pendência devem possuir os seguintes campos:

Campo

	

Descrição




ID

	

Identificador único




Título

	

Resumo curto da ação




Descrição

	

Detalhamento da pendência




Categoria

	

Cadastro, Financeiro, Operacional ou Erro




Subcategoria

	

Opcional




Origem

	

Automática ou Manual




Responsável

	

Definido pela categoria




Prioridade

	

Baixa, Média, Alta, Urgente




Status

	

Pendente, Em andamento, Aguardando cliente, Concluída, Cancelada




Data de criação

	

Automática




Prazo

	

Editável manualmente




Data de conclusão

	

Preenchida automaticamente




Entidade vinculada

	

Cliente, UC, Usina, Rateio ou Boleto

4. Categorias operacionais
Cadastro

Equipe de cadastro

Dados do cliente

Dados da UC

Dados da usina

Documentos obrigatórios

Vínculo UC ↔ Cliente

Atualização cadastral

Financeiro

Equipe financeira

Envio de boleto

Lembrete de vencimento

Boleto vencido

Inadimplência

Primeiro boleto com desconto

Operacional

Equipe operacional

Rateio

Disponibilidade de usina

Entrada no rateio

UC sem usina

Desvinculações automáticas

Erro

Administrador / suporte

Falha de importação

Falha de integração

Falha de processamento

Falha de automação

5. Prioridades

Prioridade

	

Uso




Baixa

	

Informativa




Média

	

Acompanhamento normal




Alta

	

Impacta operação ou cadastro




Urgente

	

Impacta cliente, financeiro ou sistema

6. Regras automáticas de cadastro
6.1 Cliente criado

Ao criar um cliente:

Enviar mensagem de boas-vindas

Criar evento “Cliente criado”

Se faltar UC:

Cadastro
Alta

Cliente sem UC cadastrada

Cliente foi criado, porém ainda não possui UC vinculada.

6.2 Campos obrigatórios do cliente

Campos obrigatórios:

Nome

CPF

E-mail

Telefone

Data de nascimento

Para cada campo faltante:

Cadastro
Alta

Falta [campo] do cliente

Exemplo: Falta data de nascimento do cliente João da Silva.

Ao preencher o campo → conclusão automática da pendência.

6.3 Documentos obrigatórios

Obrigatórios:

Documento de identidade

Fatura

Termo de adesão

Faltando qualquer documento:

Cadastro
Alta

Falta documento obrigatório

7. Fluxo operacional do cliente

Cliente criado

Boas-vindas

Solicitar AVA + autorização

Validar documentos

Cadastrar UC

Vincular UC ao cliente

Aguardando usina

Vincular à usina

8. Regras de UC sem usina

A pendência só será criada quando:

UC estiver vinculada a um cliente

Cliente estiver com cadastro completo

Documentos obrigatórios estiverem presentes

UC permanecer sem usina por 7 dias

Operacional
Alta

UC sem usina vinculada há 7 dias

O prazo de 7 dias deverá ser configurável futuramente.

9. Modelo de relacionamentos

Cliente

UC (1:N)

Usinas (N:N)

10. Rateio
10.1 Envio de rateio

Quando uma planilha Excel de rateio for gerada e enviada:

Criar evento “Rateio enviado”

Marcar UCs incluídas no envio

Enviar mensagem aos clientes incluídos

10.2 Entrada no rateio

Quando o usuário alterar o status para Concluído:

Criar evento “Entrada no rateio concluída”

Enviar mensagem de entrada no rateio

11. Cobrança e boletos
11.1 Importação de boleto

Ao importar um boleto:

Criar pendência “Enviar boleto ao cliente”

Categoria: Financeiro

Origem: Automática

11.2 Primeiro boleto com desconto

Quando o primeiro boleto importado possuir desconto:

Criar evento

Enviar mensagem “Primeiro boleto com desconto”

11.3 Lembrete de vencimento

5 dias antes do vencimento:

Criar alerta financeiro

Enviar lembrete ao cliente

11.4 Boleto vencido

No vencimento:

Enviar mensagem de vencimento

Após 7 dias vencido:

Financeiro
Urgente

Boleto vencido há mais de 7 dias

12. Cancelamento
12.1 Solicitação de cancelamento

Quando o cliente solicitar cancelamento:

Alterar status do cliente para Cancelamento

Remover automaticamente do rateio

Remover automaticamente vínculos com usinas

Criar alerta operacional

Enviar mensagem de solicitação recebida

12.2 Cancelamento concluído

Ao alterar o status para Cancelamento concluído:

Criar evento

Enviar mensagem de confirmação final

13. Agenda operacional

A agenda deve exibir:

Pendências com prazo

Vencimentos e tarefas operacionais

Eventos operacionais

Rateios, cancelamentos e entradas

Cobranças futuras

Lembretes e boletos futuros

14. Escalonamento por atraso

Atraso

	

Ação




1 dia

	

Muda cor do card




3 dias

	

Sobe para o topo




7 dias

	

Gera notificação




14 dias

	

Pisca o card + notificação

15. Comportamento visual

Permitido

Card piscando suavemente

Ícone de notificação piscando

Badge de prioridade

Cores por categoria

Não permitido

Piscar a tela inteira

Alertas intrusivos contínuos

Mudança aleatória de cores

16. Notificações

Canais previstos:

Tela de pendências

Agenda

Notificação em tempo real

E-mail interno

17. Configurações futuras

Criar uma tela Configurações de Automação com:

Habilitar/desabilitar cada regra automática

Alterar prazo de UC sem usina

Alterar prazo de atualização cadastral

Alterar dias de lembrete de boleto

Alterar dias para inadimplência urgente

18. Preparação para IA / leitura de documentos

O modelo deve permitir futuramente:

Leitura automática de PDF

Extração de CPF, UC, nome e vencimento

Preenchimento automático de campos

Conclusão automática de pendências

Criação automática de novas pendências

19. Tabela resumida de gatilhos

Gatilho

	

Pendência/Evento




Cliente criado

	

Boas-vindas + evento




Cliente sem UC

	

Pendência alta




Campo obrigatório faltando

	

Pendência alta automática




Documento faltando

	

Pendência alta automática




UC sem usina 7 dias

	

Pendência operacional




Importar boleto

	

Pendência financeira




5 dias antes

	

Lembrete financeiro




7 dias vencido

	

Urgente financeira




Rateio enviado

	

Evento + mensagem




Entrada no rateio concluída

	

Evento + mensagem




Solicitar cancelamento

	

Desvincular + alerta




Cancelamento concluído

	

Evento + mensagem

20. Objetivo final do HUB

Nenhuma ação operacional deve depender exclusivamente da memória humana.

O sistema deve lembrar, priorizar, alertar, acompanhar e registrar toda a operação de cadastro, rateio, cobrança e cancelamento, criando uma base preparada para automações futuras, integração com concessionárias e inteligência artificial.