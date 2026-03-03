"""
OKTAGON SAV v11.0 — Règles métier MODULAIRES
Supporte multiple product_logic types via tenant.custom_rules
BACKWARD COMPATIBLE avec v10.0 - Code OKTAGON préservé à 100%
"""
import re
import unicodedata
from typing import Optional, List

from core.constants import (
    LIVRAISON_KEYWORDS, RETOUR_KEYWORDS, ANNULATION_KEYWORDS, SHORT_PRICE
)


# ============================================================
# ANALYSE ARTICLES - VERSION MODULAIRE v10.5
# ============================================================

def analyze_order_items(line_items: list, tenant=None) -> list:
    """
    Analyse chaque article : type, flocage, remboursable, prix.
    
    v10.5 : MODULAIRE - Supporte différentes logiques via tenant.custom_rules
    v10.0 : BACKWARD COMPATIBLE - Si tenant=None, utilise logique OKTAGON par défaut
    
    Args:
        line_items: Liste d'articles Shopify
        tenant: TenantConfig (optionnel, défaut=logique OKTAGON)
    
    Returns:
        Liste d'articles analysés avec métadonnées
    """
    # Si pas de tenant fourni, utiliser logique OKTAGON par défaut (backward compat)
    if tenant is None:
        return _analyze_order_items_oktagon_legacy(line_items)
    
    # Déterminer la logique produit depuis custom_rules
    product_logic = tenant.custom_rules.get('product_logic', 'oktagon_sport_combat')
    
    # Router vers la bonne implémentation
    if product_logic == 'oktagon_sport_combat':
        return _analyze_order_items_oktagon(line_items, tenant)
    elif product_logic == 'standard':
        return _analyze_order_items_standard(line_items, tenant)
    else:
        # Fallback sécurité : OKTAGON
        return _analyze_order_items_oktagon(line_items, tenant)


def _analyze_order_items_oktagon_legacy(line_items: list) -> list:
    """
    VERSION ORIGINALE v10.0 PRÉSERVÉE (sans tenant).
    
    Utilisée pour backward compatibility si analyze_order_items appelé sans tenant.
    CODE EXACT DE LA v10.0 - AUCUNE MODIFICATION
    """
    results = []
    for item in line_items:
        title = item.get("title", "")
        if "e-book" in title.lower() or "carte-cadeau" in title.lower() or "carte cadeau" in title.lower():
            continue
        flocked = is_flocked(item)
        flocage_details = ""
        for prop in item.get("properties", []):
            name = str(prop.get("name", ""))
            value = str(prop.get("value", "")).strip()
            if name in ("Nom Flocage", "Numéro") and value:
                flocage_details += f"{name}: {value}  "
        flocage_details = flocage_details.strip()
        quantity = item.get("quantity", 1)
        variant = item.get("variant_title", "")
        total_price = float(item.get("price", 0))

        if "ensemble" in title.lower():
            haut_price = round(total_price - SHORT_PRICE, 2)
            if haut_price < 0:
                haut_price = 0
            results.append({
                "title": f"{title} (Short)",
                "variant": variant, "price": SHORT_PRICE,
                "quantity": quantity, "is_short": True,
                "is_flocked": flocked, "is_refundable": True,
                "flocage_details": flocage_details, "type": "Short"
            })
            results.append({
                "title": f"{title} (Haut)",
                "variant": variant, "price": haut_price,
                "quantity": quantity, "is_short": False,
                "is_flocked": flocked, "is_refundable": not flocked,
                "flocage_details": flocage_details, "type": "Haut"
            })
        else:
            s = is_short(item)
            results.append({
                "title": title, "variant": variant,
                "price": total_price, "quantity": quantity,
                "is_short": s, "is_flocked": flocked,
                "is_refundable": is_refundable(item),
                "flocage_details": flocage_details,
                "type": "Short" if s else "Haut"
            })
    return results


