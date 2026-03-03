"""
OKTAGON SAV v11.0 — Auto-scoring des réponses
Évalue automatiquement la qualité de chaque réponse envoyée :
1. Vérification données (tracking, commande, prix vs Shopify)
2. Réaction client (satisfait, mécontent, silence)
3. Score combiné → alimente feedback_examples

Se branche dans le pipeline :
- data_check : immédiatement après envoi
- client_check : quand le client répond
"""
import re
import logging
from datetime import datetime
import asyncpg

logger = logging.getLogger('oktagon')


# ══════════════════════════════════════════════════════════
# 1. VÉRIFICATION DONNÉES (immédiate, après envoi)
# ══════════════════════════════════════════════════════════

def check_data_accuracy(response_text: str, order_details: dict) -> dict:
    """
    Vérifie que les données dans la réponse correspondent à Shopify.
    Retourne un score et le détail des vérifications.
    """
    if not order_details or not response_text:
        return {'data_score': 'neutral', 'checks': [], 'errors': []}

    checks = []
    errors = []

    # 1. Numéro de commande
    order_num = str(order_details.get('order_number', '')).replace('#', '')
    if order_num:
        mentioned_nums = re.findall(r'#(\d{4,6})', response_text)
        if mentioned_nums:
            if all(n == order_num for n in mentioned_nums):
                checks.append('order_number_ok')
            else:
                errors.append(f'wrong_order_number:{mentioned_nums}')
        # Pas de numéro mentionné = pas d'erreur (peut-être pas pertinent)

    # 2. Tracking
    real_trackings = order_details.get('tracking_numbers', [])
    if real_trackings:
        # Chercher des trackings dans la réponse
        found_trackings = re.findall(r'[A-Z]{2,10}\d{8,}[A-Z]{0,4}|\d{12,20}', response_text)
        if found_trackings:
            for ft in found_trackings:
                if ft in real_trackings:
                    checks.append('tracking_ok')
                else:
                    errors.append(f'wrong_tracking:{ft}')

    # 3. Prix
    real_price = str(order_details.get('total_price', ''))
    if real_price:
        prices = re.findall(r'(\d+[.,]\d{2})\s*[\u20acEUR]', response_text)
        for p in prices:
            p_norm = p.replace(',', '.')
            if p_norm == real_price:
                checks.append('price_ok')
            else:
                errors.append(f'wrong_price:{p}')

    # 4. Statut commande
    real_status = order_details.get('fulfillment_status', '')
    if real_status == 'fulfilled':
        if any(w in response_text.lower() for w in ['en cours de préparation', 'pas encore expédié']):
            errors.append('wrong_status:says_preparing_but_shipped')
        elif any(w in response_text.lower() for w in ['expédié', 'en route', 'envoyé']):
            checks.append('status_ok')
    elif real_status in ('unfulfilled', None, ''):
        if any(w in response_text.lower() for w in ['a été expédié', 'est en route']):
            errors.append('wrong_status:says_shipped_but_not')
        elif any(w in response_text.lower() for w in ['en cours', 'préparation', 'traitement']):
            checks.append('status_ok')

    # 5. Transporteur mentionné (interdit)
    transporteurs = ['colissimo', 'chronopost', 'dpd', 'ups', 'fedex', 'dhl',
                     'mondial relay', 'la poste', 'gls', 'tnt']
    for tr in transporteurs:
        if tr in response_text.lower():
            errors.append(f'carrier_mentioned:{tr}')

    # 6. Promesses interdites
    forbidden = ['remboursement confirmé', 'remboursement validé',
                 'vous serez remboursé', 'nous avons procédé au remboursement',
                 'nous avons renvoyé', 'un remplacement a été envoyé']
    for f in forbidden:
        if f in response_text.lower():
            errors.append(f'forbidden_promise:{f[:30]}')

    # Score
    if errors:
        data_score = 'bad'
    elif checks:
        data_score = 'good'
    else:
        data_score = 'neutral'

    return {
        'data_score': data_score,
        'checks': checks,
        'errors': errors,
        'checks_count': len(checks),
        'errors_count': len(errors),
    }


# ══════════════════════════════════════════════════════════
# 2. RÉACTION CLIENT (quand le client répond)
# ══════════════════════════════════════════════════════════

