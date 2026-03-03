"""
OKTAGON SAV v11.0 — Ticket Tracker
Système de suivi des conversations : chaque client a un ticket OUVERT ou FERMÉ.

Un ticket est OUVERT quand :
- Le client a envoyé un email et attend une réponse
- Le client a re-écrit après notre réponse (nouveau besoin)

Un ticket est FERMÉ quand :
- On a répondu et le client ne re-écrit pas (silence = résolu après X jours)
- Le client dit merci / c'est bon / j'ai reçu (résolution explicite)
- Le client écrit sur un NOUVEAU sujet (l'ancien se ferme, un nouveau s'ouvre)

Rien n'est supprimé — tout est historisé.
"""
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger('oktagon')


# ══════════════════════════════════════════════════════════
# STATUTS DE TICKET
# ══════════════════════════════════════════════════════════

TICKET_OPEN = 'open'                    # Client attend une réponse
TICKET_RESPONDED = 'responded'          # On a répondu, en attente de retour client
TICKET_RESOLVED = 'resolved'            # Résolu (client satisfait ou silence)
TICKET_ESCALATED = 'escalated'          # En escalade humaine

# Délai avant fermeture automatique (client n'a pas re-écrit)
AUTO_CLOSE_DAYS = 5


# ══════════════════════════════════════════════════════════
# DÉTECTION DE RÉSOLUTION
# ══════════════════════════════════════════════════════════

# Patterns qui indiquent que le client considère son problème résolu
RESOLUTION_PATTERNS = [
    # Remerciements
    r'\bmerci\b.*\breçu\b', r'\bmerci\b.*\bcolis\b',
    r'\bmerci beaucoup\b', r'\bgrand merci\b',
    r'\bmerci pour (votre|tout|ta)\b',
    # Confirmation de réception
    r'\bj.ai (bien )?reçu\b', r'\bc.est (bien )?arrivé\b',
    r'\bcolis (bien )?reçu\b', r'\bcommande (bien )?reçue\b',
    r'\btout est bon\b', r'\bc.est (tout )?bon\b',
    r'\bc.est parfait\b', r'\bc.est réglé\b',
    r'\bc.est ok\b', r'\bça marche\b',
    # Satisfaction
    r'\bje suis (très )?content\b', r'\bje suis (très )?satisfait\b',
    r'\bsuper\b.*\bmerci\b', r'\btop\b.*\bmerci\b',
    r'\bexcellent\b', r'\bimpeccable\b', r'\bparfait\b',
    # Clôture explicite
    r'\bplus besoin\b', r'\bpas la peine\b',
    r'\bne vous dérangez plus\b', r'\blaissez tomber\b',
    r'\bc.est résolu\b', r'\bproblème réglé\b',
    r'\bbonne (continuation|journée|soirée)\b',
]

# Patterns qui indiquent un NOUVEAU sujet (l'ancien se ferme)
NEW_TOPIC_PATTERNS = [
    r'\bj.ai une (autre|nouvelle) question\b',
    r'\bautre chose\b', r'\bautre sujet\b',
    r'\bnouvelle commande\b', r'\bune autre commande\b',
    r'\bpar ailleurs\b', r'\bsinon\b.*\bquestion\b',
]


def detect_resolution(body: str, subject: str = '') -> dict:
    """
    Analyse si le message du client indique une résolution.

    Retourne:
    {
        'is_resolved': bool,
        'resolution_type': 'explicit' | 'new_topic' | None,
        'confidence': float (0-1),
        'trigger': str (le pattern qui a matché)
    }
    """
    text = (body + ' ' + subject).lower().strip()

    # Vérifier résolution explicite
    for pattern in RESOLUTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                'is_resolved': True,
                'resolution_type': 'explicit',
                'confidence': 0.9,
                'trigger': match.group(0)
            }

    # Vérifier nouveau sujet (= ancien résolu implicitement)
    for pattern in NEW_TOPIC_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                'is_resolved': True,
                'resolution_type': 'new_topic',
                'confidence': 0.7,
                'trigger': match.group(0)
            }

    return {
        'is_resolved': False,
        'resolution_type': None,
        'confidence': 0.0,
        'trigger': None
    }


# ══════════════════════════════════════════════════════════
# GESTION DES TICKETS EN DB
# ══════════════════════════════════════════════════════════

async def open_ticket(db, tenant_id: str, email_from: str, email_id: int,
                      subject: str, category: str = None):
    """
    Ouvre un nouveau ticket pour ce client.
    Si un ticket est déjà ouvert pour ce client → on le met à jour.
    """
    # Vérifier s'il y a un ticket ouvert
    existing = await db.fetch_one(
        """SELECT id, status FROM tickets
           WHERE tenant_id = $1 AND email_from = $2
           AND status IN ('open', 'responded')
           ORDER BY created_at DESC LIMIT 1""",
        tenant_id, email_from
    )

    if existing:
        # Ticket existant → le remettre en "open" (le client a re-écrit)
        await db.execute(
            """UPDATE tickets SET
                status = 'open',
                last_client_message_at = NOW(),
                last_email_id = $1,
                message_count = message_count + 1,
                updated_at = NOW()
               WHERE id = $2""",
            email_id, existing['id']
        )
        logger.info(f"📬 Ticket #{existing['id']} rouvert — {email_from}",
                    extra={'action': 'ticket_reopened', 'ticket_id': existing['id']})
        return existing['id']
    else:
        # Nouveau ticket
        ticket_id = await db.fetch_one(
            """INSERT INTO tickets
               (tenant_id, email_from, first_email_id, last_email_id,
                subject, category, status, message_count,
                last_client_message_at, created_at, updated_at)
               VALUES ($1, $2, $3, $3, $4, $5, 'open', 1, NOW(), NOW(), NOW())
               RETURNING id""",
            tenant_id, email_from, email_id, subject[:200] if subject else '',
            category
        )
        tid = ticket_id['id']
        logger.info(f"📬 Nouveau ticket #{tid} — {email_from} | {subject[:50]}",
                    extra={'action': 'ticket_opened', 'ticket_id': tid})
        return tid


