"""
OKTAGON SAV v11.0 — Intelligence émotionnelle.

Analyse le ton du client et définit comment le cerveau doit adapter sa réponse.
3 niveaux : détection → classification → instructions d'adaptation.
"""
import re
import logging

logger = logging.getLogger('oktagon')


# ══════════════════════════════════════════════════════════
# PATTERNS ÉMOTIONNELS (français + variantes)
# ══════════════════════════════════════════════════════════

EMOTION_PATTERNS = {
    'furieux': {
        'patterns': [
            r'scandaleux', r'inadmissible', r'honteux', r'inacceptable',
            r'arnaque', r'voleur', r'escroc', r'menteur',
            r'porter plainte', r'avocat', r'tribunal', r'signaler',
            r'dégueulasse', r'honte à vous', r'foutre de la gueule',
            r'pire service', r'lamentable', r'incompétent',
            r'je suis furieux', r'je suis furieuse', r'révolté',
            r'vous vous foutez', r'vous vous moquez',
        ],
        'weight': 3,  # Poids par match
    },
    'frustre': {
        'patterns': [
            r'pas normal', r'pas satisfait', r'déçu', r'déçue',
            r'toujours rien', r'aucune réponse', r'aucune nouvelle',
            r'j.attends depuis', r'ça fait \d+ jours', r'ça fait \d+ semaines',
            r'dernier mail', r'dernière fois', r'je perds patience',
            r'encore une fois', r'combien de fois', r'relance',
            r'pas du tout', r'absolument pas', r'n.importe quoi',
            r'je commence à', r'ras le bol', r'marre',
            r'pas sérieux', r'pas professionnel',
        ],
        'weight': 2,
    },
    'inquiet': {
        'patterns': [
            r'inquiet', r'inquiète', r'angoiss', r'stress',
            r'peur de', r'j.ai peur', r'est-ce normal',
            r'est-ce que c.est normal', r'perdu', r'je ne sais pas',
            r'je comprends pas', r'pourquoi', r'que se passe',
            r'aucun signe', r'pas de nouvelles', r'silence',
            r'important pour moi', r'c.est urgent', r'urgence',
            r'j.en ai besoin', r'cadeau', r'anniversaire',
            r'compétition', r'match', r'événement',
        ],
        'weight': 1.5,
    },
    'impatient': {
        'patterns': [
            r'quand est-ce', r'combien de temps', r'c.est long',
            r'trop long', r'ça prend du temps', r'j.attends',
            r'toujours pas reçu', r'pas encore reçu',
            r'livraison en retard', r'retard', r'délai',
            r'ça devrait déjà', r'normalement',
            r'rapide', r'vite', r'rapidement',
        ],
        'weight': 1,
    },
    'calme': {
        'patterns': [
            r'bonjour', r'bonsoir', r'cordialement',
            r'pourriez-vous', r'serait-il possible',
            r'je souhaiterais', r'j.aimerais', r'merci d.avance',
            r'svp', r's.il vous plaît', r'bien vouloir',
            r'je me permets', r'petite question',
        ],
        'weight': 1,
    },
    'satisfait': {
        'patterns': [
            r'merci beaucoup', r'merci pour', r'merci .* réactivité', r'super', r'parfait', r'génial',
            r'excellent', r'top', r'nickel', r'impeccable',
            r'très content', r'très contente', r'ravi', r'ravie',
            r'bravo', r'beau travail', r'recommande',
            r'bonne continuation', r'bonne journée',
        ],
        'weight': 1,
    },
}

