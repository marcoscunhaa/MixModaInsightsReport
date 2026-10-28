"""Persist stock-alert rules and the latest stock snapshot."""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from utils.normalization import normalize_barcode, normalize_text


class StockAlertStore:
    def __init__(self, rules_path, snapshot_path):
        self.rules_path = Path(rules_path)
        self.snapshot_path = Path(snapshot_path)
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.rules_path.exists():
            self._write_document({"version": 1, "rules": []})

    @staticmethod
    def _read_json(path, default):
        try:
            with Path(path).open(encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, json.JSONDecodeError):
            return default

    @staticmethod
    def _atomic_write(path, payload):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temp_path, path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _read_document(self):
        payload = self._read_json(self.rules_path, {})
        if isinstance(payload, list):
            return {"version": 1, "rules": payload}
        if not isinstance(payload, dict):
            return {"version": 1, "rules": []}
        rules = payload.get("rules", [])
        return {
            "version": int(payload.get("version", 1)),
            "rules": rules if isinstance(rules, list) else [],
        }

    def _write_document(self, payload):
        self._atomic_write(self.rules_path, payload)

    def load_rules(self):
        rules = [dict(rule) for rule in self._read_document()["rules"] if isinstance(rule, dict)]
        migrated = False
        for rule in rules:
            if "estoque_maximo" in rule:
                # Preserve the previous upper limit as the new single low-stock threshold.
                try:
                    rule["estoque_minimo"] = int(rule.get("estoque_maximo", rule.get("estoque_minimo", 0)))
                except (TypeError, ValueError):
                    rule["estoque_minimo"] = 0
                rule.pop("estoque_maximo", None)
                migrated = True
        if migrated:
            self.save_rules(rules)
        return rules

    def save_rules(self, rules):
        self._write_document({"version": 1, "rules": rules})

    def upsert_rule(self, rule):
        barcode = normalize_barcode(rule.get("codigo_barras"))
        description = str(rule.get("descricao", "")).strip()
        store = str(rule.get("loja", "*")).strip() or "*"
        minimum = int(rule.get("estoque_minimo", 0))
        if not barcode or not description:
            raise ValueError("A regra precisa de produto e código de barras.")
        if minimum < 0:
            raise ValueError("O limite de estoque precisa ser igual ou maior que zero.")

        rules = self.load_rules()
        identity = (barcode, normalize_text(description), normalize_text(store))
        existing = next(
            (
                item for item in rules
                if (
                    normalize_barcode(item.get("codigo_barras")),
                    normalize_text(item.get("descricao")),
                    normalize_text(item.get("loja", "*")),
                ) == identity
            ),
            None,
        )
        saved = {
            "id": existing.get("id") if existing else uuid4().hex,
            "codigo_barras": barcode,
            "descricao": description,
            "loja": store,
            "estoque_minimo": minimum,
            "ativa": True,
        }
        if existing:
            rules[rules.index(existing)] = saved
        else:
            rules.append(saved)
        self.save_rules(rules)
        return saved

    def remove_rule(self, rule_id):
        rules = self.load_rules()
        kept = [rule for rule in rules if str(rule.get("id")) != str(rule_id)]
        if len(kept) != len(rules):
            self.save_rules(kept)
        return kept

    def save_snapshot(self, rows):
        aggregated = {}
        for row in rows:
            barcode = normalize_barcode(row.get("codigo_barras"))
            description = str(row.get("descricao", "")).strip()
            store = str(row.get("loja", "")).strip()
            try:
                quantity = float(row.get("quantidade_estoque", 0) or 0)
                sale_price = float(row.get("preco_venda", 0) or 0)
            except (TypeError, ValueError):
                continue
            if not barcode or not description or not store:
                continue
            key = (barcode, normalize_text(description), normalize_text(store))
            if key not in aggregated:
                aggregated[key] = {
                    "codigo_barras": barcode,
                    "descricao": description,
                    "loja": store,
                    "quantidade_estoque": 0.0,
                    "preco_venda": sale_price,
                }
            aggregated[key]["quantidade_estoque"] += quantity
            aggregated[key]["preco_venda"] = sale_price

        snapshot = {
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "rows": list(aggregated.values()),
        }
        self._atomic_write(self.snapshot_path, snapshot)
        return snapshot

    def load_snapshot(self):
        payload = self._read_json(self.snapshot_path, {})
        if not isinstance(payload, dict):
            return {"updated_at": None, "rows": []}
        rows = payload.get("rows", [])
        return {
            "updated_at": payload.get("updated_at"),
            "rows": rows if isinstance(rows, list) else [],
        }

    def evaluate(self, rows=None):
        rules = [rule for rule in self.load_rules() if rule.get("ativa", True)]
        snapshot = self.load_snapshot() if rows is None else {"rows": rows}
        stock_rows = snapshot.get("rows", [])

        specific = {
            (
                normalize_barcode(rule.get("codigo_barras")),
                normalize_text(rule.get("descricao")),
                normalize_text(rule.get("loja")),
            )
            for rule in rules
            if str(rule.get("loja", "*")) != "*"
        }
        alerts = []
        for rule in rules:
            rule_code = normalize_barcode(rule.get("codigo_barras"))
            rule_description = normalize_text(rule.get("descricao"))
            rule_store = str(rule.get("loja", "*"))
            try:
                minimum = int(rule.get("estoque_minimo", 0))
            except (TypeError, ValueError):
                continue

            for stock in stock_rows:
                if (
                    normalize_barcode(stock.get("codigo_barras")) != rule_code
                    or normalize_text(stock.get("descricao")) != rule_description
                ):
                    continue
                stock_store = str(stock.get("loja", ""))
                if rule_store != "*" and normalize_text(stock_store) != normalize_text(rule_store):
                    continue
                if rule_store == "*" and (
                    rule_code,
                    rule_description,
                    normalize_text(stock_store),
                ) in specific:
                    continue
                try:
                    quantity = float(stock.get("quantidade_estoque", 0))
                except (TypeError, ValueError):
                    continue
                if quantity <= minimum:
                    alerts.append({
                        "rule_id": str(rule.get("id", "")),
                        "codigo_barras": rule_code,
                        "descricao": stock.get("descricao") or rule.get("descricao", ""),
                        "loja": stock_store,
                        "quantidade_estoque": quantity,
                        "preco_venda": float(stock.get("preco_venda", 0) or 0),
                        "estoque_minimo": minimum,
                    })

        return sorted(alerts, key=lambda item: (normalize_text(item["loja"]), normalize_text(item["descricao"])))

