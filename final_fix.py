#!/usr/bin/env python3

# Lire le fichier
with open('core/pipeline.py', 'r') as f:
    content = f.read()

# Remplacer le code cassé
old = '''# 🚨 BLOCAGE PRÉVENTIF DES DUPLICATES (AVANT APPEL API)
        if ticket.subject and ticket.subject.startswith("Re: Re:"):
            # Vérifier si on a DÉJÀ envoyé une réponse à ce client
            already_sent = await self.repos.db.pool.fetchval(
                """SELECT COUNT(*) FROM emails 
                WHERE email_from =  
                AND sent_at IS NOT NULL'''

new = '''# 🚨 BLOCAGE PRÉVENTIF DES DUPLICATES (AVANT APPEL API)
        if ticket.subject and ticket.subject.startswith("Re: Re:"):
            logger.warning(f"DUPLICATE PRÉVENTIF: Re: Re: bloqué pour {ticket.email_from} - Aucun appel API", 
                          extra={"action": "duplicate_prevented"})
            return  # STOP ICI - Aucun traitement, aucun appel API'''

content = content.replace(old, new, 1)

# Écrire le fichier
with open('core/pipeline.py', 'w') as f:
    f.write(content)

print('✅ Fix final appliqué - Re: Re: seront bloqués AVANT appel API')
