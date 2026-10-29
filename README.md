# Mix Moda Insights

Aplicativo desktop em Python/PySide6 para cruzar estoque e vendas da Mix Moda.

## Regras
- Estoque é a base da análise.
- Vendas somente entram com código e descrição correspondentes ao estoque.
- Descrições iniciadas por `codigo desativado`, `peça` ou `peca` são removidas.
- O catálogo JSON é somente a dimensão oficial de grupo/subclasse; quantidades e preços atuais vêm das planilhas.
- As planilhas originais nunca são alteradas. O catálogo JSON só muda pela tela **Explorar estoque**.

## Colunas

Ao gerar a análise, o app confere a coluna C: no estoque ela é a unidade (ex.: UN) e nas vendas é a quantidade. Se os arquivos estiverem trocados, a análise é interrompida com um aviso.

Estoque: A código, B descrição, D quantidade, E compra, F venda (preço atual).
Vendas: A código, B descrição, C quantidade vendida, D preço de compra, E custo total, F preço de venda, G faturamento (C × F), H lucro.

As extrações trazem números com formato de hora (`h:mm AM/PM`); a leitura converte esses valores de volta para número.

## Executar
`python -m pip install -r requirements.txt`
`python app.py`

Testes do catálogo: `python -m pip install pytest` e `python -m pytest tests`.

## EXE
Execute `build.bat`. O resultado será `dist\MixModaInsights.exe`.

## Regras comerciais e classificação atualizadas
- Produtos vendidos no período usam os preços da planilha de vendas: **preço de compra = coluna D**, **preço de venda = coluna F** e **faturamento = soma da coluna G**. Quando o mesmo produto aparece em várias linhas com preços diferentes, o faturamento é somado e o preço vira a média ponderada pela quantidade.
- Nesse caso, o card do produto mostra o quadro **Valores de venda no período**, com cada preço, a quantidade e o faturamento daquele preço, e o total; o card mostra o **preço de venda** atual (coluna F da planilha de estoque, cruzada pelo código) e, ao lado, o **preço de venda médio** do período, usado nas margens.
- Produtos sem venda no período usam o **preço de venda atual da planilha de estoque (coluna F)**. A regra de 2x o preço de compra só vale quando essa coluna vier vazia.
- O valor em estoque continua sendo quantidade em estoque × preço de compra da planilha de estoque.
- A classificação oficial por loja + código + descrição está incorporada em `data/catalogo_produtos_estoque_geral.json`.
- A análise permite selecionar até cinco lojas, uma vez cada: Sitio São João, Palmeiras, Sapiranga, Pedras e Mix Cosméticos. A lista fica em `core/stores.py` e é usada em todos os seletores de loja.
- Explorador hierárquico: **Grupo → Subclasse → Produto → Detalhes**.

## Alertas de estoque crítico

- Pesquise produtos pelo nome ou código de barras; a lista sugere resultados aproximados do catálogo oficial.
- Cada regra define um limite mínimo de unidades (o alerta aparece nesse número ou abaixo). As lojas são marcadas em caixas de seleção: **Todas as lojas** ou uma ou mais lojas específicas (cada loja marcada vira uma regra). Ao editar uma regra e desmarcar a loja dela, a regra antiga é removida.
- As regras ficam salvas em `data/stock_alert_rules.json`; a última análise fica em `data/stock_alert_snapshot.json`.
- O produto da regra é encontrado pelo código de barras; a descrição só desempata quando o mesmo código aparece com mais de uma descrição na loja. Assim a regra continua valendo se a planilha da loja usa outra descrição que o catálogo.
- Na dashboard, o ícone de alertas destaca quantos produtos atingiram as regras e abre a relação com código, loja, quantidade e preço de venda.

## Explorar estoque (cadastro, edição e exclusão)

