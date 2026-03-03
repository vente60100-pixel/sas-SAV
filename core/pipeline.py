"""
OKTAGON SAV v11.0 — Pipeline unifié
1 seul chemin : filter → identify → extract → enrich → cerveau → post-process → respond
Plus de menu, plus de double IA, plus de handlers par catégorie.
"""
import asyncio
import json
import time
import asyncpg
from core.memory_summarizer import build_smart_history
from core.emotional_intelligence import analyze_emotion, get_emotion_label, analyze_emotion_trajectory
from core.client_memory import build_client_context
from core.conversation_reader import get_full_conversation, format_conversation_for_ai, enrich_profile_from_conversation
from workers.ticket_tracker import (
    detect_resolution, open_ticket, mark_ticket_responded,
    resolve_ticket, escalate_ticket
)
from core.auto_scoring import (
    check_data_accuracy, score_response, score_previous_response
)
from core.info_extractor import extract_client_info, update_client_memory
from core.learning import (
    detect_satisfaction, get_feedback_examples, format_examples_for_prompt,
    update_learning_stats, save_feedback_example,
)
import re

from core.models import Ticket, Response
from core.constants import (
    BLOCKED_EXACT, BLOCKED_PATTERNS, STEP_ESCALATED
)
from domain.rules import (
    smart_detect_first_message, detect_human_request, detect_urgency,
    extract_signed_name, clean_reply_body, parse_shopify_contact_form,
    analyze_order_items
)
from knowledge.unified_brain import build_unified_prompt
from knowledge.templates import (
    build_ai_response_html, build_escalation_html
)

from logger import logger

# v6.0 — Validation & metrics
from core.validators import validate_and_sanitize_response, AIResponseValidationError
from core.lie_detector import detect_lies, format_violation_report
from core.metrics import metrics



