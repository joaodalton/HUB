# Download Automático de Boleto Copel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Logar automaticamente no portal da Copel por UC, baixar o boleto/fatura da competência atual quando ainda não existir no banco, e entregá-lo ao pipeline de upload de fatura já existente no HUB.

**Architecture:** Um cliente HTTP (`requests.Session`) resolve login/download no portal JSF da Copel. Um serviço de orquestração descobre UCs Copel elegíveis em todas as empresas, pula as que já têm fatura da competência atual, baixa o PDF das demais e entrega pro `upload_invoice` já existente (storage B2 + parser + `FaturaConcessionaria`, sem mudanças). Falhas de login/captcha disparam e-mail + `Pendencia` crítica em vez de retry automático. Um script de entrada é chamado 3x/dia pelo Windows Task Scheduler.

**Tech Stack:** Python 3.11, Flask + SQLAlchemy + PostgreSQL (Neon), `requests` (nova dependência direta — hoje só transitiva), `resend` (já no projeto), `pytest` + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-11-03-copel-boleto-download-design.md`

## Global Constraints

- Sem Selenium/Playwright — login é POST de formulário JSF tradicional.
- Nenhuma migration de schema — reusa `ConsumerUnit.documento` (login) e `ConsumerUnit.concessionaria_credential` → `ApiCredential.get_segredo()` (senha).
- Toda operação tenant-scoped precisa de `flask.g.current_empresa_id` setado antes de rodar (script roda fora de request HTTP).
- Reusa `services/fatura_concessionaria_upload_service.upload_invoice(client_id, file_storage)` sem alterá-lo — nenhum pipeline de storage/parsing novo.
- Se reCAPTCHA aparecer ou login falhar: e-mail (`services/email_service.send_email`) + `Pendencia(tipo='erro', prioridade='critica')`, sem retry automático na mesma execução.
- Interface do cliente de concessionária deve permitir adicionar outra concessionária depois sem tocar no orquestrador ou no script de entrada.

## Review Focus

- UC com `concessionaria_credential_id` nulo (sem senha cadastrada) — não deve tentar logar, deve gerar pendência de configuração, não erro de login.
- Login Copel aceito pelo servidor mas retornando página de erro de credencial inválida (senha errada) em vez de HTTP 401/403 — precisa ser distinguido de sucesso.
- `javax.faces.ViewState` ausente/expirado na resposta do GET inicial — a POST não pode seguir sem esse token.
- Duas UCs da mesma empresa com a mesma competência já processada numa execução anterior do mesmo dia — não deve logar de novo nem duplicar `FaturaConcessionaria` (a unicidade por `arquivo_hash` já cobre duplicata de arquivo, mas o pulo por competência evita login desnecessário).
- `upload_invoice` levantando `InvoiceUploadError` (ex. UC não encontrada, UC ambígua) após um download bem-sucedido — o PDF já foi baixado, mas a inserção falhou; precisa virar pendência, não uma exceção não tratada que aborta as UCs seguintes.

---

## File Structure

- Create: `backend/services/concessionarias/__init__.py` — módulo novo.
- Create: `backend/services/concessionarias/base.py` — interface `ConcessionariaClient` (abstrata) e `BoletoDownloadError`.
- Create: `backend/services/concessionarias/copel_client.py` — `CopelClient(ConcessionariaClient)`: login via `requests.Session`, localização e download do boleto da competência atual.
- Create: `backend/services/copel_boleto_service.py` — orquestração: descoberta de UCs elegíveis, dedup, chamada ao `CopelClient`, entrega ao `upload_invoice`, alerta em falha.
- Create: `backend/scripts/copel_boleto_downloader.py` — entrypoint CLI chamado pelo Task Scheduler.
- Create: `backend/tests/test_copel_client.py`
- Create: `backend/tests/test_copel_boleto_service.py`
- Modify: `backend/requirements.txt` — adicionar `requests` (hoje só transitiva).

---

### Task 1: `ConcessionariaClient` interface + `CopelClient`

**Files:**
- Create: `backend/services/concessionarias/base.py`
- Create: `backend/services/concessionarias/copel_client.py`
- Test: `backend/tests/test_copel_client.py`

**Interfaces:**
- Produces: `class ConcessionariaClient(ABC)` com `login(self, documento: str, senha: str) -> None` e `baixar_boleto_competencia_atual(self) -> bytes | None` (retorna `None` se não existir boleto publicado ainda pra competência atual).
- Produces: `class BoletoLoginError(Exception)` — levantada em falha de login (credencial inválida, reCAPTCHA inesperado, HTTP de erro). Tem atributo `motivo: str` com um destes valores: `'credencial_invalida'`, `'recaptcha_inesperado'`, `'erro_desconhecido'`.
- Produces: `class CopelClient(ConcessionariaClient)` com `__init__(self, session: requests.Session | None = None)`.
- Consumes: nenhuma interface de outro task.

- [ ] **Step 1: Escrever teste de login com sucesso**

```python
@patch('services.concessionarias.copel_client.requests.Session.post')
@patch('services.concessionarias.copel_client.requests.Session.get')
def test_login_sucesso_extrai_view_state_e_posta_credenciais(self, mock_get, mock_post):
    mock_get.return_value = _fake_response(
        200, html_com_view_state('ABC123'),
    )
    mock_post.return_value = _fake_response(200, '<html>Minha Agência</html>')
    client = CopelClient()
    client.login('12345678900', 'minha-senha')
    posted_data = mock_post.call_args.kwargs['data']
    assert posted_data['javax.faces.ViewState'] == 'ABC123'
    assert posted_data['formulario:numDoc'] == '12345678900'
    assert posted_data['formulario:pass'] == 'minha-senha'
