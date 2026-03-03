"""
OKTAGON SAV v11.0 — Templates email HTML
Dynamiques par tenant (brand_name, brand_color, brand_tagline).
"""
import re
import html as html_lib


def email_template(content_html: str, tenant, language: str = "fr") -> str:
    """Template email premium dynamique par tenant."""
    brand = html_lib.escape(tenant.brand_name) if tenant.brand_name else "SAV"
    color = tenant.brand_color or "#F0FF27"
    tagline = html_lib.escape(tenant.brand_tagline) if tenant.brand_tagline else ""

    thread_notice = {
        "fr": "Restez dans cette conversation en répondant directement à cet email.",
        "en": "Stay in this conversation by replying directly to this email.",
        "es": "Continúe esta conversación respondiendo directamente a este email."
    }
    notice = thread_notice.get(language, thread_notice["fr"])

    footer_text = f"&copy; {brand}"
    if tagline:
        footer_text += f" &mdash; {html_lib.escape(tagline)}"

    return f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f5f5f5; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5; padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
<tr><td style="background-color:#121212; padding:24px 32px; text-align:center;">
<span style="font-size:28px; font-weight:700; color:{color}; letter-spacing:3px;">{brand}</span>
</td></tr>
<tr><td style="padding:32px 32px 24px 32px; color:#1a1a1a; font-size:15px; line-height:1.7;">
{content_html}
</td></tr>
<tr><td style="padding:0 32px 24px 32px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="background-color:#f8f8f0; border-left:3px solid {color}; padding:12px 16px; font-size:12px; color:#666; line-height:1.5; border-radius:0 4px 4px 0;">
{notice}
</td></tr></table>
</td></tr>
<tr><td style="background-color:#121212; padding:16px 32px; text-align:center;">
<span style="color:#888; font-size:11px;">{footer_text}</span>
</td></tr>
</table></td></tr></table>
</body></html>'''


def markdown_to_html(text: str) -> str:
    """Convertit le markdown basique en HTML propre pour email."""
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" style="color:#121212; text-decoration:underline;">\1</a>', text)
    text = re.sub(r'(?<!["\'])(https?://[^\s<]+)', r'<a href="\1" style="color:#121212; text-decoration:underline;">\1</a>', text)
    lines = text.split('\n')
    html_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith('- '):
            html_lines.append(f'<div style="padding:4px 0 4px 16px;">&bull; {line[2:]}</div>')
        elif line == '':
            html_lines.append('<div style="height:12px;"></div>')
        else:
            html_lines.append(f'<div style="padding:2px 0;">{line}</div>')
    return '\n'.join(html_lines)


def build_followup_html(message: str, tenant, language: str = "fr") -> str:
    """Convertit un message followup en HTML premium."""
    return email_template(markdown_to_html(message), tenant, language)


def build_ai_response_html(ai_text: str, tenant, language: str = "fr") -> str:
    """Convertit la réponse IA en email HTML premium."""
    return email_template(markdown_to_html(ai_text), tenant, language)


def build_escalation_html(escalation_id: int, tenant, language: str = "fr") -> str:
    """Email confirmation d'escalade."""
    brand = html_lib.escape(tenant.brand_name) if tenant.brand_name else "SAV"
    contents = {
        "fr": f'''<div style="padding-bottom:12px;">Bonjour,</div>
<div style="padding-bottom:16px;">Votre demande a bien &eacute;t&eacute; enregistr&eacute;e.</div>
<table width="100%"><tr><td style="padding:14px 16px; background:#fafafa; border-left:3px solid {tenant.brand_color}; border-radius:0 4px 4px 0;">
<strong>R&eacute;f&eacute;rence :</strong> #{escalation_id}</td></tr></table>
<div style="padding:16px 0 8px;">Un membre de notre &eacute;quipe vous r&eacute;pondra dans les plus brefs d&eacute;lais.</div>
<div style="padding-bottom:16px; color:#888; font-size:13px;">D&eacute;lai habituel : sous 24h.</div>
<div>Cordialement,<br><strong>L'&eacute;quipe {brand}</strong></div>''',
        "en": f'''<div style="padding-bottom:12px;">Hello,</div>
<div style="padding-bottom:16px;">Your request has been registered.</div>
<table width="100%"><tr><td style="padding:14px 16px; background:#fafafa; border-left:3px solid {tenant.brand_color}; border-radius:0 4px 4px 0;">
<strong>Reference:</strong> #{escalation_id}</td></tr></table>
<div style="padding:16px 0 8px;">A team member will get back to you shortly.</div>
<div>Best regards,<br><strong>The {brand} Team</strong></div>'''
    }
    content = contents.get(language, contents["fr"])
    return email_template(content, tenant, language)