def _analyze_order_items_oktagon(line_items: List[dict], tenant) -> List[dict]:
    """
    Logique OKTAGON Sport Combat avec tenant (v10.5).
    
    Identique à legacy mais utilise tenant.custom_rules pour paramètres.
    """
    results = []
    
    # Récupérer paramètres depuis tenant
    short_price = float(tenant.custom_rules.get('short_price', SHORT_PRICE))
    flocage_props = tenant.custom_rules.get('flocage_property_names', ['Nom Flocage', 'Numéro'])
    
    for item in line_items:
        title = item.get("title", "")
        if "e-book" in title.lower() or "carte-cadeau" in title.lower() or "carte cadeau" in title.lower():
            continue
        
        # Analyser flocage avec propriétés configurables
        flocked = _is_flocked_oktagon(item, flocage_props)
        flocage_details = ""
        for prop in item.get("properties", []):
            name = str(prop.get("name", ""))
            value = str(prop.get("value", "")).strip()
            if name in flocage_props and value:
                flocage_details += f"{name}: {value}  "
        flocage_details = flocage_details.strip()
        
        quantity = item.get("quantity", 1)
        variant = item.get("variant_title", "")
        total_price = float(item.get("price", 0))

        if "ensemble" in title.lower():
            haut_price = round(total_price - short_price, 2)
            if haut_price < 0:
                haut_price = 0
            results.append({
                "title": f"{title} (Short)",
                "variant": variant, "price": short_price,
                "quantity": quantity, "is_short": True,
                "is_flocked": flocked, "is_refundable": True,
                "flocage_details": flocage_details, "type": "Short"
            })
            results.append({
                "title": f"{title} (Haut)",
                "variant": variant, "price": haut_price,
                "quantity": quantity, "is_short": False,
                "is_flocked": flocked, "is_refundable": not flocked,
                "flocage_details": flocage_details, "type": "Haut"
            })
        else:
            s = "short" in title.lower()
            results.append({
                "title": title, "variant": variant,
                "price": total_price, "quantity": quantity,
                "is_short": s, "is_flocked": flocked,
                "is_refundable": s or not flocked,
                "flocage_details": flocage_details,
                "type": "Short" if s else "Haut"
            })
    return results


def _analyze_order_items_standard(line_items: List[dict], tenant) -> List[dict]:
    """
    Logique STANDARD e-commerce (nouveau v10.5).
    
    Pour produits sans personnalisation complexe (cosmétiques, bijoux, etc.)
    - Pas de split d'ensembles
    - Pas de logique flocage
    - Remboursable par défaut (configurable)
    """
    results = []
    default_refundable = tenant.custom_rules.get('default_refundable', True)
    skip_keywords = tenant.custom_rules.get('skip_product_keywords', ['e-book', 'carte-cadeau', 'carte cadeau'])
    
    for item in line_items:
        title = item.get("title", "")
        
        # Skip produits configurés
        if any(keyword in title.lower() for keyword in skip_keywords):
            continue
        
        results.append({
            "title": title,
            "variant": item.get("variant_title", ""),
            "price": float(item.get("price", 0)),
            "quantity": item.get("quantity", 1),
            "is_short": False,
            "is_flocked": False,
            "is_refundable": default_refundable,
            "flocage_details": "",
            "type": "Standard"
        })
    
    return results


def _is_flocked_oktagon(item: dict, flocage_property_names: List[str]) -> bool:
    """Détecte flocage OKTAGON avec propriétés configurables."""
    for prop in item.get("properties", []):
        name = str(prop.get("name", ""))
        value = str(prop.get("value", "")).strip()
        if name in flocage_property_names and value:
            return True
    return False


# ============================================================
# FONCTIONS UTILITAIRES (préservées pour backward compat)
# ============================================================

def is_flocked(item: dict) -> bool:
    """
    DEPRECATED v10.5 : Utiliser analyze_order_items() avec tenant.
    Conservé pour backward compatibility.
    """
    for prop in item.get("properties", []):
        name = str(prop.get("name", ""))
        value = str(prop.get("value", "")).strip()
        if name == "Nom Flocage" and value:
            return True
        if name == "Numéro" and value:
            return True
    return False


def is_short(item: dict) -> bool:
    """
    DEPRECATED v10.5 : Utiliser analyze_order_items() avec tenant.
    Conservé pour backward compatibility.
    """
    return "short" in item.get("title", "").lower()


def is_refundable(item: dict) -> bool:
    """
    DEPRECATED v10.5 : Utiliser analyze_order_items() avec tenant.
    Conservé pour backward compatibility.
    """
    if is_short(item):
        return True
    return not is_flocked(item)


# ============================================================
# SMART DETECT (détection intention + numéro commande)
# CODE INCHANGÉ v10.0
# ============================================================