```

Helper `_fake_response(status_code, text)` e `html_com_view_state(token)` ficam no topo do arquivo de teste (constroem um objeto simples com `.status_code`, `.text`, `.cookies` — não precisa ser um `requests.Response` real).

- [ ] **Step 2: Rodar teste e confirmar falha**

Run: `pytest tests/test_copel_client.py::test_login_sucesso_extrai_view_state_e_posta_credenciais -v`
Expected: FAIL (`ModuleNotFoundError` ou `AttributeError`, módulo ainda não existe)

- [ ] **Step 3: Implementar `base.py` e `copel_client.py`**

`base.py`: classe abstrata simples, sem lógica.

`copel_client.py`: `CopelClient.login` faz GET em `LOGIN_URL = 'https://www.copel.com/avaweb/paginaLogin/login.jsf'`, extrai `javax.faces.ViewState` do HTML (regex ou parser simples tipo `re.search(r'name="javax\.faces\.ViewState" value="([^"]+)"', texto)`), monta o POST com `formulario:numDoc`, `formulario:pass`, `formulario:j_idt41` (nome do botão "Entrar", como visto no HTML real) e o ViewState, usando a mesma `requests.Session` (cookies/jsessionid persistem entre GET e POST). Verifica a resposta do POST: se o HTML contiver indicação de reCAPTCHA (`'g-recaptcha'` ou `'grecaptcha'`) levanta `BoletoLoginError(motivo='recaptcha_inesperado')`; se contiver mensagem de erro de login conhecida (checar o texto real da página de erro — documentar a string exata encontrada em teste manual) levanta `BoletoLoginError(motivo='credencial_invalida')`; senão considera sucesso.

- [ ] **Step 4: Rodar teste e confirmar sucesso**

Run: `pytest tests/test_copel_client.py::test_login_sucesso_extrai_view_state_e_posta_credenciais -v`
Expected: PASS

- [ ] **Step 5: Escrever e passar teste de reCAPTCHA inesperado**

```python
def test_login_com_recaptcha_inesperado_levanta_boleto_login_error(self, mock_get, mock_post):
    mock_post.return_value = _fake_response(200, '<div class="g-recaptcha"></div>')
    client = CopelClient()
    with self.assertRaises(BoletoLoginError) as ctx:
        client.login('12345678900', 'senha')
    assert ctx.exception.motivo == 'recaptcha_inesperado'
