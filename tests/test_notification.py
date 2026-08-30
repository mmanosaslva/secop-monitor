import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from src.notifications.email import EmailNotification


def test_email_send_success():
    process = {
        "id": "CO1.REQ.1234567",
        "entity_name": "Alcaldia de Barranquilla",
        "name": "Suministro de uniformes",
        "department": "Atlantico",
        "city": "Barranquilla",
        "base_price": 50000000,
        "publication_date": "2026-08-29",
        "deadline": "2026-09-15",
        "contract_type": "Suministros",
        "modality": "Licitacion publica",
        "url": "https://community.secop.gov.co/...",
    }

    mock_response = MagicMock()
    mock_response.status_code = 201

    with patch("src.notifications.email.httpx.Client") as mock_client:
        mock_client.return_value.__enter__ = lambda s: s
        mock_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.return_value.post.return_value = mock_response

        with patch("src.notifications.email.BREVO_API_KEY", "test-key"):
            emailer = EmailNotification()
            result = emailer.send(process, "test@example.com")
            assert result == (True, None)


def test_email_send_failure():
    process = {"id": "CO1.REQ.1234567", "name": "Test"}

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    with patch("src.notifications.email.httpx.Client") as mock_client:
        mock_client.return_value.__enter__ = lambda s: s
        mock_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.return_value.post.return_value = mock_response

        with patch("src.notifications.email.BREVO_API_KEY", "test-key"):
            emailer = EmailNotification()
            result = emailer.send(process, "test@example.com")
            assert result[0] is False
            assert "status=400" in result[1]
