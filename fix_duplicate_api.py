#!/usr/bin/env python3
import sys

# Lire le fichier
with open('core/pipeline.py', 'r') as f:
    lines = f.readlines()

# Trouver la ligne après logger.info EMAIL RECU (ligne ~93)
for i, line in enumerate(lines):
    if '"═══ EMAIL REÇU ═══' in line:
        # Ajouter la vérification Re: Re: JUSTE APRÈS le log
        indent = '        '
        check_lines = [
            '\n',
            indent + '# 🚨 BLOCAGE PRÉVENTIF DES DUPLICATES (AVANT APPEL API)\n',
            indent + 'if ticket.subject and ticket.subject.startswith("Re: Re:"):\n',
            indent + '    logger.warning(f"DUPLICATE PRÉVENTIF: Re: Re: détecté pour {ticket.email_from} - Aucun appel API", extra={"action": "duplicate_prevented"})\n',
            indent + '    return  # STOP ICI - Aucun traitement, aucun appel API\n',
            '\n',
        ]
        
        # Insérer après le logger.info
        lines = lines[:i+3] + check_lines + lines[i+3:]
        break

# Écrire le fichier modifié
with open('core/pipeline.py', 'w') as f:
    f.writelines(lines)

print('✅ Blocage préventif des Re: Re: ajouté AVANT tout appel API')