def safe_dict_get(obj, key, default=None):
    """Helper pour éviter les crashes 'str' object has no attribute 'get'"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

class Pipeline:
    """Pipeline v5.0 — cerveau unifié."""

    def __init__(self, tenant, repos, ecommerce, channel, ai, notifier,
                 security_check_fn):
        self.tenant = tenant
        self.repos = repos
        self.db = repos.db  # Accès direct à la DB pour learning/memory
        self.ecommerce = ecommerce
        self.channel = channel
        self.ai = ai
        self.notifier = notifier
        self.security_check = security_check_fn

    # ══════════════════════════════════════════════════════════
    # POINT D'ENTRÉE
    # ══════════════════════════════════════════════════════════

    async def process(self, message) -> None:
        """Traite un message entrant — pipeline complet."""
        start = time.time()
        ticket = Ticket(
            tenant_id=self.tenant.id,
            email_from=message.sender,
            sender_name=getattr(message, 'sender_name', '') or '',
            subject=message.subject,
            body=message.body,
            message_id=message.message_id,
            in_reply_to=message.in_reply_to,
            references=message.references,
            headers=message.headers or {},
            raw_content=message.raw_content,
            cc=getattr(message, 'cc', '') or '',
            attachment_names=getattr(message, 'attachment_names', []) or [],
        )

        logger.info(
            f"═══ EMAIL REÇU ═══ De: {ticket.email_from} | Sujet: {ticket.subject[:80]}",
            extra={"action": "email_received", "email_from": ticket.email_from, "tenant": self.tenant.id}
        )


        # 🚨 BLOCAGE PRÉVENTIF DES DUPLICATES (AVANT APPEL API)
        if ticket.subject and ticket.subject.startswith("Re: Re:"):
            already_sent = await self.repos.count_recent_responses(
                self.tenant.id, ticket.email_from, hours=24
            )
            if already_sent > 0:
                logger.warning(
                    f"DUPLICATE BLOQUÉ: {ticket.email_from} ({already_sent} réponses en 24h)",
                    extra={"action": "duplicate_prevented", "already_sent": already_sent}
                )
                return
            logger.info(
                f"Re: Re: détecté mais aucune réponse envoyée à {ticket.email_from} — traitement normal",
                extra={"action": "first_response_needed"}
            )



        try:
            # 1. FILTER
            if not await self._filter(ticket):
                return

            # 2. IDENTIFY
            await self._identify(ticket)
            # Plus de return si escaladé — l'IA gère TOUT

            # 2b. Vérifier si _identify a marqué comme spam (ex: notif Shopify)
            if ticket.is_spam:
                logger.info(f"Email marqué spam par _identify: {ticket.email_from}",
                            extra={"action": "identify_spam_blocked"})
                return

            # 3. (v9.0 — steps supprimés, cerveau unifié gère tout)

            # 4. EXTRACT — trouver le numéro de commande
            await self._extract_order(ticket)

            # 5. ENRICH — données Shopify + profil + historique
            await self._enrich(ticket)

            # 6. CERVEAU UNIFIÉ — 1 seul appel IA
            response = await self._unified_brain(ticket)

            # 7. POST-PROCESS — logique métier après le cerveau
            if response:
                response = await self._post_process(ticket, response)

            # 8. RESPOND — envoyer + sauvegarder
            if response:
                await self._respond(ticket, response)

        except Exception as e:
            logger.error(f"ERREUR PIPELINE: {e}", extra={"action": "pipeline_error",
                         "email_from": ticket.email_from, "error": str(e)})
            # En cas d'erreur, escalader plutôt que crasher silencieusement
            if self.notifier:
                await self.notifier(
                    f"💥 <b>ERREUR PIPELINE</b>\nDe: {ticket.email_from}\nErreur: {str(e)[:200]}"
                )

        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"Email traité en {duration_ms}ms",
                    extra={"action": "email_processed", "duration_ms": duration_ms, "tenant": self.tenant.id})

    async def reprocess(self, email_id: int) -> bool:
        """Retraite un email existant en DB — saute le filtre.
        Utilisé par recovery pour les emails ready_for_ai bloqués."""
        start = time.time()

        # Charger l'email depuis la DB
        row = await self.db.fetch_one(
            "SELECT id, email_from, email_subject, email_body_preview, "
            "message_id, language, conversation_step "
            "FROM processed_emails WHERE id = $1 AND tenant_id = $2",
            email_id, self.tenant.id
        )
        if not row:
            logger.warning(f"REPROCESS: email {email_id} non trouve")
            return False

        # Créer un ticket minimal
        ticket = Ticket(
            tenant_id=self.tenant.id,
            email_from=row['email_from'],
            subject=row['email_subject'] or 'SAV',
            body=row['email_body_preview'] or '',
            message_id=row['message_id'] or f"reprocess-{email_id}",
        )
        ticket.db_id = email_id
        ticket.language = row['language'] or 'fr'

        logger.info(
            f"REPROCESS | {ticket.email_from} | {(ticket.subject or '')[:50]}",
            extra={"action": "reprocess_start"}
        )

        try:
            # Sauter _filter et _identify — aller directement au traitement
            # 3. EXTRACT ORDER
            await self._extract_order(ticket)

            # 4. ENRICH
            await self._enrich(ticket)

            # 5. CERVEAU IA
            response = await self._unified_brain(ticket)
            if not response:
                logger.info(f"REPROCESS: cerveau a ignore {ticket.email_from}")
                return False

            # 6. POST-PROCESS
            response = await self._post_process(ticket, response)

            # 7. RESPOND
            if response:
                await self._respond(ticket, response)

            elapsed = time.time() - start
            logger.info(
                f"REPROCESS OK | {ticket.email_from} | {elapsed:.1f}s",
                extra={"action": "reprocess_done", "elapsed": elapsed}
            )
            return True

        except Exception as e:
            logger.error(
                f"REPROCESS ERREUR | {ticket.email_from} | {e}",
                extra={"action": "reprocess_error", "error": str(e)}
            )
            return False

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 1 : FILTER (inchangé)
    # ══════════════════════════════════════════════════════════

    async def _filter(self, ticket: Ticket) -> bool:
        """Filtre spam, emails système, rate limit. Retourne True si OK."""
        email_lower = ticket.email_from.lower()

        # Blocked exact
        all_blocked_exact = BLOCKED_EXACT + [
            self.tenant.channel_config.get('address', '').lower()
        ] + self.tenant.blocked_emails
        if email_lower in all_blocked_exact:
            logger.info(f"Email système ignoré: {ticket.email_from}",
                        extra={"action": "system_email_blocked"})
            return False

        # Blocked patterns — SAUF emails Shopify (formulaires de contact)
        SHOPIFY_WHITELIST = ['mailer@shopify.com', 'no-reply@shopify.com', 'noreply@shopify.com']
        if email_lower not in SHOPIFY_WHITELIST and any(p in email_lower for p in BLOCKED_PATTERNS):
            logger.info(f"Email pattern bloqué: {ticket.email_from}",
                        extra={"action": "pattern_blocked"})
            return False

        # Spam sujet
        if ticket.subject and '*** spam ***' in ticket.subject.lower():
            logger.info(f"SPAM sujet: {ticket.email_from}",
                        extra={"action": "spam_subject_blocked"})
            return False

        # Rate limit
        can_send = await self.repos.can_send(
            self.tenant.id, ticket.email_from,
            self.tenant.max_emails_per_hour, self.tenant.max_emails_per_day
        )
        if not can_send:
            logger.warning(f"Rate limit: {ticket.email_from}",
                           extra={"action": "rate_limited"})
            existing = await self.repos.find_active_escalation(
                self.tenant.id, ticket.email_from, "RATE_LIMIT"
            )
            if not existing:
                rl_email_id = await self.repos.create_email(
                    self.tenant.id, ticket.email_hash or f'rl_{ticket.email_from}_{__import__("time").time()}', ticket.email_from,
                    ticket.subject, ticket.body[:200], ticket.language or 'fr',
                    conversation_step='escalated_to_human',
                    category='RATE_LIMIT', message_id=ticket.message_id
                )
                esc_id = await self.repos.create_escalation(
                    self.tenant.id, rl_email_id, ticket.email_from, "RATE_LIMIT",
                    "Client rate limité — intervention humaine requise"
                )
                if self.notifier:
                    await self.notifier(
                        f"⚠️ <b>RATE LIMIT</b>\nClient: {ticket.email_from}\n→ Escalade #{esc_id}"
                    )
            return False

        # Security check
        sec = await self.security_check(
            ticket.email_from, ticket.subject, ticket.body,
            ticket.headers, ticket.raw_content
        )
        ticket.email_hash = sec.email_hash
        ticket.is_spam = sec.is_spam
        ticket.spam_reason = sec.spam_reason
        ticket.is_auto_responder = sec.is_auto_responder
        ticket.is_thank_you = sec.is_thank_you
        ticket.language = sec.language
        ticket.has_attachments = sec.has_attachments
        ticket.attachment_count = sec.attachment_count
        if sec.order_number:
            ticket.order_number = sec.order_number

        if sec.is_spam:
            logger.info(f"SPAM ignoré: {sec.spam_reason}", extra={"action": "spam_ignored"})
            return False
        if sec.is_thank_you:
            logger.info(f"Remerciement ignoré", extra={"action": "thanks_ignored"})
            return False

        # Déduplication gérée par ON CONFLICT dans l'INSERT

        return True

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 2 : IDENTIFY (simplifié — plus de menu)
    # ══════════════════════════════════════════════════════════

    async def _identify(self, ticket: Ticket):
        """Identifie le contexte : Shopify form, escaladé, step intermédiaire."""

        # Shopify form ?
        if ticket.email_from in ['mailer@shopify.com', 'no-reply@shopify.com', 'noreply@shopify.com']:
            if 'formulaire de contact' in ticket.body.lower() or 'contact form' in ticket.body.lower():
                real_email, commentaire = parse_shopify_contact_form(ticket.body)
                if real_email:
                    ticket.is_shopify_form = True
                    ticket.real_email = real_email
                    ticket.email_from = real_email
                    ticket.body = commentaire or ticket.body
                    logger.info(f"Shopify form → {real_email}",
                                extra={"action": "shopify_form_detected"})
                else:
                    return
            else:
                logger.info(f"Shopify notif ignorée", extra={"action": "shopify_notif_ignored"})
                ticket.is_spam = True
                return

        # Session existante ? (pour les steps intermédiaires)
        parent = await self.repos.find_active_session(self.tenant.id, ticket.email_from)
        if parent:
            ticket.session_id = parent['id']
            ticket.conversation_step = parent['conversation_step']
            ticket.collected_data = json.loads(parent['collected_data']) if parent.get('collected_data') and parent['collected_data'] != '{}' else {}
            ticket.is_reply = True

            # Si session en step intermédiaire ET c'est un nouveau sujet → reset
            if not ticket.in_reply_to:
                is_re = any(ticket.subject.lower().startswith(p) for p in ['re:', 're :', 'aw:', 'r:'])
                if not is_re:
                    ticket.session_id = None
                    ticket.conversation_step = "new"
                    ticket.collected_data = {}
                    ticket.is_reply = False

        # Client escaladé récemment ? → on note mais on répond quand même
        escalated = await self.repos.find_escalated(self.tenant.id, ticket.email_from)
        if escalated:
            logger.info(f"Client était escaladé — IA reprend la main",
                        extra={"action": "escalated_resumed"})
            # Ne PAS silencer — l'IA va répondre normalement

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 3 : EXTRACT ORDER (nouveau — remplace _classify)
    # ══════════════════════════════════════════════════════════

    async def _extract_order(self, ticket: Ticket):
        """Extrait le numéro de commande. C'est TOUT.
        Pas de classification — le cerveau IA s'en charge."""

        # 1. Regex sur sujet+body
        _, order_num = smart_detect_first_message(ticket.subject, ticket.body)
        if order_num:
            ticket.order_number = order_num
            ticket.detection_method = 'regex'
            logger.info(f"⚡ Numéro extrait par regex: #{order_num}",
                        extra={"action": "order_extracted_regex"})
            return

        # 2. Si security check a trouvé un numéro
        if ticket.order_number:
            ticket.detection_method = 'security'
            return

        # 2b. Chercher un numéro de confirmation dans le body (v7.3)
        # Format: code alphanumérique type 5RLVXHTWI (pas un numéro de commande #XXXX)
        import re as _re2
        body_text = (ticket.body or '') + ' ' + (ticket.subject or '')
        # Patterns: "confirmation 5RLVXHTWI" ou "n° 5RLVXHTWI" ou "numéro 5RLVXHTWI"
        conf_patterns = _re2.findall(
            r'(?:confirmation|n°|numero|numéro)[^a-zA-Z0-9]*([A-Z0-9]{8,12})',
            body_text, _re2.IGNORECASE
        )
        # Aussi chercher dans l'historique de conversation
        history_text = getattr(ticket, 'conversation_history', '') or ''
        conf_patterns += _re2.findall(
            r'(?:confirmation|n°|numero|numéro)[^a-zA-Z0-9]*([A-Z0-9]{8,12})',
            history_text, _re2.IGNORECASE
        )
        for conf_num in conf_patterns:
            conf_num = conf_num.upper()
            # Vérifier que c'est pas un numéro de commande standard
            if conf_num.isdigit():
                continue
            try:
                order = await self.ecommerce.search_by_confirmation(conf_num)
                if order:
                    ticket.order_number = str(order.get('order_number', '')).replace('#', '')
                    ticket.order_details = order
                    ticket.detection_method = 'shopify_confirmation'
                    logger.info(
                        f"📦 Commande trouvée par CONFIRMATION ({conf_num}): #{ticket.order_number}",
                        extra={"action": "order_found_by_confirmation"}
                    )
                    return
            except (OSError, ValueError, KeyError) as e:
                logger.debug(f"Recherche confirmation {conf_num} erreur: {e}")

        # 3. Lookup Shopify par email
        try:
            orders = await self.ecommerce.get_orders_by_email(ticket.email_from)
            if orders:
                if len(orders) == 1:
                    # 1 seule commande → on la prend
                    ticket.order_number = str(orders[0].get('order_number', '')).replace('#', '')
                    ticket.detection_method = 'shopify_email_single'
                    logger.info(f"📦 1 commande trouvée par email: #{ticket.order_number}",
                                extra={"action": "order_found_by_email"})
                else:
                    # Plusieurs commandes → stocker dans all_orders pour le cerveau
                    ticket.all_orders = orders
                    ticket.detection_method = 'shopify_email_multiple'
                    logger.info(f"📦 {len(orders)} commandes trouvées par email",
                                extra={"action": "multiple_orders_found"})
            else:
                # 4. Pas de commande par email → recherche exhaustive par nom (v7.3)
                name_found = await self._search_by_name_exhaustive(ticket)
                if not name_found:
                    ticket.detection_method = 'none'
                    logger.info(f"Aucune commande trouvée pour {ticket.email_from} (email+nom+préfixe)",
                                extra={"action": "no_order_found"})
        except (OSError, ValueError, KeyError) as e:
            logger.error(f"Shopify lookup erreur: {e}", extra={"action": "shopify_lookup_error"})
            ticket.detection_method = 'error'

    async def _search_by_name_exhaustive(self, ticket: Ticket) -> bool:
        """v7.3 — Recherche exhaustive par nom : essaie TOUT avant d'abandonner.
        Retourne True si une commande a été trouvée."""
        import re as _re

        # Collecter tous les noms possibles à essayer
        names_to_try = []

        # 1. Nom du client (extrait du mail ou de Shopify)
        if ticket.customer_name and len(ticket.customer_name.strip()) > 2:
            names_to_try.append(ticket.customer_name.strip())

        # 2. Nom signé dans le body
        signed = extract_signed_name(ticket.body)
        if signed and signed not in names_to_try:
            names_to_try.append(signed)

        # 3. Nom extrait du préfixe email (jacqueslemoine751@gmail.com → jacques lemoine)
        prefix = ticket.email_from.split('@')[0].lower()
        prefix_clean = _re.sub(r'[0-9._\-]+', ' ', prefix).strip()
        if prefix_clean and len(prefix_clean) > 3 and prefix_clean not in [n.lower() for n in names_to_try]:
            # Essayer de découper les prénoms/noms collés (jacqueslemoine → jacques lemoine)
            # On cherche tel quel, Shopify fera le matching
            names_to_try.append(prefix_clean)

        # 4. Nom mentionné dans le body (pattern "Prénom Nom" ou "Nom Prénom")
        body_clean = (ticket.body or '')[:500]
        # Chercher des patterns type "je suis Prénom Nom" ou signature
        name_patterns = _re.findall(r'(?:je suis|moi c.est|nom[: ]+|prenom[: ]+|cordialement[, ]+)([A-ZA-Za-zÀ-ü]+ [A-ZA-Za-zÀ-ü]+)', body_clean, _re.IGNORECASE)
        for np in name_patterns:
            if np.strip() not in names_to_try and len(np.strip()) > 4:
                names_to_try.append(np.strip())

        # Essayer chaque nom sur Shopify
        for name in names_to_try:
            parts = name.split()
            if len(parts) < 2:
                continue
            try:
                name_orders = await self.ecommerce.search_orders_by_name(parts[0], parts[-1])
                if name_orders:
                    if len(name_orders) == 1:
                        ticket.order_number = str(name_orders[0].get('order_number', '')).replace('#', '')
                        ticket.detection_method = 'shopify_name_single'
                        logger.info(
                            f"📦 Commande trouvée par NOM ({name}): #{ticket.order_number}",
                            extra={"action": "order_found_by_name"}
                        )
                    else:
                        ticket.all_orders = name_orders
                        ticket.detection_method = 'shopify_name_multiple'
                        logger.info(
                            f"📦 {len(name_orders)} commandes trouvées par NOM ({name})",
                            extra={"action": "multiple_orders_found_by_name"}
                        )
                    return True
            except (OSError, ValueError, KeyError) as e:
                logger.debug(f"Recherche par nom ({name}) erreur: {e}")
                continue

        return False

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 4 : ENRICH
    # ══════════════════════════════════════════════════════════

    async def _enrich(self, ticket: Ticket):
        """Enrichit avec données Shopify, historique, profil, urgence."""

        # Nom signé
        ticket.signed_name = extract_signed_name(ticket.body)

        # Commande Shopify
        if ticket.order_number:
            try:
                order = await self.ecommerce.get_order(ticket.order_number)
                if order:
                    ticket.order_details = order
                    if not ticket.signed_name:
                        shopify_name = order.get('customer_name', '')
                        if shopify_name:
                            ticket.customer_name = shopify_name.split()[0]
                    else:
                        ticket.customer_name = ticket.signed_name
            except (OSError, ValueError, KeyError) as e:
                logger.error(f"Shopify get_order erreur: {e}", extra={"action": "shopify_error"})

        # Multi-commandes : utiliser all_orders déjà chargé par _extract_order
        if not ticket.order_number and not ticket.order_details:
            existing_orders = getattr(ticket, 'all_orders', None)
            if existing_orders:
                if len(existing_orders) == 1:
                    # 1 seule commande → on la prend directement
                    ticket.order_details = existing_orders[0]
                    ticket.order_number = str(existing_orders[0].get('order_number', '')).replace('#', '')
                else:
                    # v9.0 — Multi-commandes : chercher si le client mentionne un numéro
                    body_text = (ticket.body or '') + ' ' + (ticket.subject or '')
                    import re as _re_multi
                    mentioned_nums = _re_multi.findall(r'#?(\d{4,6})', body_text)
                    matched = None
                    for num in mentioned_nums:
                        for order in existing_orders:
                            on = str(order.get('order_number', '')).replace('#', '')
                            if on == num:
                                matched = order
                                break
                        if matched:
                            break
                    if matched:
                        ticket.order_details = matched
                        ticket.order_number = str(matched.get('order_number', '')).replace('#', '')
                        logger.info(f"📦 Multi-commandes: #{ticket.order_number} matchée par mention",
                                    extra={"action": "multi_order_matched"})
                    else:
                        # Pas de mention → la plus récente comme référence principale
                        ticket.order_details = existing_orders[0]
                        ticket.order_number = str(existing_orders[0].get('order_number', '')).replace('#', '')
                        logger.info(f"📦 Multi-commandes: #{ticket.order_number} (plus récente par défaut)",
                                    extra={"action": "multi_order_default"})
                # Extraire le prénom client
                if not ticket.signed_name:
                    shopify_name = (ticket.order_details or {}).get('customer_name', '')
                    if shopify_name:
                        ticket.customer_name = shopify_name.split()[0]
                logger.info(f"📦 {len(existing_orders)} commande(s) enrichie(s) pour {ticket.email_from}",
                            extra={"action": "multi_orders_enriched"})

        elif ticket.signed_name:
            ticket.customer_name = ticket.signed_name

        # Historique conversation INTELLIGENT (résumé + derniers échanges)
        try:
            smart_history = await build_smart_history(
                self.db, self.ai, self.tenant.id, ticket.email_from
            )
            ticket.conversation_history = smart_history if smart_history else ""
        except (OSError, ValueError, TypeError, asyncpg.PostgresError) as e:
            logger.warning(f"Erreur historique intelligent: {e}")
            # Fallback : ancien système brut
            history_rows = await self.repos.get_conversation_history(
                self.tenant.id, ticket.email_from
            )
            if history_rows:
                history = "\n"
                for r in reversed(history_rows):
                    date = r['created_at'].strftime('%d/%m %H:%M')
                    client_msg = (r.get('email_body_preview') or '')[:300].strip()
                    if client_msg:
                        history += f"[{date}] CLIENT: {client_msg}\n"
                    resp = (r.get('response_text') or '')[:300].strip()
                    if resp:
                        history += f"[{date}] SAV: {resp}\n"
                    history += "---\n"
                ticket.conversation_history = history

        # v7.1 — Scorer la réponse précédente (réaction client)
        try:
            await score_previous_response(
                self.db, self.tenant.id, ticket.email_from,
                ticket.body, ticket.subject
            )
        except (ValueError, TypeError, asyncpg.PostgresError) as e:
            logger.debug(f"Erreur scoring retour: {e}")

        # Intelligence émotionnelle v6.3 — analyser le ton du client
        ticket.emotion = analyze_emotion(
            ticket.body, ticket.subject, ticket.conversation_history
        )
        emotion_label = get_emotion_label(
            ticket.emotion['primary_emotion'], ticket.emotion['emotion_score']
        )
        logger.info(f"Émotion: {emotion_label} | triggers={ticket.emotion.get('detected_triggers', [])}",
                    extra={'action': 'emotion_detected',
                           'emotion': ticket.emotion['primary_emotion'],
                           'score': ticket.emotion['emotion_score']})

        # v10.0 — Trajectoire emotionnelle
        try:
            trajectory = await analyze_emotion_trajectory(
                self.db, self.tenant.id, ticket.email_from, ticket.emotion
            )
            ticket.emotion_trajectory = trajectory
            if trajectory.get('urgency_boost') and ticket.urgency_level not in ('CRITICAL', 'HIGH'):
                ticket.urgency_level = 'HIGH'
                logger.info(f"Urgence montee a HIGH (trajectoire emotionnelle montante)",
                            extra={'action': 'emotion_trajectory', 'trajectory': trajectory.get('trajectory')})
        except (ValueError, TypeError):
            ticket.emotion_trajectory = None

        # Profil client ENRICHI v6.3 (tags, fidélité, état conversation, instructions)
        try:
            ticket.client_profile = await build_client_context(
                self.db, self.repos, self.tenant.id, ticket.email_from,
                current_emotion=ticket.emotion
            )
            # Si pas de prénom signé, utiliser celui du profil persistant
            if not ticket.customer_name and isinstance(ticket.client_profile, dict) and ticket.client_profile.get('prenom'):
                ticket.customer_name = ticket.client_profile['prenom']
            # v8.1 — Fallback : nom affiché dans le header From
            if not ticket.customer_name and ticket.sender_name:
                # Extraire le prénom du nom complet (ex: "Jacques Lemoine" → "Jacques")
                parts = ticket.sender_name.strip().split()
                if parts and len(parts[0]) >= 2:
                    ticket.customer_name = parts[0].capitalize()
        except (ValueError, TypeError, KeyError, asyncpg.PostgresError) as e:
            logger.warning(f"Erreur profil enrichi: {e}")
            ticket.client_profile = {}

        # Détection satisfaction — analyser le sentiment du client
        if ticket.conversation_history:
            try:
                last_response = await self.repos.get_last_sav_response(
                    self.tenant.id, ticket.email_from
                )
                satisfaction = detect_satisfaction(ticket.body, last_response)
                ticket.satisfaction = satisfaction
                if satisfaction['score'] is not None:
                    logger.info(f"Satisfaction détectée: {satisfaction['sentiment']} "
                                f"(score={satisfaction['score']:.1f})",
                                extra={'action': 'satisfaction_detected',
                                       'sentiment': satisfaction['sentiment']})
            except (ValueError, TypeError):
                ticket.satisfaction = {'score': None, 'sentiment': 'unknown', 'source': 'error'}
        else:
            ticket.satisfaction = {'score': None, 'sentiment': 'unknown', 'source': 'first_contact'}

        # v7.0 — Extraction d'infos client (adresse, tel, etc.)
        try:
            ticket.extracted_info = extract_client_info(ticket.body, ticket.subject)
            if ticket.extracted_info['extracted_infos']:
                await update_client_memory(
                    self.db, self.tenant.id, ticket.email_from, ticket.extracted_info
                )
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"Erreur extraction infos: {e}")
            ticket.extracted_info = {'extracted_infos': []}

        # v7.0 — Détecter si le client résout son ticket
        ticket.resolution = detect_resolution(ticket.body, ticket.subject)
        if ticket.resolution['is_resolved']:
            logger.info(
                f"🏁 Client résout son ticket: {ticket.resolution['resolution_type']} "
                f"({ticket.resolution['trigger']})",
                extra={'action': 'resolution_detected'}
            )
            await resolve_ticket(
                self.db, self.tenant.id, ticket.email_from,
                ticket.resolution['resolution_type'],
                ticket.resolution['trigger']
            )

        # Les exemples appris sont chargés dans _unified_brain (après classification)
        ticket.learned_examples = ""

        # Urgence
        ticket.urgency_level = detect_urgency(
            ticket.subject, ticket.body, ticket.client_profile
        )
        if ticket.urgency_level in ('CRITICAL', 'HIGH') and self.notifier:
            await self.notifier(
                f"🔴 <b>URGENCE {ticket.urgency_level}</b>\n"
                f"De: {ticket.email_from}\nSujet: {ticket.subject[:100]}"
            )

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 5 : CERVEAU UNIFIÉ
    # ══════════════════════════════════════════════════════════

    async def _unified_brain(self, ticket: Ticket) -> Response:
        """1 seul appel IA avec TOUT le dossier client."""

        # Vérifier demande humain AVANT le cerveau (pas besoin d'IA pour ça)
        cleaned_body = clean_reply_body(ticket.body)
        if detect_human_request(cleaned_body):
            logger.info(f"Client demande contact humain — IA repond avec empathie",
                        extra={"action": "human_request_detected"})
            # L'IA repond quand meme avec empathie, pas de silence
            # Le cerveau IA va voir la demande et adapter sa reponse

        # Vérifier identité Shopify (email mismatch INTELLIGENT v7.3)
        if ticket.order_details and isinstance(ticket.order_details, dict):
            shopify_email = (ticket.order_details.get('customer_email') or '').lower().strip()
            client_email = ticket.email_from.lower().strip()
            if shopify_email and shopify_email != client_email:
                # Niveau 1 : Même préfixe email (avant @) → même personne
                client_prefix = client_email.split('@')[0]
                shopify_prefix = shopify_email.split('@')[0]

                # Niveau 2 : Même nom client → même personne
                shopify_name = (ticket.order_details.get('customer_name') or '').lower().strip()
                client_name = (ticket.customer_name or '').lower().strip()

                names_match = (
                    shopify_name and client_name
                    and len(client_name) > 2
                    and (client_name in shopify_name or shopify_name in client_name)
                )
                prefixes_match = (
                    client_prefix and shopify_prefix
                    and len(client_prefix) > 2
                    and client_prefix == shopify_prefix
                )

                if names_match or prefixes_match:
                    # Même personne avec 2 emails → on traite normalement
                    match_reason = "nom" if names_match else "préfixe email"
                    logger.info(
                        f"✅ MISMATCH RÉSOLU par {match_reason} | "
                        f"Client: {client_email} | Shopify: {shopify_email} | "
                        f"Nom client: {client_name} | Nom Shopify: {shopify_name}",
                        extra={"action": "mismatch_resolved", "match_by": match_reason}
                    )
                else:
                    # Vraiment pas le même client → réponse directe (pas d'escalade)
                    logger.warning(
                        f"⚠️ IDENTITÉ MISMATCH | "
                        f"Client: {client_email} ({client_name}) | "
                        f"Shopify: {shopify_email} ({shopify_name})",
                        extra={"action": "identity_mismatch"}
                    )
                    return Response(
                        text=f"Bonjour,\n\nNous n'avons pas trouvé la commande "
                             f"**#{ticket.order_number}** associée à votre adresse email.\n\n"
                             f"Pourriez-vous vérifier votre numéro de commande dans "
                             f"l'email de confirmation reçu lors de votre achat ?\n\n"
                             f"Cordialement,\n**L'équipe {self.tenant.brand_name}**",
                        should_send=True, category='MISMATCH', confidence=1.0
                    )

        # v7.3 — Détection anti-boucle (même réponse envoyée 2+ fois)
        try:
            recent_responses = await self.repos.get_recent_responses(
                self.tenant.id, ticket.email_from, limit=3
            )
            if len(recent_responses) >= 2:
                from difflib import SequenceMatcher
                # Comparer les 2 dernières réponses entre elles
                r1 = (recent_responses[0]['response_text'] or '')[:300].lower()
                r2 = (recent_responses[1]['response_text'] or '')[:300].lower()
                similarity = SequenceMatcher(None, r1, r2).ratio()

                if similarity > 0.65:
                    # Boucle détectée → escalade en DB (sans Telegram)
                    logger.warning(
                        f"🔄 BOUCLE DÉTECTÉE | {ticket.email_from} | "
                        f"Similarité: {similarity:.0%} entre les 2 dernières réponses",
                        extra={"action": "loop_detected", "similarity": similarity}
                    )
                    return Response(
                        text=f"Bonjour,\n\nVotre demande a bien été prise en compte. "
                             f"Un conseiller de notre équipe va vous répondre personnellement "
                             f"dans les plus brefs délais.\n\n"
                             f"Cordialement,\n**L'équipe {self.tenant.brand_name}**",
                        should_send=True, should_escalate=True,
                        category='BOUCLE', confidence=1.0,
                        escalation_reason=f"Boucle détectée: {similarity:.0%} similarité sur 2 réponses"
                    )
        except (ValueError, TypeError, asyncpg.PostgresError) as e:
            logger.debug(f"Erreur détection boucle: {e}")

        # 🧠 INTELLIGENCE COMPLÈTE : Lire TOUTE la conversation
        conversation = await get_full_conversation(
            self.db, 
            ticket.email_from, 
            self.tenant.id,
            limit=20
        )
        
        # Formater pour l'IA
        conversation_text = format_conversation_for_ai(
            conversation, 
            ticket.customer_name or Client
        )
        
        # Enrichir profil client automatiquement
        if isinstance(ticket.client_profile, dict):
            ticket.client_profile = enrich_profile_from_conversation(
                ticket.client_profile,
                conversation
            )
        
        # Construire le dossier client ENRICHI v6.3
        ticket_data = {
            'email_from': ticket.email_from,
            'sender_name': ticket.sender_name,
            'subject': ticket.subject,
            'body': clean_reply_body(ticket.body) or ticket.body,
            'customer_name': ticket.customer_name,
            'order_details': ticket.order_details,
            'order_number': ticket.order_number,
            'all_orders': getattr(ticket, 'all_orders', None),
            'conversation_history': ticket.conversation_history,
            'client_profile': ticket.client_profile,
            'language': ticket.language,
            'urgency_level': ticket.urgency_level,
            'learned_examples': getattr(ticket, 'learned_examples', ''),
            # v6.3 — Intelligence émotionnelle + instructions
            'emotion': getattr(ticket, 'emotion', None),
            'emotion_trajectory': getattr(ticket, 'emotion_trajectory', None),
            'special_instructions': ticket.client_profile.get('special_instructions', '') if isinstance(ticket.client_profile, dict) else '',
            # v8.1 — Vision complète
            'cc': ticket.cc,
            'attachment_names': ticket.attachment_names,
            # 🧠 CONVERSATION COMPLÈTE (nouveau)
            'full_conversation': conversation_text,
        }

        # Charger les exemples appris (heuristique par mots-clés du message)
        try:
            body_lower = (ticket.body or '').lower()
            subject_lower = (ticket.subject or '').lower()
            guess_cat = None
            if any(w in body_lower or w in subject_lower for w in ['livraison', 'colis', 'suivi', 'tracking', 'recu', 'pas reçu', 'expedi']):
                guess_cat = 'LIVRAISON'
            elif any(w in body_lower or w in subject_lower for w in ['retour', 'echange', 'échanger', 'renvoyer', 'taille']):
                guess_cat = 'RETOUR_ECHANGE'
            elif any(w in body_lower or w in subject_lower for w in ['annuler', 'annulation', 'rembours']):
                guess_cat = 'ANNULATION'
            elif any(w in body_lower or w in subject_lower for w in ['adresse', 'modifier', 'changer l']):
                guess_cat = 'MODIFIER_ADRESSE'
            elif any(w in body_lower or w in subject_lower for w in ['question', 'produit', 'taille', 'guide', 'couleur', 'stock', 'disponible']):
                guess_cat = 'QUESTION_PRODUIT'
            elif any(w in body_lower or w in subject_lower for w in ['sponsor', 'partenaire', 'ambassadeur', 'affiliation', 'collaboration']):
                guess_cat = 'AUTRE'
            if guess_cat:
                examples = await get_feedback_examples(self.db, self.tenant.id, guess_cat, limit=3)
                ticket_data['learned_examples'] = format_examples_for_prompt(examples)
        except (ValueError, TypeError, asyncpg.PostgresError) as e:
            logger.debug(f"Erreur chargement exemples appris: {e}")

        # v10.0 — Charger les erreurs passees pour ce client
        try:
            past_errors = await self.repos.get_recent_errors(self.tenant.id, ticket.email_from, limit=3)
            if past_errors:
                error_lines = []
                for err in past_errors:
                    quality = err.get('response_quality', '')
                    # Extraire les erreurs specifiques du champ quality
                    if 'errors:' in quality:
                        error_detail = quality.split('errors:')[-1].strip()
                        error_lines.append(f"- {error_detail}")
                    elif 'data_error' in quality or 'bad' in quality:
                        error_lines.append(f"- Reponse mal scoree: {quality[:80]}")
                if error_lines:
                    ticket_data['past_errors'] = error_lines
        except (ValueError, TypeError, asyncpg.PostgresError) as e:
            logger.debug(f"Erreur chargement erreurs passées: {e}")

        # v10.0 — Verifier repetition de contenu
        self._check_content_repetition(ticket, ticket_data)

        # Construire le mega-prompt
        prompt = build_unified_prompt(self.tenant, ticket_data)

        # Appeler le cerveau IA
        # v8.0 — Cerveau intelligent avec tools Shopify
        # v9.0 — Try-except global pour ne jamais perdre un email
        try:
            raw_result = await self.ai.unified_process_with_tools(prompt, self.ecommerce)
            # v6.0 — Validate AI response
            result = validate_and_sanitize_response(raw_result, ticket_data)

            # v10.0 — Lie detector: Block AI lies BEFORE sending
            response_text_to_check = result.get('response', '')
            is_clean, violations = detect_lies(response_text_to_check)
            
            if not is_clean:
                logger.error(
                    f"🚨 LIE DETECTED - Réponse bloquée:\n{format_violation_report(violations)}",
                    extra={"action": "lie_detected", "violations": len(violations)}
                )
                # Force escalation with safe fallback response
                result = {
                    "category": result.get('category', 'AUTRE'),
                    "response": f"Bonjour,\n\nVotre demande nécessite une vérification manuelle. Un conseiller va vous répondre personnellement dans les plus brefs délais.\n\nCordialement,\nL'équipe {self.tenant.brand_name}",
                    "action": "send_and_escalate",
                    "confidence": 0.0,
                    "summary": f"IA a tenté de mentir ({len(violations)} violations détectées)"
                }
            metrics.record_ai_call(duration_ms=0, success=True)
        except Exception as e:
            logger.error(f"Cerveau IA erreur critique: {e}",
                         extra={"action": "brain_error", "error": str(e),
                                "email_from": ticket.email_from})
            metrics.record_ai_call(duration_ms=0, success=False)  # v6.0
            # Fallback : escalader plutôt que perdre l email
            result = {
                "category": "AUTRE",
                "response": (
                    f"Bonjour,\n\n"
                    f"Votre demande a bien été reçue et prise en compte. "
                    f"Un conseiller de notre équipe va vous répondre personnellement "
                    f"dans les plus brefs délais.\n\n"
                    f"Cordialement,\n**L équipe {self.tenant.brand_name}**"
                ),
                "action": "send_and_escalate",
                "confidence": 0.0,
                "summary": f"Erreur cerveau IA: {str(e)[:100]}"
            }

        category = result.get('category', 'AUTRE')
        action = result.get('action', 'send')
        response_text = result.get('response', '')
        confidence = result.get('confidence', 0.5)
        summary = result.get('summary', '')

        logger.info(
            f"🧠 CERVEAU | cat={category} | action={action} | conf={confidence:.2f} | {summary[:60]}",
            extra={"action": "brain_result", "category": category, "confidence": confidence}
        )

        # Stocker la catégorie sur le ticket pour post-process
        ticket.category = category
        ticket.brain_confidence = confidence
        ticket.brain_summary = summary

        # Convertir en Response selon l'action
        if action == 'ignore':
            logger.info(f"🚫 IGNORÉ par le cerveau: {summary}",
                        extra={"action": "brain_ignore"})
            return None

        if action == 'escalate_only':
            # Plus de silence — on transforme en send_and_escalate
            # L'IA genere quand meme une reponse pour le client
            logger.info(f"Cerveau voulait escalade seule -> IA repond + notifie",
                        extra={"action": "escalate_to_respond"})
            return Response(
                text=response_text, should_send=True,
                should_escalate=True,
                escalation_reason=summary or f"Cerveau IA: {category} — notification admin",
                category=category, confidence=confidence
            )

        if action == 'send_and_escalate':
            return Response(
                text=response_text, should_send=True,
                should_escalate=True,
                escalation_reason=summary or f"Cerveau IA: {category} — nécessite action humaine",
                category=category, confidence=confidence
            )

        # action == 'send' (défaut)
        return Response(
            text=response_text, should_send=True,
            category=category, confidence=confidence
        )

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 6 : POST-PROCESS (logique métier APRÈS le cerveau)
    # ══════════════════════════════════════════════════════════

    async def _post_process(self, ticket: Ticket, response: Response) -> Response:
        """Enrichit la réponse avec logique métier pure (code, pas IA)."""

        category = response.category or ticket.category

        # ANNULATION + commande trouvée → analyse articles + escalade
        if category == 'ANNULATION' and ticket.order_details:
            items = analyze_order_items(ticket.order_details.get('line_items', []) if isinstance(ticket.order_details, dict) else [], self.tenant)
            total_paid = float(ticket.order_details.get('total_price', 0) if isinstance(ticket.order_details, dict) else 0)
            fulfillment = ticket.order_details.get('fulfillment_status') if isinstance(ticket.order_details, dict) else None

            response.should_escalate = True
            response.escalation_reason = (
                f"Annulation #{ticket.order_number} — "
                f"Total payé: {total_paid:.2f}€ — "
                f"Statut: {'expédiée' if fulfillment == 'fulfilled' else 'non expédiée'}"
            )

            if items:
                # Créer cancellation en DB
                ticket._cancellation_data = {
                    'items': items,
                    'total_paid': total_paid,
                    'fulfillment': fulfillment
                }

                # Notification Telegram détaillée
                items_detail = ", ".join(f"{i['title']}" for i in items[:3])
                response.telegram_message = (
                    f"❌ <b>Annulation #{ticket.order_number}</b>\n"
                    f"Client: {ticket.email_from}\n"
                    f"Articles: {items_detail}\n"
                    f"Total payé: {total_paid:.2f}€ — {'Expédiée' if fulfillment == 'fulfilled' else 'Non expédiée'}"
                )

        # MODIFIER_ADRESSE → toujours escalader
        if category == 'MODIFIER_ADRESSE':
            response.should_escalate = True
            if not response.escalation_reason:
                response.escalation_reason = f"Modification adresse — {ticket.email_from}"

        # RETOUR_ECHANGE + commande trouvée → analyse articles
        if category == 'RETOUR_ECHANGE' and ticket.order_details:
            total_paid = float(ticket.order_details.get('total_price', 0))
            fulfillment = ticket.order_details.get('fulfillment_status')

            response.should_escalate = True
            response.escalation_reason = (
                f"Retour #{ticket.order_number} — "
                f"Total payé: {total_paid:.2f}€ — "
                f"Statut: {'expédiée' if fulfillment == 'fulfilled' else 'non expédiée'}"
            )
            response.telegram_message = (
                f"🔄 <b>Retour #{ticket.order_number}</b>\n"
                f"Client: {ticket.email_from}\n"
                f"Total payé: {total_paid:.2f}€"
            )

        # v6.3 — Escalade automatique si client furieux + confiance IA faible
        emotion = getattr(ticket, 'emotion', None)
        if emotion and emotion.get('is_escalation_risk') and response.confidence < 0.7:
            response.should_escalate = True
            if not response.escalation_reason:
                response.escalation_reason = (
                    f"Client furieux (intensité {emotion.get('emotion_score', 0):.0%}) "
                    f"+ confiance IA faible ({response.confidence:.0%})"
                )
            logger.warning(
                f"⚠️ AUTO-ESCALADE ÉMOTIONNELLE: {ticket.email_from}",
                extra={'action': 'emotion_auto_escalate'}
            )

        return response

    # ══════════════════════════════════════════════════════════
    # ÉTAPE 7 : RESPOND
    # ══════════════════════════════════════════════════════════

    async def _respond(self, ticket: Ticket, response: Response):
        """Envoie la réponse, sauvegarde en DB, notifie si nécessaire."""

        # v9.0 — Validation et correction unifiée (fusion inject + quality)
        if response.should_send and response.text:
            response.text = self._validate_and_fix_response(ticket, response.text)

        # Créer l'entrée DB ou mettre à jour si reprocess
        if not ticket.db_id:
            ticket.db_id = await self.repos.create_email(
                self.tenant.id, ticket.email_hash, ticket.email_from,
                ticket.subject, ticket.body[:200], ticket.language,
                ticket.has_attachments, ticket.attachment_count,
                STEP_ESCALATED if response.should_escalate else 'closed',
                ticket.collected_data, response.category or ticket.category,
                ticket.message_id, ticket.session_id,
                rerouted_from='mailer@shopify.com' if ticket.is_shopify_form else None
            )
        else:
            # Reprocess — mettre à jour le step et la catégorie
            new_step = STEP_ESCALATED if response.should_escalate else 'closed'
            await self.repos.update_email(
                ticket.db_id,
                conversation_step=new_step,
                agent=response.category or ticket.category,
                brain_category=response.category,
                brain_confidence=response.confidence
            )

        # v7.0 — Ouvrir/mettre à jour le ticket
        try:
            if not getattr(ticket, 'resolution', {}).get('is_resolved'):
                await open_ticket(
                    self.db, self.tenant.id, ticket.email_from,
                    ticket.db_id, ticket.subject,
                    response.category or ticket.category
                )
        except (asyncpg.PostgresError, ValueError) as e:
            logger.debug(f"Erreur ticket tracker: {e}")

        # Escalade
        if response.should_escalate:
            existing = await self.repos.find_active_escalation(
                self.tenant.id, ticket.email_from, response.category or ticket.category
            )
            if not existing:
                esc_id = await self.repos.create_escalation(
                    self.tenant.id, ticket.db_id, ticket.email_from,
                    response.category or ticket.category, response.escalation_reason
                )

                # Si ANNULATION → créer entrée cancellation
                if hasattr(ticket, '_cancellation_data') and ticket._cancellation_data:
                    cd = ticket._cancellation_data
                    await self.repos.create_cancellation(
                        self.tenant.id, ticket.email_from, ticket.order_number or '',
                        ticket.db_id, esc_id, cd.get('fulfillment'),
                        cd.get('items'), cd.get('total_paid', 0),
                        0,  # non_refundable — l'humain décidera
                        '1-C-1' if cd.get('fulfillment') == 'fulfilled' else '1-C-2'
                    )

                # Si pas de réponse à envoyer → envoyer email escalade standard
                if not response.should_send or not response.text:
                    esc_html = build_escalation_html(esc_id, self.tenant, ticket.language)
                    await self.channel.send_message(
                        ticket.email_from, f"Re: {ticket.subject}", esc_html, ticket.message_id
                    )
                    await self.repos.mark_sent(ticket.db_id, response.escalation_reason)

                await self.repos.update_email(
                    ticket.db_id, escalade=True, escalade_reason=response.escalation_reason,
                    conversation_step=STEP_ESCALATED
                )

                # v7.0 — Marquer ticket comme escaladé
                try:
                    await escalate_ticket(self.db, self.tenant.id, ticket.email_from)
                except (asyncpg.PostgresError, ValueError) as e:
                    logger.debug(f"Erreur escalade ticket: {e}")

                if self.notifier and not response.telegram_message:
                    await self.notifier(
                        f"🚨 <b>Escalade {response.category}</b>\n"
                        f"De: {ticket.email_from}\nRaison: {response.escalation_reason}\nRéf: #{esc_id}"
                    )
            else:
                await self.repos.update_email(
                    ticket.db_id, escalade=True, escalade_reason=response.escalation_reason,
                    conversation_step=STEP_ESCALATED
                )

        # Envoyer réponse au client
        if response.should_send and response.text:
            if not response.html:
                response.html = build_ai_response_html(response.text, self.tenant, ticket.language)
            # SÉCURITÉ ANTI-DUPLICATE
            subject_to_send = f"Re: {ticket.subject}"
            if subject_to_send.startswith("Re: Re:"):
                logger.warning(f"DUPLICATE BLOQUÉ: Double Re: pour {ticket.email_from}", extra={"action": "duplicate_blocked"})
                sent = False
            else:
                # Vérifier si on a déjà envoyé à ce client récemment
                recent_sent = await self.repos.db.pool.fetchval(
                    "SELECT COUNT(*) FROM emails WHERE email_from =  AND sent_at > NOW() - INTERVAL '1 hour' AND tenant_id = ",
                    ticket.email_from, self.tenant.id
                )
                if recent_sent and recent_sent > 2:
                    logger.warning(f"DUPLICATE BLOQUÉ: {recent_sent} emails déjà envoyés à {ticket.email_from} dans la dernière heure", extra={"action": "rate_limit_blocked"})
                    sent = False
                else:
                    sent = await self.channel.send_message(
                        ticket.email_from, subject_to_send, response.html, ticket.message_id
                    )
            if sent:
                await self.repos.mark_sent(ticket.db_id, response.text)
                await self.repos.update_email(
                    ticket.db_id, agent=response.category, confidence=response.confidence,
                    detection_method=ticket.detection_method,
                    brain_category=response.category,
                    brain_confidence=response.confidence
                )
                logger.info(f"✅ RÉPONSE ENVOYÉE | {response.category} | conf={response.confidence:.2f}",
                            extra={"action": "response_sent", "category": response.category})

                # v7.0 — Marquer le ticket comme répondu
                try:
                    await mark_ticket_responded(
                        self.db, self.tenant.id, ticket.email_from, ticket.db_id
                    )
                except (asyncpg.PostgresError, ValueError) as e:
                    logger.debug(f"Erreur marquage ticket répondu: {e}")

                # v7.1 — Score qualité données (immédiat)
                try:
                    data_check = check_data_accuracy(
                        response.text, ticket.order_details
                    )
                    await score_response(
                        self.db, self.tenant.id, ticket.db_id, data_check
                    )
                    if data_check['errors']:
                        logger.warning(
                            f"Score données: {data_check['data_score']} | "
                            f"erreurs: {data_check['errors']}",
                            extra={'action': 'data_score', 'score': data_check['data_score']}
                        )
                except (ValueError, TypeError, asyncpg.PostgresError) as e:
                    logger.debug(f"Erreur scoring: {e}")

            # Mettre à jour profil client + émotion (v7.2 — enrichi)
            try:
                profile = getattr(ticket, 'client_profile', {})
                await self.repos.upsert_client_profile(
                    self.tenant.id, ticket.email_from,
                    prenom=ticket.customer_name,
                    dernier_ton=getattr(ticket, 'emotion', {}).get('primary_emotion'),
                    derniere_commande=ticket.order_number,
                    tags=profile.get('tags') or None,
                    loyalty_score=profile.get('loyalty_score'),
                    conversation_state=profile.get('conversation_state'),
                    avg_satisfaction=profile.get('avg_satisfaction'),
                )
                # Sauvegarder l'émotion dans processed_emails
                emotion = getattr(ticket, 'emotion', None)
                if emotion and ticket.db_id:
                    await self.repos.update_email(
                        ticket.db_id,
                        emotion_detected=emotion.get('primary_emotion'),
                        emotion_score=emotion.get('emotion_score', 0)
                    )
            except (ValueError, TypeError, asyncpg.PostgresError) as e:
                logger.debug(f"Erreur mise à jour profil client: {e}")

            # Apprentissage — sauvegarder satisfaction + ajuster confiance
            try:
                satisfaction = getattr(ticket, 'satisfaction', None)
                if satisfaction and satisfaction.get('score') is not None:
                    await self.db.execute(
                        """UPDATE processed_emails
                           SET satisfaction_score = $1,
                               satisfaction_source = $2,
                               client_reply_sentiment = $3
                           WHERE id = $4""",
                        satisfaction['score'], satisfaction['source'],
                        satisfaction['sentiment'], ticket.db_id
                    )
                    # v7.2 — Zone neutre : 0.4-0.6 = neutre, on ne touche pas le learning
                    sat_score = satisfaction['score']
                    if sat_score >= 0.6:
                        await update_learning_stats(self.db, self.tenant.id, True)
                    elif sat_score < 0.4:
                        await update_learning_stats(self.db, self.tenant.id, False)
                    # 0.4-0.6 = neutre, pas de mise à jour du learning

                    # Si positif + haute confiance → sauvegarder comme exemple
                    if satisfaction['score'] >= 0.7 and response.confidence and response.confidence >= 0.6:
                        await save_feedback_example(
                            self.db, self.tenant.id,
                            response.category or 'AUTRE',
                            ticket.body[:500], response.text[:1000],
                            source='auto_positive'
                        )
            except (ValueError, TypeError, asyncpg.PostgresError) as e:
                logger.debug(f"Erreur apprentissage: {e}")

        # Notification Telegram custom
        if response.telegram_message and self.notifier:
            await self.notifier(response.telegram_message)

    # ══════════════════════════════════════════════════════════
    # QUALITY CHECK
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_factual_data(text):
        """v10.0 — Extrait les donnees factuelles d'une reponse (tracking, statut, commande)."""
        if not text:
            return {}
        data = {}
        # Tracking numbers
        trackings = re.findall(r'[A-Z]{2,10}\d{8,}[A-Z]{0,4}|\d{12,20}', text)
        data['trackings'] = set(trackings)
        # Order numbers
        orders = re.findall(r'#(\d{4,6})', text)
        data['orders'] = set(orders)
        # Status
        text_lower = text.lower()
        if any(w in text_lower for w in ['expedie', 'en route', 'envoye', 'expédiée', 'expédié', 'envoyé']):
            data['status'] = 'shipped'
        elif any(w in text_lower for w in ['preparation', 'en cours', 'traitement', 'préparation']):
            data['status'] = 'preparing'
        return data

    def _check_content_repetition(self, ticket, ticket_data):
        """v10.0 — Verifie si la reponse precedente contenait les memes infos factuelles."""
        try:
            last_resp = ticket.conversation_history or ''
            # Extraire la derniere reponse SAV de l'historique
            if '[SAV]' in last_resp:
                parts = last_resp.split('[SAV]')
                last_sav = parts[-1].split('[Client]')[0] if len(parts) > 1 else ''
            else:
                last_sav = ''
            if not last_sav or len(last_sav) < 20:
                return
            last_data = self._extract_factual_data(last_sav)
            # Comparer avec les donnees du ticket actuel
            current_trackings = set()
            current_orders = set()
            if ticket.order_details:
                current_trackings = set(ticket.order_details.get('tracking_numbers', []))
                on = str(ticket.order_details.get('order_number', ''))
                if on:
                    current_orders = {on}
            # Si le client revient et les donnees sont identiques
            if (last_data.get('trackings') and current_trackings
                    and last_data['trackings'] == current_trackings):
                ticket_data['content_repetition_warning'] = (
                    "Tu as DEJA donne ces informations de tracking dans ta reponse "
                    "precedente. Le client revient car elles ne suffisent pas. "
                    "Propose une ACTION NOUVELLE : verification aupres du transporteur, "
                    "escalade interne, ou explication du statut actuel du colis."
                )
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"Erreur vérification répétition contenu: {e}")

    def _validate_and_fix_response(self, ticket: Ticket, text: str) -> str:
        """v9.0 — Validation unifiée : injection données réelles + contrôle qualité.
        Fusionne _inject_real_data() et _quality_check() pour éviter les doublons."""

        # 1. Vérifier cohérence numéro de commande
        if ticket.order_number:
            numbers_in_response = re.findall(r'#(\d{4,6})', text)
            for num in numbers_in_response:
                if num != ticket.order_number and not (2020 <= int(num) <= 2030):
                    logger.warning(f"⚠️ QUALITÉ: mauvais numéro dans réponse ({num} vs {ticket.order_number})",
                                   extra={"action": "quality_wrong_number"})
                    text = text.replace(f"#{num}", f"#{ticket.order_number}")

        # 2. Vérifier les numéros de tracking (v7.1 — protection anti-corruption)
        if ticket.order_details:
            real_trackings = ticket.order_details.get('tracking_numbers', [])
            real_urls = ticket.order_details.get('tracking_urls', [])

            # 2a. Remplacer toute variante corrompue d'un vrai tracking
            # Ex: WNBWNBWNBAA0434699685YQ contient le vrai WNBAA0434699685YQ
            for real_t in real_trackings:
                # Chercher des versions allongées/corrompues du vrai tracking
                corrupted = re.findall(r'[A-Z0-9]*' + re.escape(real_t), text)
                for c in corrupted:
                    if c != real_t:
                        logger.warning(f"⚠️ TRACKING CORROMPU: {c} → {real_t}",
                                       extra={"action": "quality_corrupted_tracking"})
                        text = text.replace(c, real_t)

            # 2b. Chercher des trackings totalement inventés (pas dans les vrais)
            tracking_patterns = re.findall(r'[A-Z]{2,10}\d{8,}[A-Z]{0,4}|\d{12,20}', text)
            for t in tracking_patterns:
                if t not in real_trackings:
                    logger.warning(f"⚠️ HALLUCINATION: tracking inventé: {t}",
                                   extra={"action": "quality_fake_tracking"})
                    if real_trackings:
                        text = text.replace(t, real_trackings[0])
                    else:
                        text = text.replace(t, "[numéro de suivi en cours d'attribution]")

        # 3. Vérifier les URLs de tracking inventées
        url_patterns = re.findall(r'https?://[^\s)>]+track[^\s)>]*', text, re.IGNORECASE)
        if url_patterns and ticket.order_details:
            real_urls = ticket.order_details.get('tracking_urls', [])
            for url in url_patterns:
                if url not in real_urls and not any(url in ru for ru in real_urls):
                    logger.warning(f"⚠️ HALLUCINATION: URL tracking inventée: {url}",
                                   extra={"action": "quality_fake_url"})
                    if real_urls:
                        text = text.replace(url, real_urls[0])

        # 4. Vérifier les prix inventés (sans écraser les prix d'articles)
        if ticket.order_details:
            real_price = ticket.order_details.get('total_price', '')
            if real_price:
                # Collecter tous les prix valides
                valid_prices = {str(real_price).replace(',', '.')}
                for item in ticket.order_details.get('line_items', []):
                    ip = str(item.get('price', '')).replace(',', '.')
                    if ip:
                        valid_prices.add(ip)
                    try:
                        qty = int(item.get('quantity', 1))
                        unit = float(item.get('price', 0))
                        if qty > 1:
                            valid_prices.add(f"{unit * qty:.2f}")
                    except (ValueError, TypeError):
                        pass
                prices_in_response = re.findall(r'(\d+[.,]\d{2})\s*[€EUR]', text)
                for price in prices_in_response:
                    price_normalized = price.replace(',', '.')
                    if price_normalized not in valid_prices:
                        logger.warning(f"⚠️ HALLUCINATION: prix inventé ({price} — valides: {valid_prices})",
                                       extra={"action": "quality_fake_price"})
                        text = text.replace(price, str(real_price).replace('.', ','))

        # 5. Vérifier les dates de livraison inventées
        # L'IA ne doit JAMAIS donner une date précise de livraison
        date_promises = re.findall(
            r"(?:livr[eé]|re[cç]u|arriv)\w*\s+(?:le|avant le|d.ici)\s+\d{1,2}[/\s]\w+",
            text, re.IGNORECASE
        )
        if date_promises:
            for dp in date_promises:
                logger.warning(f"⚠️ HALLUCINATION: date de livraison promise: {dp}",
                               extra={"action": "quality_date_promise"})

        # 6. Vérifier et SUPPRIMER promesses interdites
        forbidden = [
            'remboursement confirmé', 'remboursement validé',
            'vous serez remboursé', 'le remboursement a été effectué',
            'nous avons procédé au remboursement',
            'votre remboursement est en cours',
            'nous vous remboursons', 'remboursement effectué',
        ]
        text_lower = text.lower()
        for phrase in forbidden:
            if phrase in text_lower:
                logger.warning(f"⚠️ QUALITÉ: promesse interdite SUPPRIMÉE: {phrase}",
                               extra={"action": "quality_forbidden_removed"})
                # Supprimer la ligne entière contenant la promesse
                lines = text.split('\n')
                text = '\n'.join(l for l in lines if phrase not in l.lower())

        # 7. Vérifier que l'IA ne mentionne pas des articles qui n'existent pas
        if ticket.order_details:
            real_items = [item.get('title', '').lower() for item in ticket.order_details.get('line_items', [])]
            # Chercher des mentions de produits entre ** ** (markdown bold)
            mentioned_items = re.findall(r'\*\*([^*]+)\*\*', text)
            for item in mentioned_items:
                item_lower = item.lower()
                # Ignorer les mentions standard (l'équipe OKTAGON, etc.)
                if any(skip in item_lower for skip in ["équipe", "oktagon", "important", "attention"]) or re.match(r"[A-Z0-9]{10,}", item):
                    continue
                # Si c'est un nom de produit mais pas dans la commande
                if real_items and len(item) > 5 and not any(ri in item_lower or item_lower in ri for ri in real_items):
                    logger.info(f"\u2139\ufe0f QUALITÉ: produit mentionné non vérifié: {item}",
                                extra={"action": "quality_unverified_item"})

        # 8. v7.1 — Vérifier cohérence statut commande
        if ticket.order_details:
            real_status = ticket.order_details.get('fulfillment_status', '')
            status_map = {
                'fulfilled': ['expédié', 'envoyé', 'en route', 'expediee', 'expédiée'],
                'unfulfilled': ['en cours', 'préparation', 'preparation', 'traitement'],
                'partial': ['partiellement'],
            }
            # Si la commande est expédiée mais Claude dit "en préparation"
            if real_status == 'fulfilled':
                wrong_phrases = ['en cours de préparation', 'en cours de fabrication',
                                 'en cours de personnalisation', 'pas encore expédié',
                                 'pas encore été expédié', 'n\'a pas encore été envoyé']
                for wp in wrong_phrases:
                    if wp in text.lower():
                        logger.warning(f"\u26a0\ufe0f QUALITÉ: statut faux — commande expédiée mais dit '{wp}'",
                                       extra={"action": "quality_wrong_status"})
                        text = text.replace(wp, 'a bien été expédiée')
                        text = text.replace(wp.capitalize(), 'A bien été expédiée')

            # Si la commande N'est PAS expédiée mais Claude dit "expédiée"
            if real_status in ('unfulfilled', None, ''):
                if any(w in text.lower() for w in ['a été expédiée', 'a été envoyé', 'est en route']):
                    if 'sera expédié' not in text.lower():
                        logger.warning(f"\u26a0\ufe0f QUALITÉ: dit expédié mais commande pas expédiée ({real_status})",
                                       extra={"action": "quality_false_shipped"})
                        for wrong in ['a été expédiée', 'a été envoyée', 'a été expédié', 'a été envoyé']:
                            text = text.replace(wrong, 'est en cours de préparation')
                        text = text.replace('est en route', 'est en cours de traitement')

        # 9. v7.1 — Supprimer nom de transporteur
        transporteurs = ['colissimo', 'chronopost', 'dpd', 'ups', 'fedex', 'dhl',
                         'mondial relay', 'la poste', 'gls', 'tnt', 'hermes',
                         'royal mail', 'usps', 'postnl', 'bpost', 'swiss post']
        text_lower = text.lower()
        for tr in transporteurs:
            if tr in text_lower:
                logger.warning(f"\u26a0\ufe0f QUALITÉ: transporteur mentionné: {tr}",
                               extra={"action": "quality_carrier_mentioned"})
                # Supprimer la mention du transporteur
                text = re.sub(re.escape(tr), 'notre partenaire logistique', text, flags=re.IGNORECASE)

        # 10. v7.1 — Supprimer promesses d'actions non autorisées
        forbidden_actions = [
            'nous avons renvoyé', 'nous vous renvoyons', 'un remplacement a été envoyé',
            'nous avons contacté le transporteur', 'nous allons vous envoyer un nouveau',
            'votre commande a été annulée', 'nous avons annulé',
            'un avoir a été créé', 'nous avons créé un avoir',
            'nous avons modifié votre adresse', 'l\'adresse a été changée',
            'nous avons appliqué un code promo', 'un geste commercial',
        ]
        for fa in forbidden_actions:
            if fa in text.lower():
                logger.warning(f"\u26a0\ufe0f QUALITÉ: action non autorisée: {fa}",
                               extra={"action": "quality_unauthorized_action"})
                lines = text.split('\n')
                text = '\n'.join(l for l in lines if fa not in l.lower())

        # 11. v7.1 — Vérifier cohérence prénom client
        if ticket.customer_name and ticket.order_details:
            real_name = ticket.order_details.get('customer_name', '')
            if real_name:
                real_first = real_name.split()[0]
                # Chercher "Bonjour [Prénom]" dans la réponse
                greet_match = re.search(r'(?:Bonjour|Salut|Cher)\s+([A-ZÀ-Ü][a-zà-ü]+)', text)
                if greet_match:
                    used_name = greet_match.group(1)
                    if used_name.lower() != real_first.lower() and used_name.lower() != ticket.customer_name.lower():
                        logger.warning(f"\u26a0\ufe0f QUALITÉ: mauvais prénom ({used_name} vs {real_first})",
                                       extra={"action": "quality_wrong_name"})
                        text = text.replace(used_name, real_first)

        return text