- No menu inicial, **EXPLORAR ESTOQUE** abre os produtos do catálogo em cards: **Grupo → Subclasse → Produto**, com busca por descrição ou código.
- **＋ NOVO PRODUTO** cadastra um produto; dentro de um grupo/subclasse eles já vêm preenchidos.
- Clicar num produto abre o formulário para editar código, descrição, grupo, subclasse, situação e em quais lojas ele existe, ou excluir o produto. Quantidades e preços não são editados aqui: vêm das planilhas importadas na análise.
- Cada alteração é gravada na hora em `data/catalogo_produtos_estoque_geral.json`; a versão anterior fica em `catalogo_produtos_estoque_geral.json.bak`. Os totais do `meta` são recalculados.
- A descrição de cada loja é preservada quando difere da descrição geral, porque o cruzamento com as vendas usa loja + código + descrição. Ao trocar a descrição geral, só as lojas que usavam a mesma descrição acompanham.
- Códigos que viram o mesmo número sem os zeros à esquerda são bloqueados em produtos novos.
- Ao abrir, o app valida o catálogo. Se o JSON estiver inválido (ex.: editado à mão), ele avisa o problema e oferece restaurar o `.bak` ou, no executável, o catálogo original embutido. O arquivo com problema é guardado como `catalogo_produtos_estoque_geral.corrompido-<data-hora>.json`.
- No executável, o catálogo embutido é copiado na primeira execução para a pasta `data` ao lado do `.exe` (ou para a pasta de dados do usuário) e as edições vão para essa cópia. Um `.exe` novo com catálogo atualizado não sobrescreve essa cópia; para recomeçar do catálogo embutido, apague-a.

## Dashboard: estoque zerado ou negativo

- Status de estoque: **NEGATIVO** (estoque abaixo de zero, venda sem entrada no sistema) e **SEM ESTOQUE** (estoque igual a zero, com ou sem venda). Os dois aparecem no filtro de status.
- Com um desses status selecionado, clicar no KPI **Valor em estoque** lista esses produtos, dos mais negativos para os zerados, com estoque, vendas, preço, faturamento e status. Um clique na linha abre o card do produto.

## Dashboard: KPIs e status

- Cada KPI mostra emoji, nome, valor e uma frase que explica o número (ex.: "59% dos produtos não venderam"). Em ruptura, Estoque crítico e Sem vendas ficam vermelhos/âmbar quando há casos e verdes com ✓ quando não há. Cards com "Ver lista ›" abrem os produtos.
- O status do estoque é escolhido em pílulas com a contagem de cada status (Negativo, Sem estoque, Crítico, Baixo, Sem venda, Excesso, Normal); passar o mouse mostra a regra de cada um. As contagens seguem os demais filtros.

## Dashboard: listas por loja

- Todo KPI com **Ver lista ›** abre no formato produto × loja: uma linha por produto, uma coluna por loja, o total do produto e uma linha de total por loja, com chips de cada loja no topo. Clicar numa loja abre o card do produto naquela loja.
- O número de cada célula depende do KPI: **Valor em estoque** (R$ do estoque), **Unidades em estoque**, **Unidades vendidas** (vendas do período), **Sem vendas** (unidades paradas), **Em ruptura** (quanto vendeu antes de zerar) e **Estoque crítico** (unidades). Com o status Sem estoque ou Negativo selecionado, o Valor em estoque lista as unidades zeradas/negativas.
- Zerado fica em âmbar e negativo em vermelho; "—" indica que o produto não entra naquela lista naquela loja (ou, no estoque, que não está na planilha da loja).
- Em análises com várias lojas, o KPI Unidades em estoque também mostra a divisão por loja na frase do card.

## Dashboard: produto isolado

- Quando os filtros deixam um único produto, os KPIs de contagem mostram texto em vez de 0 ou 1: **Em ruptura** → SEM ESTOQUE / ESTOQUE NEGATIVO / COM ESTOQUE; **Sem vendas** → SEM VENDAS / COM VENDAS; **Críticos** → o status do produto; **Produtos ativos** → 1 PRODUTO.

## PDF exportado

- Depois de **Prioridades de estoque**, a página **Estoque parado** mostra os 20 produtos sem nenhuma venda no período com a maior quantidade em estoque (estoque, custo unitário e valor parado), com o total de produtos, unidades e valor parado no topo.
