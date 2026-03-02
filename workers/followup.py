"""
OKTAGON SAV v7.1 — Worker de suivi automatique
Scan toutes les 10 secondes :

1. Mails sans réponse (y compris escaladés non traités)
2. Vérification résolution des échanges
3. Tickets ouverts trop longtemps
4. Auto-fermeture tickets silencieux
5. Rapport quotidien enrichi
"""
import asyncio
import os
import logging
from datetime import datetime, timedelta

from workers.ticket_tracker import (
    auto_close_stale_tickets, get_unanswered_tickets,
    get_ticket_stats, get_open_tickets
)

logger = logging.getLogger('oktagon')

FOLLOWUP_INTERVAL_SECONDS = 10  # 10 secondes
DAILY_REPORT_HOUR = 20  # 20h UTC = 21h FR
ALERT_COOLDOWN_SECONDS = 3600  # 1h entre chaque alerte



# v9.0 — Persister la date du dernier rapport (survit aux restarts)
_REPORT_STATE_FILE = '/tmp/oktagon_last_daily_report.txt'

def _load_last_report_date():
    try:
        if os.path.exists(_REPORT_STATE_FILE):
            with open(_REPORT_STATE_FILE) as f:
                from datetime import datetime
                return datetime.fromisoformat(f.read().strip())
    except Exception:
        pass
    return None

def _save_last_report_date(dt):
    try:
        with open(_REPORT_STATE_FILE, 'w') as f:
            f.write(dt.isoformat())
    except Exception:
        pass


