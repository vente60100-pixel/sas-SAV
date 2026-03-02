"""
OKTAGON SAV v6.0 — Validators
Validation stricte des réponses IA pour garantir la cohérence.

Principe : L'IA peut générer n'importe quoi, on vérifie TOUT.
"""
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator, ValidationError
from logger import logger


# v6.0 — Custom exception for validation errors
class AIResponseValidationError(Exception):
    """Raised when AI response validation fails."""
    pass



# ═══════════════════════════════════════════════════════════
# SCHEMAS PYDANTIC — Structure obligatoire des réponses IA
# ═══════════════════════════════════════════════════════════

class AIResponseSchema(BaseModel):
    """Schema de validation pour les réponses du cerveau IA."""
    
    category: str = Field(..., description="Catégorie du ticket")
    response: str = Field(..., min_length=10, description="Réponse au client")
    action: str = Field(..., description="Action à effectuer")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Score de confiance")
    needs_order_number: bool = Field(default=False)
    summary: str = Field(default="", max_length=500)
    
    @validator('category')
    def validate_category(cls, v):
        """Valide que la catégorie est reconnue."""
        valid_categories = {
            'LIVRAISON', 'COMMANDE', 'RETOUR', 'PERSONNALISATION',
            'PRODUIT', 'PAIEMENT', 'AUTRE', 'PRE_ACHAT'
        }
        v_upper = v.upper()
        if v_upper not in valid_categories:
            logger.warning(f"⚠️ Catégorie invalide : {v} → AUTRE")
            return "AUTRE"
        return v_upper
    
    @validator('action')
    def validate_action(cls, v):
        """Valide que l'action est reconnue."""
        valid_actions = {
            'send', 'send_and_escalate', 'escalate', 'ignore'
        }
        if v not in valid_actions:
            logger.warning(f"⚠️ Action invalide : {v} → send_and_escalate")
            return "send_and_escalate"
        return v
    
    @validator('response')
    def validate_response_content(cls, v):
        """Valide le contenu de la réponse."""
        # Ne doit pas être vide ou juste des espaces
        if not v or not v.strip():
            raise ValueError("Réponse vide détectée")
        
        # Ne doit pas contenir de placeholder non remplacé
        placeholders = re.findall(r'\{\{.*?\}\}|\[.*?\]|XXX|TODO', v, re.IGNORECASE)
        if placeholders:
            raise ValueError(f"Placeholders non remplacés détectés : {placeholders}")
        
        # Doit contenir une signature
        if "L'équipe" not in v and "Cordialement" not in v:
            logger.warning("⚠️ Pas de signature détectée dans la réponse IA")
        
        return v.strip()


# ═══════════════════════════════════════════════════════════
# VALIDATEURS MÉTIER
# ═══════════════════════════════════════════════════════════

