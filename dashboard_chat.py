"""
OKTAGON SAV v7.0 — Chat IA avec Tools (lecture + actions)
Claude intégré au dashboard avec accès DB, Shopify, emails.
Peut AGIR : envoyer des emails, résoudre des escalations, marquer des remboursements.
"""
import json
import anthropic
import os
from logger import logger


TOOLS = [
    # ═══ LECTURE ═══
    {
        "name": "search_client",
        "description": "Cherche un client par email OU par prénom dans la base SAV. Retourne la liste des clients trouvés avec leurs stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Email, partie d'email, ou prénom à chercher"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_client_history",
        "description": "Récupère l'historique complet d'un client : tous ses messages et toutes les réponses SAV envoyées. Utile pour comprendre le contexte avant d'agir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email exact du client"}
            },
            "required": ["email"]
        }
    },
    {
        "name": "get_stats",
        "description": "Récupère les statistiques du SAV : emails traités, temps moyen, taux d'escalade, catégories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["today", "week", "month", "all"], "description": "Période à analyser"}
            },
            "required": ["period"]
        }
    },
    {
        "name": "get_escalations",
        "description": "Récupère les escalations en attente (non résolues) qui nécessitent une action humaine.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "search_order",
        "description": "Cherche une commande Shopify par numéro. Retourne les détails : client, articles, tracking, statut, montant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_number": {"type": "string", "description": "Numéro de commande (ex: 8460)"}
            },
            "required": ["order_number"]
        }
    },
    {
        "name": "get_recent_emails",
        "description": "Récupère les derniers emails traités par le SAV avec catégorie, confiance et réponse.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Nombre d'emails à récupérer (max 20)", "default": 10}
            }
        }
    },
    # ═══ ACTIONS ═══
    {
        "name": "send_email",
        "description": "Envoie un email à un client au nom d'OKTAGON SAV. L'email sera formaté avec le template premium OKTAGON (noir/jaune). Utilise cette action quand l'admin demande d'écrire ou répondre à un client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Adresse email du destinataire"},
                "subject": {"type": "string", "description": "Objet de l'email"},
                "body": {"type": "string", "description": "Contenu de l'email en texte. Rédige un message professionnel, chaleureux, au nom d'OKTAGON. NE PAS mettre de HTML."}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "resolve_escalation",
        "description": "Résout une escalation en attente. Utilise quand l'admin dit de traiter/résoudre/fermer un dossier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escalation_id": {"type": "integer", "description": "ID de l'escalation à résoudre"},
                "action": {"type": "string", "description": "Action effectuée (ex: 'remboursé', 'renvoi effectué', 'résolu par email', 'refusé')", "default": "résolu"},
                "response_note": {"type": "string", "description": "Note interne sur ce qui a été fait", "default": ""}
            },
            "required": ["escalation_id"]
        }
    },
    {
        "name": "mark_refund",
        "description": "Marque une commande comme remboursée dans le système. ATTENTION : ceci ne fait PAS le remboursement Shopify, c'est juste un marquage interne + notification. L'admin doit faire le remboursement manuellement sur Shopify. Utilise quand l'admin dit 'rembourse X' ou 'valide le remboursement'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email du client"},
                "order_number": {"type": "string", "description": "Numéro de commande à rembourser"},
                "reason": {"type": "string", "description": "Raison du remboursement", "default": "Demande client"},
                "send_confirmation": {"type": "boolean", "description": "Envoyer un email de confirmation au client", "default": True}
            },
            "required": ["email", "order_number"]
        }
    },
    {
        "name": "add_note",
        "description": "Ajoute une note interne sur un client (ex: VIP, à surveiller, remboursé, etc.). Visible dans la fiche client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email du client"},
                "note": {"type": "string", "description": "Note à ajouter"}
            },
            "required": ["email", "note"]
        }
    },
    {
        "name": "resend_info",
        "description": "Cherche et renvoie les informations de suivi (tracking) d'une commande au client par email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email du client"},
                "order_number": {"type": "string", "description": "Numéro de commande"}
            },
            "required": ["email", "order_number"]
        }
    }
]

SYSTEM_PROMPT = """Tu es l'assistant IA du dashboard OKTAGON SAV. Tu parles à l'ADMIN (le patron).
Tu as accès complet à la base de données clients, à Shopify, aux stats, et tu peux AGIR.

TON RÔLE :
- Répondre aux questions sur les clients, commandes, stats
- EXÉCUTER des actions quand l'admin le demande : envoyer des emails, résoudre des escalations, marquer des remboursements
- Être proactif : si l'admin dit "rembourse Inès", cherche d'abord le client, trouve la commande, puis agis
- Donner des insights et résumés clairs

RÈGLES :
- Parle en français, concis et direct — tu parles au patron, pas à un client
- Tutoie l'admin
- Pour les remboursements : mark_refund marque dans le système MAIS le remboursement réel doit être fait sur Shopify manuellement. Précise-le toujours.
- Pour les emails aux clients : rédige un message PRO, chaleureux, au nom d'OKTAGON. Utilise "vous" avec les clients.
- Quand l'admin dit un prénom (ex: "Inès"), cherche d'abord par prénom, puis par email
- Si tu dois faire plusieurs actions, fais-les dans l'ordre logique (chercher → comprendre → agir)
- Formate bien tes réponses pour être lisibles dans un chat

MARQUE : OKTAGON — sport de combat / MMA — personnalisé sur mesure, 12-15 jours de fabrication.
"""