# Instructions d'adaptation du ton pour le cerveau IA
TONE_INSTRUCTIONS = {
    'furieux': """
⚠️ CLIENT FURIEUX — Ton ULTRA-EMPATHIQUE requis :
- Commence DIRECTEMENT par reconnaître sa colère : "Je comprends parfaitement votre mécontentement"
- Sois factuel et concret — donne des ACTIONS, pas des excuses
- Propose une solution immédiate ou une escalade rapide
- Ton sérieux et professionnel, pas de phrases légères
- NE DIS PAS "je comprends votre frustration" (trop robotique) → dis "vous avez raison d'être mécontent, voici ce qu'on fait"
- Réponse un peu plus longue que d'habitude (6-10 lignes) pour montrer qu'on prend au sérieux
""",
    'frustre': """
⚠️ CLIENT FRUSTRÉ — Ton RASSURANT requis :
- Reconnais le problème sans minimiser : "Effectivement, ce délai est anormal"
- Donne des infos CONCRÈTES (tracking, statut, prochaines étapes)
- Montre que tu agis MAINTENANT, pas "nous allons voir"
- Si c'est une relance → dis "je revérifie votre dossier" (pas "comme indiqué précédemment")
- Évite tout ce qui sonne comme du copier-coller
""",
    'inquiet': """
ℹ️ CLIENT INQUIET — Ton APAISANT requis :
- Rassure dès la première phrase : "Pas d'inquiétude, tout est en ordre"
- Explique le processus étape par étape pour qu'il comprenne où il en est
- Si c'est un cadeau/événement → montre que tu as compris l'enjeu personnel
- Donne un maximum de détails factuels (dates, statut, tracking)
- Termine par une note positive et concrète
""",
    'impatient': """
ℹ️ CLIENT IMPATIENT — Ton EFFICACE requis :
- Va DROIT AU BUT dès la première ligne (pas de blabla)
- Donne immédiatement l'info demandée (statut, tracking, délai)
- Phrases ultra-courtes et factuelles
- Si tu n'as pas l'info → dis-le clairement et donne un délai pour revenir vers lui
""",
    'calme': """
Client calme — Ton STANDARD :
- Réponse professionnelle et chaleureuse
- Donne l'info demandée de manière claire
- Réponse concise (4-6 lignes)
""",
    'satisfait': """
Client satisfait — Ton CHALEUREUX :
- Remercie-le pour son retour positif
- Si question supplémentaire → réponds naturellement
- Réponse courte et positive
- Glisse un petit mot sur la communauté OKTAGON si pertinent
""",
}


def analyze_emotion(text: str, subject: str = '', history: str = '') -> dict:
    """
    Analyse l'émotion du client à partir de son message.

    Retourne:
    {
        'primary_emotion': str,      # Émotion dominante
        'emotion_score': float,      # Intensité 0-1
        'is_escalation_risk': bool,  # Risque d'escalade émotionnelle
        'tone_instruction': str,     # Instructions pour le cerveau
        'detected_triggers': list,   # Mots-clés détectés
        'contact_count_factor': str, # 'first', 'returning', 'recurring'
    }
    """
    full_text = f"{subject} {text}".lower()

    # Compter les matches par émotion
    emotion_scores = {}
    triggers = []

    for emotion, config in EMOTION_PATTERNS.items():
        count = 0
        for pattern in config['patterns']:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                count += len(matches)
                triggers.extend(matches[:2])  # Garder max 2 exemples par pattern
        emotion_scores[emotion] = count * config['weight']

    # Déterminer l'émotion dominante
    if not any(emotion_scores.values()):
        primary = 'calme'
        intensity = 0.3
    else:
        primary = max(emotion_scores, key=emotion_scores.get)
        max_score = emotion_scores[primary]
        # Normaliser l'intensité (0-1)
        intensity = min(1.0, max_score / 8.0)

    # Facteurs aggravants
    aggravating = 0

    # Majuscules excessives = énervement
    upper_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if upper_ratio > 0.3 and len(text) > 20:
        aggravating += 0.15
        triggers.append('MAJUSCULES')

    # Points d'exclamation multiples
    excl_count = text.count('!')
    if excl_count >= 3:
        aggravating += 0.1
        triggers.append(f'{excl_count}x !')

    # Points de suspension (hésitation/frustration)
    if text.count('...') >= 2:
        aggravating += 0.05

    # Message très court + négatif = très frustré
    if len(text.strip()) < 50 and primary in ('furieux', 'frustre'):
        aggravating += 0.1

    # Message très long = a besoin d'être entendu
    if len(text.strip()) > 500 and primary in ('furieux', 'frustre', 'inquiet'):
        aggravating += 0.05

    intensity = min(1.0, intensity + aggravating)

    # Risque d'escalade
    is_risk = (
        primary == 'furieux' or
        (primary == 'frustre' and intensity > 0.2) or
        any(w in full_text for w in ['avocat', 'plainte', 'tribunal', 'signaler'])
    )

    # Déterminer le contexte de contact (1er contact vs relance)
    contact_factor = 'first'
    if history:
        history_lines = [l for l in history.split('\n') if l.strip().startswith('[')]
        if len(history_lines) >= 6:
            contact_factor = 'recurring'
        elif len(history_lines) >= 2:
            contact_factor = 'returning'

    # Ajuster pour les clients récurrents frustrés
    if contact_factor == 'recurring' and primary in ('frustre', 'impatient'):
        primary = 'frustre'  # Upgrader impatient → frustré si récurrent
        intensity = min(1.0, intensity + 0.15)

    return {
        'primary_emotion': primary,
        'emotion_score': round(intensity, 2),
        'is_escalation_risk': is_risk,
        'tone_instruction': TONE_INSTRUCTIONS.get(primary, TONE_INSTRUCTIONS['calme']),
        'detected_triggers': triggers[:5],  # Max 5 triggers
        'contact_count_factor': contact_factor,
    }


