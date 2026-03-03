"""
OKTAGON SAV v11.0 — Modèles centraux
Ticket : l'objet qui traverse tout le pipeline
Response : le résultat retourné par chaque handler
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Ticket:
    """Objet central qui traverse tout le pipeline.
    Créé à l'étape INTAKE, enrichi à chaque étape suivante."""

    # --- Identité email ---
    email_from: str = ""
    subject: str = ""
    body: str = ""
    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    headers: dict = field(default_factory=dict)
    raw_content: str = ""
    language: str = "fr"

    # --- Tenant ---
    tenant_id: str = ""

    # --- Expéditeur enrichi ---
    sender_name: str = ""              # Nom affiché (ex: "Jacques Lemoine")
    cc: str = ""                       # Destinataires en copie
    attachment_names: list = field(default_factory=list)  # Noms des pièces jointes

    # --- Sécurité (rempli par FILTER) ---
    email_hash: str = ""
    is_spam: bool = False
    spam_reason: str = ""
    is_auto_responder: bool = False
    is_thank_you: bool = False
    has_attachments: bool = False
    attachment_count: int = 0

    # --- Classification (rempli par CLASSIFY) ---
    category: Optional[str] = None
    subcategory: Optional[str] = None
    order_number: Optional[str] = None
    detection_method: str = ""  # "smart", "menu", "claude", "keywords"

    # --- Enrichissement (rempli par ENRICH) ---
    order_details: Optional[dict] = None
    conversation_history: str = ""
    customer_name: str = ""
    signed_name: str = ""

    # --- Session (rempli par IDENTIFY) ---
    db_id: Optional[int] = None
    session_id: Optional[int] = None
    conversation_step: str = "new"
    collected_data: dict = field(default_factory=dict)
    is_reply: bool = False
    is_escalated: bool = False
    is_shopify_form: bool = False
    real_email: Optional[str] = None  # Si rerouted (Shopify form)

    # --- Flow menu ---
    flow_followup: Optional[str] = None  # Message followup à envoyer
    flow_next_step: Optional[str] = None

    # --- Intelligence v4.1 ---
    client_profile: Optional[dict] = None
    urgency_level: Optional[str] = None   # CRITICAL, HIGH, MEDIUM


@dataclass
class Response:
    """Résultat retourné par un handler après traitement."""

    text: str = ""                          # Texte brut de la réponse
    html: str = ""                          # HTML formaté (si déjà construit)
    should_send: bool = True                # Envoyer au client ?
    should_escalate: bool = False           # Escalader vers humain ?
    escalation_reason: str = ""
    category: str = ""
    confidence: float = 0.0
    next_step: str = "closed"              # Prochain step conversation
    update_data: dict = field(default_factory=dict)  # Données à merger dans collected_data
    telegram_message: Optional[str] = None  # Notification admin Telegram
    db_updates: dict = field(default_factory=dict)   # Champs à UPDATE dans processed_emails


@dataclass
class OrderItem:
    """Article d'une commande analysé."""
    title: str = ""
    variant: str = ""
    price: float = 0.0
    quantity: int = 1
    is_short: bool = False
    is_flocked: bool = False
    is_refundable: bool = False
    flocage_details: str = ""
    item_type: str = ""  # "Short" ou "Haut"
