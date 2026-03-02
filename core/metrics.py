"""
OKTAGON SAV v6.0 — Metrics & Monitoring
Collecte de métriques temps réel pour observabilité du moteur.

Principe : Tout ce qui est mesurable est améliorable.
"""
import time
from typing import Optional, Dict
from dataclasses import dataclass, field
from collections import defaultdict
from logger import logger


@dataclass
class MetricSnapshot:
    """Snapshot instantané d'une métrique."""
    count: int = 0
    total: float = 0.0
    min: float = float('inf')
    max: float = 0.0
    last_update: float = 0.0
    
    def record(self, value: float):
        """Enregistre une nouvelle valeur."""
        self.count += 1
        self.total += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.last_update = time.time()
    
    @property
    def avg(self) -> float:
        """Moyenne."""
        return self.total / self.count if self.count > 0 else 0.0
    
    def to_dict(self) -> dict:
        """Export en dict."""
        return {
            "count": self.count,
            "avg": round(self.avg, 2),
            "min": round(self.min, 2) if self.min != float('inf') else 0,
            "max": round(self.max, 2),
            "total": round(self.total, 2)
        }


class MetricsCollector:
    """
    Collecteur de métriques temps réel du moteur SAV.
    
    Usage:
        metrics.record_email_processed(duration_ms=350)
        metrics.record_ai_call(duration_ms=1200, success=True)
        status = metrics.get_status()
    """
    
    def __init__(self):
        # Métriques de base
        self.emails_received = 0
        self.emails_processed = 0
        self.emails_filtered = 0
        self.emails_duplicates = 0
        self.emails_rate_limited = 0
        
        # Réponses envoyées
        self.responses_sent = 0
        self.responses_escalated = 0
        self.responses_failed = 0
        
        # Appels IA
        self.ai_calls_success = 0
        self.ai_calls_failed = 0
        self.ai_tool_uses = 0
        
        # Appels Shopify
        self.shopify_calls_success = 0
        self.shopify_calls_failed = 0
        
        # Timing détaillés
        self.timing_email_processing = MetricSnapshot()
        self.timing_ai_calls = MetricSnapshot()
        self.timing_shopify_calls = MetricSnapshot()
        self.timing_email_sending = MetricSnapshot()
        
        # Circuit breakers
        self.circuit_breaker_opens = defaultdict(int)
        
        # Erreurs par type
        self.errors_by_type = defaultdict(int)
        
        # Start time
        self.start_time = time.time()
    
    # ═══════════════════════════════════════════════════════════
    # ENREGISTREMENT MÉTRIQUES
    # ═══════════════════════════════════════════════════════════
    
    def record_email_received(self):
        """Email reçu du polling."""
        self.emails_received += 1
    
    def record_email_filtered(self, reason: str):
        """Email filtré (spam, duplicate, etc)."""
        self.emails_filtered += 1
        if reason == "duplicate":
            self.emails_duplicates += 1
        elif reason == "rate_limit":
            self.emails_rate_limited += 1
    
    def record_email_processed(self, duration_ms: float):
        """Email traité avec succès."""
        self.emails_processed += 1
        self.timing_email_processing.record(duration_ms)
    
    def record_response_sent(self):
        """Réponse envoyée au client."""
        self.responses_sent += 1
    
    def record_response_escalated(self):
        """Réponse escaladée à l'humain."""
        self.responses_escalated += 1
    
    def record_response_failed(self):
        """Échec d'envoi de réponse."""
        self.responses_failed += 1
    
    def record_ai_call(self, duration_ms: float, success: bool, tool_uses: int = 0):
        """Appel au cerveau IA."""
        if success:
            self.ai_calls_success += 1
        else:
            self.ai_calls_failed += 1
        
        self.ai_tool_uses += tool_uses
        self.timing_ai_calls.record(duration_ms)
    
    def record_shopify_call(self, duration_ms: float, success: bool):
        """Appel à l'API Shopify."""
        if success:
            self.shopify_calls_success += 1
        else:
            self.shopify_calls_failed += 1
        
        self.timing_shopify_calls.record(duration_ms)
    
    def record_circuit_breaker_open(self, service: str):
        """Circuit breaker ouvert."""
        self.circuit_breaker_opens[service] += 1
        logger.warning(
            f"📊 Circuit breaker ouvert : {service} (total: {self.circuit_breaker_opens[service]})",
            extra={"action": "metrics_circuit_open", "service": service}
        )
    
    def record_error(self, error_type: str):
        """Erreur catégorisée."""
        self.errors_by_type[error_type] += 1
    
    # ═══════════════════════════════════════════════════════════
    # STATISTIQUES CALCULÉES
    # ═══════════════════════════════════════════════════════════
    
    @property
    def uptime_seconds(self) -> float:
        """Temps de fonctionnement en secondes."""
        return time.time() - self.start_time
    
    @property
    def processing_rate(self) -> float:
        """Emails traités par minute."""
        minutes = self.uptime_seconds / 60
        return self.emails_processed / minutes if minutes > 0 else 0.0
    
    @property
    def ai_success_rate(self) -> float:
        """Taux de succès des appels IA (%)."""
        total = self.ai_calls_success + self.ai_calls_failed
        return (self.ai_calls_success / total * 100) if total > 0 else 0.0
    
    @property
    def shopify_success_rate(self) -> float:
        """Taux de succès des appels Shopify (%)."""
        total = self.shopify_calls_success + self.shopify_calls_failed
        return (self.shopify_calls_success / total * 100) if total > 0 else 0.0
    
    @property
    def escalation_rate(self) -> float:
        """Taux d'escalade (%)."""
        total = self.responses_sent + self.responses_escalated
        return (self.responses_escalated / total * 100) if total > 0 else 0.0
    
    @property
    def filter_rate(self) -> float:
        """Taux de filtrage (%)."""
        total = self.emails_received
        return (self.emails_filtered / total * 100) if total > 0 else 0.0
    
    # ═══════════════════════════════════════════════════════════
    # EXPORT STATUS
    # ═══════════════════════════════════════════════════════════
    
    def get_status(self) -> dict:
        """
        Retourne un statut complet des métriques.
        """
        uptime_hours = self.uptime_seconds / 3600
        
        return {
            "uptime": {
                "seconds": round(self.uptime_seconds, 1),
                "hours": round(uptime_hours, 2),
                "start_time": self.start_time
            },
            "emails": {
                "received": self.emails_received,
                "processed": self.emails_processed,
                "filtered": self.emails_filtered,
                "duplicates": self.emails_duplicates,
                "rate_limited": self.emails_rate_limited,
                "filter_rate_pct": round(self.filter_rate, 1)
            },
            "responses": {
                "sent": self.responses_sent,
                "escalated": self.responses_escalated,
                "failed": self.responses_failed,
                "escalation_rate_pct": round(self.escalation_rate, 1)
            },
            "ai": {
                "calls_success": self.ai_calls_success,
                "calls_failed": self.ai_calls_failed,
                "success_rate_pct": round(self.ai_success_rate, 1),
                "tool_uses": self.ai_tool_uses,
                "timing": self.timing_ai_calls.to_dict()
            },
            "shopify": {
                "calls_success": self.shopify_calls_success,
                "calls_failed": self.shopify_calls_failed,
                "success_rate_pct": round(self.shopify_success_rate, 1),
                "timing": self.timing_shopify_calls.to_dict()
            },
            "performance": {
                "processing_rate_per_min": round(self.processing_rate, 2),
                "email_processing_ms": self.timing_email_processing.to_dict(),
                "email_sending_ms": self.timing_email_sending.to_dict()
            },
            "errors": {
                "by_type": dict(self.errors_by_type),
                "circuit_breaker_opens": dict(self.circuit_breaker_opens)
            }
        }
    
    def get_health(self) -> dict:
        """
        Retourne le health check du système.
        """
        # Critères de santé
        is_healthy = (
            self.ai_success_rate >= 95.0 and
            self.shopify_success_rate >= 90.0 and
            self.escalation_rate <= 30.0 and
            len(self.circuit_breaker_opens) == 0
        )
        
        status = "healthy" if is_healthy else "degraded"
        
        if self.ai_success_rate < 80.0 or self.shopify_success_rate < 70.0:
            status = "unhealthy"
        
        return {
            "status": status,
            "is_healthy": is_healthy,
            "checks": {
                "ai_success_rate": self.ai_success_rate >= 95.0,
                "shopify_success_rate": self.shopify_success_rate >= 90.0,
                "escalation_rate": self.escalation_rate <= 30.0,
                "no_circuit_opens": len(self.circuit_breaker_opens) == 0
            },
            "uptime_hours": round(self.uptime_seconds / 3600, 2)
        }
    
    def log_summary(self):
        """Log un résumé des métriques (pour debug)."""
        status = self.get_status()
        logger.info(
            f"📊 MÉTRIQUES | Emails: {status['emails']['processed']} | "
            f"IA: {status['ai']['success_rate_pct']}% | "
            f"Escalade: {status['responses']['escalation_rate_pct']}%",
            extra={"action": "metrics_summary", "metrics": status}
        )


# ═══════════════════════════════════════════════════════════
# INSTANCE GLOBALE
# ═══════════════════════════════════════════════════════════

# Singleton global pour collecter les métriques
metrics = MetricsCollector()