# ═══════════════════════════════════════════════════════════
# TEMPLATES FALLBACK INTELLIGENTS — v4.2
# Quand l'IA doute, on envoie une réponse utile avec les données Shopify
# au lieu d'escalader bêtement
# ═══════════════════════════════════════════════════════════

def build_smart_fallback(ticket, tenant, order_details=None, category='LIVRAISON'):
    """Construit une réponse intelligente basée sur les données Shopify disponibles.

    Utilisé quand l'IA a un doute mais qu'on a assez d'infos pour répondre.
    """
    lang = getattr(ticket, 'language', 'fr') or 'fr'
    brand = tenant.brand_name or 'OKTAGON'
    customer = getattr(ticket, 'customer_name', '') or ''
    greeting = f"Bonjour {customer}" if customer else "Bonjour"

    if category == 'LIVRAISON':
        return _fallback_shipping(greeting, brand, tenant, order_details, lang)
    elif category == 'RETOUR_ECHANGE':
        return _fallback_return(greeting, brand, tenant, order_details, lang)
    elif category == 'QUESTION_PRODUIT':
        return _fallback_product(greeting, brand, tenant, lang)
    elif category == 'MODIFIER_ADRESSE':
        return _fallback_address(greeting, brand, tenant, order_details, lang)
    elif category == 'ANNULATION':
        return _fallback_cancellation(greeting, brand, tenant, order_details, lang)
    else:
        return _fallback_generic(greeting, brand, tenant, lang)


def _fallback_shipping(greeting, brand, tenant, od, lang):
    """Fallback livraison — donne tout ce qu'on sait sur la commande."""
    lines = [f"{greeting},\n"]
    lines.append(f"Merci de nous avoir contactés concernant votre commande.\n")

    if od:
        order_num = od.get('order_number', '')
        if order_num:
            lines.append(f"Votre commande **#{order_num}** :\n")

        # Statut
        fulfillment = od.get('fulfillment_status')
        financial = od.get('financial_status', '')

        if fulfillment == 'fulfilled':
            lines.append("**Statut :** Votre commande a été expédiée !\n")

            # Tracking
            tracking_numbers = od.get('tracking_numbers', [])
            tracking_urls = od.get('tracking_urls', [])
            if tracking_numbers:
                for idx, t in enumerate(tracking_numbers):
                    lines.append(f"**Numéro de suivi :** {t}")
                    if idx < len(tracking_urls) and tracking_urls[idx]:
                        lines.append(f"**Suivre votre colis :** [Cliquez ici]({tracking_urls[idx]})\n")
            else:
                lines.append("Le numéro de suivi sera disponible sous peu.\n")
        elif fulfillment == 'partial':
            lines.append("**Statut :** Votre commande est partiellement expédiée. Le reste suivra sous peu.\n")
        else:
            lines.append("**Statut :** Votre commande est en cours de préparation.\n")
            lines.append("Nos articles étant **personnalisés sur mesure**, le délai de fabrication est de **12 à 15 jours ouvrés**.\n")

        # Adresse
        address = od.get('shipping_address', '')
        if address and address != 'N/A':
            lines.append(f"**Adresse de livraison :** {address}\n")
    else:
        # Pas de données Shopify
        lines.append("Nos articles étant **personnalisés sur mesure**, le délai de fabrication est de **12 à 15 jours ouvrés** avant expédition.\n")
        lines.append("Si vous avez un numéro de commande (format #XXXX), n'hésitez pas à nous le communiquer pour un suivi plus précis.\n")

    # Message réassurance
    lines.append("\n🔥 **OKTAGON** connaît une très forte demande actuellement ! Nos équipes travaillent d'arrache-pied pour préparer et expédier toutes les commandes. Merci pour votre patience et votre confiance !\n")

    lines.append(f"N'hésitez pas si vous avez d'autres questions.\n")
    lines.append(f"Cordialement,\n**L'équipe {brand}**")

    return "\n".join(lines)


def _fallback_return(greeting, brand, tenant, od, lang):
    """Fallback retour/échange."""
    return_addr = ''
    if tenant.return_address:
        return_addr = tenant.return_address
    elif hasattr(tenant, 'custom_rules') and tenant.custom_rules:
        return_addr = tenant.custom_rules.get('return_address', '')

    lines = [f"{greeting},\n"]
    lines.append("Merci de nous avoir contactés concernant un retour ou échange.\n")

    if od and od.get('order_number'):
        lines.append(f"Concernant votre commande **#{od['order_number']}** :\n")

    lines.append("Pour effectuer un retour, voici la procédure :\n")
    lines.append("1. Assurez-vous que l'article est dans son état d'origine")
    lines.append("2. Emballez-le soigneusement")
    if return_addr:
        lines.append(f"3. Envoyez-le à : **{return_addr}**")
    else:
        lines.append("3. Répondez à cet email avec votre numéro de commande et nous vous communiquerons l'adresse de retour")
    lines.append("4. Une fois envoyé, communiquez-nous le numéro de suivi retour\n")
    lines.append("**Note :** Les articles personnalisés (avec flocage/prénom) ne sont pas remboursables.\n")
    lines.append(f"Cordialement,\n**L'équipe {brand}**")

    return "\n".join(lines)