def check_client_reaction(new_message: str, subject: str = '') -> dict:
    """
    Analyse la réaction du client à notre réponse.
    Appelé quand un client envoie un NOUVEAU message après notre réponse.
    """
    text = (new_message + ' ' + subject).lower()

    # Satisfait
    satisfied_patterns = [
        r'merci\b', r'parfait', r'super\b', r'genial', r'g[eé]nial',
        r'c.?est bon', r'bien re[cç]u', r'j.?ai re[cç]u',
        r'top\b', r'nickel', r'impeccable', r'excellent',
        r'bonne journ[eé]e', r'bonne soir[eé]e',
        r'au revoir', r'plus besoin', r'c.?est r[eé]gl[eé]',
        r'probl[eè]me r[eé]solu', r'tout est ok',
    ]
    satisfied_count = sum(1 for p in satisfied_patterns if re.search(p, text))

    # Mécontent / répète sa question
    unhappy_patterns = [
        r'toujours pas', r'encore rien', r'pas re[cç]u',
        r'[cç]a fait \d+ jours', r'quand est.ce', r'combien de temps',
        r'inadmissible', r'scandaleux', r'honteux', r'arnaque',
        r'je veux [eê]tre rembours', r'remboursez', r'porter plainte',
        r'paypal\s+litige', r'signaler', r'avocat',
        r'je vous ai d[eé]j[aà]', r'je r[eé]p[eè]te',
        r'vous ne r[eé]pondez pas', r'aucune r[eé]ponse',
        r'm[eé]content', r'furieux', r'en col[eè]re',
        r'votre r[eé]ponse ne', r'[cç]a ne r[eé]pond pas',
    ]
    unhappy_count = sum(1 for p in unhappy_patterns if re.search(p, text))

    # Nouvelle question (ni satisfait ni mécontent, juste une suite)
    new_question_patterns = [
        r'autre question', r'aussi\b.*\?', r'par ailleurs',
        r'et pour', r'concernant', r'j.?aurais voulu',
    ]
    new_question = any(re.search(p, text) for p in new_question_patterns)

    # Déterminer la réaction
    if satisfied_count >= 2 and unhappy_count == 0:
        reaction = 'very_satisfied'
    elif satisfied_count >= 1 and unhappy_count == 0:
        reaction = 'satisfied'
    elif unhappy_count >= 2:
        reaction = 'very_unhappy'
    elif unhappy_count >= 1:
        reaction = 'unhappy'
    elif new_question:
        reaction = 'new_question'
    else:
        reaction = 'neutral'

    return {
        'reaction': reaction,
        'satisfied_score': satisfied_count,
        'unhappy_score': unhappy_count,
        'is_positive': reaction in ('satisfied', 'very_satisfied'),
        'is_negative': reaction in ('unhappy', 'very_unhappy'),
    }


# ══════════════════════════════════════════════════════════
# 3. SCORING COMBINÉ + APPRENTISSAGE
# ══════════════════════════════════════════════════════════

async def score_response(db, tenant_id: str, email_id: int,
                          data_check: dict, client_reaction: dict = None) -> str:
    """
    Score combiné d'une réponse. Met à jour response_quality en DB.
    Alimente feedback_examples si la réponse est bonne.
    """
    data_score = data_check.get('data_score', 'neutral')

    # Si pas encore de réaction client → score basé uniquement sur les données
    if client_reaction is None:
        if data_score == 'bad':
            quality = 'data_error'
        elif data_score == 'good':
            quality = 'data_ok'
        else:
            quality = 'pending'

        await _update_quality(db, email_id, quality, data_check)
        return quality

    # Réaction client disponible → scoring complet
    reaction = client_reaction.get('reaction', 'neutral')

    if data_score == 'bad':
        # Données fausses = toujours mauvais, peu importe le client
        quality = 'bad'
    elif data_score == 'good' and client_reaction.get('is_positive'):
        # Données OK + client content = EXCELLENT
        quality = 'excellent'
    elif data_score == 'good' and client_reaction.get('is_negative'):
        # Données OK mais client mécontent = à analyser
        quality = 'needs_review'
    elif client_reaction.get('is_positive'):
        # Client content (même sans données vérifiables) = bon
        quality = 'good'
    elif client_reaction.get('is_negative'):
        # Client mécontent = mauvais
        quality = 'bad'
    else:
        # Neutre
        quality = 'neutral'

    await _update_quality(db, email_id, quality, data_check, client_reaction)

    # APPRENTISSAGE : alimenter feedback_examples si excellent ou good
    if quality in ('excellent', 'good'):
        await _auto_feed_example(db, tenant_id, email_id, quality)

    return quality


async def _update_quality(db, email_id: int, quality: str,
                           data_check: dict, client_reaction: dict = None):
    """Met à jour response_quality en DB."""
    try:
        detail = f"data:{data_check.get('data_score', '?')}"
        if client_reaction:
            detail += f"|client:{client_reaction.get('reaction', '?')}"
        if data_check.get('errors'):
            detail += f"|errors:{','.join(data_check['errors'][:3])}"

        await db.execute(
            """UPDATE processed_emails
               SET response_quality = $1
               WHERE id = $2""",
            f"{quality}|{detail}"[:200],
            email_id
        )
        logger.info(
            f"Score reponse #{email_id}: {quality}",
            extra={'action': 'response_scored', 'quality': quality}
        )
    except asyncpg.PostgresError as e:
        logger.debug(f"Erreur update quality: {e}")


