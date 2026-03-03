"""
OKTAGON SAV v11.0 — Constantes globales
Extraites de sav_oktagon.py, ai_agent.py, security.py
"""

# Emails à bloquer (jamais traiter)
BLOCKED_EXACT = ['sam@shop.tiktok.com', 'mailer-daemon@googlemail.com', 'test-real@example.com']

BLOCKED_PATTERNS = [
    'mailer-daemon@', 'communications.paypal.com',
    'transactional.hs-send.com', 'noreply@', 'no-reply@',
    'notifications@', 'newsletter@', 'marketing@',
    'postmaster@', 'bounce@', 'corefy.com',
    'hubspot.com', 'hs-send.com', 'sendgrid.net',
    'mailchimp.com', 'campaign-archive.com'
]

# Mots-clés demande humain
HUMAN_REQUEST_KEYWORDS = [
    'humain', 'conseiller', 'pas un bot', 'pas un robot',
    'vrai personne', 'vrais personnes', 'parler a quelqu',
    'parler à quelqu', 'agent humain', 'real person',
    'human agent', 'want a human', 'talk to someone',
    'want to speak', 'personne reelle', 'personne réelle',
    'responsable', 'superviseur', 'manager', 'direction',
    'pas une ia', 'pas une intelligence', 'not a bot',
    'je veux parler', 'je veut parler',
    'bot automatisé', 'bot automatise',
    'parler a un conseiller', 'parler à un conseiller',
    'conseiller humain', 'un vrai conseiller', 'une vraie personne',
    'je veux un humain', 'un etre humain', 'un être humain'
]

# Catégories SAV
CATEGORIES = [
    'LIVRAISON', 'MODIFIER_ADRESSE', 'ANNULATION',
    'RETOUR_ECHANGE', 'QUESTION_PRODUIT',
    'SPONSORING', 'AFFILIATION', 'AUTRE', 'SPAM'
]

# Catégories auto (bypass AUTONOMY_LEVEL)
DEFAULT_AUTO_CATEGORIES = ['QUESTION_PRODUIT', 'LIVRAISON']

# Mots-clés smart detect : intention livraison
LIVRAISON_KEYWORDS = [
    'livraison', 'livre', 'livrer', 'colis', 'recu', 'recois',
    'suivi', 'tracking', 'expedie', 'expedition', 'transit',
    'pas recu', 'toujours pas', 'reception', 'recevoir',
    'acheminement', 'ou est', 'ou en est', 'delivery',
    'envoye', 'envoi'
]

# Mots-clés smart detect : intention retour/échange
RETOUR_KEYWORDS = [
    'retour', 'echange', 'echanger', 'renvoyer', 'rembourse',
    'taille', 'mauvaise taille', 'erreur', 'defectueux',
    'return', 'exchange', 'refund'
]

# Mots-clés smart detect : intention annulation
ANNULATION_KEYWORDS = [
    'annuler', 'annulation', 'cancel', 'rembourse'
]

# Steps du flow conversationnel
STEP_FIRST_CONTACT = 'step1_category'
STEP_READY = 'ready_for_ai'
STEP_ESCALATED = 'escalated_to_human'
STEP_CLOSED = 'closed'

# Prix short (pour split ensemble)
SHORT_PRICE = 29.99