def _fallback_product(greeting, brand, tenant, lang):
    """Fallback question produit."""
    website = tenant.website or 'oktagon-shop.com'
    instagram = tenant.instagram or ''

    lines = [f"{greeting},\n"]
    lines.append("Merci pour votre intérêt pour nos produits !\n")
    lines.append(f"Vous pouvez retrouver l'ensemble de notre catalogue sur **{website}**.\n")
    lines.append("**Informations utiles :**")
    lines.append("- Tous nos articles sont **personnalisables sur mesure**")
    lines.append("- Délai de fabrication : **12 à 15 jours ouvrés**")
    lines.append("- Livraison offerte en France métropolitaine\n")
    if instagram:
        lines.append(f"Suivez-nous sur Instagram : **{instagram}** pour les dernières nouveautés !\n")
    lines.append("N'hésitez pas à nous poser des questions plus précises sur un produit.\n")
    lines.append(f"Cordialement,\n**L'équipe {brand}**")

    return "\n".join(lines)


def _fallback_address(greeting, brand, tenant, od, lang):
    """Fallback modifier adresse."""
    lines = [f"{greeting},\n"]
    lines.append("Concernant votre demande de modification d'adresse :\n")
    if od and od.get('order_number'):
        lines.append(f"Commande **#{od['order_number']}**\n")
    lines.append("Pour modifier votre adresse de livraison, merci de nous communiquer :\n")
    lines.append("1. Votre **numéro de commande** (si pas encore fourni)")
    lines.append("2. Votre **nouvelle adresse complète** (rue, code postal, ville, pays)\n")
    lines.append("**Important :** La modification n'est possible que si votre commande n'a pas encore été expédiée.\n")
    lines.append(f"Cordialement,\n**L'équipe {brand}**")

    return "\n".join(lines)


def _fallback_cancellation(greeting, brand, tenant, od, lang):
    """Fallback annulation."""
    lines = [f"{greeting},\n"]
    lines.append("Nous avons bien reçu votre demande d'annulation.\n")
    if od and od.get('order_number'):
        lines.append(f"Commande **#{od['order_number']}**\n")
    lines.append("Pour traiter votre demande, merci de nous confirmer :\n")
    lines.append("1. Votre **numéro de commande** (format #XXXX)")
    lines.append("2. La **raison de l'annulation**\n")
    lines.append("**Rappel :** Les articles personnalisés (avec flocage) ne sont pas annulables une fois en production.\n")
    lines.append(f"Cordialement,\n**L'équipe {brand}**")

    return "\n".join(lines)


def _fallback_generic(greeting, brand, tenant, lang):
    """Fallback générique — quand on ne sait pas la catégorie."""
    website = tenant.website or 'oktagon-shop.com'

    lines = [f"{greeting},\n"]
    lines.append("Merci de nous avoir contactés !\n")
    lines.append("Pour mieux traiter votre demande, pourriez-vous nous préciser :\n")
    lines.append("- S'il s'agit d'une **commande en cours** → votre numéro de commande (format #XXXX)")
    lines.append("- S'il s'agit d'une **question produit** → le nom ou lien du produit")
    lines.append("- S'il s'agit d'un **retour/échange** → votre numéro de commande\n")
    lines.append(f"Vous pouvez aussi consulter notre site : **{website}**\n")
    lines.append(f"Cordialement,\n**L'équipe {brand}**")

    return "\n".join(lines)


def build_ask_order_number(tenant, category='LIVRAISON', lang='fr'):
    """Template pour demander le numéro de commande au client.

    Au lieu d'escalader quand on n'a pas le numéro, on le demande poliment.
    """
    brand = tenant.brand_name or 'OKTAGON'

    category_text = {
        'LIVRAISON': 'le suivi de votre livraison',
        'RETOUR_ECHANGE': 'votre demande de retour/échange',
        'MODIFIER_ADRESSE': 'la modification de votre adresse',
        'ANNULATION': 'votre demande d\'annulation',
    }

    context = category_text.get(category, 'votre demande')

    return (
        f"Bonjour,\n\n"
        f"Merci de nous avoir contactés concernant {context}.\n\n"
        f"Pour traiter votre demande rapidement, pourriez-vous nous communiquer "
        f"votre **numéro de commande** ? Vous le trouverez dans votre email de "
        f"confirmation (format : #XXXX).\n\n"
        f"Cordialement,\n**L'équipe {brand}**"
    )
