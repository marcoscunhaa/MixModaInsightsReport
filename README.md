# Mix Moda Insights

Aplicativo desktop em Python/PySide6 para cruzar estoque e vendas da Mix Moda.

## Regras
- Estoque é a base da análise.
- Vendas somente entram com código e descrição correspondentes ao estoque.
- Descrições iniciadas por `codigo desativado`, `peça` ou `peca` são removidas.
- O catálogo JSON é somente a dimensão oficial de grupo/subclasse; quantidades e preços atuais vêm das planilhas.
- As planilhas originais nunca são alteradas. O catálogo JSON só muda pela tela **Explorar estoque**.

## Colunas
Estoque: A código, B descrição, D quantidade, E compra, G venda.
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
- Produtos sem venda no período mantêm a regra: preço de venda = **2x o preço de compra** do estoque.
- O valor em estoque continua sendo quantidade em estoque × preço de compra da planilha de estoque.
- A classificação oficial por loja + código + descrição está incorporada em `data/catalogo_produtos_estoque_geral.json`.
- A análise permite selecionar até cinco lojas, uma vez cada: Sitio São João, Palmeiras, Sapiranga, Pedras e Mix Cosméticos. A lista fica em `core/stores.py` e é usada em todos os seletores de loja.
- Explorador hierárquico: **Grupo → Subclasse → Produto → Detalhes**.

## Alertas de estoque crítico

- Pesquise produtos pelo nome ou código de barras; a lista sugere resultados aproximados do catálogo oficial.
- Cada regra define um limite mínimo de unidades (o alerta aparece nesse número ou abaixo) e pode valer para uma loja ou para todas.
- As regras ficam salvas em `data/stock_alert_rules.json`; a última análise fica em `data/stock_alert_snapshot.json`.
- Na dashboard, o ícone de alertas destaca quantos produtos atingiram as regras e abre a relação com código, loja, quantidade e preço de venda.

## Explorar estoque (cadastro, edição e exclusão)

- No menu inicial, **EXPLORAR ESTOQUE** abre os produtos do catálogo em cards: **Grupo → Subclasse → Produto**, com busca por descrição ou código.
- **＋ NOVO PRODUTO** cadastra um produto; dentro de um grupo/subclasse eles já vêm preenchidos.
- Clicar num produto abre o formulário para editar código, descrição, grupo, subclasse, situação e em quais lojas ele existe, ou excluir o produto. Quantidades e preços não são editados aqui: vêm das planilhas importadas na análise.
- Cada alteração é gravada na hora em `data/catalogo_produtos_estoque_geral.json`; a versão anterior fica em `catalogo_produtos_estoque_geral.json.bak`. Os totais do `meta` são recalculados.
- A descrição de cada loja é preservada quando difere da descrição geral, porque o cruzamento com as vendas usa loja + código + descrição. Ao trocar a descrição geral, só as lojas que usavam a mesma descrição acompanham.
- Códigos que viram o mesmo número sem os zeros à esquerda são bloqueados em produtos novos.
- No executável, o catálogo embutido é copiado na primeira execução para a pasta `data` ao lado do `.exe` (ou para a pasta de dados do usuário) e as edições vão para essa cópia. Um `.exe` novo com catálogo atualizado não sobrescreve essa cópia; para recomeçar do catálogo embutido, apague-a.
