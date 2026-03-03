"""
OKTAGON SAV v11.0 — Handler Annulation (CAS 1-C)
Analyse articles, vérifie remboursabilité, gère retour.
"""
import json
import html as html_lib
from core.models import Ticket, Response
from domain.rules import analyze_order_items, clean_reply_body
from knowledge.templates import email_template
from logger import logger


async def handle_cancellation(ticket: Ticket, pipeline) -> Response:
    """CAS 1-C : Annuler commande."""
    tenant = pipeline.tenant
    order_number = ticket.order_number or ticket.collected_data.get('order_number', '')
    lang = ticket.language

    if not order_number:
        from knowledge.templates import build_ask_order_number
        ask_text = build_ask_order_number(tenant, 'ANNULATION', ticket.language)
        logger.info("📋 ANNULATION | Pas de numéro → demande au client",
                     extra={"action": "ask_order_number"})
        return Response(text=ask_text, should_send=True, confidence=1.0,
                        category='ANNULATION', next_step='ready_for_ai')

    order = await pipeline.ecommerce.get_order(order_number)
    if not order:
        msg = f"Bonjour,\n\nNous n'avons pas trouvé la commande **#{order_number}**.\n\nVérifiez le numéro dans votre email de confirmation.\n\nCordialement,\n**L'équipe {tenant.brand_name}**"
        return Response(text=msg, should_send=True, category='ANNULATION', confidence=1.0, next_step='ready_for_ai')

    line_items = order.get('line_items', [])
    items_analysis = analyze_order_items(line_items, tenant)
    fulfillment = order.get('fulfillment_status')

    if fulfillment == 'fulfilled':
        return await _handle_delivered(ticket, pipeline, order_number, order, items_analysis, lang)
    else:
        return await _handle_not_shipped(ticket, pipeline, order_number, order, items_analysis, lang)


async def _handle_delivered(ticket, pipeline, order_number, order, items, lang):
    """CAS 1-C-1 : Commande livrée → analyse articles + adresse retour."""
    tenant = pipeline.tenant
    refundable = [i for i in items if i['is_refundable']]
    non_refundable = [i for i in items if not i['is_refundable']]
    refund_total = sum(i['price'] * i['quantity'] for i in refundable)
    non_refund_total = sum(i['price'] * i['quantity'] for i in non_refundable)

    return_addr = tenant.return_address or tenant.custom_rules.get('return_address', '')

    # Construire le message
    lines = [f"Bonjour,\n\nVoici l'analyse de votre commande **#{order_number}** :\n"]

    if refundable:
        lines.append("**Articles remboursables :**")
        for i in refundable:
            lines.append(f"- {i['title']} ({i['variant']}) — {i['price']}€")

    if non_refundable:
        lines.append("\n**Articles NON remboursables (personnalisés) :**")
        for i in non_refundable:
            detail = f" ({i['flocage_details']})" if i['flocage_details'] else ""
            lines.append(f"- {i['title']} ({i['variant']}){detail} — {i['price']}€")

    if refundable and return_addr:
        lines.append(f"\n**Pour obtenir votre remboursement de {refund_total:.2f}€**, renvoyez les articles remboursables à :")
        lines.append(f"**{return_addr}**")
        lines.append(f"\nUne fois votre colis retour envoyé, répondez à cet email avec votre **numéro de suivi retour**.")

    if not refundable:
        lines.append(f"\nMalheureusement, tous les articles sont personnalisés et ne peuvent pas être remboursés.")

    lines.append(f"\nCordialement,\n**L'équipe {tenant.brand_name}**")
    msg = "\n".join(lines)

    # Enregistrer dans cancellations
    esc_id = await pipeline.repos.create_escalation(
        tenant.id, ticket.db_id or 0, ticket.email_from, 'ANNULATION',
        f"Retour commande livrée #{order_number} — remboursable: {refund_total:.2f}€"
    )
    await pipeline.repos.create_cancellation(
        tenant.id, ticket.email_from, order_number,
        ticket.db_id, esc_id, 'fulfilled', items,
        refund_total, non_refund_total, '1-C-1'
    )

    next_step = 'step5_return_tracking' if refundable else 'escalated_to_human'
    return Response(text=msg, should_send=True, category='ANNULATION', confidence=1.0, next_step=next_step)


async def _handle_not_shipped(ticket, pipeline, order_number, order, items, lang):
    """CAS 1-C-2 : Pas encore expédiée → escalade dashboard."""
    tenant = pipeline.tenant
    refundable = [i for i in items if i['is_refundable']]
    non_refundable = [i for i in items if not i['is_refundable']]
    refund_total = sum(i['price'] * i['quantity'] for i in refundable)
    non_refund_total = sum(i['price'] * i['quantity'] for i in non_refundable)

    esc_id = await pipeline.repos.create_escalation(
        tenant.id, ticket.db_id or 0, ticket.email_from, 'ANNULATION',
        f"Annulation commande non expédiée #{order_number}"
    )
    await pipeline.repos.create_cancellation(
        tenant.id, ticket.email_from, order_number,
        ticket.db_id, esc_id, None, items,
        refund_total, non_refund_total, '1-C-2'
    )

    msg = (f"Bonjour,\n\nVotre demande d'annulation pour la commande **#{order_number}** a été enregistrée.\n\n"
           f"Notre équipe vérifie le statut de votre commande et vous répondra sous 24h.\n\n"
           f"Cordialement,\n**L'équipe {tenant.brand_name}**")

    if pipeline.notifier:
        items_detail = ", ".join(f"{i['title']}" for i in items[:3])
        await pipeline.notifier(
            f"❌ <b>Annulation #{order_number}</b>\n"
            f"Client: {ticket.email_from}\n"
            f"Articles: {items_detail}\n"
            f"Remboursable: {refund_total:.2f}€\n"
            f"Escalade #{esc_id}"
        )

    return Response(text=msg, should_send=True, category='ANNULATION', confidence=1.0, next_step='escalated_to_human')


async def handle_return_tracking(ticket: Ticket, pipeline) -> Response:
    """Suite CAS 1-C : Client envoie son numéro de suivi retour."""
    tenant = pipeline.tenant
    body = clean_reply_body(ticket.body).strip()
    order_number = ticket.collected_data.get('order_number', '')

    import re
    tracking_match = re.search(r'([A-Z0-9]{8,30})', body.upper())
    if not tracking_match:
        msg = f"Merci d'indiquer votre numéro de suivi retour.\n\nCordialement,\n**L'équipe {tenant.brand_name}**"
        return Response(text=msg, should_send=True, category='ANNULATION', confidence=1.0, next_step='step5_return_tracking')

    tracking = tracking_match.group(1)
    await pipeline.repos.create_return_tracking(tenant.id, ticket.email_from, order_number, tracking)

    msg = (f"Bonjour,\n\nMerci ! Votre numéro de suivi retour **{tracking}** a été enregistré.\n\n"
           f"Nous suivrons la réception de votre colis et procéderons au remboursement dès réception.\n\n"
           f"Cordialement,\n**L'équipe {tenant.brand_name}**")

    if pipeline.notifier:
        await pipeline.notifier(
            f"📦 <b>Suivi retour reçu</b>\n"
            f"Client: {ticket.email_from}\nCommande: #{order_number}\nTracking: {tracking}"
        )

    return Response(text=msg, should_send=True, category='ANNULATION', confidence=1.0, next_step='escalated_to_human')