async def _execute_tool(name: str, input_data: dict, db, repos, shopify, email_connector, tenant_id: str) -> str:
    """Exécute un tool et retourne le résultat en string."""
    try:
        # ═══ LECTURE ═══
        if name == "search_client":
            query = input_data['query']
            # Chercher par email
            clients = await repos.get_all_clients(tenant_id, search=query, limit=10)
            # Si pas de résultat par email, chercher par prénom
            if not clients:
                rows = await db.fetch_all(
                    """SELECT cp.email, cp.prenom, cp.derniere_commande, cp.vip,
                              COUNT(pe.id) as total_emails
                       FROM client_profiles cp
                       LEFT JOIN processed_emails pe ON pe.email_from = cp.email AND pe.tenant_id = cp.tenant_id
                       WHERE cp.tenant_id = $1 AND cp.prenom ILIKE $2
                       GROUP BY cp.email, cp.prenom, cp.derniere_commande, cp.vip
                       LIMIT 10""",
                    tenant_id, f'%{query}%'
                )
                if rows:
                    result = f"{len(rows)} client(s) trouvé(s) par prénom :\n"
                    for c in rows:
                        vip = " ⭐VIP" if c.get('vip') else ""
                        result += f"- {c['prenom'] or '?'} | {c['email']} | {c.get('total_emails', 0)} emails | Commande: #{c.get('derniere_commande', '?')}{vip}\n"
                    return result
                return f"Aucun client trouvé pour '{query}'."
            result = f"{len(clients)} client(s) trouvé(s) :\n"
            for c in clients:
                vip = " ⭐VIP" if c.get('vip') else ""
                result += f"- {c.get('prenom', '?')} | {c['email']} | {c['total_emails']} emails | Commande: #{c.get('derniere_commande', '?')}{vip}\n"
            return result

        elif name == "get_client_history":
            detail = await repos.get_client_detail(tenant_id, input_data['email'])
            if not detail['history']:
                return f"Aucun historique pour {input_data['email']}"
            result = f"Client: {input_data['email']}\n"
            result += f"Profil: {detail['profile'].get('total_emails', 0)} emails, {detail['profile'].get('total_escalations', 0)} escalations\n"
            if detail['profile'].get('prenom'):
                result += f"Prénom: {detail['profile']['prenom']}\n"
            result += "\n"
            for h in detail['history'][-10:]:
                date = h['date'][:16] if h['date'] else '?'
                if h['client_message']:
                    msg = h['client_message'][:200]
                    result += f"[{date}] CLIENT: {msg}\n"
                if h['sav_response']:
                    resp = h['sav_response'][:200]
                    result += f"[{date}] SAV ({h.get('category', '?')}): {resp}\n"
                result += "---\n"
            if detail['escalations']:
                result += f"\nEscalations ({len(detail['escalations'])}) :\n"
                for e in detail['escalations'][:5]:
                    status = "✅ Résolu" if e['resolved'] else "⏳ En attente"
                    result += f"- [{e['date'][:10] if e['date'] else '?'}] {e['category']} | {e.get('reason', '')[:60]} | {status}\n"
            return result

        elif name == "get_stats":
            period = input_data.get('period', 'today')
            stats = await repos.get_dashboard_stats(tenant_id, period)
            cats = await repos.get_stats_by_category(tenant_id, period)
            result = f"Stats ({period}) :\n"
            result += f"- Emails traités : {stats['total_emails']}\n"
            result += f"- Réponses envoyées : {stats['emails_sent']}\n"
            result += f"- Escalations : {stats['escalations']}\n"
            result += f"- Temps moyen : {stats['avg_processing_ms']}ms\n"
            if cats:
                result += "\nPar catégorie :\n"
                for c in cats:
                    result += f"  {c['category']}: {c['count']}\n"
            return result

        elif name == "get_escalations":
            pending = await repos.get_pending_escalations(tenant_id)
            if not pending:
                return "Aucune escalation en attente. Tout est propre !"
            result = f"{len(pending)} escalation(s) en attente :\n"
            for e in pending:
                date = e['date'][:16] if e['date'] else '?'
                result += f"- ID#{e['id']} | [{date}] {e['email']} | {e['category']} | {e.get('reason', '')[:80]}\n"
                if e.get('subject'):
                    result += f"  Sujet: {e['subject'][:50]}\n"
            return result

        elif name == "search_order":
            if not shopify:
                return "Connecteur Shopify non disponible."
            order = await shopify.get_order(input_data['order_number'])
            if not order:
                return f"Commande #{input_data['order_number']} non trouvée sur Shopify."
            result = f"Commande #{input_data['order_number']} :\n"
            result += f"- Client : {order.get('customer_name', '?')}\n"
            result += f"- Email : {order.get('customer_email', '?')}\n"
            result += f"- Total : {order.get('total_price', '?')} {order.get('currency', 'EUR')}\n"
            result += f"- Statut : {order.get('fulfillment_status') or 'non expédié'}\n"
            result += f"- Statut financier : {order.get('financial_status', '?')}\n"
            tracking = order.get('tracking_numbers', [])
            if tracking:
                result += f"- Tracking : {', '.join(tracking)}\n"
            result += f"- Articles :\n"
            for it in order.get('line_items', []):
                result += f"  • {it.get('title', '')} | {it.get('variant_title', '')} | {it.get('price', '?')}€\n"
            return result

        elif name == "get_recent_emails":
            limit = min(input_data.get('limit', 10), 20)
            emails = await repos.get_recent_emails(tenant_id, limit=limit)
            if not emails:
                return "Aucun email récent."
            result = f"{len(emails)} dernier(s) email(s) :\n"
            for e in emails:
                date = e['date'][:16] if e['date'] else '?'
                conf = f"{e['confidence']:.0%}" if e['confidence'] else '?'
                sent = "✅" if e['sent'] else "❌"
                result += f"- [{date}] {e['email'][:25]} | {e.get('subject', '')[:30]} | {e.get('category', '?')} ({conf}) {sent}\n"
            return result

        # ═══ ACTIONS ═══
        elif name == "send_email":
            if not email_connector:
                return "Erreur : connecteur email non disponible."
            to = input_data['to']
            subject = input_data['subject']
            body_text = input_data['body']
            # Convertir le texte en HTML simple
            body_html = body_text.replace('\n', '<br>')
            # Utiliser le template OKTAGON
            try:
                from knowledge.templates import build_ai_response_html
                full_html = build_ai_response_html(body_html, 'OKTAGON')
            except Exception:
                full_html = f"<html><body style='font-family:Arial'>{body_html}</body></html>"
            success = await email_connector.send_message(to, subject, full_html)
            if success:
                # Logger dans la DB
                try:
                    await repos.log_outgoing(tenant_id, to, 'manual_dashboard')
                except Exception:
                    pass
                return f"✅ Email envoyé à {to} avec succès !\nObjet: {subject}"
            return f"❌ Erreur lors de l'envoi de l'email à {to}"

        elif name == "resolve_escalation":
            esc_id = input_data['escalation_id']
            action = input_data.get('action', 'résolu')
            note = input_data.get('response_note', '')
            await repos.resolve_escalation(esc_id, action=action, response=note)
            return f"✅ Escalation #{esc_id} résolue ! Action: {action}"

        elif name == "mark_refund":
            email_addr = input_data['email']
            order_num = input_data['order_number']
            reason = input_data.get('reason', 'Demande client')
            send_conf = input_data.get('send_confirmation', True)

            # 1. Résoudre toutes les escalations liées
            pending = await repos.get_pending_escalations(tenant_id)
            resolved_count = 0
            for esc in pending:
                if esc['email'] == email_addr:
                    await repos.resolve_escalation(esc['id'], action=f'remboursé #{order_num}', response=reason)
                    resolved_count += 1

            # 2. Ajouter une note dans le profil
            try:
                await db.execute(
                    """UPDATE client_profiles SET notes = COALESCE(notes, '') || $1, updated_at = NOW()
                       WHERE tenant_id = $2 AND email = $3""",
                    f"\n[REMBOURSEMENT] #{order_num} — {reason}", tenant_id, email_addr
                )
            except Exception:
                pass

            # 3. Envoyer email de confirmation si demandé
            email_sent = False
            if send_conf and email_connector:
                try:
                    # Chercher le prénom
                    profile = await db.fetch_one(
                        "SELECT prenom FROM client_profiles WHERE tenant_id = $1 AND email = $2",
                        tenant_id, email_addr
                    )
                    prenom = profile['prenom'] if profile and profile.get('prenom') else ''
                    salut = f"Bonjour {prenom}" if prenom else "Bonjour"

                    body = f"""{salut},

Nous vous confirmons que le remboursement de votre commande #{order_num} a bien été validé.

Le montant sera recrédité sur votre moyen de paiement d'origine sous 5 à 10 jours ouvrés selon votre banque.

Nous vous remercions pour votre patience et restons à votre disposition.

Sportivement,
L'équipe OKTAGON"""
                    body_html = body.replace('\n', '<br>')
                    from knowledge.templates import build_ai_response_html
                    full_html = build_ai_response_html(body_html, 'OKTAGON')
                    email_sent = await email_connector.send_message(
                        email_addr, f"Confirmation de remboursement — Commande #{order_num}", full_html
                    )
                except Exception as e:
                    logger.error(f"Erreur envoi confirmation remboursement: {e}")

            result = f"✅ Remboursement marqué pour #{order_num} ({email_addr})\n"
            result += f"- Escalations résolues : {resolved_count}\n"
            if email_sent:
                result += f"- Email de confirmation envoyé au client\n"
            result += f"\n⚠️ RAPPEL : Le remboursement réel doit être fait manuellement sur Shopify !"
            return result

        elif name == "add_note":
            email_addr = input_data['email']
            note = input_data['note']
            # Vérifier si le profil existe
            profile = await db.fetch_one(
                "SELECT email FROM client_profiles WHERE tenant_id = $1 AND email = $2",
                tenant_id, email_addr
            )
            if profile:
                await db.execute(
                    """UPDATE client_profiles SET notes = COALESCE(notes, '') || $1, updated_at = NOW()
                       WHERE tenant_id = $2 AND email = $3""",
                    f"\n[NOTE] {note}", tenant_id, email_addr
                )
            else:
                await db.execute(
                    """INSERT INTO client_profiles (tenant_id, email, notes, nb_contacts, updated_at)
                       VALUES ($1, $2, $3, 0, NOW())""",
                    tenant_id, email_addr, f"[NOTE] {note}"
                )
            return f"✅ Note ajoutée pour {email_addr} : {note}"

        elif name == "resend_info":
            email_addr = input_data['email']
            order_num = input_data['order_number']
            if not shopify or not email_connector:
                return "Erreur : connecteurs non disponibles."
            # Chercher la commande
            order = await shopify.get_order(order_num)
            if not order:
                return f"Commande #{order_num} non trouvée."
            tracking = order.get('tracking_numbers', [])
            if not tracking:
                return f"Commande #{order_num} n'a pas encore de numéro de suivi."
            # Envoyer le mail
            profile = await db.fetch_one(
                "SELECT prenom FROM client_profiles WHERE tenant_id = $1 AND email = $2",
                tenant_id, email_addr
            )
            prenom = profile['prenom'] if profile and profile.get('prenom') else ''
            salut = f"Bonjour {prenom}" if prenom else "Bonjour"
            tracking_str = ', '.join(tracking)
            body = f"""{salut},

Voici les informations de suivi de votre commande #{order_num} :

Numéro(s) de suivi : {tracking_str}

Vous pouvez suivre votre colis ici : https://www.17track.net/fr/track?nums={tracking[0]}

N'hésitez pas à revenir vers nous si besoin.

Sportivement,
L'équipe OKTAGON"""
            body_html = body.replace('\n', '<br>')
            from knowledge.templates import build_ai_response_html
            full_html = build_ai_response_html(body_html, 'OKTAGON')
            success = await email_connector.send_message(
                email_addr, f"Suivi de votre commande #{order_num}", full_html
            )
            if success:
                return f"✅ Infos de suivi renvoyées à {email_addr} !\nTracking: {tracking_str}"
            return f"❌ Erreur envoi à {email_addr}"

        return f"Outil '{name}' non reconnu."

    except Exception as e:
        logger.error(f"Erreur tool {name}: {e}", extra={"action": "chat_tool_error"})
        return f"❌ Erreur outil {name}: {str(e)}"


async def chat_with_tools(message: str, db, repos, shopify, tenant_id: str,
                          email_connector=None) -> str:
    """Appelle Claude avec les tools et retourne la réponse."""
    api_key = os.environ.get('CLAUDE_API_KEY') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return "Erreur: clé API Claude non configurée."

    client = anthropic.AsyncAnthropic(api_key=api_key)
    messages = [{"role": "user", "content": message}]

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        # Boucle tool use (max 8 itérations pour les actions enchaînées)
        max_iterations = 8
        iteration = 0
        while response.stop_reason == "tool_use" and iteration < max_iterations:
            iteration += 1
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Chat tool: {block.name}({json.dumps(block.input, ensure_ascii=False)[:100]})",
                                extra={"action": "chat_tool_call"})
                    result = await _execute_tool(
                        block.name, block.input, db, repos, shopify,
                        email_connector, tenant_id
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = await client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

        # Extraire le texte final
        text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                text += block.text

        return text or "Action effectuée."

    except Exception as e:
        logger.error(f"Chat IA erreur: {e}", extra={"action": "chat_error"})
        return f"Erreur: {str(e)}"
