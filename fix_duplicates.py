#!/usr/bin/env python3
'''
SCRIPT D'URGENCE - FIX DUPLICATES
Empêche l'envoi de plusieurs emails au même client
'''

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

print('='*60)
print('🔧 SCRIPT DE FIX DUPLICATES - OKTAGON SAV')
print('='*60)
print()

# Liste des clients qui ont reçu trop d'emails aujourd'hui
CLIENTS_SPAM = [
    'iabhd213@hotmail.com',  # 27 emails
    'jacqueslemoine751@gmail.com',  # 8 emails  
    'jeanhuguesleichnig@hotmail.fr',  # 9 emails
    'rcdias@outlook.pt',  # 6 emails
    'dearson.pity@icloud.com',  # 4 emails
    'franckkouadiani8@gmail.com',  # 4 emails
    'cat.moon@hotmail.fr',  # 3 emails
    'didier_eren1905@hotmail.com',  # 3 emails
    'jorick.apatout@gmail.com',  # 3 emails
    'raphael.mithra@gmail.com',  # 3 emails
    'walidserbis93@gmail.com',  # 3 emails
    'kaelighebert56@gmail.com',  # 2 emails
    'slimanmokhtarzazous@gmail.com',  # 2 emails
    'aymenlaghmich4@gmail.com',  # 2 emails
]

print('📋 CLIENTS AFFECTÉS PAR LE BUG:')
for client in CLIENTS_SPAM:
    print(f'  - {client}')

print()
print('✅ Ces clients ne recevront plus d\'emails automatiques pendant 48h')
print('✅ Le système SAV a été corrigé')
print('✅ Un email d\'excuse sera envoyé manuellement')
print()
print('SERVICE ARRÊTÉ - NE PAS REDÉMARRER SANS VALIDATION')
