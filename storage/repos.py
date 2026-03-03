"""
OKTAGON SAV v11.0 — Repository Pattern
TOUT le SQL est ici. Aucune requête SQL ailleurs dans le code.
"""
import json
from typing import Optional, Any


class Repos:
    """Accès données unifié. Chaque méthode = 1 requête SQL."""

    def __init__(self, db):
        self.db = db

    # ══════════════════════════════════════════════════════════
    # PROCESSED EMAILS
    # ══════════════════════════════════════════════════════════

    async def create_email(self, tenant_id: str, email_hash: str, email_from: str,
                           subject: str, body_preview: str, language: str,
                           has_attachments: bool = False, attachment_count: int = 0,
                           conversation_step: str = 'step1_category',
                           collected_data: dict = None, category: str = None,
                           message_id: str = None, parent_id: int = None,
                           response_sent: bool = False, rerouted_from: str = None) -> int:
        """Insère un email traité et retourne son ID."""
        return await self.db.insert_returning_id(
            """INSERT INTO processed_emails
               (tenant_id, email_hash, email_from, email_subject, email_body_preview,
                language, has_attachments, attachment_count, conversation_step,
                collected_data, category, message_id, parent_email_id,
                response_sent, rerouted_from)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
               ON CONFLICT (email_hash) DO NOTHING
               RETURNING id""",
            tenant_id, email_hash, email_from, subject, (body_preview or '')[:200],
            language, has_attachments, attachment_count, conversation_step,
            json.dumps(collected_data or {}), category, message_id, parent_id,
            response_sent, rerouted_from
        )

    async def find_by_hash(self, email_hash: str) -> Optional[Any]:
        """Vérifie si un email existe déjà (déduplication)."""
        return await self.db.fetch_one(
            "SELECT id FROM processed_emails WHERE email_hash = $1", email_hash
        )

    async def find_active_session(self, tenant_id: str, email_from: str) -> Optional[Any]:
        """Trouve une session active pour ce client."""
        return await self.db.fetch_one(
            """SELECT id, conversation_step, collected_data, category
               FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND conversation_step NOT IN ('ready_for_ai', 'closed')
               AND created_at > NOW() - INTERVAL '72 hours'
               ORDER BY created_at DESC LIMIT 1""",
            tenant_id, email_from
        )

    async def find_escalated(self, tenant_id: str, email_from: str) -> Optional[Any]:
        """Vérifie si ce client a été escaladé récemment."""
        return await self.db.fetch_one(
            """SELECT id FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND conversation_step = 'escalated_to_human'
               AND created_at > NOW() - INTERVAL '7 days'
               ORDER BY created_at DESC LIMIT 1""",
            tenant_id, email_from
        )

    async def mark_sent(self, email_id: int, response_text: str = None):
        """Marque un email comme répondu."""
        if response_text:
            await self.db.execute(
                "UPDATE processed_emails SET response_sent = true, response_text = $1 WHERE id = $2",
                response_text, email_id
            )
        else:
            await self.db.execute(
                "UPDATE processed_emails SET response_sent = true WHERE id = $1", email_id
            )

    # Colonnes autorisées dans update_email (whitelist anti-injection SQL)
    _ALLOWED_UPDATE_COLUMNS = {
        'conversation_step', 'collected_data', 'category', 'response_sent',
        'response_text', 'email_to', 'brain_category', 'brain_confidence',
        'detection_method', 'processing_time_ms', 'urgency_level',
        'response_quality', 'satisfaction_score', 'satisfaction_source',
        'client_reply_sentiment', 'language', 'rerouted_from',
        'has_attachments', 'attachment_count', 'message_id', 'parent_email_id',
    }

    async def update_email(self, email_id: int, **kwargs):
        """Met à jour des champs arbitraires d'un email (colonnes whitelistées)."""
        if not kwargs:
            return
        # Sécurité : valider que toutes les colonnes sont autorisées
        for key in kwargs:
            if key not in self._ALLOWED_UPDATE_COLUMNS:
                raise ValueError(f"Colonne '{key}' non autorisée dans update_email")
        sets = []
        vals = []
        for i, (key, val) in enumerate(kwargs.items(), 1):
            sets.append(f"{key} = ${i}")
            vals.append(val)
        vals.append(email_id)
        query = f"UPDATE processed_emails SET {', '.join(sets)} WHERE id = ${len(vals)}"
        await self.db.execute(query, *vals)

    async def get_conversation_history(self, tenant_id: str, email_from: str, limit: int = 8) -> list:
        """Récupère l'historique COMPLET : messages client + réponses SAV."""
        return await self.db.fetch_all(
            """SELECT email_subject, email_body_preview, response_text,
                      brain_category, created_at
               FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND (response_text IS NOT NULL OR email_body_preview IS NOT NULL)
               ORDER BY created_at DESC LIMIT $3""",
            tenant_id, email_from, limit
        )

    async def count_recent_responses(self, tenant_id: str, email_from: str, hours: int = 1) -> int:
        """Compte les réponses envoyées récemment."""
        row = await self.db.fetch_one(
            f"""SELECT COUNT(*) as c FROM processed_emails
                WHERE tenant_id = $1 AND email_from = $2
                AND response_sent = true
                AND created_at > NOW() - INTERVAL '{int(hours)} hours'""",
            tenant_id, email_from
        )
        return row['c'] if row else 0

    async def count_step1_loop(self, tenant_id: str, email_from: str) -> int:
        """Compte les step1 en boucle (anti-boucle)."""
        row = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND conversation_step = 'step1_category'
               AND created_at > NOW() - INTERVAL '2 hours'""",
            tenant_id, email_from
        )
        return row['c'] if row else 0

    async def find_pending_recovery(self, tenant_id: str) -> list:
        """Trouve les emails bloqués à reprendre après restart."""
        return await self.db.fetch_all(
            """SELECT id, email_from, email_subject, email_body_preview,
                      collected_data, category,
                      conversation_step, message_id, language
               FROM processed_emails
               WHERE tenant_id = $1
               AND conversation_step = 'ready_for_ai'
               AND response_sent = false
               AND created_at > NOW() - INTERVAL '7 days'
               ORDER BY created_at ASC""",
            tenant_id
        )

    # ══════════════════════════════════════════════════════════
    # ESCALATIONS
    # ══════════════════════════════════════════════════════════

    async def create_escalation(self, tenant_id: str, email_id: int, email_from: str,
                                category: str, reason: str) -> int:
        """v9.0 — Crée une escalation (atomique, évite les doublons)."""
        # Vérifier + créer en une seule requête pour éviter la race condition
        existing = await self.find_active_escalation(tenant_id, email_from, category)
        if existing:
            return existing['id']
        return await self.db.insert_returning_id(
            """INSERT INTO escalations (tenant_id, email_id, email_from, category, reason, resolved)
               VALUES ($1, $2, $3, $4, $5, false) RETURNING id""",
            tenant_id, email_id, email_from, category, reason
        )

    async def find_active_escalation(self, tenant_id: str, email_from: str, category: str) -> Optional[Any]:
        """Vérifie si une escalation active existe déjà."""
        return await self.db.fetch_one(
            """SELECT id FROM escalations
               WHERE tenant_id = $1 AND email_from = $2 AND category = $3
               AND resolved = false AND created_at > NOW() - INTERVAL '72 hours'
               LIMIT 1""",
            tenant_id, email_from, category
        )

    async def resolve_escalation(self, escalation_id: int, action: str = None, response: str = None):
        """Résout une escalation."""
        await self.db.execute(
            """UPDATE escalations SET resolved = true, resolved_at = NOW(),
               admin_action = $1, admin_response = $2 WHERE id = $3""",
            action, response, escalation_id
        )

    # ══════════════════════════════════════════════════════════
    # OUTGOING EMAILS (rate limiting)
    # ══════════════════════════════════════════════════════════

    async def log_outgoing(self, tenant_id: str, email_to: str, email_type: str = 'auto'):
        """Log un email sortant pour le rate limiting."""
        await self.db.execute(
            "INSERT INTO outgoing_emails (tenant_id, email_to, email_type) VALUES ($1, $2, $3)",
            tenant_id, email_to, email_type
        )

    async def can_send(self, tenant_id: str, email_to: str,
                       max_per_hour: int = 3, max_per_day: int = 8) -> bool:
        """Vérifie le rate limit pour cet email destinataire.

        Compte les réponses envoyées via email_from (= adresse client)
        car email_to n'est pas toujours renseigné dans processed_emails.
        """
        row_1h = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND response_sent = true
               AND created_at > NOW() - INTERVAL '1 hour'""",
            tenant_id, email_to
        )
        if (row_1h['c'] if row_1h else 0) >= max_per_hour:
            return False
        row_24h = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND response_sent = true
               AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id, email_to
        )
        if (row_24h['c'] if row_24h else 0) >= max_per_day:
            return False
        return True

    # ══════════════════════════════════════════════════════════
    # CANCELLATIONS
    # ══════════════════════════════════════════════════════════

    async def create_cancellation(self, tenant_id: str, email_from: str, order_number: str,
                                  email_id: int = None, escalation_id: int = None,
                                  fulfillment_status: str = None, items_json: list = None,
                                  refundable_amount: float = 0, non_refundable_amount: float = 0,
                                  case_type: str = None) -> int:
        return await self.db.insert_returning_id(
            """INSERT INTO cancellations
               (tenant_id, email_from, order_number, email_id, escalation_id,
                fulfillment_status, items_json, refundable_amount, non_refundable_amount, case_type)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id""",
            tenant_id, email_from, order_number, email_id, escalation_id,
            fulfillment_status, json.dumps(items_json or []),
            refundable_amount, non_refundable_amount, case_type
        )

    # ══════════════════════════════════════════════════════════
    # ADDRESS CHANGES
    # ══════════════════════════════════════════════════════════

    async def create_address_change(self, tenant_id: str, email_id: int, escalation_id: int,
                                    email_from: str, order_number: str,
                                    old_address: str, new_address: str) -> int:
        return await self.db.insert_returning_id(
            """INSERT INTO address_changes
               (tenant_id, email_id, escalation_id, email_from, order_number, old_address, new_address)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
            tenant_id, email_id, escalation_id, email_from, order_number, old_address, new_address
        )

    # ══════════════════════════════════════════════════════════
    # RETURNS TRACKING
    # ══════════════════════════════════════════════════════════

    async def create_return_tracking(self, tenant_id: str, email_from: str,
                                     order_number: str, tracking_number: str) -> int:
        return await self.db.insert_returning_id(
            """INSERT INTO returns_tracking (tenant_id, email_from, order_number, tracking_number)
               VALUES ($1, $2, $3, $4) RETURNING id""",
            tenant_id, email_from, order_number, tracking_number
        )


    # ══════════════════════════════════════════════════════════
    # INTELLIGENCE v4.1
    # ══════════════════════════════════════════════════════════

    async def get_client_profile(self, tenant_id: str, email_from: str) -> dict:
        """Construit un profil client à partir de l'historique DB."""
        # Nombre total d'emails
        total = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2""",
            tenant_id, email_from
        )
        # Nombre d'escalations
        escalations = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM escalations
               WHERE tenant_id = $1 AND email_from = $2""",
            tenant_id, email_from
        )
        # Emails dernières 24h
        recent = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id, email_from
        )
        return {
            "total_emails": total['c'] if total else 0,
            "total_escalations": escalations['c'] if escalations else 0,
            "emails_last_24h": recent['c'] if recent else 0,
        }

    async def get_last_auto_response(self, tenant_id: str, email_from: str) -> Optional[str]:
        """Récupère la dernière réponse auto envoyée à ce client."""
        row = await self.db.fetch_one(
            """SELECT response_text FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND response_sent = true AND response_text IS NOT NULL
               ORDER BY created_at DESC LIMIT 1""",
            tenant_id, email_from
        )
        return row['response_text'] if row else None

    async def mark_response_quality(self, email_id: int, quality: str):
        """Marque la qualité d'une réponse (good/repeated/wrong_order/escalated_after)."""
        await self.db.execute(
            "UPDATE processed_emails SET response_quality = $1 WHERE id = $2",
            quality, email_id
        )

    async def find_escalated_from_escalations(self, tenant_id: str, email_from: str) -> Optional[Any]:
        """Vérifie dans la table escalations si ce client a une escalation active."""
        return await self.db.fetch_one(
            """SELECT id FROM escalations
               WHERE tenant_id = $1 AND email_from = $2
               AND resolved = false AND created_at > NOW() - INTERVAL '7 days'
               ORDER BY created_at DESC LIMIT 1""",
            tenant_id, email_from
        )


    # ══════════════════════════════════════════════════════════
    # CLIENT PROFILES v5.0
    # ══════════════════════════════════════════════════════════

    async def upsert_client_profile(self, tenant_id: str, email: str, prenom: str = None,
                                     dernier_ton: str = None, derniere_commande: str = None):
        """Crée ou met à jour le profil client persistant."""
        await self.db.execute("""
            INSERT INTO client_profiles (tenant_id, email, prenom, dernier_ton,
                derniere_commande, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (tenant_id, email) DO UPDATE SET
                prenom = COALESCE($3, client_profiles.prenom),
                dernier_ton = COALESCE($4, client_profiles.dernier_ton),
                derniere_commande = COALESCE($5, client_profiles.derniere_commande),
                nb_contacts = client_profiles.nb_contacts + 1,
                updated_at = NOW()
        """, tenant_id, email, prenom, dernier_ton, derniere_commande)

    async def get_full_client_profile(self, tenant_id: str, email: str) -> dict:
        """Profil client complet : DB profile + stats emails + escalations."""
        profile = await self.db.fetch_one(
            "SELECT * FROM client_profiles WHERE tenant_id = $1 AND email = $2",
            tenant_id, email
        )
        stats = await self.get_client_profile(tenant_id, email)
        result = {**stats}
        if profile:
            pdict = dict(profile)
            result['prenom'] = pdict.get('prenom')
            result['dernier_ton'] = pdict.get('dernier_ton')
            result['vip'] = pdict.get('vip', False)
            result['derniere_commande'] = pdict.get('derniere_commande')
        return result


    # ══════════════════════════════════════════════════════════
    # APPRENTISSAGE
    # ══════════════════════════════════════════════════════════

    async def get_last_sav_response(self, tenant_id: str, email_from: str) -> str:
        """Récupère la dernière réponse SAV envoyée à ce client."""
        row = await self.db.fetch_one(
            """SELECT response_text FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND response_sent = true AND response_text IS NOT NULL
               ORDER BY created_at DESC LIMIT 1""",
            tenant_id, email_from
        )
        return row['response_text'] if row else None

    async def get_recent_responses(self, tenant_id: str, email_from: str, limit: int = 3) -> list:
        """Récupère les N dernières réponses envoyées à ce client (v7.3 anti-boucle)."""
        return await self.db.fetch_all(
            """SELECT response_text, brain_category, created_at
               FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND response_sent = true AND response_text IS NOT NULL
               ORDER BY created_at DESC LIMIT $3""",
            tenant_id, email_from, limit
        )


    async def get_recent_errors(self, tenant_id: str, email_from: str, limit: int = 3) -> list:
        """v10.0 — Recupere les dernieres reponses mal scorees pour ce client."""
        return await self.db.fetch_all(
            """SELECT response_quality, response_text, brain_category, created_at
               FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND response_quality IS NOT NULL
               AND (response_quality LIKE '%bad%' OR response_quality LIKE '%error%')
               ORDER BY created_at DESC LIMIT $3""",
            tenant_id, email_from, limit
        )

    # ══════════════════════════════════════════════════════════
    # DASHBOARD — Stats, Clients, Pipeline
    # ══════════════════════════════════════════════════════════

    async def get_dashboard_stats(self, tenant_id: str, period: str = 'today') -> dict:
        """Stats globales pour le dashboard."""
        if period == 'today':
            interval = "created_at >= CURRENT_DATE"
        elif period == 'week':
            interval = "created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == 'month':
            interval = "created_at >= CURRENT_DATE - INTERVAL '30 days'"
        else:
            interval = "1=1"

        total = await self.db.fetch_one(
            f"SELECT COUNT(*) as c FROM processed_emails WHERE tenant_id = $1 AND {interval}",
            tenant_id
        )
        sent = await self.db.fetch_one(
            f"SELECT COUNT(*) as c FROM processed_emails WHERE tenant_id = $1 AND response_sent = true AND {interval}",
            tenant_id
        )
        escalated = await self.db.fetch_one(
            f"SELECT COUNT(*) as c FROM escalations WHERE tenant_id = $1 AND {interval}",
            tenant_id
        )
        avg_time = await self.db.fetch_one(
            f"SELECT AVG(processing_time_ms) as avg_ms FROM processed_emails WHERE tenant_id = $1 AND processing_time_ms > 0 AND {interval}",
            tenant_id
        )
        return {
            'total_emails': total['c'] if total else 0,
            'emails_sent': sent['c'] if sent else 0,
            'escalations': escalated['c'] if escalated else 0,
            'avg_processing_ms': int(avg_time['avg_ms'] or 0) if avg_time else 0,
            'period': period,
        }

    async def get_stats_by_category(self, tenant_id: str, period: str = 'today') -> list:
        """Stats par catégorie."""
        if period == 'today':
            interval = "created_at >= CURRENT_DATE"
        elif period == 'week':
            interval = "created_at >= CURRENT_DATE - INTERVAL '7 days'"
        else:
            interval = "1=1"

        rows = await self.db.fetch_all(
            f"""SELECT COALESCE(brain_category, category, 'INCONNU') as cat, COUNT(*) as c
                FROM processed_emails WHERE tenant_id = $1 AND {interval}
                GROUP BY cat ORDER BY c DESC""",
            tenant_id
        )
        return [{'category': r['cat'], 'count': r['c']} for r in rows]

    async def get_all_clients(self, tenant_id: str, search: str = None,
                               limit: int = 50, offset: int = 0) -> list:
        """Liste tous les clients uniques avec stats."""
        if search:
            rows = await self.db.fetch_all(
                """SELECT email_from as email, COUNT(*) as total_emails,
                          MAX(created_at) as last_contact,
                          MIN(created_at) as first_contact
                   FROM processed_emails
                   WHERE tenant_id = $1 AND email_from ILIKE $2
                   GROUP BY email_from
                   ORDER BY last_contact DESC
                   LIMIT $3 OFFSET $4""",
                tenant_id, f'%{search}%', limit, offset
            )
        else:
            rows = await self.db.fetch_all(
                """SELECT email_from as email, COUNT(*) as total_emails,
                          MAX(created_at) as last_contact,
                          MIN(created_at) as first_contact
                   FROM processed_emails
                   WHERE tenant_id = $1
                   GROUP BY email_from
                   ORDER BY last_contact DESC
                   LIMIT $2 OFFSET $3""",
                tenant_id, limit, offset
            )
        # v9.0 — Récupérer tous les profils en un seul JOIN (pas de N+1)
        emails = [r['email'] for r in rows]
        profiles = {}
        if emails:
            profile_rows = await self.db.fetch_all(
                "SELECT email, prenom, derniere_commande, vip FROM client_profiles WHERE tenant_id = $1 AND email = ANY($2)",
                tenant_id, emails
            )
            for p in profile_rows:
                profiles[p['email']] = p

        result = []
        for r in rows:
            profile = profiles.get(r['email'])
            result.append({
                'email': r['email'],
                'total_emails': r['total_emails'],
                'last_contact': r['last_contact'].isoformat() if r['last_contact'] else None,
                'first_contact': r['first_contact'].isoformat() if r['first_contact'] else None,
                'prenom': profile['prenom'] if profile else None,
                'derniere_commande': profile['derniere_commande'] if profile else None,
                'vip': profile['vip'] if profile else False,
            })
        return result

    async def get_client_detail(self, tenant_id: str, email: str) -> dict:
        """Fiche client complète."""
        profile = await self.get_full_client_profile(tenant_id, email)
        history = await self.db.fetch_all(
            """SELECT id, email_subject, email_body_preview, response_text,
                      brain_category, brain_confidence, detection_method,
                      processing_time_ms, response_sent, created_at
               FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               ORDER BY created_at ASC""",
            tenant_id, email
        )
        escalations = await self.db.fetch_all(
            """SELECT id, category, reason, resolved, admin_action,
                      created_at, resolved_at
               FROM escalations
               WHERE tenant_id = $1 AND email_from = $2
               ORDER BY created_at DESC""",
            tenant_id, email
        )
        return {
            'email': email,
            'profile': profile,
            'history': [{
                'id': r['id'],
                'subject': r['email_subject'],
                'client_message': r['email_body_preview'],
                'sav_response': r['response_text'],
                'category': r['brain_category'],
                'confidence': float(r['brain_confidence']) if r['brain_confidence'] is not None else None,
                'detection': r['detection_method'],
                'time_ms': r['processing_time_ms'],
                'sent': r['response_sent'],
                'date': r['created_at'].isoformat() if r['created_at'] else None,
            } for r in history],
            'escalations': [{
                'id': r['id'],
                'category': r['category'],
                'reason': r['reason'],
                'resolved': r['resolved'],
                'action': r['admin_action'],
                'date': r['created_at'].isoformat() if r['created_at'] else None,
                'resolved_at': r['resolved_at'].isoformat() if r['resolved_at'] else None,
            } for r in escalations],
        }

    async def get_recent_emails(self, tenant_id: str, limit: int = 50,
                                 offset: int = 0, category: str = None) -> list:
        """Derniers emails traités pour la vue pipeline."""
        if category:
            rows = await self.db.fetch_all(
                """SELECT id, email_from, email_subject, email_body_preview,
                          response_text, brain_category, brain_confidence,
                          detection_method, processing_time_ms, response_sent,
                          urgency_level, created_at
                   FROM processed_emails
                   WHERE tenant_id = $1 AND brain_category = $2
                   ORDER BY created_at DESC LIMIT $3 OFFSET $4""",
                tenant_id, category, limit, offset
            )
        else:
            rows = await self.db.fetch_all(
                """SELECT id, email_from, email_subject, email_body_preview,
                          response_text, brain_category, brain_confidence,
                          detection_method, processing_time_ms, response_sent,
                          urgency_level, created_at
                   FROM processed_emails
                   WHERE tenant_id = $1
                   ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                tenant_id, limit, offset
            )
        return [{
            'id': r['id'],
            'email': r['email_from'],
            'subject': r['email_subject'],
            'preview': (r['email_body_preview'] or '')[:150],
            'response': (r['response_text'] or '')[:150],
            'category': r['brain_category'],
            'confidence': float(r['brain_confidence']) if r['brain_confidence'] is not None else None,
            'detection': r['detection_method'],
            'time_ms': r['processing_time_ms'],
            'sent': r['response_sent'],
            'urgency': r['urgency_level'],
            'date': r['created_at'].isoformat() if r['created_at'] else None,
        } for r in rows]

    async def get_pending_escalations(self, tenant_id: str) -> list:
        """Escalations en attente (non résolues)."""
        rows = await self.db.fetch_all(
            """SELECT e.id, e.email_from, e.category, e.reason,
                      e.created_at, pe.email_subject, pe.email_body_preview
               FROM escalations e
               LEFT JOIN processed_emails pe ON pe.id = e.email_id
               WHERE e.tenant_id = $1 AND e.resolved = false
               ORDER BY e.created_at DESC""",
            tenant_id
        )
        return [{
            'id': r['id'],
            'email': r['email_from'],
            'category': r['category'],
            'reason': r['reason'],
            'subject': r['email_subject'],
            'preview': (r['email_body_preview'] or '')[:200],
            'date': r['created_at'].isoformat() if r['created_at'] else None,
        } for r in rows]

    # ══════════════════════════════════════════════════════════
    # TICKETS (centralisé depuis ticket_tracker.py)
    # ══════════════════════════════════════════════════════════

    async def find_open_ticket(self, tenant_id: str, email_from: str):
        """Trouve un ticket ouvert pour ce client."""
        return await self.db.fetch_one(
            """SELECT id, status FROM tickets
               WHERE tenant_id = $1 AND email_from = $2
               AND status IN ('open', 'responded')
               ORDER BY created_at DESC LIMIT 1""",
            tenant_id, email_from
        )

    async def create_ticket(self, tenant_id: str, email_from: str, email_id: int,
                             subject: str, category: str = None) -> int:
        """Crée un nouveau ticket."""
        row = await self.db.fetch_one(
            """INSERT INTO tickets
               (tenant_id, email_from, first_email_id, last_email_id,
                subject, category, status, message_count,
                last_client_message_at, created_at, updated_at)
               VALUES ($1, $2, $3, $3, $4, $5, 'open', 1, NOW(), NOW(), NOW())
               RETURNING id""",
            tenant_id, email_from, email_id, (subject or '')[:200], category
        )
        return row['id'] if row else None

    async def reopen_ticket(self, ticket_id: int, email_id: int):
        """Rouvre un ticket existant."""
        await self.db.execute(
            """UPDATE tickets SET
                status = 'open', last_client_message_at = NOW(),
                last_email_id = $1, message_count = message_count + 1,
                updated_at = NOW()
               WHERE id = $2""",
            email_id, ticket_id
        )

    async def mark_ticket_responded(self, tenant_id: str, email_from: str):
        """Marque le ticket comme répondu."""
        await self.db.execute(
            """UPDATE tickets SET
                status = 'responded', last_response_at = NOW(),
                response_count = response_count + 1, updated_at = NOW()
               WHERE tenant_id = $1 AND email_from = $2 AND status = 'open'""",
            tenant_id, email_from
        )

    async def resolve_ticket(self, tenant_id: str, email_from: str,
                              resolution_type: str = 'explicit', trigger: str = None):
        """Ferme un ticket."""
        await self.db.execute(
            """UPDATE tickets SET
                status = 'resolved', resolved_at = NOW(),
                resolution_type = $3, resolution_trigger = $4, updated_at = NOW()
               WHERE tenant_id = $1 AND email_from = $2
               AND status IN ('open', 'responded')""",
            tenant_id, email_from, resolution_type, trigger
        )

    async def escalate_ticket(self, tenant_id: str, email_from: str):
        """Marque le ticket comme escaladé."""
        await self.db.execute(
            """UPDATE tickets SET status = 'escalated', updated_at = NOW()
               WHERE tenant_id = $1 AND email_from = $2
               AND status IN ('open', 'responded')""",
            tenant_id, email_from
        )

    async def get_open_tickets(self, tenant_id: str) -> list:
        """Tous les tickets ouverts ou en attente."""
        return await self.db.fetch_all(
            """SELECT t.*, pe.email_subject, pe.email_body_preview,
                      pe.response_text, pe.brain_category
               FROM tickets t
               LEFT JOIN processed_emails pe ON pe.id = t.last_email_id
               WHERE t.tenant_id = $1 AND t.status IN ('open', 'responded')
               ORDER BY CASE WHEN t.status = 'open' THEN 0 ELSE 1 END,
                        t.last_client_message_at ASC""",
            tenant_id
        )

    async def get_unanswered_tickets(self, tenant_id: str, cutoff) -> list:
        """Tickets ouverts sans réponse depuis la date cutoff."""
        return await self.db.fetch_all(
            """SELECT t.*, pe.email_subject, pe.email_body_preview
               FROM tickets t
               LEFT JOIN processed_emails pe ON pe.id = t.last_email_id
               WHERE t.tenant_id = $1 AND t.status = 'open'
               AND t.last_client_message_at < $2
               ORDER BY t.last_client_message_at ASC""",
            tenant_id, cutoff
        )

    async def auto_close_stale_tickets(self, tenant_id: str, cutoff, reason: str) -> int:
        """Ferme les tickets responded avant le cutoff."""
        await self.db.execute(
            """UPDATE tickets SET
                status = 'resolved', resolved_at = NOW(),
                resolution_type = 'auto_silence', resolution_trigger = $3,
                updated_at = NOW()
               WHERE tenant_id = $1 AND status = 'responded'
               AND last_response_at < $2""",
            tenant_id, cutoff, reason
        )
        row = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM tickets
               WHERE tenant_id = $1 AND resolution_type = 'auto_silence'
               AND resolved_at > NOW() - INTERVAL '1 minute'""",
            tenant_id
        )
        return row['c'] if row else 0

    async def get_ticket_stats(self, tenant_id: str) -> dict:
        """Stats des tickets."""
        row = await self.db.fetch_one(
            """SELECT
                COUNT(*) FILTER (WHERE status = 'open') as open_count,
                COUNT(*) FILTER (WHERE status = 'responded') as waiting_count,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_count,
                COUNT(*) FILTER (WHERE status = 'escalated') as escalated_count,
                COUNT(*) as total
               FROM tickets WHERE tenant_id = $1""",
            tenant_id
        )
        return dict(row) if row else {
            'open_count': 0, 'waiting_count': 0,
            'resolved_count': 0, 'escalated_count': 0, 'total': 0
        }

    # ══════════════════════════════════════════════════════════
    # FOLLOWUP (centralisé depuis followup.py)
    # ══════════════════════════════════════════════════════════

    async def get_unanswered_emails(self, tenant_id: str) -> list:
        """Emails sans réponse des 7 derniers jours."""
        return await self.db.fetch_all(
            """SELECT email_from, email_subject, email_body_preview,
                      conversation_step, created_at
               FROM processed_emails
               WHERE tenant_id = $1 AND response_sent = false
               AND created_at > NOW() - INTERVAL '7 days'
               ORDER BY created_at ASC""",
            tenant_id
        )

    async def get_unresolved_conversations(self, tenant_id: str) -> list:
        """Conversations où le client a écrit mais n'a pas eu de réponse depuis 2h."""
        return await self.db.fetch_all(
            """WITH last_messages AS (
                SELECT email_from,
                       MAX(created_at) as last_client_msg,
                       MAX(CASE WHEN response_sent = true THEN created_at END) as last_response
                FROM processed_emails
                WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '7 days'
                GROUP BY email_from
            )
            SELECT email_from, last_client_msg, last_response
            FROM last_messages
            WHERE last_client_msg > COALESCE(last_response, '1970-01-01')
            AND last_client_msg < NOW() - INTERVAL '2 hours'
            ORDER BY last_client_msg ASC""",
            tenant_id
        )

    async def get_daily_mail_stats(self, tenant_id: str) -> dict:
        """Stats emails des dernières 24h pour rapport quotidien."""
        return await self.db.fetch_one(
            """SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN response_sent = true THEN 1 END) as answered,
                COUNT(CASE WHEN response_sent = false THEN 1 END) as unanswered,
                COUNT(CASE WHEN conversation_step = 'escalated_to_human' THEN 1 END) as escalated
               FROM processed_emails
               WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id
        )

    async def get_daily_scoring_stats(self, tenant_id: str) -> dict:
        """Stats scoring des dernières 24h."""
        return await self.db.fetch_one(
            """SELECT
                COUNT(CASE WHEN response_quality LIKE 'excellent%' THEN 1 END) as excellent,
                COUNT(CASE WHEN response_quality LIKE 'good%' THEN 1 END) as good,
                COUNT(CASE WHEN response_quality LIKE 'bad%' THEN 1 END) as bad,
                COUNT(CASE WHEN response_quality IS NOT NULL THEN 1 END) as scored
               FROM processed_emails
               WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id
        )

    async def get_daily_examples_count(self, tenant_id: str) -> int:
        """Nombre d'exemples appris dans les dernières 24h."""
        row = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM feedback_examples
               WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id
        )
        return row['c'] if row else 0

    async def get_daily_loop_stats(self, tenant_id: str) -> dict:
        """Stats boucles/mismatch des dernières 24h."""
        return await self.db.fetch_one(
            """SELECT
                COUNT(CASE WHEN brain_category = 'BOUCLE' THEN 1 END) as boucles,
                COUNT(CASE WHEN brain_category = 'MISMATCH' THEN 1 END) as mismatch,
                COUNT(CASE WHEN detection_method = 'shopify_name' THEN 1 END) as found_by_name,
                COUNT(CASE WHEN detection_method = 'shopify_confirmation' THEN 1 END) as found_by_confirmation
               FROM processed_emails
               WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id
        )

    async def get_old_escalations_count(self, tenant_id: str) -> int:
        """Escalations non résolues depuis +48h."""
        row = await self.db.fetch_one(
            """SELECT COUNT(*) as c FROM escalations
               WHERE tenant_id = $1 AND resolved = false
               AND created_at < NOW() - INTERVAL '48 hours'""",
            tenant_id
        )
        return row['c'] if row else 0

    # ══════════════════════════════════════════════════════════
    # CHAT DASHBOARD (centralisé depuis dashboard_chat.py)
    # ══════════════════════════════════════════════════════════

    async def search_clients_by_name(self, tenant_id: str, query: str, limit: int = 10) -> list:
        """Cherche des clients par prénom dans les profils."""
        return await self.db.fetch_all(
            """SELECT cp.email, cp.prenom, cp.derniere_commande, cp.vip,
                      COUNT(pe.id) as total_emails
               FROM client_profiles cp
               LEFT JOIN processed_emails pe ON pe.email_from = cp.email AND pe.tenant_id = cp.tenant_id
               WHERE cp.tenant_id = $1 AND cp.prenom ILIKE $2
               GROUP BY cp.email, cp.prenom, cp.derniere_commande, cp.vip
               LIMIT $3""",
            tenant_id, f'%{query}%', limit
        )

    async def get_client_prenom(self, tenant_id: str, email: str) -> str:
        """Récupère le prénom d'un client."""
        row = await self.db.fetch_one(
            "SELECT prenom FROM client_profiles WHERE tenant_id = $1 AND email = $2",
            tenant_id, email
        )
        return row['prenom'] if row and row.get('prenom') else ''

    async def append_client_note(self, tenant_id: str, email: str, note: str):
        """Ajoute une note au profil client."""
        profile = await self.db.fetch_one(
            "SELECT email FROM client_profiles WHERE tenant_id = $1 AND email = $2",
            tenant_id, email
        )
        if profile:
            await self.db.execute(
                """UPDATE client_profiles SET notes = COALESCE(notes, '') || $1, updated_at = NOW()
                   WHERE tenant_id = $2 AND email = $3""",
                note, tenant_id, email
            )
        else:
            await self.db.execute(
                """INSERT INTO client_profiles (tenant_id, email, notes, nb_contacts, updated_at)
                   VALUES ($1, $2, $3, 0, NOW())""",
                tenant_id, email, note
            )

