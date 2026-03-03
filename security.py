"""
OKTAGON SAV v11.0 — Sécurité et validation
Anti-spam, détection langue, hash emails, validation
"""
import hashlib
import re
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from config import config
from logger import logger


@dataclass
class SecurityResult:
    """Résultat analyse sécurité d'un email"""
    email_hash: str
    is_spam: bool
    is_auto_responder: bool
    is_thank_you: bool
    language: str
    has_attachments: bool
    attachment_count: int
    order_number: Optional[str]
    spam_reason: Optional[str]


def compute_email_hash(email_from: str, subject: str, body: str) -> str:
    """
    Génère hash SHA256 unique pour anti-doublon

    Args:
        email_from: Email expéditeur
        subject: Sujet
        body: Corps (premiers 200 chars)

    Returns:
        Hash SHA256 hexadécimal
    """
    content = f"{email_from}|{subject}|{body[:200]}|{config.security.hash_salt}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def is_auto_responder(headers: dict[str, str]) -> bool:
    """
    Détecte si email = auto-répondeur

    Args:
        headers: Headers email

    Returns:
        True si auto-répondeur détecté
    """
    auto_headers = [
        'auto-submitted',
        'x-auto-response-suppress',
        'x-autoreply',
        'precedence'
    ]

    for header in auto_headers:
        if header.lower() in [h.lower() for h in headers.keys()]:
            return True

    return False


def is_spam_sender(email_from: str, subject: str, headers: dict[str, str]) -> tuple[bool, Optional[str]]:
    """
    Détecte si email = spam/newsletter

    Args:
        email_from: Email expéditeur
        subject: Sujet
        headers: Headers email

    Returns:
        (is_spam, reason)
    """
    # Prefixes spam
    spam_prefixes = ['no-reply@', 'no_reply@', 'noreply@', 'donotreply@', 'newsletter@', 'marketing@', 'info@', 'calendar-notification@', 'calendar-server@']
    email_lower = email_from.lower()

    for prefix in spam_prefixes:
        if email_lower.startswith(prefix):
            return True, f"Prefix spam: {prefix}"

    # Mots-clés spam dans le from
    spam_keywords = ['newsletter', 'noreply', 'no-reply', 'automated']
    for keyword in spam_keywords:
        if keyword in email_lower:
            return True, f"Keyword spam: {keyword}"

    # Header List-Unsubscribe (newsletter)
    if 'list-unsubscribe' in [h.lower() for h in headers.keys()]:
        return True, "List-Unsubscribe header"

    # Invitations Calendar (Google Calendar, Outlook, etc.)
    content_type = headers.get('Content-Type', headers.get('content-type', ''))
    if 'text/calendar' in content_type.lower():
        return True, "Calendar invitation (Content-Type)"
    subject_lower = subject.lower()
    calendar_patterns = ['invitation:', 'updated invitation:', 'canceled event:', 'accepted:', 'declined:', 'tentative:']
    for pattern in calendar_patterns:
        if subject_lower.startswith(pattern):
            return True, f"Calendar invitation (sujet: {pattern})"

    return False, None


def is_thank_you_message(body: str) -> bool:
    """
    Détecte si message = simple remerciement

    Args:
        body: Corps email

    Returns:
        True si remerciement simple
    """
    if len(body.strip()) > 200:
        return False

    thank_words = ['merci', 'thank', 'gracias', 'ok', 'super', 'parfait', 'bien reçu', 'received']
    body_lower = body.lower()

    return any(word in body_lower for word in thank_words) and len(body.strip()) < 100


def detect_language(subject: str, body: str) -> str:
    """
    Détecte langue email (FR/EN/ES)

    Args:
        subject: Sujet
        body: Corps

    Returns:
        Code langue: 'fr', 'en', 'es'
    """
    text = (subject + " " + body).lower()

    # Mots-clés par langue
    fr_words = ['bonjour', 'merci', 'commande', 'livraison', 'retour', 'je', 'vous', 'mon', 'ma']
    en_words = ['hello', 'thank', 'order', 'delivery', 'return', 'my', 'your', 'please']
    es_words = ['hola', 'gracias', 'pedido', 'envío', 'devolver', 'mi', 'su', 'por favor']

    # Compter occurrences (mots entiers uniquement, pas sous-chaines)
    words_in_text = set(re.findall(r'\b\w+\b', text))
    fr_count = sum(1 for word in fr_words if word in words_in_text)
    en_count = sum(1 for word in en_words if word in words_in_text)
    es_count = sum(1 for word in es_words if word in words_in_text)

    # Retourner langue avec le plus de matches
    max_count = max(fr_count, en_count, es_count)
    if max_count == 0:
        return 'fr'
    if es_count == max_count and es_count > fr_count and es_count > en_count:
        return 'es'
    if en_count == max_count and en_count > fr_count:
        return 'en'
    return 'fr'


def extract_order_number(text: str) -> Optional[str]:
    """
    Extrait numéro de commande du texte

    Args:
        text: Texte à analyser

    Returns:
        Numéro de commande ou None
    """
    # Pattern : #XXXX ou #XXXXX (3-6 chiffres)
    patterns = [
        r'#(\d{3,6})',           # #8485
        r'commande[\s:]*#?(\d{3,6})',  # commande #8485
        r'order[\s:]*#?(\d{3,6})',     # order #8485
        r'pedido[\s:]*#?(\d{3,6})',    # pedido #8485
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num = match.group(1)
            # Filtrer les années (2020-2030) — ce ne sont pas des numéros de commande
            if 2020 <= int(num) <= 2030:
                continue
            return num

    return None


def count_attachments(headers: dict[str, str], raw_content: str) -> tuple[bool, int]:
    """
    Compte pièces jointes

    Args:
        headers: Headers email
        raw_content: Contenu brut email

    Returns:
        (has_attachments, count)
    """
    # Simple détection via content-disposition
    attachment_count = raw_content.lower().count('content-disposition: attachment')
    has_attachments = attachment_count > 0

    return has_attachments, attachment_count


async def security_check(
    email_from: str,
    subject: str,
    body: str,
    headers: dict[str, str],
    raw_content: str = ""
) -> SecurityResult:
    """
    Effectue analyse sécurité complète d'un email

    Args:
        email_from: Email expéditeur
        subject: Sujet
        body: Corps
        headers: Headers email
        raw_content: Contenu brut (pour PJ)

    Returns:
        SecurityResult avec analyse complète
    """
    # Hash
    email_hash = compute_email_hash(email_from, subject, body)

    # Spam
    is_spam, spam_reason = is_spam_sender(email_from, subject, headers)

    # Auto-responder
    is_auto = is_auto_responder(headers)

    # Remerciement
    is_thanks = is_thank_you_message(body)

    # Langue
    language = detect_language(subject, body)

    # PJ
    has_attach, attach_count = count_attachments(headers, raw_content)

    # Numéro commande
    order_num = extract_order_number(subject + " " + body)

    result = SecurityResult(
        email_hash=email_hash,
        is_spam=is_spam or is_auto,
        is_auto_responder=is_auto,
        is_thank_you=is_thanks,
        language=language,
        has_attachments=has_attach,
        attachment_count=attach_count,
        order_number=order_num,
        spam_reason=spam_reason
    )

    if result.is_spam:
        logger.info(f"Email spam détecté: {spam_reason}", extra={"action": "spam_detected", "email_from": email_from})

    return result
