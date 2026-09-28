# Mix Moda Insights

Aplicativo desktop em Python/PySide6 para cruzar estoque e vendas da Mix Moda.

## Regras
- Estoque é a base da análise.
- Vendas somente entram com código e descrição correspondentes ao estoque.
- Descrições iniciadas por `codigo desativado`, `peça` ou `peca` são removidas.
- O catálogo JSON é somente a dimensão oficial de grupo/subclasse; quantidades e preços atuais vêm das planilhas.
- Os arquivos originais nunca são alterados.

## Colunas
Estoque: A código, B descrição, D quantidade, E compra, G venda.
Vendas: A código, B descrição, C quantidade vendida.

## Executar
`python -m pip install -r requirements.txt`
`python app.py`

## EXE
Execute `build.bat`. O resultado será `dist\MixModaInsights.exe`.

## Regras comerciais e classificação atualizadas
- Preço de venda calculado como **2x o preço de compra** para todos os produtos.
- Faturamento do período = preço de venda × quantidade vendida.
- O arquivo `data/estoque_geral_classificacao.json` foi gerado a partir da planilha `estoque geral(4).xlsx` enviada pelo usuário e é a referência de grupo/subclasse por loja + código + descrição.
- Explorador hierárquico: **Grupo → Subclasse → Produto → Detalhes**.
