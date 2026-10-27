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
- A classificação oficial por loja + código + descrição está incorporada em `data/catalogo_produtos_estoque_geral.json`.
- A análise permite selecionar até quatro lojas, uma vez cada: Sitio São João, Palmeiras, Sapiranga e Pedras.
- Explorador hierárquico: **Grupo → Subclasse → Produto → Detalhes**.

## Alertas de estoque crítico

- Pesquise produtos pelo nome ou código de barras; a lista sugere resultados aproximados do catálogo oficial.
- Cada regra define uma faixa de unidades e pode valer para uma loja ou para todas.
- As regras e o número de destino ficam em \`data/stock_alert_rules.json\`. O token da Meta fica no cofre de credenciais do sistema.
- O último estoque analisado fica em \`data/stock_alert_snapshot.json\` para avaliar alertas ao abrir o aplicativo.
- Para envio automático, configure a integração oficial WhatsApp Business Cloud API no aplicativo: Phone Number ID, token de acesso, nome e idioma de um template Utility aprovado e número destinatário. O template precisa ter um único campo de texto no corpo (\`{{1}}\`), e o destinatário deve ter autorizado as mensagens.
