#!/usr/bin/env python3
import sys

# Lire le fichier
with open('core/pipeline.py', 'r') as f:
    lines = f.readlines()

# Trouver la ligne où on envoie l'email (ligne ~1154)
for i, line in enumerate(lines):
    if 'sent = await self.channel.send_message(' in line and 'Re:' in lines[i+1]:
        # Ajouter la vérification anti-duplicate AVANT l'envoi
        indent = '            '
        check_lines = [
            indent + '# SÉCURITÉ ANTI-DUPLICATE\n',
            indent + 'subject_to_send = f"Re: {ticket.subject}"\n',
            indent + 'if subject_to_send.startswith("Re: Re:"):\n',
            indent + '    logger.warning(f"DUPLICATE BLOQUÉ: Double Re: pour {ticket.email_from}", extra={"action": "duplicate_blocked"})\n',
            indent + '    sent = False\n',
            indent + 'else:\n',
            indent + '    # Vérifier si on a déjà envoyé à ce client récemment\n',
            indent + '    recent_sent = await self.repos.db.fetchval(\n',
            indent + '        "SELECT COUNT(*) FROM emails WHERE email_from =  AND sent_at > NOW() - INTERVAL \'1 hour\' AND tenant_id = ",\n',
            indent + '        ticket.email_from, self.tenant.id\n',
            indent + '    )\n',
            indent + '    if recent_sent and recent_sent > 2:\n',
            indent + '        logger.warning(f"DUPLICATE BLOQUÉ: {recent_sent} emails déjà envoyés à {ticket.email_from} dans la dernière heure", extra={"action": "rate_limit_blocked"})\n',
            indent + '        sent = False\n',
            indent + '    else:\n',
            indent + '        sent = await self.channel.send_message(\n',
            indent + '            ticket.email_from, subject_to_send, response.html, ticket.message_id\n',
            indent + '        )\n',
        ]
        
        # Remplacer les 3 lignes originales par notre nouveau code
        lines = lines[:i] + check_lines + lines[i+3:]
        break

# Écrire le fichier modifié
with open('core/pipeline.py', 'w') as f:
    f.writelines(lines)

print('✅ Protection anti-duplicate ajoutée')
