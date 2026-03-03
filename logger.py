"""
OKTAGON SAV v11.0 — Logging structuré
Logs JSON pour production + logs lisibles pour dev
"""
import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from logging.handlers import RotatingFileHandler


class StructuredFormatter(logging.Formatter):
    """Formatter JSON pour logs structurés en production"""

    def format(self, record: logging.LogRecord) -> str:
        """Formate un log en JSON"""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Ajouter extra fields si présents
        if hasattr(record, 'email_id'):
            log_data['email_id'] = record.email_id
        if hasattr(record, 'category'):
            log_data['category'] = record.category
        if hasattr(record, 'agent'):
            log_data['agent'] = record.agent
        if hasattr(record, 'action'):
            log_data['action'] = record.action
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'email_from'):
            log_data['email_from'] = record.email_from

        # Exception si présente
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Formatter lisible pour développement"""

    def format(self, record: logging.LogRecord) -> str:
        """Formate un log de manière lisible"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname
        message = record.getMessage()

        # Couleurs ANSI pour le terminal
        colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Vert
            'WARNING': '\033[33m',  # Jaune
            'ERROR': '\033[31m',    # Rouge
            'CRITICAL': '\033[35m', # Magenta
        }
        reset = '\033[0m'

        color = colors.get(level, '')
        formatted = f'{color}[{timestamp}] {level:8s}{reset} {message}'

        # Ajouter extra fields
        extras = []
        if hasattr(record, 'email_id'):
            extras.append(f'email_id={record.email_id}')
        if hasattr(record, 'category'):
            extras.append(f'category={record.category}')
        if hasattr(record, 'action'):
            extras.append(f'action={record.action}')

        if extras:
            formatted += f' ({" | ".join(extras)})'

        if record.exc_info:
            formatted += '\n' + self.formatException(record.exc_info)

        return formatted


def setup_logger(name: str = 'oktagon_sav', log_level: str = 'INFO') -> logging.Logger:
    """
    Configure et retourne un logger avec handlers fichier + console

    Args:
        name: Nom du logger
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Éviter duplication si déjà configuré
    if logger.handlers:
        return logger

    # Handler fichier : JSON structuré, rotation 10MB × 5
    log_dir = Path(os.environ.get('LOG_DIR', str(Path(__file__).parent / 'logs')))
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / 'sav.log',
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter())

    # Handler console : Lisible, couleurs
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(HumanFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Singleton
logger = setup_logger()
