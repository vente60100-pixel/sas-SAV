"""
OKTAGON SAV v6.3 — Mémoire client intelligente.

Profil client enrichi avec :
- Score de fidélité (basé sur nb commandes, ancienneté, satisfaction)
- Tags automatiques (VIP, à risque, nouveau, fidèle)
- État de conversation (1er contact, suivi, relance)
- Historique émotionnel (tendance du ton)
- Contexte pour le cerveau (tout ce qu'on sait sur ce client)
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('oktagon')


# ══════════════════════════════════════════════════════════
# PROFIL CLIENT ENRICHI
# ══════════════════════════════════════════════════════════

async def build_client_context(db, repos, tenant_id: str, email: str,
                                current_emotion: dict = None) -> dict:
    """
    Construit le contexte client complet pour le cerveau.

    Retourne un dict enrichi avec :
    - Toutes les stats du client
    - Ses tags (VIP, nouveau, à risque, fidèle)
    - Son état de conversation (1er contact, suivi, relance)
    - Son score de fidélité
    - Instructions spéciales pour le cerveau
    """
    # 1. Stats de base
    stats = await repos.get_client_profile(tenant_id, email)

    # 2. Profil persistant
    profile_row = await db.fetch_one(
        "SELECT * FROM client_profiles WHERE tenant_id = $1 AND email = $2",
        tenant_id, email
    )

    # 3. Historique satisfaction
    satisfaction_stats = await db.fetch_one(
        """SELECT
            COUNT(*) as total_interactions,
            AVG(satisfaction_score) as avg_satisfaction,
            COUNT(CASE WHEN satisfaction_score >= 0.7 THEN 1 END) as positive_count,
            COUNT(CASE WHEN satisfaction_score < 0.4 THEN 1 END) as negative_count
           FROM processed_emails
           WHERE tenant_id = $1 AND email_from = $2
           AND satisfaction_score IS NOT NULL""",
        tenant_id, email
    )

    # 4. Dernières commandes Shopify
    orders_info = await db.fetch_one(
        """SELECT COUNT(DISTINCT COALESCE(
                NULLIF(brain_category, ''), category
           )) as categories_count
           FROM processed_emails
           WHERE tenant_id = $1 AND email_from = $2""",
        tenant_id, email
    )

    # 5. Temps depuis premier et dernier contact
    time_info = await db.fetch_one(
        """SELECT MIN(created_at) as first_contact,
                  MAX(created_at) as last_contact
           FROM processed_emails
           WHERE tenant_id = $1 AND email_from = $2""",
        tenant_id, email
    )

    # 6. Escalations non résolues
    open_escalations = await db.fetch_one(
        """SELECT COUNT(*) as c FROM escalations
           WHERE tenant_id = $1 AND email_from = $2
           AND resolved = false""",
        tenant_id, email
    )

    # Calculer le contexte
    total_emails = stats.get('total_emails', 0)
    total_escalations = stats.get('total_escalations', 0)
    emails_24h = stats.get('emails_last_24h', 0)
    avg_satisfaction = float(satisfaction_stats['avg_satisfaction'] or 0) if satisfaction_stats else 0
    positive_count = satisfaction_stats['positive_count'] if satisfaction_stats else 0
    negative_count = satisfaction_stats['negative_count'] if satisfaction_stats else 0
    open_esc = open_escalations['c'] if open_escalations else 0

    # ═══ TAGS AUTOMATIQUES ═══
    tags = []

    # Nouveau client
    if total_emails <= 1:
        tags.append('NOUVEAU')

    # Client fidèle (5+ contacts positifs)
    if total_emails >= 5 and avg_satisfaction >= 0.6:
        tags.append('FIDÈLE')

    # VIP (10+ contacts ou satisfaction très haute)
    is_vip = (profile_row and profile_row.get('vip')) or total_emails >= 10
    if is_vip:
        tags.append('VIP')

    # À risque (insatisfaction récurrente)
    if negative_count >= 2 or (current_emotion and current_emotion.get('primary_emotion') == 'furieux'):
        tags.append('À_RISQUE')

    # Relanceur (3+ emails en 24h)
    if emails_24h >= 3:
        tags.append('RELANCEUR')

    # Escalation ouverte
    if open_esc > 0:
        tags.append('ESCALATION_ACTIVE')

    # ═══ ÉTAT DE CONVERSATION ═══
    if total_emails == 0:
        conversation_state = 'premier_contact'
    elif emails_24h >= 2:
        conversation_state = 'relance'
    elif total_emails <= 2:
        conversation_state = 'suivi'
    else:
        conversation_state = 'client_regulier'

    # ═══ SCORE DE FIDÉLITÉ (0-100) ═══
    loyalty_score = _calculate_loyalty(
        total_emails, total_escalations, avg_satisfaction,
        positive_count, negative_count, time_info
    )

    # ═══ INSTRUCTIONS SPÉCIALES POUR LE CERVEAU ═══
    special_instructions = _build_special_instructions(
        tags, conversation_state, loyalty_score,
        current_emotion, open_esc, total_emails, emails_24h
    )

    context = {
        'total_emails': total_emails,
        'total_escalations': total_escalations,
        'emails_last_24h': emails_24h,
        'prenom': (profile_row['prenom'] if profile_row and profile_row.get('prenom') else None),
        'vip': is_vip,
        'tags': tags,
        'conversation_state': conversation_state,
        'loyalty_score': loyalty_score,
        'avg_satisfaction': round(avg_satisfaction, 2),
        'open_escalations': open_esc,
        'special_instructions': special_instructions,
    }

    logger.info(
        f"Profil client: {email} | tags={tags} | state={conversation_state} | "
        f"loyalty={loyalty_score} | sat={avg_satisfaction:.2f}",
        extra={'action': 'client_context_built', 'tags': ','.join(tags)}
    )

    return context


def _calculate_loyalty(total_emails, total_escalations, avg_satisfaction,
                       positive_count, negative_count, time_info) -> int:
    """Calcule un score de fidélité client (0-100)."""
    score = 50  # Base neutre

    # Ancienneté (max +15)
    if time_info and time_info.get('first_contact'):
        days_since = (datetime.now(time_info['first_contact'].tzinfo) -
                      time_info['first_contact']).days
        if days_since > 90:
            score += 15
        elif days_since > 30:
            score += 10
        elif days_since > 7:
            score += 5

    # Satisfaction moyenne (max +20 / -20)
    if avg_satisfaction > 0:
        score += int((avg_satisfaction - 0.5) * 40)  # -20 à +20

    # Volume de contacts (modéré = bon, trop = problème)
    if 2 <= total_emails <= 5:
        score += 5  # Client engagé
    elif total_emails > 10:
        score -= 5  # Trop de contacts = problèmes

    # Escalations (négatif)
    score -= total_escalations * 5

    # Ratio positif/négatif
    if positive_count > negative_count:
        score += 10
    elif negative_count > positive_count:
        score -= 10

    return max(0, min(100, score))


def _build_special_instructions(tags, state, loyalty, emotion,
                                 open_esc, total_emails, emails_24h) -> str:
    """Construit des instructions spéciales pour le cerveau selon le profil."""
    instructions = []

    # Client VIP
    if 'VIP' in tags:
        instructions.append(
            "🌟 CLIENT VIP — Traitement prioritaire. "
            "Sois extra attentif et personnalisé. "
            "Ce client est un ambassadeur potentiel de la marque."
        )

    # Client à risque
    if 'À_RISQUE' in tags:
        instructions.append(
            "⚠️ CLIENT À RISQUE — Ce client a déjà exprimé son mécontentement. "
            "Sois proactif : propose des solutions concrètes AVANT qu'il ne demande. "
            "Évite toute phrase qui pourrait aggraver la situation."
        )

    # Nouveau client
    if 'NOUVEAU' in tags:
        instructions.append(
            "🆕 PREMIER CONTACT — Ce client découvre le SAV OKTAGON. "
            "Fais bonne impression : sois accueillant, clair, et efficace. "
            "C'est le moment de créer une relation de confiance."
        )

    # Relanceur
    if 'RELANCEUR' in tags:
        instructions.append(
            f"🔄 CLIENT EN RELANCE ({emails_24h} emails en 24h) — "
            "Il est clairement en attente d'une réponse. "
            "NE RÉPÈTE PAS ce que tu as déjà dit. "
            "Donne de NOUVELLES informations ou escalade si tu ne peux pas aider."
        )

    # Escalation active
    if 'ESCALATION_ACTIVE' in tags:
        instructions.append(
            f"📋 ESCALATION EN COURS ({open_esc} active(s)) — "
            "Ce client a un dossier en cours chez un humain. "
            "Informe-le que son dossier est traité en priorité. "
            "NE DONNE PAS de nouvelles informations contradictoires."
        )

    # Client fidèle
    if 'FIDÈLE' in tags and 'À_RISQUE' not in tags:
        instructions.append(
            "💛 CLIENT FIDÈLE — Ce client revient régulièrement. "
            "Il connaît probablement déjà les procédures. "
            "Sois direct et efficace, pas besoin de tout réexpliquer."
        )

    # État de conversation
    if state == 'relance':
        instructions.append(
            "📨 C'EST UNE RELANCE — Le client a déjà écrit récemment. "
            "VÉRIFIE l'historique pour ne pas te répéter. "
            "Apporte un élément NOUVEAU dans ta réponse."
        )

    # Adapter selon émotion si fournie
    if emotion and emotion.get('tone_instruction'):
        instructions.append(emotion['tone_instruction'])

    if not instructions:
        return ""

    return "\n".join(instructions)


async def update_client_emotion(db, tenant_id: str, email: str,
                                 emotion: str, score: float):
    """Met à jour le dernier ton émotionnel du client."""
    try:
        await db.execute(
            """UPDATE client_profiles
               SET dernier_ton = $1, updated_at = NOW()
               WHERE tenant_id = $2 AND email = $3""",
            f"{emotion}:{score:.2f}", tenant_id, email
        )
    except Exception:
        pass  # Pas grave si ça échoue
