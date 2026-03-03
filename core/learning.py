"""
OKTAGON SAV v11.0 — Système d'apprentissage automatique.

3 mécanismes :
1. Détection satisfaction : analyse la réponse du client pour noter la qualité
2. Feedback loop : sauvegarde les escalations résolues comme exemples
3. Confiance progressive : ajuste le seuil selon le taux de satisfaction
"""
import logging
import re

logger = logging.getLogger('oktagon')

# ══════════════════════════════════════════════════════════
# 1. DÉTECTION DE SATISFACTION
# ══════════════════════════════════════════════════════════

POSITIVE_PATTERNS = [
    r'merci', r'parfait', r'super', r'genial', r'g[eé]nial', r'excellent',
    r'top', r'nickel', r'impeccable', r"c['\u2019]est bon", r'ok merci',
    r'bien re[cç]u', r'je vous remercie', r'bonne journ[eé]e',
    r'cordialement', r'au revoir', r'tr[eè]s bien', r'cool',
    r'bonne continuation', r'merci beaucoup', r'thanks', r'thank you',
    r"j['\u2019]ai bien re[cç]u", r"c['\u2019]est not[eé]", r'ok super',
    r"c['\u2019]est parfait", r"d['\u2019]accord merci", r"ok d['\u2019]accord",
]

NEGATIVE_PATTERNS = [
    r'pas satisfait', r'inadmissible', r'scandaleux', r'honteux',
    r'arnaque', r'voleur', r'rembours', r'plainte', r'avocat',
    r'tribunal', r'signaler', r'porter plainte', r'inacceptable',
    r"n['\u2019]importe quoi", r"c['\u2019]est nul", r"vous [eê]tes nul",
    r'je vais signaler', r'service client lamentable',
    r'r[eé]pondez[\s-]moi', r'aucune r[eé]ponse', r'toujours rien',
    r'je perds patience', r'dernier mail', r'derni[eè]re fois',
    r'pas du tout', r'absolument pas', r"c['\u2019]est faux",
]

NEUTRAL_FOLLOW_UP = [
    r"j['\u2019]ai une autre question", r'aussi', r'par ailleurs',
    r'autre chose', r'sinon', r'en plus', r'et pour',
]


def detect_satisfaction(client_message: str, previous_sav_response: str = None) -> dict:
    """
    Analyse le message du client pour détecter sa satisfaction
    par rapport à la réponse précédente du SAV.

    Retourne: {score: float 0-1, sentiment: str, source: str}
    """
    if not client_message:
        return {'score': None, 'sentiment': 'unknown', 'source': 'empty'}

    text = client_message.lower().strip()

    # Nettoyer les citations (enlever les lignes quoted)
    lines = text.split('\n')
    clean_lines = [l for l in lines if not l.strip().startswith('>')]
    text = '\n'.join(clean_lines).strip()

    if len(text) < 3:
        return {'score': None, 'sentiment': 'unknown', 'source': 'too_short'}

    pos_count = sum(1 for p in POSITIVE_PATTERNS if re.search(p, text, re.IGNORECASE))
    neg_count = sum(1 for p in NEGATIVE_PATTERNS if re.search(p, text, re.IGNORECASE))
    neutral_count = sum(1 for p in NEUTRAL_FOLLOW_UP if re.search(p, text, re.IGNORECASE))

    # Message court positif (juste "merci" ou "ok")
    if len(text) < 30 and pos_count > 0 and neg_count == 0:
        return {'score': 1.0, 'sentiment': 'positive', 'source': 'short_positive'}

    # Message négatif clair
    if neg_count >= 2 or (neg_count > 0 and pos_count == 0):
        score = max(0.0, 0.3 - (neg_count * 0.1))
        return {'score': score, 'sentiment': 'negative', 'source': 'negative_patterns'}

    # Message positif
    if pos_count > 0 and neg_count == 0:
        score = min(1.0, 0.7 + (pos_count * 0.1))
        return {'score': score, 'sentiment': 'positive', 'source': 'positive_patterns'}

    # Question de suivi (neutre — le client continue la conversation)
    if neutral_count > 0:
        return {'score': 0.6, 'sentiment': 'neutral_followup', 'source': 'follow_up'}

    # Par défaut — le client répond avec une nouvelle question = plutôt neutre
    return {'score': 0.5, 'sentiment': 'neutral', 'source': 'default'}