```

Run: `pytest tests/test_copel_client.py -v` — ambos devem passar.

- [ ] **Step 6: Escrever e passar teste de `baixar_boleto_competencia_atual` retornando `None` quando não publicado**

Mocka a chamada HTTP que lista/baixa o boleto retornando uma resposta indicando "nenhum documento disponível para este mês" (string real a documentar após inspeção manual da área logada — até lá, usar um placeholder de resposta vazia/404 e marcar com TODO no teste). `baixar_boleto_competencia_atual` deve retornar `None` nesse caso, não levantar exceção.

- [ ] **Step 7: Escrever e passar teste de ViewState ausente/expirado na página de login**

```python
def test_login_sem_view_state_levanta_boleto_login_error(self, mock_get, mock_post):
    mock_get.return_value = _fake_response(200, '<html>pagina sem o campo esperado</html>')
    client = CopelClient()
    with self.assertRaises(BoletoLoginError) as ctx:
        client.login('12345678900', 'senha')
    assert ctx.exception.motivo == 'erro_desconhecido'
    mock_post.assert_not_called()
```

`login` deve checar se a extração do ViewState retornou algo antes de montar o POST; se não, levanta `BoletoLoginError(motivo='erro_desconhecido')` sem chegar a chamar `session.post`.

Run: `pytest tests/test_copel_client.py -v`
Expected: PASS (todos)

- [ ] **Step 8: Commit**

```bash
git add backend/services/concessionarias backend/tests/test_copel_client.py backend/requirements.txt
git commit -m "feat: adiciona CopelClient para login e download de boleto via requests"
```

---

### Task 2: Descoberta de UCs elegíveis e checagem de dedup

**Files:**
- Create: `backend/services/copel_boleto_service.py` (parte 1 — só a descoberta, sem download ainda)
- Test: `backend/tests/test_copel_boleto_service.py`

**Interfaces:**
- Consumes: nada do Task 1 ainda.
- Produces: `def ucs_copel_elegiveis() -> list[ConsumerUnit]` — roda SEM `g.current_empresa_id` setado (limpa com `g.pop('current_empresa_id', None)` antes), filtra `ConsumerUnit.concessionaria == 'Copel'` e `ConsumerUnit.concessionaria_credential_id.isnot(None)`, across todas as empresas.
- Produces: `def ja_tem_fatura_da_competencia_atual(uc: ConsumerUnit) -> bool` — seta `g.current_empresa_id = uc.empresa_id` e consulta `FaturaConcessionaria.query.filter_by(consumer_unit_id=uc.id, competencia=competencia_atual())`.
- Produces: `def competencia_atual() -> str` — `datetime.utcnow().strftime('%Y-%m')`.

- [ ] **Step 1: Escrever teste de `ucs_copel_elegiveis` ignorando UC sem credencial**

```python
def test_ucs_copel_elegiveis_ignora_uc_sem_credencial(self):
    empresa = self._criar_empresa()
    uc_sem_credencial = self._criar_uc(empresa, concessionaria='Copel', concessionaria_credential_id=None)
    credencial = self._criar_api_credential(empresa)
    uc_com_credencial = self._criar_uc(empresa, concessionaria='Copel', concessionaria_credential_id=credencial.id)
    resultado = ucs_copel_elegiveis()
    assert [uc.id for uc in resultado] == [uc_com_credencial.id]
```

Reusar os helpers `_criar_empresa`/`_criar_uc` já existentes em `tests/test_fatura_concessionaria_upload.py` ou `tests/support.py` se já existirem; senão criar versões mínimas locais no novo arquivo de teste.

- [ ] **Step 2: Rodar teste e confirmar falha**

Run: `pytest tests/test_copel_boleto_service.py::test_ucs_copel_elegiveis_ignora_uc_sem_credencial -v`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implementar `ucs_copel_elegiveis`, `competencia_atual`, `ja_tem_fatura_da_competencia_atual`**

- [ ] **Step 4: Rodar teste e confirmar sucesso**

Run: `pytest tests/test_copel_boleto_service.py::test_ucs_copel_elegiveis_ignora_uc_sem_credencial -v`
Expected: PASS

- [ ] **Step 5: Escrever e passar teste de `ja_tem_fatura_da_competencia_atual`**

```python
def test_ja_tem_fatura_da_competencia_atual_true_quando_existe(self):
    uc = self._criar_uc_com_credencial()
    self._criar_fatura_concessionaria(consumer_unit_id=uc.id, competencia=competencia_atual())
    assert ja_tem_fatura_da_competencia_atual(uc) is True

def test_ja_tem_fatura_da_competencia_atual_false_quando_nao_existe(self):
    uc = self._criar_uc_com_credencial()
    assert ja_tem_fatura_da_competencia_atual(uc) is False
