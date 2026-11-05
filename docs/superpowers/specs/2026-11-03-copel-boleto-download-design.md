# Download automático de boleto Copel — Design

## Intenção

O HUB hoje recebe faturas de concessionária (Copel) por upload manual
(`services/fatura_concessionaria_upload_service.py`). O objetivo deste
projeto é eliminar esse passo manual para a Copel: logar no portal da
concessionária com o CPF/CNPJ e a senha já cadastrados por UC, verificar se
já existe fatura da competência atual para aquela UC, e, se não existir,
baixar o PDF e entregá-lo ao pipeline de upload já existente.

## Goals

- Login automatizado no portal Copel (`https://www.copel.com/avaweb/paginaLogin/login.jsf`)
  usando CPF/CNPJ (`ConsumerUnit.documento`) e senha (via
  `ConsumerUnit.concessionaria_credential` → `ApiCredential.get_segredo()`).
- Rodar 3x/dia (manhã, meio-dia, fim do dia) via Windows Task Scheduler,
  para todas as UCs de todas as empresas com `concessionaria == 'Copel'`
  e `concessionaria_credential_id` configurado.
- Pular login de uma UC se já existir `FaturaConcessionaria` da
  competência atual para aquela UC — evita logins repetidos na mesma
  máquina no mesmo dia.
- Reusar o pipeline de upload existente (`upload_invoice`) para
  storage (B2), parsing (`invoice_parsers/copel.py`) e criação de
  `FaturaConcessionaria` — nenhum pipeline novo de persistência.
- Se o login falhar ou aparecer reCAPTCHA (não deveria aparecer no login
  normal, só no fluxo "esqueci senha" após várias tentativas), **não
  tentar de novo automaticamente**: enviar e-mail de alerta e criar uma
  `Pendencia` com `prioridade='critica'`.

## Non-goals

- Outras concessionárias além da Copel (a interface fica pronta para
  isso, mas só a Copel é implementada agora).
- Resolver reCAPTCHA automaticamente (serviço de terceiros) — fora de
  escopo e de risco de ToS, não decidido pelo usuário.
- Mudar o pipeline de parsing/validação de fatura já existente.

## Constraints

- Stack: Python 3.11, Flask + SQLAlchemy + PostgreSQL (Neon), mesmo
  backend do HUB (`HUB/backend`).
- Sem Selenium/Playwright: login é form HTML tradicional JSF (POST com
  `javax.faces.ViewState`), via `requests.Session`.
- Sem dependência nova no `requirements.txt` — tudo que precisa já
  existe no projeto (`requests` já é transitiva via libs atuais, se não
  estiver direto no requirements.txt, adicionar como única exceção).
- Credenciais: fase de teste usa `.env` local; fase final usa os campos
  já existentes (`ConsumerUnit.documento` + `ApiCredential` via
  `concessionaria_credential_id`) — **nenhuma migration de schema é
  necessária**, a modelagem já suporta login+senha por UC.
- Toda query/escrita tenant-scoped precisa de `flask.g.current_empresa_id`
  setado manualmente (o script roda fora de uma request HTTP).

## Decisões já tomadas (não reabrir sem motivo)

- Boleto == PDF da fatura de consumo (não é um documento separado de
  cobrança).
- Rodar para todas as UCs/clientes Copel automaticamente.
- Pipeline pós-download roda o parser e cria `FaturaConcessionaria`
  automaticamente (igual upload manual).
- Escopo: só Copel agora, mas com uma interface adaptável
  (`ConcessionariaClient` ou equivalente) para outras concessionárias
  entrarem depois sem reescrever o scheduler.

## O que fica a cargo de quem implementar

- Nome exato das classes/módulos do adapter Copel.
- Estratégia de retry/backoff dentro de uma mesma execução (não entre
  execuções — pendência crítica aborta o dia para aquela UC).
- Formato exato do e-mail de alerta.
