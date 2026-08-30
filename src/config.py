import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SECOP_APP_TOKEN = os.getenv("SECOP_APP_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "notificaciones@tudominio.com")
SENDER_NAME = os.getenv("SENDER_NAME", "SECOP Monitor")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
STEALTH_MODE = os.getenv("STEALTH_MODE", "true").lower() == "true"