```

Run: `pytest tests/test_copel_boleto_service.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 6: Commit**

```bash
git add backend/services/copel_boleto_service.py backend/tests/test_copel_boleto_service.py
git commit -m "feat: adiciona descoberta de UCs Copel elegíveis e checagem de dedup por competência"
```

---

### Task 3: Alerta de falha (e-mail + Pendencia crítica)

**Files:**
- Modify: `backend/services/copel_boleto_service.py`
- Test: `backend/tests/test_copel_boleto_service.py`

**Interfaces:**
- Consumes: `BoletoLoginError` (Task 1), `Pendencia` model, `send_email` de `services/email_service.py`.
- Produces: `def registrar_falha_login(uc: ConsumerUnit, erro: BoletoLoginError) -> None` — seta `g.current_empresa_id = uc.empresa_id`, cria `Pendencia(tipo='erro', categoria='UCs', origem='copel_boleto_download', prioridade='critica', consumer_unit_id=uc.id, client_id=uc.client_id, titulo=..., descricao=..., metadados={'motivo': erro.motivo})` com `db.session.commit()` (envolto em `try/except IntegrityError` + `rollback` pra idempotência, seguindo o padrão de `_registrar_pendencia_erro_processamento`), e chama `send_email(...)` com o e-mail configurado em `Config` (adicionar `COPEL_ALERT_EMAIL = os.getenv('COPEL_ALERT_EMAIL', '')`; se vazio, só loga warning e segue, mesmo espírito de `email_service`).

- [ ] **Step 1: Escrever teste de pendência criada em falha de credencial inválida**

```python
@patch('services.copel_boleto_service.send_email')
def test_registrar_falha_login_cria_pendencia_critica(self, mock_send_email):
    uc = self._criar_uc_com_credencial()
    erro = BoletoLoginError('credencial invalida')
    erro.motivo = 'credencial_invalida'
    registrar_falha_login(uc, erro)
    pendencia = Pendencia.query.filter_by(consumer_unit_id=uc.id, origem='copel_boleto_download').first()
    assert pendencia is not None
    assert pendencia.prioridade == 'critica'
    mock_send_email.assert_called_once()
```

- [ ] **Step 2: Rodar teste e confirmar falha**

Run: `pytest tests/test_copel_boleto_service.py::test_registrar_falha_login_cria_pendencia_critica -v`
Expected: FAIL

- [ ] **Step 3: Implementar `registrar_falha_login` e `Config.COPEL_ALERT_EMAIL`**

Adicionar em `backend/config.py`, junto das outras `os.getenv`: `COPEL_ALERT_EMAIL = os.getenv('COPEL_ALERT_EMAIL', '')`.

- [ ] **Step 4: Rodar teste e confirmar sucesso**

Run: `pytest tests/test_copel_boleto_service.py::test_registrar_falha_login_cria_pendencia_critica -v`
Expected: PASS

- [ ] **Step 5: Escrever e passar teste de idempotência (não duplica pendência na mesma competência)**

```python
def test_registrar_falha_login_nao_duplica_pendencia(self):
    uc = self._criar_uc_com_credencial()
    erro = BoletoLoginError('x'); erro.motivo = 'erro_desconhecido'
    registrar_falha_login(uc, erro)
    registrar_falha_login(uc, erro)
    total = Pendencia.query.filter_by(consumer_unit_id=uc.id, origem='copel_boleto_download').count()
    assert total == 1
```

Run: `pytest tests/test_copel_boleto_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/copel_boleto_service.py backend/config.py backend/tests/test_copel_boleto_service.py
git commit -m "feat: adiciona alerta por email e pendencia critica em falha de login Copel"
```

---

### Task 4: Orquestração ponta a ponta (`processar_uc` + `processar_todas_ucs_copel`)

**Files:**
- Modify: `backend/services/copel_boleto_service.py`
- Test: `backend/tests/test_copel_boleto_service.py`

