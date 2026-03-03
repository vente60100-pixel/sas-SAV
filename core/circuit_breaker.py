"""
OKTAGON SAV v11.0 — Circuit Breaker Pattern
Protection intelligente contre les pannes d'API externes (Shopify, Claude).

Pattern : CLOSED → OPEN → HALF_OPEN → CLOSED
- CLOSED : Tout fonctionne normalement
- OPEN : API détectée HS, on coupe pendant N secondes
- HALF_OPEN : On teste si l'API est revenue
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
from logger import logger


class CircuitState(Enum):
    """États possibles du circuit breaker."""
    CLOSED = "closed"        # Tout va bien, on laisse passer
    OPEN = "open"            # API HS, on bloque tout
    HALF_OPEN = "half_open"  # On teste si l'API est revenue


@dataclass
class CircuitBreakerConfig:
    """Configuration du circuit breaker."""
    failure_threshold: int = 5        # Nb erreurs avant ouverture
    success_threshold: int = 2        # Nb succès pour refermer
    timeout: int = 60                 # Temps en OPEN (secondes)
    half_open_max_calls: int = 3      # Nb appels max en HALF_OPEN


class CircuitBreaker:
    """
    Circuit Breaker pour protéger contre les pannes d'API.
    
    Usage:
        cb = CircuitBreaker(name="Shopify")
        result = await cb.call(shopify.get_order, order_id)
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Exécute une fonction en la protégeant avec le circuit breaker.
        
        Args:
            func: Fonction async à exécuter
            *args, **kwargs: Arguments de la fonction
            
        Returns:
            Résultat de la fonction
            
        Raises:
            CircuitBreakerOpenError: Si le circuit est ouvert
            Exception: L'exception originale de la fonction
        """
        # Vérifier l'état du circuit
        current_state = self._get_state()
        
        if current_state == CircuitState.OPEN:
            logger.warning(
                f"🚫 Circuit Breaker OPEN pour {self.name} — Appel bloqué",
                extra={"action": "circuit_breaker_open", "service": self.name}
            )
            raise CircuitBreakerOpenError(
                f"Service {self.name} temporairement indisponible (circuit ouvert)"
            )
        
        if current_state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                logger.warning(
                    f"🚫 Circuit Breaker HALF_OPEN saturé pour {self.name}",
                    extra={"action": "circuit_breaker_half_open_full"}
                )
                raise CircuitBreakerOpenError(
                    f"Service {self.name} en cours de test (limite atteinte)"
                )
            self.half_open_calls += 1
        
        # Exécuter la fonction
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise
    
    def _get_state(self) -> CircuitState:
        """Détermine l'état actuel du circuit."""
        if self.state == CircuitState.OPEN:
            # Vérifier si le timeout est écoulé
            if time.time() - self.last_failure_time >= self.config.timeout:
                logger.info(
                    f"🔄 Circuit Breaker {self.name} : OPEN → HALF_OPEN",
                    extra={"action": "circuit_breaker_half_open", "service": self.name}
                )
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                
        return self.state
    
    def _on_success(self):
        """Appelé quand la fonction réussit."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                logger.info(
                    f"✅ Circuit Breaker {self.name} : HALF_OPEN → CLOSED",
                    extra={"action": "circuit_breaker_closed", "service": self.name}
                )
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_calls = 0
        
        elif self.state == CircuitState.CLOSED:
            # Reset compteur d'échecs si succès
            self.failure_count = max(0, self.failure_count - 1)
    
    def _on_failure(self):
        """Appelé quand la fonction échoue."""
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(
                f"⚠️ Circuit Breaker {self.name} : HALF_OPEN → OPEN (échec test)",
                extra={"action": "circuit_breaker_reopen", "service": self.name}
            )
            self.state = CircuitState.OPEN
            self.failure_count = self.config.failure_threshold
            self.success_count = 0
            self.half_open_calls = 0
            
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            
            if self.failure_count >= self.config.failure_threshold:
                logger.error(
                    f"🔴 Circuit Breaker {self.name} : CLOSED → OPEN ({self.failure_count} échecs)",
                    extra={"action": "circuit_breaker_open", "service": self.name}
                )
                self.state = CircuitState.OPEN
    
    def reset(self):
        """Reset manuel du circuit (admin)."""
        logger.info(
            f"🔧 Circuit Breaker {self.name} : Reset manuel",
            extra={"action": "circuit_breaker_reset", "service": self.name}
        )
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
    
    def get_status(self) -> dict:
        """Retourne le statut actuel du circuit."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Exception levée quand le circuit est ouvert."""
    pass


# ═══════════════════════════════════════════════════════════
# INSTANCES GLOBALES — Un circuit par service externe
# ═══════════════════════════════════════════════════════════

# Circuit pour Shopify API
shopify_circuit = CircuitBreaker(
    name="Shopify",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60,
        success_threshold=2
    )
)

# Circuit pour Claude API
claude_circuit = CircuitBreaker(
    name="Claude",
    config=CircuitBreakerConfig(
        failure_threshold=3,
        timeout=30,
        success_threshold=2
    )
)

# Circuit pour Gmail SMTP
gmail_circuit = CircuitBreaker(
    name="Gmail",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout=120,
        success_threshold=2
    )
)
