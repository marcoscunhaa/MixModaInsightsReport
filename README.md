# Mix Moda Insights

Desktop app in Python/PySide6 that matches stock and sales data for the Mix Moda retail chain.

## Rules
- Stock is the base of the analysis.
- Sales only count when their barcode and description match a stock item.
- Rows whose description starts with `codigo desativado` (disabled code), `peça` or `peca` (loose part) are removed.
- The JSON catalog is only the official group/subclass dimension; current quantities and prices come from the spreadsheets.
- The original spreadsheets are never modified. The JSON catalog only changes through the **Explore stock** screen.

## Columns

When generating the analysis, the app checks column C: in the stock file it holds the unit (e.g. UN) and in the sales file it holds the quantity. If the files are swapped, the analysis stops with a warning.

Stock: A barcode, B description, D quantity, E purchase price, F sale price (current price).
Sales: A barcode, B description, C quantity sold, D purchase price, E total cost, F sale price, G revenue (C × F), H profit.

The exports carry numbers with a time format (`h:mm AM/PM`); the reader converts those values back to numbers.

> The source spreadsheets come from a Brazilian point-of-sale system, so headers, product descriptions and amounts (BRL) are in their original form. The currency symbol shown in the app is set in `utils/formatting.py`.

## Run
`python -m pip install -r requirements.txt`
`python app.py`

Catalog tests: `python -m pip install pytest` and `python -m pytest tests`.

## EXE
On Windows, run `build.bat`. The output is `dist\MixModaInsights.exe`.

