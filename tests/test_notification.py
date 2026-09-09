import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from src.notifications.email import EmailNotification


def make_process(**kwargs):
    defaults = {
        "id": "CO1.REQ.1234567",
        "entity_name": "Alcaldia de Barranquilla",
        "name": "Suministro de uniformes",
        "department": "Atlantico",
        "city": "Barranquilla",
        "base_price": 50000000,
        "publication_date": "2026-08-29",
        "deadline": "2026-09-15",
        "contract_type": "Suministros",
        "modality": "Mínima cuantía",
        "url": "https://community.secop.gov.co/...",
    }
    defaults.update(kwargs)
    return defaults


def test_email_send_success():
    process = make_process()
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


def test_build_badges_minima_cuantia():
    emailer = EmailNotification()
    certs = {"favorece_mujer_lider": False, "favorece_pyme": False, "requiere_equidad_genero": False}
    badges = emailer._build_badges(certs)
    assert "Minima Cuantia" in badges
    assert "Mujer Lider" not in badges
    assert "Equidad de Genero" not in badges
    assert "PYME" not in badges


def test_build_badges_with_mujer_lider():
    emailer = EmailNotification()
    certs = {"favorece_mujer_lider": True, "favorece_pyme": False, "requiere_equidad_genero": False}
    badges = emailer._build_badges(certs)
    assert "Minima Cuantia" in badges
    assert "Mujer Lider" in badges


def test_build_badges_with_equidad():
    emailer = EmailNotification()
    certs = {"favorece_mujer_lider": False, "favorece_pyme": False, "requiere_equidad_genero": True}
    badges = emailer._build_badges(certs)
    assert "Equidad de Genero" in badges


def test_build_badges_all():
    emailer = EmailNotification()
    certs = {"favorece_mujer_lider": True, "favorece_pyme": True, "requiere_equidad_genero": True}
    badges = emailer._build_badges(certs)
    assert "Minima Cuantia" in badges
    assert "Mujer Lider" in badges
    assert "Equidad de Genero" in badges
    assert "PYME" in badges


def test_build_ventaja_with_certs():
    emailer = EmailNotification()
    certs = {"favorece_mujer_lider": True, "favorece_pyme": False, "requiere_equidad_genero": False}
    ventaja = emailer._build_ventaja(certs)
    assert "Ventaja competitiva" in ventaja
    assert "mujeres" in ventaja


def test_build_ventaja_without_certs():
    emailer = EmailNotification()
    certs = {"favorece_mujer_lider": False, "favorece_pyme": False, "requiere_equidad_genero": False}
    ventaja = emailer._build_ventaja(certs)
    assert ventaja == ""


def test_format_html_includes_badges():
    emailer = EmailNotification()
    process = make_process()
    certs = {"favorece_mujer_lider": True, "favorece_pyme": False, "requiere_equidad_genero": True}
    html = emailer._format_html(process, certs)
    assert "Minima Cuantia" in html
    assert "Mujer Lider" in html
    assert "Equidad de Genero" in html
    assert "Ventaja competitiva" in html


def test_format_html_without_certs():
    emailer = EmailNotification()
    process = make_process()
    html = emailer._format_html(process, None)
    assert "Minima Cuantia" in html
    assert "Ventaja competitiva" not in html