# ══════════════════════════════════════════════════════════
# 2. FEEDBACK LOOP — Sauvegarder les exemples
# ══════════════════════════════════════════════════════════

async def save_feedback_example(db, tenant_id: str, category: str,
                                client_message: str, correct_response: str,
                                source: str = 'escalation'):
    """Sauvegarde un exemple de bonne réponse pour apprentissage futur."""
    # Vérifier qu'on n'a pas déjà un exemple trop similaire
    existing = await db.fetch_one(
        """SELECT id FROM feedback_examples
           WHERE tenant_id = $1 AND category = $2
           AND client_message = $3""",
        tenant_id, category, client_message[:500]
    )
    if existing:
        logger.info(f"Exemple déjà existant pour {category}")
        return existing['id']

    result = await db.fetch_one(
        """INSERT INTO feedback_examples
           (tenant_id, category, client_message, correct_response, source)
           VALUES ($1, $2, $3, $4, $5) RETURNING id""",
        tenant_id, category, client_message[:500], correct_response[:1000], source
    )
    logger.info(f"Nouvel exemple appris : {category} (source={source})",
                extra={'action': 'feedback_saved', 'category': category})
    return result['id'] if result else None


async def get_feedback_examples(db, tenant_id: str, category: str, limit: int = 3) -> list:
    """Récupère les meilleurs exemples pour une catégorie donnée."""
    rows = await db.fetch_all(
        """SELECT client_message, correct_response, quality_score
           FROM feedback_examples
           WHERE tenant_id = $1 AND category = $2
           ORDER BY quality_score DESC, created_at DESC
           LIMIT $3""",
        tenant_id, category, limit
    )
    # Incrémenter le compteur d'utilisation
    for row in rows:
        await db.execute(
            "UPDATE feedback_examples SET used_count = used_count + 1 WHERE tenant_id = $1 AND category = $2 AND client_message = $3",
            tenant_id, category, row['client_message']
        )
    return [{'client': r['client_message'], 'response': r['correct_response']} for r in rows]


def format_examples_for_prompt(examples: list) -> str:
    """Formate les exemples appris pour injection dans le prompt."""
    if not examples:
        return ""

    text = "\n\n--- EXEMPLES APPRIS (réponses validées par l'équipe) ---\n"
    for i, ex in enumerate(examples, 1):
        client_preview = ex['client'][:200].strip()
        response_preview = ex['response'][:300].strip()
        text += f"\n--- Exemple {i} ---\nCLIENT : {client_preview}\nBONNE RÉPONSE : {response_preview}\n"
    text += "\nInspire-toi de ces exemples pour formuler ta réponse.\n"
    return text


# ══════════════════════════════════════════════════════════
# 3. CONFIANCE PROGRESSIVE
# ══════════════════════════════════════════════════════════

async def get_confidence_threshold(db, tenant_id: str) -> float:
    """Récupère le seuil de confiance actuel pour ce tenant."""
    row = await db.fetch_one(
        "SELECT confidence_threshold FROM tenant_learning WHERE tenant_id = $1",
        tenant_id
    )
    return row['confidence_threshold'] if row else 0.85