class ResponseValidator:
    """Validateur avancé des réponses IA avec règles métier."""
    
    @staticmethod
    def validate_ai_response(raw_response: dict) -> Dict[str, Any]:
        """
        Valide une réponse brute de l'IA et la normalise.
        
        Args:
            raw_response: Dict brut retourné par l'IA
            
        Returns:
            Dict validé et normalisé
            
        Raises:
            ValidationError: Si la réponse est invalide
        """
        try:
            # Validation Pydantic
            validated = AIResponseSchema(**raw_response)
            return validated.dict()
            
        except ValidationError as e:
            logger.error(
                f"❌ Validation IA échouée : {e}",
                extra={"action": "validation_failed", "errors": str(e)}
            )
            
            # Fallback : créer une réponse d'escalade
            return {
                "category": "AUTRE",
                "response": "",
                "action": "escalate",
                "confidence": 0.0,
                "needs_order_number": False,
                "summary": f"Validation échouée : {str(e)[:100]}"
            }
    
    @staticmethod
    def check_response_sanity(response_text: str, ticket_data: dict) -> tuple[bool, Optional[str]]:
        """
        Vérifie la cohérence de la réponse avec les données du ticket.
        
        Returns:
            (is_valid, error_message)
        """
        # 1. Vérifier que le numéro de commande mentionné existe
        mentioned_orders = re.findall(r'#?(\d{4,5})', response_text)
        if mentioned_orders and ticket_data.get('order_details'):
            real_order = str(ticket_data['order_details'].get('order_number', ''))
            for mentioned in mentioned_orders:
                if mentioned != real_order:
                    return False, f"Numéro de commande incohérent : #{mentioned} vs #{real_order}"
        
        # 2. Vérifier qu'on ne promet pas un délai impossible
        if 'livraison' in response_text.lower():
            impossible_delays = re.findall(r'(\d+)\s*(heure|jour)(?!s ouvrés)', response_text, re.IGNORECASE)
            for delay, unit in impossible_delays:
                if int(delay) < 5 and unit == 'jour':
                    return False, f"Délai impossible promis : {delay} {unit}"
        
        # 3. Vérifier qu'on ne donne pas d'info sur un mauvais pays
        if ticket_data.get('order_details', {}).get('shipping_address'):
            country = ticket_data['order_details']['shipping_address'].get('country', '')
            # Liste de pays à ne pas confondre
            sensitive_countries = ['Maroc', 'Algérie', 'Tunisie', 'France', 'Palestine']
            for sc in sensitive_countries:
                if sc.lower() in response_text.lower() and sc != country:
                    logger.warning(f"⚠️ Mention pays {sc} alors que client est en {country}")
        
        # 4. Vérifier qu'on ne donne pas de numéro de tracking invalide
        tracking_pattern = r'[A-Z0-9]{10,20}'
        mentioned_tracking = re.findall(tracking_pattern, response_text)
        if mentioned_tracking and ticket_data.get('order_details', {}).get('tracking_number'):
            real_tracking = ticket_data['order_details']['tracking_number']
            for mt in mentioned_tracking:
                if mt != real_tracking and len(mt) > 8:
                    return False, f"Numéro de tracking incohérent : {mt}"
        
        return True, None
    
    @staticmethod
    def detect_forbidden_content(response_text: str) -> tuple[bool, Optional[str]]:
        """
        Détecte du contenu interdit dans la réponse.
        
        Returns:
            (is_forbidden, reason)
        """
        # Liste de contenu absolument interdit
        forbidden_patterns = [
            (r'remboursement\s+immédiat', "Remboursement immédiat promis sans validation"),
            (r'retour\s+gratuit', "Retour gratuit promis (politique = client paie)"),
            (r'(livraison|expédition)\s+en\s+\d+\s+heures', "Délai de livraison irréaliste"),
            (r'(usine|fabrication|chine|fournisseur)', "Mention de l'usine/fabrication"),
            (r'(excuse|désolé|pardon).*bug', "Admission de bug technique"),
            (r'(code\s+promo|réduction).*\d+%', "Réduction non autorisée promise"),
        ]
        
        for pattern, reason in forbidden_patterns:
            if re.search(pattern, response_text, re.IGNORECASE):
                logger.error(
                    f"🚫 Contenu interdit détecté : {reason}",
                    extra={"action": "forbidden_content", "pattern": pattern}
                )
                return True, reason
        
        return False, None


# ═══════════════════════════════════════════════════════════
# FONCTION PRINCIPALE D'EXPORT
# ═══════════════════════════════════════════════════════════

def validate_and_sanitize_response(raw_response: dict, ticket_data: dict) -> dict:
    """
    Pipeline de validation complète d'une réponse IA.
    
    Args:
        raw_response: Réponse brute de l'IA
        ticket_data: Données du ticket pour validation croisée
        
    Returns:
        Réponse validée et sanitizée (ou escalade si invalide)
    """
    # Étape 1 : Validation schema
    validated = ResponseValidator.validate_ai_response(raw_response)
    
    # Si déjà escaladé à cause d'une erreur de validation
    if validated['action'] == 'escalate':
        return validated
    
    # Étape 2 : Vérification sanity
    is_sane, error = ResponseValidator.check_response_sanity(
        validated['response'], 
        ticket_data
    )
    if not is_sane:
        logger.warning(
            f"⚠️ Réponse incohérente : {error}",
            extra={"action": "sanity_check_failed"}
        )
        validated['action'] = 'send_and_escalate'
        validated['summary'] = f"Incohérence détectée : {error}"
    
    # Étape 3 : Détection contenu interdit
    is_forbidden, reason = ResponseValidator.detect_forbidden_content(validated['response'])
    if is_forbidden:
        logger.error(
            f"🚫 Contenu interdit bloqué : {reason}",
            extra={"action": "forbidden_content_blocked"}
        )
        # Bloquer complètement, ne pas envoyer
        validated['action'] = 'escalate'
        validated['response'] = ''
        validated['summary'] = f"Contenu interdit : {reason}"
    
    return validated
