"""
OKTAGON SAV v6.0 — Retry Logic
Retry automatique intelligent avec exponential backoff.

Principe : Si un appel API échoue, on réessaye avec des délais croissants.
"""
import asyncio
import time
from typing import Callable, Any, Optional, Type
from functools import wraps
from logger import logger


class RetryConfig:
    """Configuration du système de retry."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calcule le délai avant le prochain retry (exponential backoff).
    
    Formula: delay = min(base * (exp_base ^ attempt), max_delay)
    + jitter optionnel pour éviter thundering herd
    """
    import random
    
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        # Ajoute +/- 25% de variation aléatoire
        jitter_amount = delay * 0.25
        delay = delay + random.uniform(-jitter_amount, jitter_amount)
    
    return max(0, delay)


async def retry_async(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    retry_on: tuple[Type[Exception], ...] = (Exception,),
    **kwargs
) -> Any:
    """
    Exécute une fonction async avec retry automatique.
    
    Args:
        func: Fonction async à exécuter
        *args, **kwargs: Arguments de la fonction
        config: Configuration du retry
        retry_on: Tuple des exceptions qui déclenchent un retry
        
    Returns:
        Résultat de la fonction
        
    Raises:
        Exception: La dernière exception après max_attempts
    """
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            result = await func(*args, **kwargs)
            
            # Succès
            if attempt > 0:
                logger.info(
                    f"✅ Retry réussi au {attempt + 1}ème essai : {func.__name__}",
                    extra={"action": "retry_success", "attempts": attempt + 1}
                )
            
            return result
            
        except retry_on as e:
            last_exception = e
            
            # Dernier essai, on abandonne
            if attempt == config.max_attempts - 1:
                logger.error(
                    f"❌ Échec définitif après {config.max_attempts} essais : {func.__name__}",
                    extra={
                        "action": "retry_exhausted",
                        "attempts": config.max_attempts,
                        "error": str(e)
                    }
                )
                raise
            
            # Calculer le délai avant prochain essai
            delay = calculate_delay(attempt, config)
            
            logger.warning(
                f"⚠️ Retry {attempt + 1}/{config.max_attempts} : {func.__name__} — Attente {delay:.1f}s",
                extra={
                    "action": "retry_attempt",
                    "attempt": attempt + 1,
                    "delay": delay,
                    "error": str(e)[:100]
                }
            )
            
            await asyncio.sleep(delay)
    
    # Ne devrait jamais arriver ici
    raise last_exception


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retry_on: tuple[Type[Exception], ...] = (Exception,)
):
    """
    Décorateur pour ajouter automatiquement du retry à une fonction async.
    
    Usage:
        @with_retry(max_attempts=5, base_delay=2.0)
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay
            )
            return await retry_async(
                func,
                *args,
                config=config,
                retry_on=retry_on,
                **kwargs
            )
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
# CONFIGURATIONS PRÉDÉFINIES PAR SERVICE
# ═══════════════════════════════════════════════════════════

# Config pour Shopify (peut être lent, on est patient)
SHOPIFY_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0
)

# Config pour Claude (réponse rapide normalement)
CLAUDE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0
)

# Config pour Gmail SMTP (peut être lent)
GMAIL_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=3.0,
    max_delay=60.0,
    exponential_base=2.0
)

# Config pour opérations DB (rapide, on ne retry presque pas)
DB_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=1.5
)
