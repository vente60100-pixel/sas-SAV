"""
OKTAGON SAV v11.0 — Modèle Tenant (multi-tenant)
Chaque boutique = 1 tenant avec sa propre config.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TenantConfig:
    """Configuration complète d'un tenant (boutique e-commerce)."""

    # Identité
    id: str = ""                              # "oktagon"
    name: str = ""                            # "OKTAGON Shop"
    active: bool = True

    # Connecteur e-commerce
    ecommerce_type: str = "shopify"           # "shopify" / "woocommerce"
    ecommerce_config: dict = field(default_factory=dict)  # {store, client_id, client_secret, api_version}

    # Connecteur canal
    channel_type: str = "email"               # "email" / "whatsapp"
    channel_config: dict = field(default_factory=dict)    # {address, password, imap_host, smtp_host}

    # Connecteur IA
    ai_type: str = "claude"                   # "claude" / "openai"
    ai_config: dict = field(default_factory=dict)         # {api_key, model, max_tokens, temperature}

    # Notifications
    telegram_config: dict = field(default_factory=dict)   # {bot_token, chat_id}

    # Règles métier
    auto_categories: list = field(default_factory=lambda: ['QUESTION_PRODUIT', 'LIVRAISON'])
    confidence_threshold: float = 0.90
    autonomy_level: int = 2
    max_emails_per_hour: int = 10
    max_emails_per_day: int = 30

    # Marque
    brand_name: str = ""                      # "OKTAGON"
    brand_color: str = "#F0FF27"              # Couleur accent
    brand_tagline: str = ""                   # "Sport de combat premium"
    product_type: str = ""                    # "sport combat/MMA"
    return_address: str = ""                  # Adresse retour (Creil)

    # Règles custom
    custom_rules: dict = field(default_factory=dict)
    # Ex: {"flocage_gratuit": true, "delai_jours": "12-15", "short_price": 29.99}

    # Prompts IA (par catégorie)
    prompts: dict = field(default_factory=dict)
    # Ex: {"LIVRAISON": "Tu es l'assistant...", "RETOUR": "...", "QUESTION_PRODUIT": "..."}

    # Template email HTML (avec {content} et {notice} comme placeholders)
    email_template: str = ""

    # Emails à bloquer (propres au tenant)
    blocked_emails: list = field(default_factory=list)