async def _auto_feed_example(db, tenant_id: str, email_id: int, quality: str):
    """Alimente feedback_examples avec une bonne réponse."""
    try:
        row = await db.fetch_one(
            """SELECT email_body_preview, response_text, brain_category
               FROM processed_emails WHERE id = $1""",
            email_id
        )
        if not row or not row.get('response_text') or not row.get('brain_category'):
            return

        category = row['brain_category']
        client_msg = row.get('email_body_preview', '')[:300]
        response = row['response_text'][:500]

        # Vérifier qu'on n'a pas déjà cet exemple
        existing = await db.fetch_one(
            """SELECT id FROM feedback_examples
               WHERE tenant_id = $1 AND category = $2
               AND client_message = $3""",
            tenant_id, category, client_msg
        )
        if existing:
            return

        # Insérer l'exemple
        await db.execute(
            """INSERT INTO feedback_examples
               (tenant_id, category, client_message, correct_response, source, created_at)
               VALUES ($1, $2, $3, $4, $5, NOW())""",
            tenant_id, category, client_msg, response, f'auto_{quality}'
        )
        logger.info(
            f"Exemple auto-alimente: {category} (source={quality})",
            extra={'action': 'auto_feedback', 'category': category}
        )

        # Limiter à 10 exemples par catégorie (garder les meilleurs)
        await db.execute(
            """DELETE FROM feedback_examples
               WHERE id IN (
                   SELECT id FROM feedback_examples
                   WHERE tenant_id = $1 AND category = $2
                   ORDER BY created_at DESC
                   OFFSET 10
               )""",
            tenant_id, category
        )
    except asyncpg.PostgresError as e:
        logger.debug(f"Erreur auto-feed: {e}")


# ══════════════════════════════════════════════════════════
# 4. SCORING AU RETOUR DU CLIENT (appelé par le pipeline)
# ══════════════════════════════════════════════════════════

async def score_previous_response(db, tenant_id: str, email_from: str,
                                    new_message: str, new_subject: str = ''):
    """
    Quand un client réécrit, on score la DERNIÈRE réponse qu'on lui a envoyée.
    Appelé au début du pipeline quand on détecte un client qui revient.
    """
    # Trouver la dernière réponse envoyée à ce client
    last_response = await db.fetch_one(
        """SELECT id, response_text, brain_category
           FROM processed_emails
           WHERE tenant_id = $1 AND email_from = $2
           AND response_sent = true AND response_text IS NOT NULL
           AND (response_quality IS NULL OR response_quality LIKE 'data_%' OR response_quality = 'pending')
           ORDER BY created_at DESC LIMIT 1""",
        tenant_id, email_from
    )

    if not last_response:
        return  # Pas de réponse précédente à scorer

    # Analyser la réaction du client
    client_reaction = check_client_reaction(new_message, new_subject)

    # Récupérer le data_check existant ou en créer un neutre
    existing_quality = last_response.get('response_quality') or ''
    if 'data:good' in existing_quality:
        data_check = {'data_score': 'good', 'checks': [], 'errors': []}
    elif 'data:bad' in existing_quality:
        data_check = {'data_score': 'bad', 'checks': [], 'errors': []}
    else:
        data_check = {'data_score': 'neutral', 'checks': [], 'errors': []}

    # Score combiné
    quality = await score_response(
        db, tenant_id, last_response['id'],
        data_check, client_reaction
    )

    logger.info(
        f"Scoring retour client: {email_from} -> {quality} "
        f"(reaction={client_reaction['reaction']})",
        extra={'action': 'return_scoring', 'quality': quality,
               'reaction': client_reaction['reaction']}
    )

# ======================================================================
# 5. APPRENTISSAGE DES RESOLUTIONS HUMAINES (v10.0)
# ======================================================================

async def learn_from_escalation(db, tenant_id: str, escalation_id: int, admin_response: str):
    """
    Quand un humain resout une escalation avec une reponse,
    sauvegarder le couple (message client -> reponse humaine) comme exemple.
    Les reponses humaines sont la reference qualite.
    """
    try:
        # Recuperer le message client original via l escalation
        row = await db.fetch_one(
            """SELECT e.email_from, e.category, pe.email_body_preview, pe.brain_category
               FROM escalations e
               LEFT JOIN processed_emails pe ON pe.id = e.email_id
               WHERE e.id = $1 AND e.tenant_id = $2""",
            escalation_id, tenant_id
        )
        if not row or not row.get('email_body_preview'):
            return

        category = row.get('brain_category') or row.get('category') or 'AUTRE'
        client_msg = row['email_body_preview'][:300]
        response = admin_response[:500]

        # Verifier qu on n a pas deja cet exemple
        existing = await db.fetch_one(
            """SELECT id FROM feedback_examples
               WHERE tenant_id = $1 AND category = $2
               AND client_message = $3""",
            tenant_id, category, client_msg
        )
        if existing:
            return

        # Inserer l exemple humain (source = human_escalation)
        await db.execute(
            """INSERT INTO feedback_examples
               (tenant_id, category, client_message, correct_response, source, created_at)
               VALUES ($1, $2, $3, $4, $5, NOW())""",
            tenant_id, category, client_msg, response, 'human_escalation'
        )
        logger.info(
            f"Exemple humain appris: {category} (escalation #{escalation_id})",
            extra={'action': 'feedback_saved', 'category': category,
                   'source': 'human_escalation'}
        )
    except asyncpg.PostgresError as e:
        logger.debug(f"Erreur learn_from_escalation: {e}")
