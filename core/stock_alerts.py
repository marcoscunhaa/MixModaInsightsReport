"""Persistent rules, WhatsApp settings, and stock snapshots for low-stock alerts."""
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from utils.normalization import normalize_barcode, normalize_text


KEYRING_SERVICE = "MixModaInsights.WhatsAppCloudAPI"
KEYRING_ACCOUNT = "access_token"


class StockAlertStore:
    def __init__(self, rules_path, snapshot_path):
        self.rules_path = Path(rules_path)
        self.snapshot_path = Path(snapshot_path)
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.rules_path.exists():
            self._write_document({"version": 1, "settings": {}, "rules": []})

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
            return {"version": 1, "settings": {}, "rules": payload}
        if not isinstance(payload, dict):
            return {"version": 1, "settings": {}, "rules": []}
        rules = payload.get("rules", [])
        settings = payload.get("settings", {})
        return {
            "version": int(payload.get("version", 1)),
            "settings": settings if isinstance(settings, dict) else {},
            "rules": rules if isinstance(rules, list) else [],
        }

    def _write_document(self, payload):
        self._atomic_write(self.rules_path, payload)

    def load_rules(self):
        return [rule for rule in self._read_document()["rules"] if isinstance(rule, dict)]

    def save_rules(self, rules):
        document = self._read_document()
        document["rules"] = rules
        self._write_document(document)

    def load_settings(self):
        return dict(self._read_document()["settings"])

    def save_settings(self, settings, access_token=None):
        settings = dict(settings or {})
        recipient_raw = str(settings.get("whatsapp_recipient", "")).strip()
        recipient = re.sub(r"\D", "", recipient_raw)
        if recipient and not 10 <= len(recipient) <= 15:
            raise ValueError("Informe o número de WhatsApp com código do país e DDD.")
        phone_number_id = re.sub(r"\D", "", str(settings.get("phone_number_id", "")).strip())
        if settings.get("phone_number_id") and not phone_number_id:
            raise ValueError("O Phone Number ID deve conter apenas números.")
        settings["whatsapp_recipient"] = recipient
        settings["phone_number_id"] = phone_number_id
        settings["template_name"] = str(settings.get("template_name", "")).strip()
        settings["template_language"] = str(settings.get("template_language", "pt_BR")).strip() or "pt_BR"

        if access_token and str(access_token).strip():
            self.set_access_token(str(access_token).strip())

        document = self._read_document()
        document["settings"] = settings
        self._write_document(document)
        return settings

    @staticmethod
    def set_access_token(token):
        try:
            import keyring
            backend = keyring.get_keyring()
            if getattr(backend, "priority", 0) <= 0:
                raise RuntimeError("O cofre de credenciais do sistema não está disponível.")
            keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, token)
        except Exception as error:
            raise RuntimeError(
                "Não foi possível salvar o token no cofre de credenciais do sistema. "
                "Verifique se o gerenciador de credenciais do computador está ativo."
            ) from error

    @staticmethod
    def get_access_token():
        token = os.environ.get("MIXMODA_WA_ACCESS_TOKEN", "").strip()
        if token:
            return token
        try:
            import keyring
            return keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception:
            return None

    def has_access_token(self):
        return bool(self.get_access_token())

    def upsert_rule(self, rule):
        barcode = normalize_barcode(rule.get("codigo_barras"))
        description = str(rule.get("descricao", "")).strip()
        store = str(rule.get("loja", "*")).strip() or "*"
        minimum = int(rule.get("estoque_minimo", 0))
        maximum = int(rule.get("estoque_maximo", 0))
        if not barcode or not description:
            raise ValueError("A regra precisa de produto e código de barras.")
        if minimum < 0 or maximum < minimum:
            raise ValueError("A faixa de estoque informada é inválida.")

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
            "estoque_maximo": maximum,
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

        previous = self.load_snapshot()
        snapshot = {
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "rows": list(aggregated.values()),
            "sent_alerts": previous.get("sent_alerts", {}),
        }
        self._atomic_write(self.snapshot_path, snapshot)
        return snapshot

    def load_snapshot(self):
        payload = self._read_json(self.snapshot_path, {})
        if not isinstance(payload, dict):
            return {"updated_at": None, "rows": [], "sent_alerts": {}}
        rows = payload.get("rows", [])
        sent = payload.get("sent_alerts", {})
        return {
            "updated_at": payload.get("updated_at"),
            "rows": rows if isinstance(rows, list) else [],
            "sent_alerts": sent if isinstance(sent, dict) else {},
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
                maximum = int(rule.get("estoque_maximo", 0))
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
                if minimum <= quantity <= maximum:
                    alerts.append({
                        "rule_id": str(rule.get("id", "")),
                        "codigo_barras": rule_code,
                        "descricao": stock.get("descricao") or rule.get("descricao", ""),
                        "loja": stock_store,
                        "quantidade_estoque": quantity,
                        "preco_venda": float(stock.get("preco_venda", 0) or 0),
                        "estoque_minimo": minimum,
                        "estoque_maximo": maximum,
                    })

        return sorted(alerts, key=lambda item: (normalize_text(item["loja"]), normalize_text(item["descricao"])))

    @staticmethod
    def _alert_key(alert):
        return "|".join((
            str(alert.get("rule_id", "")),
            normalize_barcode(alert.get("codigo_barras")),
            normalize_text(alert.get("descricao")),
            normalize_text(alert.get("loja")),
        ))

    @staticmethod
    def _alert_signature(alert):
        return "|".join((
            f"{float(alert.get('quantidade_estoque', 0)):g}",
            str(int(alert.get("estoque_minimo", 0))),
            str(int(alert.get("estoque_maximo", 0))),
        ))

    def unsent_alerts(self, alerts):
        snapshot = self.load_snapshot()
        previous = snapshot.get("sent_alerts", {})
        current_keys = {self._alert_key(alert) for alert in alerts}
        previous = {key: value for key, value in previous.items() if key in current_keys}
        pending = [
            alert for alert in alerts
            if previous.get(self._alert_key(alert)) != self._alert_signature(alert)
        ]
        snapshot["sent_alerts"] = previous
        self._atomic_write(self.snapshot_path, snapshot)
        return pending

    def mark_alerts_sent(self, alerts):
        if not alerts:
            return
        snapshot = self.load_snapshot()
        sent = snapshot.get("sent_alerts", {})
        for alert in alerts:
            sent[self._alert_key(alert)] = self._alert_signature(alert)
        snapshot["sent_alerts"] = sent
        snapshot["last_alert_sent_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self._atomic_write(self.snapshot_path, snapshot)
