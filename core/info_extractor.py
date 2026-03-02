"""
OKTAGON SAV v7.0 — Extracteur d'infos client
Détecte et extrait automatiquement les infos que le client donne dans ses mails :
- Changement d'adresse
- Numéro de téléphone
- Prénom / nom
- Numéro de commande mentionné
- Taille souhaitée (retour/échange)
- Nouvelle info pertinente

Met à jour la mémoire client automatiquement.
"""
import re
import logging
from datetime import datetime

logger = logging.getLogger('oktagon')


# ══════════════════════════════════════════════════════════
# PATTERNS D'EXTRACTION
# ══════════════════════════════════════════════════════════

# Adresse postale (rue + code postal + ville)
ADDRESS_PATTERNS = [
    # "ma nouvelle adresse est..."
    r'(?:nouvelle |mon |ma )?adresse\s*(?:est|:)\s*(.{10,120})',
    # "livrer au / livrer à"
    r'(?:livrer? (?:au?|à)|envoy(?:er|ez) (?:au?|à))\s*[:.]?\s*(.{10,120})',
    # "je suis au / j'habite"
    r'(?:j.?habite|je suis au?|je vis au?)\s*[:.]?\s*(.{10,120})',
    # Détection directe code postal FR
    r'(\d{1,4}[,\s]+(?:rue|avenue|boulevard|allée|impasse|chemin|place|bd|av)\s+.{5,80}[,\s]+\d{5}\s+\w+)',
]

# Téléphone
PHONE_PATTERNS = [
    r'(?:tel|téléphone|tél|portable|mobile|num[ée]ro)\s*(?:est|:)?\s*((?:\+?\d[\d\s\-\.]{8,15}))',
    r'(?:joignable|contactable|appelez?[\- ]moi)\s+(?:au\s+)?((?:\+?\d[\d\s\-\.]{8,15}))',
    # Numéro direct format FR
    r'\b(0[67][\s\.\-]?\d{2}[\s\.\-]?\d{2}[\s\.\-]?\d{2}[\s\.\-]?\d{2})\b',
    r'\b(\+33[\s\.\-]?[67][\s\.\-]?\d{2}[\s\.\-]?\d{2}[\s\.\-]?\d{2}[\s\.\-]?\d{2})\b',
]

# Email alternatif
EMAIL_PATTERNS = [
    r'(?:mon |nouvel? )?(?:email|mail|adresse mail)\s*(?:est|:)\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
    r'(?:contact(?:ez|er)?[\- ]moi|écriv(?:ez|re)[\- ]moi)\s+(?:à|sur)\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
]

# Prénom
NAME_PATTERNS = [
    r'(?:je (?:m.?appelle|suis)|mon (?:prénom|nom)\s+(?:est|c.?est))\s+([A-ZÀ-Ü][a-zà-ü]+)',
    r'(?:cordialement|bien à vous|cdlt)\s*,?\s*\n\s*([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)?)\s*$',
]

# Taille (pour retour/échange)
SIZE_PATTERNS = [
    r'(?:taille|size)\s*(?:est|:)?\s*(X?[SML]|XX?L|\d{2,3})',
    r'(?:je (?:fais|porte|chausse)|ma taille)\s+(?:du\s+)?(\d{2,3}|X?[SML]|XX?L)',
    r'(?:échanger?|changer)\s+(?:pour|en|contre)\s+(?:(?:un|une|du|la|le)\s+)?(?:taille\s+)?(\d{2,3}|X?[SML]|XX?L)',
]


