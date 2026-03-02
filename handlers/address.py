"""
OKTAGON SAV v4.0 — Handler Modifier Adresse (CAS 1-B)
Vérifie Shopify, propose modification, attend confirmation.
"""
import json
import html as html_lib
from core.models import Ticket, Response
from domain.rules import clean_reply_body
from knowledge.templates import email_template, markdown_to_html
from logger import logger


async def handle_address(ticket: Ticket, pipeline) -> Response:
    """CAS 1-B : Modifier adresse de livraison."""
    tenant = pipeline.tenant
    order_number = ticket.order_number or ticket.collected_data.get('order_number', '')
    lang = ticket.language

    if not order_number:
        from knowledge.templates import build_ask_order_number
        ask_text = build_ask_order_number(tenant, 'MODIFIER_ADRESSE', ticket.language)
        logger.info("📋 MODIFIER_ADRESSE | Pas de numéro → demande au client",
                     extra={"action": "ask_order_number"})
        return Response(text=ask_text, should_send=True, confidence=1.0,
                        category='MODIFIER_ADRESSE', next_step='ready_for_ai')

    order = await pipeline.ecommerce.get_order(order_number)
    if not order:
        msg = f"Bonjour,\n\nNous n'avons pas trouvé la commande **#{order_number}**.\n\nVérifiez le numéro dans votre email de confirmation.\n\nCordialement,\n**L'équipe {tenant.brand_name}**"
        return Response(text=msg, should_send=True, category='MODIFIER_ADRESSE', confidence=1.0, next_step='ready_for_ai')

    fulfillment = order.get('fulfillment_status')
    address = order.get('shipping_address', 'Non disponible')

    if fulfillment == 'fulfilled':
        # Déjà expédiée
        tracking = order.get('tracking_numbers', [])
        tracking_info = f"\n\nNuméro de suivi : **{tracking[0]}**" if tracking else ""
        msg = (f"Bonjour,\n\nVotre commande **#{order_number}** a déjà été expédiée à l'adresse :\n**{address}**\n\n"
               f"Il n'est malheureusement plus possible de modifier l'adresse de livraison.{tracking_info}\n\n"
               f"Cordialement,\n**L'équipe {tenant.brand_name}**")
        return Response(text=msg, should_send=True, category='MODIFIER_ADRESSE', confidence=1.0, next_step='ready_for_ai')

    # Pas encore expédiée → demander nouvelle adresse
    msg = (f"Bonjour,\n\nVotre commande **#{order_number}** n'a pas encore été expédiée.\n\n"
           f"Adresse actuelle :\n**{address}**\n\n"
           f"Merci d'indiquer votre **nouvelle adresse complète** en réponse.\n\n"
           f"Cordialement,\n**L'équipe {tenant.brand_name}**")

    return Response(
        text=msg, should_send=True, category='MODIFIER_ADRESSE',
        confidence=1.0, next_step='step4_confirm_address',
        update_data={"order_number": order_number, "old_address": address}
    )


async def handle_address_confirmation(ticket: Ticket, pipeline) -> Response:
    """Suite CAS 1-B : Client envoie sa nouvelle adresse."""
    tenant = pipeline.tenant
    new_address = clean_reply_body(ticket.body).strip()
    old_data = ticket.collected_data
    order_number = old_data.get('order_number', '')
    old_address = old_data.get('old_address', '')

    if len(new_address) < 10:
        msg = f"Merci d'indiquer votre adresse complète (rue, code postal, ville, pays).\n\nCordialement,\n**L'équipe {tenant.brand_name}**"
        return Response(text=msg, should_send=True, category='MODIFIER_ADRESSE', confidence=1.0, next_step='step4_confirm_address')

    # Créer escalade pour l'usine
    esc_id = await pipeline.repos.create_escalation(
        tenant.id, ticket.db_id or 0, ticket.email_from,
        'MODIFIER_ADRESSE', f"Nouvelle adresse: {new_address}"
    )
    await pipeline.repos.create_address_change(
        tenant.id, ticket.db_id or 0, esc_id, ticket.email_from,
        order_number, old_address, new_address
    )

    msg = (f"Bonjour,\n\nVotre demande de modification d'adresse pour la commande **#{order_number}** a été enregistrée.\n\n"
           f"**Nouvelle adresse :** {new_address}\n\n"
           f"Notre équipe va traiter votre demande dans les plus brefs délais.\n\n"
           f"Cordialement,\n**L'équipe {tenant.brand_name}**")

    if pipeline.notifier:
        await pipeline.notifier(
            f"📦 <b>Modifier adresse #{order_number}</b>\n"
            f"Client: {ticket.email_from}\n"
            f"Ancienne: {old_address[:80]}\n"
            f"Nouvelle: {new_address[:80]}\n"
            f"Escalade #{esc_id}"
        )

    return Response(text=msg, should_send=True, category='MODIFIER_ADRESSE', confidence=1.0, next_step='escalated_to_human')