def get_emotion_label(emotion: str, score: float) -> str:
    """Label lisible pour le dashboard."""
    labels = {
        'furieux': '🔴 Furieux',
        'frustre': '🟠 Frustré',
        'inquiet': '🟡 Inquiet',
        'impatient': '🟡 Impatient',
        'calme': '🟢 Calme',
        'satisfait': '🟢 Satisfait',
    }
    base = labels.get(emotion, '⚪ Inconnu')
    if score > 0.7:
        return f"{base} (forte intensité)"
    return base


# ======================================================================
# TRAJECTOIRE EMOTIONNELLE (v10.0)
# ======================================================================

EMOTION_SEVERITY = {
    'furieux': 5, 'frustre': 4, 'inquiet': 3,
    'impatient': 2, 'calme': 1, 'satisfait': 0,
}

TRAJECTORY_INSTRUCTIONS = {
    'escalating': (
        "Ce client MONTE EN PRESSION. Chaque reponse doit apporter "
        "quelque chose de NOUVEAU. Si tu n'as rien de nouveau a lui "
        "dire -> ESCALADE IMMEDIATE."
    ),
    'stable_negative': (
        "Ce client est frustre depuis plusieurs echanges. "
        "Propose une action CONCRETE (verification, escalade interne)."
    ),
    'de-escalating': (
        "Le client se calme. Continue sur cette voie, "
        "reste professionnel et chaleureux."
    ),
    'stable': "",
}


async def analyze_emotion_trajectory(db, tenant_id, email_from, current_emotion):
    """Calcule la trajectoire emotionnelle du client sur ses derniers echanges."""
    try:
        rows = await db.fetch_all(
            """SELECT emotion_detected, emotion_score, created_at
               FROM processed_emails
               WHERE tenant_id = $1 AND email_from = $2
               AND emotion_detected IS NOT NULL
               ORDER BY created_at DESC LIMIT 5""",
            tenant_id, email_from
        )

        if len(rows) < 2:
            return {'trajectory': 'insufficient_data', 'instruction': '', 'urgency_boost': False}

        # Construire la serie (du plus ancien au plus recent)
        emotions = list(reversed(rows))
        current_emo = current_emotion.get('primary_emotion', 'calme') if current_emotion else 'calme'

        # Calculer les severites
        severities = [EMOTION_SEVERITY.get(e.get('emotion_detected', 'calme'), 1) for e in emotions]
        severities.append(EMOTION_SEVERITY.get(current_emo, 1))

        # Tendance : comparer premiere et derniere moitie
        mid = len(severities) // 2
        avg_first = sum(severities[:mid]) / max(mid, 1)
        avg_second = sum(severities[mid:]) / max(len(severities) - mid, 1)
        delta = avg_second - avg_first

        # Classifier
        if delta >= 1.0:
            trajectory = 'escalating'
        elif delta <= -1.0:
            trajectory = 'de-escalating'
        elif avg_second >= 3.0:
            trajectory = 'stable_negative'
        else:
            trajectory = 'stable'

        # Labels lisibles
        emo_names = [e.get('emotion_detected', '?') for e in emotions] + [current_emo]
        label = ' -> '.join(emo_names[-3:])

        return {
            'trajectory': trajectory,
            'label': label,
            'instruction': TRAJECTORY_INSTRUCTIONS.get(trajectory, ''),
            'urgency_boost': trajectory == 'escalating' and severities[-1] >= 3,
            'delta': round(delta, 2),
        }
    except (ValueError, TypeError, KeyError) as e:
        return {'trajectory': 'error', 'instruction': '', 'urgency_boost': False}
