"""Los ciclos del cron y su hora en Colombia.

Una sola fuente para el motor (que anota que ciclo cubria cada ejecucion) y
para la web (que dibuja el dia y detecta ciclos que no corrieron). Las
expresiones deben coincidir con .github/workflows/secop.yml; una prueba lo
verifica.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Colombia no tiene horario de verano: UTC-5 todo el año.
COT = timezone(timedelta(hours=-5), "COT")

# (nombre, hora COT, minuto COT, expresion cron en UTC)
CICLOS = [
    ("nocturno", 0, 45, "45 5 * * *"),
    ("mañana", 10, 0, "0 15 * * *"),
    ("mediodía", 13, 30, "30 18 * * *"),
    ("noche", 20, 0, "0 1 * * *"),
]

# GitHub retrasa los cron programados en la capa gratuita: en este repositorio
# se han visto de 4 a 6 h. Pasado este margen sin ejecucion, el ciclo se
# considera omitido; antes, solo "esperando a GitHub".
MARGEN_RETRASO = timedelta(hours=8)


def etiqueta(hora: int, minuto: int) -> str:
    return f"{hora:02d}:{minuto:02d}"


def ciclo_por_cron(expresion: Optional[str]) -> Optional[str]:
    """Etiqueta ('13:30') del ciclo al que pertenece una expresion cron."""
    for _, hora, minuto, cron in CICLOS:
        if cron == (expresion or "").strip():
            return etiqueta(hora, minuto)
    return None


def ciclo_mas_cercano(momento: datetime) -> str:
    """Ciclo programado mas reciente antes de `momento` (con 15 min de gracia).

    Se usa cuando la ejecucion no dice que cron la disparo (manual o local).
    """
    local = momento.astimezone(COT)
    candidatos = []
    for dia in (local.date() - timedelta(days=1), local.date()):
        for _, hora, minuto, _ in CICLOS:
            programado = datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=COT)
            if programado <= local + timedelta(minutes=15):
                candidatos.append(programado)
    return etiqueta(max(candidatos).hour, max(candidatos).minute)


def programados_del_dia(dia) -> List[dict]:
    """Los ciclos de una fecha (COT), con su momento exacto."""
    return [
        {
            "nombre": nombre,
            "etiqueta": etiqueta(hora, minuto),
            "programado": datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=COT),
        }
        for nombre, hora, minuto, _ in CICLOS
    ]


def siguiente_programado(ahora: datetime) -> datetime:
    """Proximo ciclo programado despues de `ahora`."""
    hoy = ahora.astimezone(COT).date()
    for dia in (hoy, hoy + timedelta(days=1)):
        for p in programados_del_dia(dia):
            if p["programado"] > ahora:
                return p["programado"]