def smart_detect_first_message(subject: str, body: str):
    """Detecte intention + numero commande dans le 1er message.
    v7.1 : nettoie les parties quotees et threads AVANT extraction."""
    # 1. Supprimer les lignes quotees (> ...)
    body_clean = re.sub(r'^>.*$', '', body, flags=re.MULTILINE).strip()
    # 2. Couper au "Le xxx a ecrit :" (debut du thread quote)
    cut = re.search(r'Le \w{3}[\.,].*a [\xe9e]crit\s*:', body_clean)
    if cut:
        body_clean = body_clean[:cut.start()].strip()
    # 3. Couper au "On xxx wrote:" (thread anglais)
    cut2 = re.search(r'On .+ wrote:', body_clean)
    if cut2:
        body_clean = body_clean[:cut2.start()].strip()
    # 4. Couper au "------" ou "______" (separateurs)
    cut3 = re.search(r'[-_]{5,}', body_clean)
    if cut3:
        body_clean = body_clean[:cut3.start()].strip()

    text = f"{subject} {body_clean}".lower()
    text_norm = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

    # Extraire numero de commande — UNIQUEMENT dans le message du client
    order_num = None

    # 1. #XXXX dans le body nettoye (client a mis le #)
    m = re.search(r'#(\d{4,6})', body_clean)
    if m and not (2020 <= int(m.group(1)) <= 2030):
        order_num = m.group(1)

    # 1b. #XXXX dans le sujet (ex: "Commande #8418")
    if not order_num:
        m = re.search(r'#(\d{4,6})', subject)
        if m and not (2020 <= int(m.group(1)) <= 2030):
            order_num = m.group(1)

    # 2. "commande 8288", "n 8418", "commandes 8422", "numero 8355"
    if not order_num:
        combined_clean = f"{subject} {body_clean}"
        m = re.search(
            r'(?:commande[s]?|n[\xb0\xba\xb0o]|numero|num[\xe9e]ro|order|pedido)\s*:?\s*#?(\d{4,6})',
            combined_clean, re.IGNORECASE
        )
        if m and not (2020 <= int(m.group(1)) <= 2030):
            order_num = m.group(1)

    # 3. "est le 8460", "c'est 8460"
    if not order_num:
        combined_clean = f"{subject} {body_clean}"
        m = re.search(
            r"(?:est\s+le|c'?est|voici|voil[\xe0a])\s*#?(\d{4,6})",
            combined_clean, re.IGNORECASE
        )
        if m and not (2020 <= int(m.group(1)) <= 2030):
            order_num = m.group(1)

    # 4. Numero 4-5 chiffres dans le sujet — MAIS PAS dans un tracking
    # Un tracking = lettres+chiffres+lettres (ex: WNBAA0431333221YQ)
    if not order_num:
        subj_clean = re.sub(r'[A-Z]{2,}\d{6,}[A-Z]{0,2}', '', subject)
        subj_clean = re.sub(r'^(Re|Fwd|Fw|Aw|R)\s*:\s*', '', subj_clean, flags=re.IGNORECASE).strip()
        m = re.search(r'\b(\d{4,5})\b', subj_clean)
        if m and not (2020 <= int(m.group(1)) <= 2030):
            order_num = m.group(1)

    # 5. Numero 4-5 chiffres isole dans le body clean
    if not order_num:
        m = re.search(r'\b(\d{4,5})\b', body_clean)
        if m and not (2020 <= int(m.group(1)) <= 2030):
            order_num = m.group(1)

    # Detecter l'intention
    intent = None
    if any(kw in text_norm for kw in LIVRAISON_KEYWORDS):
        intent = 'LIVRAISON'
    elif any(kw in text_norm for kw in RETOUR_KEYWORDS):
        intent = 'RETOUR_ECHANGE'
    elif any(kw in text_norm for kw in ANNULATION_KEYWORDS):
        intent = 'ANNULATION'

    if order_num and intent:
        return intent, order_num
    if order_num:
        return 'LIVRAISON', order_num
    # Intention sans numero -> le pipeline gere (lookup email, etc.)
    if intent:
        return intent, None

    return None, None


# ============================================================
# DÉTECTION HUMAIN
# ============================================================

def detect_human_request(body: str) -> bool:
    """Détecte si le client demande explicitement un humain."""
    from core.constants import HUMAN_REQUEST_KEYWORDS
    body_lower = body.lower()
    return any(kw in body_lower for kw in HUMAN_REQUEST_KEYWORDS)


# ============================================================
# EXTRACTION PRÉNOM SIGNÉ
# ============================================================

