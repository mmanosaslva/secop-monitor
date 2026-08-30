import httpx
import structlog
from typing import Dict
from .base import NotificationChannel
from ..config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME

logger = structlog.get_logger()


class EmailNotification(NotificationChannel):
    def __init__(self):
        self.api_key = BREVO_API_KEY
        self.sender = {"name": SENDER_NAME, "email": SENDER_EMAIL}

    def _format_html(self, process: Dict) -> str:
        price = process.get("base_price", 0)
        price_str = f"${price:,.0f} COP" if price else "No definido"
        deadline = process.get("deadline") or "No definida"
        pub_date = process.get("publication_date") or "No definida"

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1a56db; margin-bottom: 20px;">Nueva Oportunidad SECOP II</h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Entidad</td>
                    <td style="padding: 10px 0; color: #111827;">{process.get('entity_name', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Objeto</td>
                    <td style="padding: 10px 0; color: #111827;">{process.get('name', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Ubicacion</td>
                    <td style="padding: 10px 0; color: #111827;">{process.get('city', '')}, {process.get('department', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Valor base</td>
                    <td style="padding: 10px 0; color: #111827;">{price_str}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Fecha publicacion</td>
                    <td style="padding: 10px 0; color: #111827;">{pub_date}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Fecha limite</td>
                    <td style="padding: 10px 0; color: #111827;">{deadline}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Tipo contrato</td>
                    <td style="padding: 10px 0; color: #111827;">{process.get('contract_type', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">Modalidad</td>
                    <td style="padding: 10px 0; color: #111827;">{process.get('modality', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px 0; font-weight: bold; color: #374151;">ID Proceso</td>
                    <td style="padding: 10px 0; color: #111827;">{process.get('id', '')}</td>
                </tr>
            </table>
            <a href="{process.get('url', '#')}"
               style="display: inline-block; padding: 12px 24px; background: #1a56db; color: white; text-decoration: none; border-radius: 6px; font-weight: bold;">
                Ver Proceso en SECOP II
            </a>
        </div>
        """

    def send(self, process: Dict, recipient: str):
        if not self.api_key:
            logger.error("brevo_api_key_missing")
            return False, "api_key_missing"

        subject = f"Nueva oportunidad: {process.get('name', '')[:80]}"
        html = self._format_html(process)

        payload = {
            "sender": self.sender,
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html,
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": self.api_key, "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code in (200, 201, 202):
                    logger.info("email_sent", process_id=process["id"], recipient=recipient)
                    return True, None
                else:
                    error_msg = f"status={resp.status_code} body={resp.text[:200]}"
                    logger.error("email_failed", status=resp.status_code, body=resp.text[:200])
                    return False, error_msg
        except Exception as e:
            logger.error("email_exception", error=str(e))
            return False, str(e)
