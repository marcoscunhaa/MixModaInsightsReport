"""Official WhatsApp Cloud API sender for critical stock alerts."""
import re

import requests

from core.stock_alerts import StockAlertStore


GRAPH_API_VERSION = "v26.0"
MAX_TEMPLATE_PARAMETER_CHARS = 900


class WhatsAppConfigurationError(ValueError):
    pass


class WhatsAppSendError(RuntimeError):
    pass


def _brl(value):
    formatted = f"{float(value):,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _format_item(alert):
    quantity = f"{float(alert.get('quantidade_estoque', 0)):g}"
    description = str(alert.get("descricao", "Produto"))[:140]
    price = _brl(alert.get("preco_venda", 0))
    return (
        f"• {description}\n"
        f"Código: {alert.get('codigo_barras', '')}\n"
        f"Preço de venda: {price}\n"
        f"Unidades em estoque: {quantity} ({alert.get('loja', '')})"
    )


def _message_chunks(alerts):
    header = "Mix Moda | Estoque crítico\n\n"
    chunks = []
    current = header
    for alert in alerts:
        item = _format_item(alert)
        candidate = current + item + "\n\n"
        if len(candidate) > MAX_TEMPLATE_PARAMETER_CHARS and current != header:
            chunks.append(current.rstrip())
            current = header + item + "\n\n"
        else:
            current = candidate
    if current.strip() != header.strip():
        chunks.append(current.rstrip())
    return chunks


class WhatsAppCloudClient:
    """Sends one or more approved utility-template messages through Meta Cloud API."""

    def __init__(self, alert_store: StockAlertStore):
        self.alert_store = alert_store

    def missing_configuration(self):
        settings = self.alert_store.load_settings()
        missing = []
        if not settings.get("whatsapp_recipient"):
            missing.append("número de WhatsApp destinatário")
        if not settings.get("phone_number_id"):
            missing.append("Phone Number ID da Meta")
        if not self.alert_store.get_access_token():
            missing.append("token de acesso da Meta")
        if not settings.get("template_name"):
            missing.append("nome do template aprovado")
        return missing

    def send_stock_alerts(self, alerts):
        if not alerts:
            return []
        missing = self.missing_configuration()
        if missing:
            raise WhatsAppConfigurationError(
                "Configure: " + ", ".join(missing) + "."
            )

        settings = self.alert_store.load_settings()
        recipient = re.sub(r"\D", "", settings["whatsapp_recipient"])
        phone_number_id = re.sub(r"\D", "", settings["phone_number_id"])
        if not 10 <= len(recipient) <= 15 or not phone_number_id:
            raise WhatsAppConfigurationError(
                "Confira o número destinatário e o Phone Number ID da Meta."
            )

        token = self.alert_store.get_access_token()
        template_name = settings["template_name"]
        language = settings.get("template_language", "pt_BR")
        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        message_ids = []
        for text in _message_chunks(alerts):
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language},
                    "components": [{
                        "type": "body",
                        "parameters": [{"type": "text", "text": text}],
                    }],
                },
            }
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=(5, 20))
            except requests.RequestException as error:
                raise WhatsAppSendError(
                    "Não foi possível conectar à API do WhatsApp. Verifique a conexão e tente novamente."
                ) from error

            try:
                body = response.json()
            except ValueError:
                body = {}

            if not response.ok:
                api_error = body.get("error", {}) if isinstance(body, dict) else {}
                message = api_error.get("message") or f"Resposta HTTP {response.status_code}."
                raise WhatsAppSendError(f"A Meta recusou o envio: {message}")

            messages = body.get("messages", []) if isinstance(body, dict) else []
            if not messages:
                raise WhatsAppSendError("A API não confirmou o recebimento da mensagem.")
            message_ids.extend(item.get("id", "") for item in messages if item.get("id"))

        return message_ids