async def followup_loop(db, tenant_id: str, notifier=None,
                         shutdown_event=None):
    """Boucle de suivi. Scan toutes les 10 secondes."""
    # v9.0 — print supprimé (doublon avec logger)
    logger.info(
        f"Worker suivi ACTIF — scan toutes les {FOLLOWUP_INTERVAL_SECONDS}s",
        extra={'action': 'followup_start'}
    )

    last_daily_report = _load_last_report_date()
    last_alert_time = None
    scan_count = 0

    while True:
        if shutdown_event and shutdown_event.is_set():
            break

        scan_count += 1

        try:
            now = datetime.utcnow()

            # ═══ 1. TOUS LES MAILS SANS RÉPONSE (derniers 7 jours) ═══
            all_unanswered = await db.fetch_all(
                """SELECT email_from, email_subject, email_body_preview,
                          conversation_step, created_at
                   FROM processed_emails
                   WHERE tenant_id = $1
                   AND response_sent = false
                   AND created_at > NOW() - INTERVAL '7 days'
                   ORDER BY created_at ASC""",
                tenant_id
            )

            # Séparer : escaladés vs vraiment sans réponse
            escalated_waiting = [m for m in all_unanswered
                                  if m.get('conversation_step') == 'escalated_to_human']
            no_response = [m for m in all_unanswered
                           if m.get('conversation_step') != 'escalated_to_human']

            # ═══ 2. ÉCHANGES NON RÉSOLUS ═══
            # Clients qui ont écrit mais dont le dernier message n'est PAS d'OKTAGON
            unresolved = await db.fetch_all(
                """WITH last_messages AS (
                    SELECT email_from,
                           MAX(created_at) as last_client_msg,
                           MAX(CASE WHEN response_sent = true THEN created_at END) as last_response
                    FROM processed_emails
                    WHERE tenant_id = $1
                    AND created_at > NOW() - INTERVAL '7 days'
                    GROUP BY email_from
                )
                SELECT email_from, last_client_msg, last_response
                FROM last_messages
                WHERE last_client_msg > COALESCE(last_response, '1970-01-01')
                AND last_client_msg < NOW() - INTERVAL '2 hours'
                ORDER BY last_client_msg ASC""",
                tenant_id
            )

            # ═══ 3. TICKETS OUVERTS +24H ═══
            try:
                stale_tickets = await get_unanswered_tickets(db, tenant_id, hours=24)
            except Exception:
                stale_tickets = []

            # ═══ 4. AUTO-FERMETURE TICKETS PÉRIMÉS ═══
            try:
                closed = await auto_close_stale_tickets(db, tenant_id)
                if closed > 0:
                    logger.info(
                        f"{closed} ticket(s) auto-ferme(s) (silence 5j)",
                        extra={'action': 'auto_close_tickets', 'count': closed}
                    )
            except Exception:
                closed = 0

            # ═══ 4b. AUTO-SATISFACTION SILENCE 48H (toutes les 30 min) ═══
            if scan_count % 180 == 0:
                try:
                    from core.learning import check_no_reply_satisfaction
                    sat_count = await check_no_reply_satisfaction(db, tenant_id)
                    if sat_count > 0:
                        logger.info(
                            f"Auto-satisfaction: {sat_count} emails silence 48h -> presumes satisfaits",
                            extra={'action': 'auto_satisfaction_48h', 'count': sat_count}
                        )
                except Exception as e:
                    logger.debug(f"Erreur auto-satisfaction: {e}")

            # ═══ 5. LOG PÉRIODIQUE (toutes les 5 min = 30 scans) ═══
            if scan_count % 30 == 0:
                # v9.0 — print supprimé (doublon avec logger)
                logger.info(
                    f"Scan #{scan_count} | "
                    f"sans_reponse={len(no_response)} | "
                    f"escalades={len(escalated_waiting)} | "
                    f"non_resolus={len(unresolved)} | "
                    f"tickets_stale={len(stale_tickets or [])}",
                    extra={'action': 'followup_scan'}
                )

            # ═══ 6. ALERTES TELEGRAM ═══
            if notifier:
                should_alert = (
                    last_alert_time is None or
                    (now - last_alert_time).total_seconds() > ALERT_COOLDOWN_SECONDS
                )

                total_waiting = len(no_response) + len(unresolved)

                if should_alert and total_waiting > 0:
                    msg = f"<b>SUIVI SAV — {total_waiting} client(s) en attente</b>\n\n"

                    if no_response:
                        msg += f"<b>Sans reponse ({len(no_response)}) :</b>\n"
                        for m in no_response[:3]:
                            email = m['email_from'][:25]
                            subj = (m.get('email_subject') or '')[:35]
                            hours = (now - m['created_at'].replace(tzinfo=None)).total_seconds() / 3600
                            msg += f"  {email}\n  {subj} ({hours:.0f}h)\n"

                    if unresolved:
                        msg += f"\n<b>Non resolus ({len(unresolved)}) :</b>\n"
                        for u in unresolved[:3]:
                            email = u['email_from'][:25]
                            hours = (now - u['last_client_msg'].replace(tzinfo=None)).total_seconds() / 3600
                            msg += f"  {email} ({hours:.0f}h)\n"

                    if escalated_waiting:
                        msg += f"\n<b>Escalades en attente : {len(escalated_waiting)}</b>\n"

                    await notifier(msg)
                    last_alert_time = now

            # ═══ 7. RAPPORT QUOTIDIEN ═══
            if (now.hour == DAILY_REPORT_HOUR and
                    (last_daily_report is None or last_daily_report.date() != now.date())):
                await _send_daily_report(db, tenant_id, notifier, escalated_waiting)
                last_daily_report = now
                _save_last_report_date(now)

        except Exception as e:
            logger.error(
                f"Erreur worker suivi: {e}",
                extra={'action': 'followup_error', 'error': str(e)}
            )

        # Attendre
        try:
            if shutdown_event:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=FOLLOWUP_INTERVAL_SECONDS
                )
                break
            else:
                await asyncio.sleep(FOLLOWUP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def _send_daily_report(db, tenant_id: str, notifier,
                              pending_escalations=None):
    """Rapport quotidien enrichi."""
    if not notifier:
        return

    stats = await get_ticket_stats(db, tenant_id)

    # Stats du jour
    mail_stats = await db.fetch_one(
        """SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN response_sent = true THEN 1 END) as answered,
            COUNT(CASE WHEN response_sent = false THEN 1 END) as unanswered,
            COUNT(CASE WHEN conversation_step = 'escalated_to_human' THEN 1 END) as escalated
           FROM processed_emails
           WHERE tenant_id = $1
           AND created_at > NOW() - INTERVAL '24 hours'""",
        tenant_id
    )

    # Stats scoring
    scoring = await db.fetch_one(
        """SELECT
            COUNT(CASE WHEN response_quality LIKE 'excellent%' THEN 1 END) as excellent,
            COUNT(CASE WHEN response_quality LIKE 'good%' THEN 1 END) as good,
            COUNT(CASE WHEN response_quality LIKE 'bad%' THEN 1 END) as bad,
            COUNT(CASE WHEN response_quality IS NOT NULL THEN 1 END) as scored
           FROM processed_emails
           WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
        tenant_id
    )

    # Exemples appris
    examples = await db.fetch_one(
        """SELECT COUNT(*) as c FROM feedback_examples
           WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
        tenant_id
    )

    total = mail_stats['total'] if mail_stats else 0
    answered = mail_stats['answered'] if mail_stats else 0
    unanswered = mail_stats['unanswered'] if mail_stats else 0
    escalated = mail_stats['escalated'] if mail_stats else 0

    msg = (
        f"<b>RAPPORT QUOTIDIEN SAV</b>\n"
        f"{'=' * 20}\n\n"
        f"Mails recus: <b>{total}</b>\n"
        f"Repondus: <b>{answered}</b>\n"
        f"Sans reponse: <b>{unanswered}</b>\n"
        f"Escalades: <b>{escalated}</b>\n"
    )

    if scoring and scoring['scored'] > 0:
        msg += (
            f"\n<b>Qualite reponses :</b>\n"
            f"Excellentes: {scoring['excellent']}\n"
            f"Bonnes: {scoring['good']}\n"
            f"Mauvaises: {scoring['bad']}\n"
        )

    if stats:
        msg += (
            f"\n<b>Tickets :</b>\n"
            f"Ouverts: {stats.get('open_count', 0)}\n"
            f"En attente: {stats.get('waiting_count', 0)}\n"
            f"Resolus: {stats.get('resolved_count', 0)}\n"
        )

    if examples and examples['c'] > 0:
        msg += f"\nExemples auto-appris: <b>{examples['c']}</b>\n"

    if pending_escalations:
        msg += f"\n<b>{len(pending_escalations)} escalade(s) en attente</b>\n"

    # v8.0 — Stats détaillées boucles et mismatch
    try:
        loop_stats = await db.fetch_one(
            """SELECT
                COUNT(CASE WHEN brain_category = 'BOUCLE' THEN 1 END) as boucles,
                COUNT(CASE WHEN brain_category = 'MISMATCH' THEN 1 END) as mismatch,
                COUNT(CASE WHEN detection_method = 'shopify_name' THEN 1 END) as found_by_name,
                COUNT(CASE WHEN detection_method = 'shopify_confirmation' THEN 1 END) as found_by_confirmation
               FROM processed_emails
               WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '24 hours'""",
            tenant_id
        )
        if loop_stats:
            boucles = loop_stats.get('boucles', 0) or 0
            mismatch = loop_stats.get('mismatch', 0) or 0
            by_name = loop_stats.get('found_by_name', 0) or 0
            by_conf = loop_stats.get('found_by_confirmation', 0) or 0
            if boucles or mismatch or by_name or by_conf:
                msg += f"\n<b>Intelligence v8.0 :</b>\n"
                if boucles:
                    msg += f"Boucles detectees: {boucles}\n"
                if mismatch:
                    msg += f"Mismatch: {mismatch}\n"
                if by_name:
                    msg += f"Trouves par nom: {by_name}\n"
                if by_conf:
                    msg += f"Trouves par confirmation: {by_conf}\n"
    except Exception:
        pass

    # v8.0 — Escalades en attente depuis > 48h
    try:
        old_esc = await db.fetch_one(
            """SELECT COUNT(*) as c FROM escalations
               WHERE tenant_id = $1 AND resolved = false
               AND created_at < NOW() - INTERVAL '48 hours'""",
            tenant_id
        )
        if old_esc and old_esc['c'] > 0:
            msg += f"\n<b>ATTENTION: {old_esc['c']} escalade(s) en attente depuis +48h</b>\n"
    except Exception:
        pass

    await notifier(msg)
    logger.info("Rapport quotidien envoye", extra={'action': 'daily_report_sent'})