async def mark_ticket_responded(db, tenant_id: str, email_from: str,
                                 response_email_id: int = None):
    """
    Marque le ticket comme 'responded' — on a répondu, on attend le retour client.
    """
    result = await db.execute(
        """UPDATE tickets SET
            status = 'responded',
            last_response_at = NOW(),
            response_count = response_count + 1,
            updated_at = NOW()
           WHERE tenant_id = $1 AND email_from = $2
           AND status = 'open'""",
        tenant_id, email_from
    )
    if result:
        logger.info(f"✅ Ticket répondu — {email_from}",
                    extra={'action': 'ticket_responded'})


async def resolve_ticket(db, tenant_id: str, email_from: str,
                          resolution_type: str = 'explicit',
                          trigger: str = None):
    """
    Ferme le ticket — le client n'a plus besoin d'aide.
    """
    result = await db.execute(
        """UPDATE tickets SET
            status = 'resolved',
            resolved_at = NOW(),
            resolution_type = $3,
            resolution_trigger = $4,
            updated_at = NOW()
           WHERE tenant_id = $1 AND email_from = $2
           AND status IN ('open', 'responded')""",
        tenant_id, email_from, resolution_type, trigger
    )
    if result:
        logger.info(f"🏁 Ticket résolu — {email_from} ({resolution_type}: {trigger})",
                    extra={'action': 'ticket_resolved', 'resolution_type': resolution_type})


async def escalate_ticket(db, tenant_id: str, email_from: str):
    """Marque le ticket comme escaladé (intervention humaine)."""
    await db.execute(
        """UPDATE tickets SET
            status = 'escalated',
            updated_at = NOW()
           WHERE tenant_id = $1 AND email_from = $2
           AND status IN ('open', 'responded')""",
        tenant_id, email_from
    )


# ══════════════════════════════════════════════════════════
# SCAN DES TICKETS OUVERTS (pour le worker de suivi)
# ══════════════════════════════════════════════════════════

async def get_open_tickets(db, tenant_id: str) -> list:
    """
    Retourne tous les tickets ouverts ou en attente de retour client.
    """
    rows = await db.fetch_all(
        """SELECT t.*, pe.email_subject, pe.email_body_preview,
                  pe.response_text, pe.brain_category
           FROM tickets t
           LEFT JOIN processed_emails pe ON pe.id = t.last_email_id
           WHERE t.tenant_id = $1
           AND t.status IN ('open', 'responded')
           ORDER BY
             CASE WHEN t.status = 'open' THEN 0 ELSE 1 END,
             t.last_client_message_at ASC""",
        tenant_id
    )
    return rows


async def get_unanswered_tickets(db, tenant_id: str, hours: int = 24) -> list:
    """
    Retourne les tickets ouverts sans réponse depuis X heures.
    Ce sont les clients qui attendent.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = await db.fetch_all(
        """SELECT t.*, pe.email_subject, pe.email_body_preview
           FROM tickets t
           LEFT JOIN processed_emails pe ON pe.id = t.last_email_id
           WHERE t.tenant_id = $1
           AND t.status = 'open'
           AND t.last_client_message_at < $2
           ORDER BY t.last_client_message_at ASC""",
        tenant_id, cutoff
    )
    return rows


async def auto_close_stale_tickets(db, tenant_id: str,
                                     days: int = AUTO_CLOSE_DAYS) -> int:
    """
    Ferme automatiquement les tickets 'responded' depuis X jours
    sans nouvelle du client. Silence = résolu.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        """UPDATE tickets SET
            status = 'resolved',
            resolved_at = NOW(),
            resolution_type = 'auto_silence',
            resolution_trigger = $3,
            updated_at = NOW()
           WHERE tenant_id = $1
           AND status = 'responded'
           AND last_response_at < $2""",
        tenant_id, cutoff,
        f"Pas de réponse client depuis {days} jours"
    )
    # Compter les tickets fermés
    closed = await db.fetch_one(
        """SELECT COUNT(*) as c FROM tickets
           WHERE tenant_id = $1 AND resolution_type = 'auto_silence'
           AND resolved_at > NOW() - INTERVAL '1 minute'""",
        tenant_id
    )
    count = closed['c'] if closed else 0
    if count > 0:
        logger.info(f"🔒 {count} ticket(s) fermé(s) automatiquement (silence {days}j)",
                    extra={'action': 'tickets_auto_closed', 'count': count})
    return count


async def get_ticket_stats(db, tenant_id: str) -> dict:
    """Stats des tickets pour le dashboard."""
    stats = await db.fetch_one(
        """SELECT
            COUNT(*) FILTER (WHERE status = 'open') as open_count,
            COUNT(*) FILTER (WHERE status = 'responded') as waiting_count,
            COUNT(*) FILTER (WHERE status = 'resolved') as resolved_count,
            COUNT(*) FILTER (WHERE status = 'escalated') as escalated_count,
            COUNT(*) as total
           FROM tickets WHERE tenant_id = $1""",
        tenant_id
    )
    return dict(stats) if stats else {
        'open_count': 0, 'waiting_count': 0,
        'resolved_count': 0, 'escalated_count': 0, 'total': 0
    }