**Interfaces:**
- Consumes: `ucs_copel_elegiveis`, `ja_tem_fatura_da_competencia_atual`, `registrar_falha_login` (Tasks 2/3), `CopelClient`, `BoletoLoginError` (Task 1), `upload_invoice` de `services/fatura_concessionaria_upload_service.py`.
- Produces: `def processar_uc(uc: ConsumerUnit) -> dict` — retorna `{'ucId': uc.id, 'status': 'pulada' | 'baixada' | 'sem_boleto' | 'falha_login' | 'falha_upload'}`.
- Produces: `def processar_todas_ucs_copel() -> list[dict]` — itera `ucs_copel_elegiveis()`, chama `processar_uc` pra cada, captura qualquer exceção não prevista por UC (loga e segue pra próxima, nunca aborta o loop inteiro).
- Produces internamente: classe `_BoletoFileStorage` (bytes, filename) com `.filename`, `.mimetype = 'application/pdf'`, `.read(n=-1)`, `.seek(0)` — duck-type mínimo que `upload_invoice` espera, sem depender de `werkzeug.FileStorage`.

- [ ] **Step 1: Escrever teste de UC pulada por já ter fatura da competência**

```python
@patch('services.copel_boleto_service.CopelClient')
def test_processar_uc_pula_quando_ja_tem_fatura(self, mock_client_cls):
    uc = self._criar_uc_com_credencial()
    self._criar_fatura_concessionaria(consumer_unit_id=uc.id, competencia=competencia_atual())
    resultado = processar_uc(uc)
    assert resultado['status'] == 'pulada'
    mock_client_cls.assert_not_called()
```

- [ ] **Step 2: Rodar teste e confirmar falha**

Run: `pytest tests/test_copel_boleto_service.py::test_processar_uc_pula_quando_ja_tem_fatura -v`
Expected: FAIL

- [ ] **Step 3: Implementar `processar_uc` (parte dedup + instanciação do client)**

- [ ] **Step 4: Rodar teste e confirmar sucesso**

Run: igual ao Step 1
Expected: PASS

- [ ] **Step 5: Escrever e passar teste de download e upload bem-sucedidos**

```python
@patch('services.copel_boleto_service.upload_invoice')
@patch('services.copel_boleto_service.CopelClient')
def test_processar_uc_baixa_e_envia_para_upload_invoice(self, mock_client_cls, mock_upload_invoice):
    uc = self._criar_uc_com_credencial()
    mock_client = mock_client_cls.return_value
    mock_client.baixar_boleto_competencia_atual.return_value = b'%PDF-1.4 conteudo falso'
    mock_upload_invoice.return_value = ({'invoiceId': 1, 'invoice': {}}, False)
    resultado = processar_uc(uc)
    assert resultado['status'] == 'baixada'
    mock_client.login.assert_called_once_with(uc.documento, ANY)
    mock_upload_invoice.assert_called_once()
    assert mock_upload_invoice.call_args.kwargs['client_id'] == uc.client_id
```

- [ ] **Step 6: Implementar o restante de `processar_uc`** (login, download, `_BoletoFileStorage`, chamada a `upload_invoice`, captura de `BoletoLoginError` → `registrar_falha_login` + status `'falha_login'`, captura de `InvoiceUploadError` → pendência genérica (categoria `'Documentos'`, reaproveitando o padrão de `_registrar_pendencia_erro_processamento`) + status `'falha_upload'`, retorno `'sem_boleto'` quando `baixar_boleto_competencia_atual` retorna `None`)

- [ ] **Step 7: Rodar teste e confirmar sucesso**

Run: `pytest tests/test_copel_boleto_service.py -v`
Expected: PASS (todos)

- [ ] **Step 7b: Escrever e passar teste de falha no `upload_invoice` após download bem-sucedido**

```python
@patch('services.copel_boleto_service.upload_invoice')
@patch('services.copel_boleto_service.CopelClient')
def test_processar_uc_registra_pendencia_quando_upload_invoice_falha(self, mock_client_cls, mock_upload_invoice):
    uc = self._criar_uc_com_credencial()
    mock_client_cls.return_value.baixar_boleto_competencia_atual.return_value = b'%PDF-1.4 x'
    mock_upload_invoice.side_effect = InvoiceUploadError('UC ambigua', 'UC_MATCH_AMBIGUOUS', 409)
    resultado = processar_uc(uc)
    assert resultado['status'] == 'falha_upload'
    pendencia = Pendencia.query.filter_by(consumer_unit_id=uc.id, categoria='Documentos').first()
    assert pendencia is not None
```

