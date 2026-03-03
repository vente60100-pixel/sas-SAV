"""
OKTAGON SAV v11.0 — Mémoire résumée intelligente.

Au lieu de garder 8 messages bruts :
- Résumé IA des anciens échanges (> 5)
- 5 derniers messages complets (client + SAV)

Le cerveau a TOUT le contexte sans exploser le prompt.
"""
import logging
import json
import anthropic

logger = logging.getLogger('oktagon')


async def build_smart_history(db, ai_connector, tenant_id: str, email_from: str) -> str:
    """
    Construit l'historique intelligent :
    - Si <= 5 échanges : tout en brut (comme avant)
    - Si > 5 échanges : résumé des anciens + 5 derniers complets
    """
    # Récupérer TOUS les échanges
    rows = await db.fetch_all(
        """SELECT email_subject, email_body_preview, response_text,
                  brain_category, created_at
           FROM processed_emails
           WHERE tenant_id = $1 AND email_from = $2
           AND (response_text IS NOT NULL OR email_body_preview IS NOT NULL)
           ORDER BY created_at ASC""",
        tenant_id, email_from
    )

    if not rows:
        return ""

    total = len(rows)

    if total <= 5:
        # Peu d'échanges → tout en brut
        return _format_raw_history(rows)

    # Plus de 5 échanges → résumer les anciens + garder les 5 derniers
    old_rows = rows[:-5]
    recent_rows = rows[-5:]

    # Construire le résumé des anciens échanges
    summary = await _summarize_old_exchanges(ai_connector, old_rows, email_from)

    # Formater les 5 derniers en brut
    recent_text = _format_raw_history(recent_rows)

    history = f"""
RÉSUMÉ DES ÉCHANGES PRÉCÉDENTS ({len(old_rows)} messages) :
{summary}

DERNIERS ÉCHANGES (5 plus récents) :
{recent_text}"""

    return history


def _format_raw_history(rows) -> str:
    """Formate des échanges en texte brut lisible."""
    text = ""
    for r in rows:
        date = r['created_at'].strftime('%d/%m %H:%M')
        client_msg = (r.get('email_body_preview') or '').strip()
        if client_msg:
            # Nettoyer les citations
            clean = '\n'.join(
                l for l in client_msg.split('\n')
                if not l.strip().startswith('>')
            ).strip()[:400]
            if clean:
                text += f"[{date}] CLIENT: {clean}\n"
        resp = (r.get('response_text') or '').strip()
        if resp:
            text += f"[{date}] SAV: {resp[:400]}\n"
        text += "---\n"
    return text


async def _summarize_old_exchanges(ai_connector, rows, email_from: str) -> str:
    """Utilise l'IA pour résumer les anciens échanges en 3-5 lignes."""
    # Construire un texte condensé des vieux échanges
    exchanges_text = ""
    for r in rows:
        date = r['created_at'].strftime('%d/%m')
        cat = r.get('brain_category') or '?'
        client = (r.get('email_body_preview') or '')[:150].strip()
        sav = (r.get('response_text') or '')[:150].strip()
        if client or sav:
            exchanges_text += f"[{date}] {cat} | Client: {client} | SAV: {sav}\n"

    # Si le texte est court, pas besoin de résumer
    if len(exchanges_text) < 500:
        return exchanges_text

    try:
        client = anthropic.AsyncAnthropic(api_key=ai_connector.api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku pour le résumé (rapide + pas cher)
            max_tokens=300,
            temperature=0,
            messages=[{
                "role": "user",
                "content": f"""Résume en 3-5 lignes l'historique de ce client SAV ({email_from}).

RÈGLES ABSOLUES :
- Sois 100%% FACTUEL — ne mentionne QUE ce qui est écrit dans les échanges
- N'INVENTE aucune information (pas de dates, pas de montants, pas de détails absents)
- Si tu n'es pas sûr d'une info, ne la mentionne pas
- Mentionne : ses problèmes, les réponses données, son ton (calme/énervé)
- N'inclus PAS de numéros de tracking, de prix, ou de détails techniques — juste le CONTEXTE

ÉCHANGES :
{exchanges_text}

RÉSUMÉ FACTUEL (3-5 lignes, en français, UNIQUEMENT les faits visibles ci-dessus) :"""
            }]
        )
        summary = response.content[0].text.strip()
        logger.info(f"Résumé historique généré ({len(rows)} échanges → {len(summary)} chars)",
                    extra={'action': 'history_summarized'})
        return summary
    except (anthropic.APIError, anthropic.APITimeoutError) as e:
        logger.warning(f"Erreur résumé historique: {e}", extra={'action': 'summary_error'})
        # Fallback : juste les catégories et dates
        fallback = ""
        for r in rows:
            date = r['created_at'].strftime('%d/%m')
            cat = r.get('brain_category') or '?'
            fallback += f"[{date}] {cat} — "
        return fallback.rstrip(' — ')
