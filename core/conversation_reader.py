"""
Module pour lire et analyser TOUTE la conversation email d'un client
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional

async def get_full_conversation(db, email_from: str, tenant_id: str, limit: int = 20) -> List[Dict]:
    """
    Récupère TOUTE la conversation avec un client
    
    Args:
        db: Database wrapper instance
    
    Returns:
        Liste des emails dans l'ordre chronologique
    """
    # Emails du client (reçus) UNIQUEMENT
    client_emails = await db.fetch_all('''
        SELECT
            email_body_preview as message,
            response_sent,
            category,
            conversation_step
        FROM processed_emails
        WHERE tenant_id = $1
        AND email_from = $2
        ORDER BY id DESC
        LIMIT $3
    ''', tenant_id, email_from, limit)

    # Construire la conversation
    conversation = []

    for email in client_emails:
        conversation.append({
            'direction': 'client',
            'message': email.get('message') or '',
            'response_sent': email.get('response_sent', False),
            'category': email.get('category'),
            'step': email.get('conversation_step', 1)
        })

    # Inverser pour avoir le plus ancien en premier
    conversation.reverse()

    return conversation

def format_conversation_for_ai(conversation: List[Dict], client_name: str = "Client") -> str:
    """
    Formate la conversation pour l'IA de manière claire
    """
    if not conversation:
        return "📭 Aucun historique de conversation"

    lines = []
    lines.append("📜 HISTORIQUE CONVERSATION COMPLÈTE :")
    lines.append("=" * 80)

    for i, msg in enumerate(conversation, 1):
        direction = f"👤 {client_name}"

        # Résumé du message (150 premiers caractères)
        message = msg.get('message') or ''
        message_preview = message[:150].replace('\n', ' ').strip()
        if len(message) > 150:
            message_preview += "..."

        lines.append(f"\n{i}. {direction}:")
        lines.append(f"   {message_preview}")

        if msg.get('category'):
            lines.append(f"   Catégorie: {msg['category']}")

        if not msg.get('response_sent'):
            lines.append(f"   ⚠️  PAS DE RÉPONSE ENVOYÉE")

    lines.append("\n" + "=" * 80)

    # Analyse
    total = len(conversation)
    no_response = sum(1 for m in conversation if not m.get('response_sent'))

    lines.append(f"\n📊 ANALYSE:")
    lines.append(f"  Total messages client: {total}")
    if no_response > 0:
        lines.append(f"  ⚠️  Messages sans réponse: {no_response}")

    # Détecter relances
    if no_response >= 2:
        lines.append(f"  🚨 CLIENT RELANCE ({no_response} fois sans réponse)")

    return "\n".join(lines)

def enrich_profile_from_conversation(profile: Dict, conversation: List[Dict]) -> Dict:
    """
    Enrichit automatiquement le profil client depuis la conversation
    """
    if not conversation:
        return profile

    # Compter relances sans réponse
    relances = sum(1 for m in conversation if not m.get('response_sent'))
    profile['relances_sans_reponse'] = relances

    # Détecter urgence
    if relances >= 2:
        profile['urgence'] = 'HAUTE'
    elif relances == 1:
        profile['urgence'] = 'MOYENNE'
    else:
        profile['urgence'] = 'NORMALE'

    return profile