def extract_signed_name(body: str) -> str:
    """Extrait le prénom signé dans l'email du client."""
    lines = body.strip().split('\n')
    for line in reversed(lines[-8:]):
        stripped = line.strip()
        if not stripped or stripped.startswith('>') or stripped.startswith('--') or stripped.startswith('___'):
            continue
        if '@' in stripped or 'http' in stripped:
            continue
        if re.match(r'^[A-ZÀ-Ÿa-zà-ÿ]{2,}(?:\s+[A-ZÀ-Ÿa-zà-ÿ]{2,}){0,2}$', stripped):
            return stripped.split()[0].capitalize()
        m = re.match(r'(?:cordialement|cdlt|bien [àa] vous|regards|merci|bonne journ[ée]e),?\s*([A-ZÀ-Ÿa-zà-ÿ]{2,})', stripped, re.IGNORECASE)
        if m:
            return m.group(1).capitalize()
        m = re.match(r'envoy[ée] par\s+([A-ZÀ-Ÿa-zà-ÿ]{2,})', stripped, re.IGNORECASE)
        if m:
            return m.group(1).capitalize()
    return ""


# ============================================================
# CLEAN REPLY BODY
# ============================================================

def clean_reply_body(body: str) -> str:
    """Nettoie le corps d'un email en supprimant le texte cité."""
    if not body:
        return ""
    lines = body.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if re.match(r"^Le \d{4}-", stripped):
            break
        if re.match(r"^Le [a-z]{3}\.", stripped):
            break
        if re.match(r"^On .+ wrote:", stripped):
            break
        if stripped.startswith("From:") and "@" in stripped:
            break
        if stripped.startswith("----------") or stripped.startswith("_____"):
            break
        if stripped.startswith("Envoy"):
            break
        if ("a \u00e9crit" in stripped or "wrote" in stripped) and "@" in stripped:
            break
        clean_lines.append(line)
    while clean_lines and clean_lines[-1].strip() == "":
        clean_lines.pop()
    return "\n".join(clean_lines).strip().replace("\r", "")


# ============================================================
# PARSE SHOPIFY CONTACT FORM
# ============================================================

def parse_shopify_contact_form(body: str):
    """Parse un formulaire contact Shopify.
    Retourne (email, commentaire) ou (None, None)."""
    email_match = re.search(r'E-mail:\s*\n?\s*([^\s@]+@[^\s@]+\.[^\s@]+)', body)
    if not email_match:
        return None, None
    real_email = email_match.group(1).strip().lower()
    comment_match = re.search(r'Commentaire:\s*\n?(.*)', body, re.DOTALL)
    commentaire = ""
    if comment_match:
        commentaire = comment_match.group(1).strip()[:500]
    return real_email, commentaire



# ============================================================
# DÉTECTION URGENCE (NOUVEAU v4.2)
# ============================================================

URGENCY_PATTERNS = [
    (r'\d+\s*mois', 'CRITICAL'),
    (r'3[eè]me?\s*fois', 'CRITICAL'),
    (r'plusieurs\s*fois', 'HIGH'),
    (r'inadmissible', 'HIGH'),
    (r'scandaleux', 'HIGH'),
    (r'arnaque', 'CRITICAL'),
    (r'plainte', 'CRITICAL'),
    (r'avocat', 'CRITICAL'),
    (r'signal\w*\s*conso', 'CRITICAL'),
    (r'jamais\s*re[çc]u', 'HIGH'),
    (r'toujours\s*pas', 'MEDIUM'),
    (r'aucune\s*nouvelle', 'HIGH'),
    (r'procedure', 'HIGH'),
    (r'porter\s*plainte', 'CRITICAL'),
]


def detect_urgency(subject: str, body: str, client_profile: dict = None) -> Optional[str]:
    """Détecte le niveau d'urgence. Retourne 'CRITICAL', 'HIGH', 'MEDIUM' ou None."""
    text = f"{subject} {body}".lower()
    text_norm = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    levels = {'CRITICAL': 3, 'HIGH': 2, 'MEDIUM': 1}
    max_level = None

    for pattern, level in URGENCY_PATTERNS:
        if re.search(pattern, text_norm, re.IGNORECASE):
            if not max_level or levels[level] > levels.get(max_level, 0):
                max_level = level

    # Urgence comportementale
    if client_profile:
        if client_profile.get('emails_last_24h', 0) >= 3:
            if not max_level or levels.get(max_level, 0) < 2:
                max_level = 'HIGH'
        if client_profile.get('escalations', 0) >= 2:
            if not max_level or levels.get(max_level, 0) < 2:
                max_level = 'HIGH'

    return max_level
