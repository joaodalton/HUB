# Fixture Copel F4

`core_anon.pdf` é uma reconstrução anonimizada dos blocos core e da geometria
observados em uma única fatura real DANF3EA4B V1.06. `build_fixture.py` reproduz
o arquivo sem ler o PDF privado. Todos os valores são fictícios; o CNPJ público
da distribuidora é uma âncora do emissor. A chave fiscal fictícia não passa por
validação fiscal nesta sprint. CPF mascarado permanece ilegível.

Não foram copiados imagens, QR/PIX, códigos bancários, metadados ou dados pessoais
do original. A fixture não é uma segunda amostra real nem uma reprodução visual
integral. As variações em memória verificam comportamento estrutural, não
comprovam suporte a outra versão do DANF3E. O campo de quantidade do item difere
intencionalmente do consumo do medidor para detectar confusão entre as fontes.

O PDF privado fica ignorado em `private/` e não é necessário para os testes.
Não adicionar seus valores a expected JSON, documentação ou logs.

## Expansão F5

Inclui quatro itens com duas colunas de tarifa, PIS/COFINS e ICMS por item,
quadro de três tributos, 13 competências históricas, medidor e quatro avisos.
Valores continuam fictícios e deliberadamente não precisam fechar por fórmula:
o teste comprova leitura, não cálculo. Células vazias no item de iluminação
foram preservadas; não inserir zeros. `core_anon.expected.json` cobre os campos
novos e mantém o Core F4. Histórico conserva labels documentais de mês/ano.

O gerador aceita variações em memória para testar labels desconhecidos,
valores ilegíveis, lacunas de histórico e deslocamento. Labels adversariais de
GD/crédito nesses testes não são evidência de um layout GD real. Não há segunda
amostra real e não se declara suporte a energia compensada/injetada ou saldos.

## F6 parcial

PDF e gerador não alterados. Expected ampliado com três componentes documentais
já presentes: consumed para ENERGIA ELET CONSUMO e other para USO SISTEMA e
B.AMARELA. Consumo do medidor permanece independente. Campos GD-I/GD-II,
injeção, compensação e saldo continuam not_present com aviso de suporte ausente.
Isso não comprova ausência de GD na instalação. Não existe fixture GD real;
os casos adversariais do teste F6 não são evidência de um novo layout.
Descobertas e exemplos documentais faltantes em FATURAS_E_COBRANCAS.md, F6.