def extract_client_info(body: str, subject: str = '') -> dict:
    """
    Extrait toutes les infos client détectables dans le message.

    Retourne un dict avec les infos trouvées :
    {
        'new_address': str ou None,
        'phone': str ou None,
        'alt_email': str ou None,
        'prenom': str ou None,
        'size': str ou None,
        'extracted_infos': list de dicts [{type, value, raw_match}]
    }
    """
    text = body + '\n' + subject
    result = {
        'new_address': None,
        'phone': None,
        'alt_email': None,
        'prenom': None,
        'size': None,
        'extracted_infos': [],
    }

    # Adresse
    for pattern in ADDRESS_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            addr = match.group(1).strip().rstrip('.')
            # Vérifier que ça ressemble à une adresse (a un chiffre et > 15 chars)
            if len(addr) > 15 and re.search(r'\d', addr):
                result['new_address'] = addr
                result['extracted_infos'].append({
                    'type': 'address',
                    'value': addr,
                    'raw_match': match.group(0)
                })
                break

    # Téléphone
    for pattern in PHONE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            phone = re.sub(r'[\s\.\-]', '', match.group(1))
            if len(phone) >= 10:
                result['phone'] = phone
                result['extracted_infos'].append({
                    'type': 'phone',
                    'value': phone,
                    'raw_match': match.group(0)
                })
                break

    # Email alternatif
    for pattern in EMAIL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            email = match.group(1).lower()
            result['alt_email'] = email
            result['extracted_infos'].append({
                'type': 'email',
                'value': email,
                'raw_match': match.group(0)
            })
            break

    # Prénom (signature)
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            prenom = match.group(1).strip()
            if len(prenom) >= 2 and len(prenom) <= 30:
                result['prenom'] = prenom
                result['extracted_infos'].append({
                    'type': 'prenom',
                    'value': prenom,
                    'raw_match': match.group(0)
                })
                break

    # Taille
    for pattern in SIZE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            size = match.group(1).upper()
            result['size'] = size
            result['extracted_infos'].append({
                'type': 'size',
                'value': size,
                'raw_match': match.group(0)
            })
            break

    return result


# ══════════════════════════════════════════════════════════
# MISE À JOUR MÉMOIRE CLIENT
# ══════════════════════════════════════════════════════════

async def update_client_memory(db, tenant_id: str, email_from: str,
                                extracted: dict):
    """
    Met à jour le profil client en DB avec les infos extraites.
    Tout est historisé — on ne supprime rien, on ajoute.
    """
    if not extracted['extracted_infos']:
        return  # Rien à mettre à jour

    updates = []

    # Prénom
    if extracted['prenom']:
        await db.execute(
            """UPDATE client_profiles
               SET prenom = $1, updated_at = NOW()
               WHERE tenant_id = $2 AND email = $3
               AND (prenom IS NULL OR prenom = '')""",
            extracted['prenom'], tenant_id, email_from
        )
        updates.append(f"prenom={extracted['prenom']}")

    # Téléphone → stocker dans notes (on ne crée pas une colonne exprès)
    if extracted['phone']:
        await _append_client_note(
            db, tenant_id, email_from,
            f"Téléphone: {extracted['phone']}"
        )
        updates.append(f"phone={extracted['phone']}")

    # Adresse → stocker dans notes + flag pour attention
    if extracted['new_address']:
        await _append_client_note(
            db, tenant_id, email_from,
            f"Nouvelle adresse: {extracted['new_address']}"
        )
        updates.append(f"address={extracted['new_address'][:50]}")

    # Email alternatif → stocker dans notes
    if extracted['alt_email']:
        await _append_client_note(
            db, tenant_id, email_from,
            f"Email alternatif: {extracted['alt_email']}"
        )
        updates.append(f"alt_email={extracted['alt_email']}")

    # Taille → stocker dans notes
    if extracted['size']:
        await _append_client_note(
            db, tenant_id, email_from,
            f"Taille: {extracted['size']}"
        )
        updates.append(f"size={extracted['size']}")

    if updates:
        logger.info(
            f"📝 Mémoire client mise à jour: {email_from} | {', '.join(updates)}",
            extra={'action': 'client_memory_updated', 'updates': updates}
        )


async def _append_client_note(db, tenant_id: str, email_from: str, note: str):
    """Ajoute une note au profil client (avec horodatage)."""
    timestamp = datetime.utcnow().strftime('%d/%m/%Y %H:%M')
    full_note = f"[{timestamp}] {note}"

    # Vérifier si le profil existe
    existing = await db.fetch_one(
        "SELECT notes FROM client_profiles WHERE tenant_id = $1 AND email = $2",
        tenant_id, email_from
    )

    if existing:
        current_notes = existing['notes'] or ''
        # Éviter les doublons
        if note not in current_notes:
            new_notes = (current_notes + '\n' + full_note).strip()
            await db.execute(
                """UPDATE client_profiles
                   SET notes = $1, updated_at = NOW()
                   WHERE tenant_id = $2 AND email = $3""",
                new_notes[-2000:],  # Limiter à 2000 chars
                tenant_id, email_from
            )
    else:
        # Créer le profil avec la note
        await db.execute(
            """INSERT INTO client_profiles (tenant_id, email, notes, created_at, updated_at)
               VALUES ($1, $2, $3, NOW(), NOW())
               ON CONFLICT (tenant_id, email) DO UPDATE SET
                 notes = COALESCE(client_profiles.notes, '') || E'\n' || $3,
                 updated_at = NOW()""",
            tenant_id, email_from, full_note
        )
