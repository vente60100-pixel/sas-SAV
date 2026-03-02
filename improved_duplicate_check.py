#!/usr/bin/env python3

# Lire le fichier
with open('core/pipeline.py', 'r') as f:
    lines = f.readlines()

# Trouver et remplacer le blocage simple par un check intelligent
new_check = '''
        # 🚨 BLOCAGE PRÉVENTIF DES DUPLICATES (AVANT APPEL API)
        if ticket.subject and ticket.subject.startswith("Re: Re:"):
            # Vérifier si on a DÉJÀ envoyé une réponse à ce client
            already_sent = await self.repos.db.fetchval(
                """SELECT COUNT(*) FROM emails 
                WHERE email_from =  
                AND sent_at IS NOT NULL 
                AND created_at > NOW() - INTERVAL '24 hours'
                AND tenant_id = """,
                ticket.email_from, self.tenant.id
            )
            if already_sent and already_sent > 0:
                logger.warning(f"DUPLICATE PRÉVENTIF: Re: Re: détecté pour {ticket.email_from} ({already_sent} réponses déjà envoyées) - Aucun appel API", 
                              extra={"action": "duplicate_prevented", "already_sent": already_sent})
                return  # STOP ICI - Aucun traitement, aucun appel API
            else:
                logger.info(f"Re: Re: détecté mais AUCUNE réponse envoyée à {ticket.email_from} - Traitement normal",
                           extra={"action": "first_response_needed"})

'''

# Remplacer l'ancien check par le nouveau
for i, line in enumerate(lines):
    if 'BLOCAGE PRÉVENTIF DES DUPLICATES' in line:
        # Trouver la fin du bloc (return)
        end_idx = i
        for j in range(i, min(i+20, len(lines))):
            if 'return  # STOP ICI' in lines[j]:
                end_idx = j + 1
                break
        
        # Remplacer tout le bloc
        lines = lines[:i] + [new_check] + lines[end_idx:]
        break

# Écrire le fichier
with open('core/pipeline.py', 'w') as f:
    f.writelines(lines)

print('✅ Check intelligent ajouté : on bloque SEULEMENT si on a déjà répondu')
