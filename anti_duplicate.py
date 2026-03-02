#!/usr/bin/env python3
'''
SCRIPT DE SÉCURITÉ ANTI-DUPLICATE
Empêche l'envoi de multiples emails au même client
'''

import os
from datetime import datetime, timedelta

# Liste des clients qui ont déjà reçu des emails aujourd'hui
BLOCKED_TODAY = set([
    'iabhd213@hotmail.com',
    'jacqueslemoine751@gmail.com',
    'jeanhuguesleichnig@hotmail.fr',
    'rcdias@outlook.pt',
    'dearson.pity@icloud.com',
    'franckkouadiani8@gmail.com',
    'cat.moon@hotmail.fr',
    'didier_eren1905@hotmail.com',
    'jorick.apatout@gmail.com',
    'raphael.mithra@gmail.com',
    'walidserbis93@gmail.com',
    'kaelighebert56@gmail.com',
    'slimanmokhtarzazous@gmail.com',
    'aymenlaghmich4@gmail.com',
    'amjad.elm@icloud.com',
    'arthurjoly804@gmail.com',
    'y9499553@gmail.com',
    'support@judge.me',
])

# Dictionnaire pour tracker les emails envoyés pendant cette session
SENT_THIS_SESSION = {}

def is_duplicate_email(email_address: str, subject: str) -> bool:
    '''
    Vérifie si c'est un duplicate
    - Bloque si le client est dans BLOCKED_TODAY
    - Bloque si on a déjà envoyé à ce client avec le même sujet
    - Bloque si le sujet commence par Re: Re:
    '''
    email_lower = email_address.lower()
    
    # 1. Client bloqué aujourd'hui ?
    if email_lower in BLOCKED_TODAY:
        print(f'⛔ BLOQUÉ: {email_lower} a déjà reçu des emails aujourd\'hui')
        return True
    
    # 2. Double Re: ?
    if subject and subject.startswith('Re: Re:'):
        print(f'⛔ BLOQUÉ: Double Re: détecté pour {email_lower}')
        return True
    
    # 3. Déjà envoyé dans cette session ?
    key = f'{email_lower}:{subject}'
    if key in SENT_THIS_SESSION:
        print(f'⛔ BLOQUÉ: Déjà envoyé {subject} à {email_lower}')
        return True
    
    # Marquer comme envoyé
    SENT_THIS_SESSION[key] = datetime.now()
    return False

print('✅ Module anti-duplicate chargé')
print(f'📋 {len(BLOCKED_TODAY)} clients bloqués aujourd\'hui')