async def update_learning_stats(db, tenant_id: str, is_positive: bool):
    """Met à jour les stats d'apprentissage et ajuste le seuil si nécessaire."""
    if is_positive:
        await db.execute(
            """UPDATE tenant_learning
               SET total_responses = total_responses + 1,
                   positive_responses = positive_responses + 1
               WHERE tenant_id = $1""",
            tenant_id
        )
    else:
        await db.execute(
            """UPDATE tenant_learning
               SET total_responses = total_responses + 1,
                   negative_responses = negative_responses + 1
               WHERE tenant_id = $1""",
            tenant_id
        )

    # Vérifier si on doit ajuster le seuil (tous les 20 emails)
    stats = await db.fetch_one(
        """SELECT confidence_threshold, total_responses, positive_responses, negative_responses
           FROM tenant_learning WHERE tenant_id = $1""",
        tenant_id
    )
    if not stats or stats['total_responses'] < 20:
        return

    if stats['total_responses'] % 20 != 0:
        return

    total = stats['total_responses']
    positive = stats['positive_responses']
    current_threshold = stats['confidence_threshold']
    satisfaction_rate = positive / total if total > 0 else 0

    new_threshold = current_threshold

    # Si taux de satisfaction > 80% et seuil > 0.5 → baisser de 0.05
    if satisfaction_rate > 0.80 and current_threshold > 0.50:
        new_threshold = round(current_threshold - 0.05, 2)
        logger.info(f"Confiance ajustée: {current_threshold} -> {new_threshold} "
                    f"(satisfaction={satisfaction_rate:.0%}, n={total})",
                    extra={'action': 'threshold_lowered'})

    # Si taux de satisfaction < 60% → remonter de 0.05
    elif satisfaction_rate < 0.60 and current_threshold < 0.95:
        new_threshold = round(current_threshold + 0.05, 2)
        logger.info(f"Confiance remontée: {current_threshold} -> {new_threshold} "
                    f"(satisfaction={satisfaction_rate:.0%}, n={total})",
                    extra={'action': 'threshold_raised'})

    if new_threshold != current_threshold:
        await db.execute(
            """UPDATE tenant_learning
               SET confidence_threshold = $1, last_adjusted_at = NOW()
               WHERE tenant_id = $2""",
            new_threshold, tenant_id
        )


# ══════════════════════════════════════════════════════════
# 4. AUTO-FEEDBACK APRÈS 48H SANS RÉPONSE
# ══════════════════════════════════════════════════════════

async def check_no_reply_satisfaction(db, tenant_id: str):
    """
    Emails envoyés il y a >48h sans réponse du client = probablement satisfait.
    Appelé périodiquement par le polling.
    """
    rows = await db.fetch_all(
        """SELECT pe.id, pe.email_from
           FROM processed_emails pe
           WHERE pe.tenant_id = $1
           AND pe.response_sent = true
           AND pe.satisfaction_score IS NULL
           AND pe.created_at < NOW() - INTERVAL '48 hours'
           AND NOT EXISTS (
               SELECT 1 FROM processed_emails pe2
               WHERE pe2.tenant_id = $1
               AND pe2.email_from = pe.email_from
               AND pe2.created_at > pe.created_at
           )
           LIMIT 50""",
        tenant_id
    )

    count = 0
    learned = 0
    for r in rows:
        await db.execute(
            """UPDATE processed_emails
               SET satisfaction_score = 0.7,
                   satisfaction_source = 'no_reply_48h',
                   client_reply_sentiment = 'presumed_satisfied'
               WHERE id = $1""",
            r['id']
        )
        await update_learning_stats(db, tenant_id, is_positive=True)
        count += 1

        # v10.0 — Auto-feed : silence 48h + data_score good = bonne réponse
        try:
            row = await db.fetch_one(
                """SELECT response_quality, response_text, brain_category, email_body_preview
                   FROM processed_emails WHERE id = $1""",
                r['id']
            )
            if (row and row.get('response_quality') and 'data:good' in (row['response_quality'] or '')
                    and row.get('response_text') and row.get('brain_category')):
                existing = await db.fetch_one(
                    """SELECT id FROM feedback_examples
                       WHERE tenant_id = $1 AND category = $2 AND client_message = $3""",
                    tenant_id, row['brain_category'], (row.get('email_body_preview') or '')[:500]
                )
                if not existing:
                    await db.execute(
                        """INSERT INTO feedback_examples
                           (tenant_id, category, client_message, correct_response, source, created_at)
                           VALUES ($1, $2, $3, $4, 'auto_silence_good', NOW())""",
                        tenant_id, row['brain_category'],
                        (row.get('email_body_preview') or '')[:500],
                        row['response_text'][:1000]
                    )
                    learned += 1
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"Erreur auto-feed silence 48h: {e}")

    if count > 0:
        logger.info(f"Auto-satisfaction: {count} emails sans réponse -> présumés satisfaits"
                    + (f" | {learned} exemples appris" if learned else ""),
                    extra={'action': 'auto_satisfaction', 'count': count, 'learned': learned})
    return count