For a faster startup, build the **folder version**: `build.bat folder` creates `dist\MixModaInsights\` with `MixModaInsights.exe` inside. The single-file build (`build.bat`) has to extract ~200 MB to the temp folder every time it opens, which takes several seconds (more on laptops with an HDD or active antivirus); the folder version skips that step. Distribute the whole folder (CI produces `MixModaInsights-folder.zip`). Both versions show a splash screen while loading.

No Windows machine at hand? GitHub Actions builds the `.exe` on every push (workflow `.github/workflows/build-windows.yml`). It runs the tests, runs `build.bat` on a Windows runner and leaves the files under **Actions → run → Artifacts**: **MixModaInsights-folder** (recommended) and **MixModaInsights-exe** (kept for 30 days). When a `v*` tag is created (e.g. `v1.0`), the `.exe` is also published under **Releases**. It can also be triggered manually from **Actions → Build Windows .exe → Run workflow**.

## Pricing and classification rules
- Products sold in the period use prices from the sales spreadsheet: **purchase price = column D**, **sale price = column F** and **revenue = sum of column G**. When the same product appears on several rows with different prices, revenue is summed and the price becomes the quantity-weighted average.
- In that case, the product card shows the **Sale prices in the period** panel, with each price, its quantity and revenue, plus the total; the card shows the current **sale price** (column F of the stock spreadsheet, matched by barcode) and, next to it, the period's **average sale price**, which is used for margins.
- Products with no sales in the period use the **current sale price from the stock spreadsheet (column F)**. The 2x purchase price rule only applies when that column is empty.
- Stock value is still quantity in stock × purchase price from the stock spreadsheet.
- The official classification by store + barcode + description is built into `data/catalogo_produtos_estoque_geral.json`.
- The analysis lets you select up to five stores, each one once: Sitio São João, Palmeiras, Sapiranga, Pedras and Mix Cosméticos. The list lives in `core/stores.py` and is used by every store selector.
- Hierarchical explorer: **Group → Subclass → Product → Details**.

## Critical stock alerts

- Search products by name or barcode; the list suggests fuzzy matches from the official catalog.
- Each rule sets a minimum number of units (the alert fires at that number or below). Stores are picked with checkboxes: **All stores** or one or more specific stores (each checked store becomes one rule). When editing a rule and unchecking its store, the old rule is removed.
- Rules are saved in `data/stock_alert_rules.json`; the latest analysis is saved in `data/stock_alert_snapshot.json`.
- The rule's product is found by barcode; the description only breaks ties when the same barcode appears with more than one description in the store. This way the rule still applies if the store's spreadsheet uses a different description than the catalog.
- On the dashboard, the alerts button shows how many products reached their rules and opens the list with barcode, store, quantity and sale price, exportable to Excel.

## Explore stock (create, edit and delete)

- On the home screen, **EXPLORE STOCK** opens the catalog products as cards: **Group → Subclass → Product**, with search by description or barcode.
- **＋ NEW PRODUCT** adds a product; inside a group/subclass those fields come pre-filled.
- Clicking a product opens the form to edit barcode, description, group, subclass, status and which stores carry it, or to delete the product. Quantities and prices are not edited here: they come from the spreadsheets imported in the analysis.
- Every change is written immediately to `data/catalogo_produtos_estoque_geral.json`; the previous version is kept in `catalogo_produtos_estoque_geral.json.bak`. The `meta` totals are recalculated.
- Each store's description is preserved when it differs from the general description, because sales matching uses store + barcode + description. When the general description changes, only the stores that used the same description follow it.
- Barcodes that become the same number without leading zeros are blocked for new products.
- On startup, the app validates the catalog. If the JSON is invalid (e.g. edited by hand), it explains the problem and offers to restore the `.bak` or, in the executable, the original bundled catalog. The broken file is kept as `catalogo_produtos_estoque_geral.corrupted-<date-time>.json`.
- In the executable, the bundled catalog is copied on first run to the `data` folder next to the `.exe` (or to the user's data folder) and edits go to that copy. A newer `.exe` with an updated catalog does not overwrite that copy; to start over from the bundled catalog, delete it.

## Dashboard: zero or negative stock

- Stock statuses: **NEGATIVE** (stock below zero, sold without a stock receipt in the system) and **OUT OF STOCK** (stock equal to zero, with or without sales). Both appear in the status filter.
- With one of those statuses selected, clicking the **Stock value** KPI lists those products, from most negative to zero, with stock, sales, price, revenue and status. Clicking a row opens the product card.

## Dashboard: KPIs and status

- Each KPI shows an emoji, a name, a value and a sentence explaining the number (e.g. "59% of products did not sell"). Stockouts, Critical stock and No sales turn red/amber when there are cases and green with ✓ when there are none. Cards with "See list ›" open the products.
- Stock status is picked from pills showing the count for each status (Negative, Out of stock, Critical, Low, No sales, Excess, Normal); hovering shows each rule. Counts follow the other filters.

## Dashboard: lists by store

- Every KPI with **See list ›** opens as product × store: one row per product, one column per store, the product total and a total row per store, with a chip for each store at the top. Clicking a store opens the product card for that store.
- Each cell's number depends on the KPI: **Revenue** (sales value, column G), **Stock value** (stock cost), **Units in stock**, **Units sold** (period sales), **No sales** (idle units), **Stockouts** (how much sold before running out) and **Critical stock** (units). With the Out of stock or Negative status selected, Stock value lists the zero/negative units.
- Zero is shown in amber and negative in red; "—" means the product is not part of that list at that store (or, for stock, that it is not in the store's spreadsheet).
- In multi-store analyses, the Units in stock KPI also shows the split by store in the card sentence.

## Dashboard: single product

- When the filters leave a single product, the count KPIs show text instead of 0 or 1: **Stockouts** → OUT OF STOCK / NEGATIVE STOCK / IN STOCK; **No sales** → NO SALES / HAS SALES; **Critical stock** → the product's status; **Products analyzed** → 1 PRODUCT.

## Exported PDF

- After **Stock priorities**, the **Idle stock** page lists the 20 products with no sales in the period and the largest quantity in stock (stock, unit cost and idle value), with the total number of products, units and idle value at the top.
