"""
OKTAGON SAV v11.0 — Configuration centrale
Toutes les configurations via dataclasses frozen + variables d'environnement
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Charger .env
load_dotenv()


@dataclass(frozen=True)
class ClaudeConfig:
    """Configuration API Claude"""
    api_key: str = os.getenv('ANTHROPIC_API_KEY', '')
    model: str = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')
    max_tokens: int = 8000
    temperature: float = 0.7


@dataclass(frozen=True)
class ShopifyConfig:
    """Configuration Shopify API"""
    store: str = os.getenv('SHOPIFY_STORE', '')
    client_id: str = os.getenv('SHOPIFY_CLIENT_ID', '')
    client_secret: str = os.getenv('SHOPIFY_CLIENT_SECRET', '')
    api_version: str = os.getenv('SHOPIFY_API_VERSION', '2025-01')


@dataclass(frozen=True)
class GmailConfig:
    """Configuration Gmail IMAP/SMTP"""
    address: str = os.getenv('GMAIL_ADDRESS', '')
    password: str = os.getenv('GMAIL_APP_PASSWORD', '').replace(' ', '')  # Supprimer espaces


@dataclass(frozen=True)
class TelegramConfig:
    """Configuration Telegram (2 bots : Admin + Usine)"""
    bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    admin_chat_id: str = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '')
    usine_bot_token: str = os.getenv('TELEGRAM_USINE_BOT_TOKEN', '')
    usine_chat_id: str = os.getenv('TELEGRAM_USINE_CHAT_ID', '')


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration PostgreSQL"""
    host: str = os.getenv('POSTGRES_HOST', 'localhost')
    port: int = int(os.getenv('POSTGRES_PORT', '5432'))
    database: str = os.getenv('POSTGRES_DB', 'oktagon_sav')
    user: str = os.getenv('POSTGRES_USER', 'oktagon_sav')
    password: str = os.getenv('POSTGRES_PASSWORD', '')
    pool_min: int = 2
    pool_max: int = 10


@dataclass(frozen=True)
class SecurityConfig:
    """Configuration sécurité et anti-spam"""
    hash_salt: str = os.getenv('HASH_SALT', 'oktagon_sav_v24')
    # 48h entre chaque auto-reply au même client pour éviter le spam
    # si le client réécrit dans ce délai, on traite mais sans renvoyer
    anti_loop_window_hours: int = 48
    # Limite globale : max 50 emails sortants par heure (tous clients confondus)
    # Protège contre un bug qui enverrait en masse
    anti_spam_max_per_hour: int = 50
    # Limite par client : max 10 emails par heure vers la même adresse
    # Valeur haute car inclut les réponses manuelles dashboard
    anti_spam_max_per_client_hour: int = 10


@dataclass(frozen=True)
class AgentConfig:
    """Configuration agents IA et autonomie"""
    # Niveau d'autonomie : 1=conservateur (escalade souvent), 2=modéré, 3=agressif
    autonomy_level: int = int(os.getenv('AUTONOMY_LEVEL', '1'))
    # Seuil de confiance IA : en dessous → escalade humaine
    # 0.90 = l'IA doit être à 90%+ sûre pour répondre seule
    confidence_threshold: float = float(os.getenv('CONFIDENCE_THRESHOLD', '0.90'))
    # Montant minimum pour proposer l'ebook en compensation (EUR)
    ebook_min_amount: float = 10.0
    ebook_link: str = 'https://oktagon-shop.com/pages/ebook-musculation-combat'


@dataclass(frozen=True)
class ServerConfig:
    """Configuration serveur"""
    port: int = int(os.getenv('SERVER_PORT', '8888'))
    test_mode: bool = os.getenv('TEST_MODE', 'false').lower() == 'true'
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')


@dataclass(frozen=True)
class Config:
    """Configuration globale - Singleton"""
    claude: ClaudeConfig
    shopify: ShopifyConfig
    gmail: GmailConfig
    telegram: TelegramConfig
    database: DatabaseConfig
    security: SecurityConfig
    agent: AgentConfig
    server: ServerConfig


# Singleton
config = Config(
    claude=ClaudeConfig(),
    shopify=ShopifyConfig(),
    gmail=GmailConfig(),
    telegram=TelegramConfig(),
    database=DatabaseConfig(),
    security=SecurityConfig(),
    agent=AgentConfig(),
    server=ServerConfig()
)
