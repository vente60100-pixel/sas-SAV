"""
OKTAGON SAV v4.0 — Interface abstraite IA
Claude aujourd'hui, OpenAI/Mistral demain.
"""
from abc import ABC, abstractmethod
from typing import Optional


class AIConnector(ABC):
    """Interface pour tout moteur IA."""

    @abstractmethod
    async def generate(self, prompt: str, context: str) -> dict:
        """Génère une réponse IA.
        Retourne dict avec: response (str), escalade (bool), confidence (float)"""
        pass

    @abstractmethod
    async def classify(self, subject: str, body: str) -> tuple[str, float]:
        """Classifie un email.
        Retourne (category, confidence)."""
        pass