O PDF já baixado não é reenviado nem descartado automaticamente nesta etapa — fica só registrado na pendência (`metadados={'erro': str(exc)}`) pra alguém revisar manualmente; repetir o upload sozinho poderia mascarar o motivo real do `InvoiceUploadError` (ex. UC ainda ambígua).

Run: `pytest tests/test_copel_boleto_service.py -v`
Expected: PASS (todos)

- [ ] **Step 8: Escrever e passar teste de `processar_todas_ucs_copel` não abortando no erro de uma UC**

```python
@patch('services.copel_boleto_service.processar_uc')
@patch('services.copel_boleto_service.ucs_copel_elegiveis')
def test_processar_todas_ucs_copel_continua_apos_excecao_de_uma_uc(self, mock_elegiveis, mock_processar_uc):
    uc1, uc2 = Mock(id=1), Mock(id=2)
    mock_elegiveis.return_value = [uc1, uc2]
    mock_processar_uc.side_effect = [RuntimeError('boom'), {'ucId': 2, 'status': 'baixada'}]
    resultados = processar_todas_ucs_copel()
    assert len(resultados) == 2
    assert resultados[0]['status'] == 'erro_inesperado'
    assert resultados[1]['status'] == 'baixada'
```

Run: `pytest tests/test_copel_boleto_service.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/services/copel_boleto_service.py backend/tests/test_copel_boleto_service.py
git commit -m "feat: adiciona orquestracao ponta a ponta de download de boleto Copel por UC"
```

---

### Task 5: Script de entrada para o Task Scheduler

**Files:**
- Create: `backend/scripts/copel_boleto_downloader.py`
- Test: `backend/tests/test_copel_boleto_downloader_script.py`

**Interfaces:**
- Consumes: `processar_todas_ucs_copel` (Task 4), `create_app` de `backend/app.py`.
- Produces: função `main() -> int` (código de saída: `0` se nenhum resultado teve status de falha, `1` se algum teve `'falha_login'`, `'falha_upload'` ou `'erro_inesperado'`) chamada em `if __name__ == '__main__': sys.exit(main())`.

- [ ] **Step 1: Escrever teste de `main()` retornando 0 quando tudo ok**

```python
@patch('scripts.copel_boleto_downloader.processar_todas_ucs_copel')
def test_main_retorna_zero_quando_sem_falhas(self, mock_processar):
    mock_processar.return_value = [{'ucId': 1, 'status': 'baixada'}, {'ucId': 2, 'status': 'pulada'}]
    assert main() == 0
```

- [ ] **Step 2: Rodar teste e confirmar falha**

Run: `pytest tests/test_copel_boleto_downloader_script.py::test_main_retorna_zero_quando_sem_falhas -v`
Expected: FAIL

- [ ] **Step 3: Implementar `scripts/copel_boleto_downloader.py`**

Abre app context com `create_app().app_context()`, chama `processar_todas_ucs_copel()`, loga um resumo (`LogService`) e calcula o código de saída. Incluir no topo do arquivo um comentário com o comando exato de registro no Task Scheduler (`schtasks /create ...`, 3 horários) — é infra do SO, não precisa de automação Python pra isso, só documentar o comando.

- [ ] **Step 4: Rodar teste e confirmar sucesso**

Run: `pytest tests/test_copel_boleto_downloader_script.py::test_main_retorna_zero_quando_sem_falhas -v`
Expected: PASS

- [ ] **Step 5: Escrever e passar teste de `main()` retornando 1 quando há falha**

```python
@patch('scripts.copel_boleto_downloader.processar_todas_ucs_copel')
def test_main_retorna_um_quando_ha_falha_login(self, mock_processar):
    mock_processar.return_value = [{'ucId': 1, 'status': 'falha_login'}]
    assert main() == 1
```

Run: `pytest tests/test_copel_boleto_downloader_script.py -v`
Expected: PASS

- [ ] **Step 6: Rodar a suíte completa do backend**

Run: `pytest`
Expected: PASS (nenhuma regressão nos testes existentes)

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/copel_boleto_downloader.py backend/tests/test_copel_boleto_downloader_script.py
git commit -m "feat: adiciona script de entrada do download de boleto Copel para o Task Scheduler"
```
