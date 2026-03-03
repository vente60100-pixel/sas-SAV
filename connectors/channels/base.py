"""
OKTAGON SAV v11.0 — Interface abstraite Channel (communication)
Email aujourd'hui, WhatsApp/Instagram demain.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class IncomingMessage:
    """Message entrant (email, WhatsApp, etc.)"""
    sender: str = ""
    sender_name: str = ""          # Nom affiché (ex: "Jacques Lemoine")
    subject: str = ""
    body: str = ""
    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    headers: dict = None
    raw_content: str = ""
    channel: str = "email"
    cc: str = ""                   # Destinataires en copie
    attachment_names: list = None  # Noms des pièces jointes

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.attachment_names is None:
            self.attachment_names = []


class ChannelConnector(ABC):
    """Interface pour tout canal de communication."""

    @abstractmethod
    async def fetch_messages(self) -> list[IncomingMessage]:
        """Récupère les nouveaux messages non lus."""
        pass

    @abstractmethod
    async def send_message(self, to: str, subject: str, html_body: str,
                           in_reply_to: Optional[str] = None) -> bool:
        """Envoie un message. Retourne True si succès."""
        pass
