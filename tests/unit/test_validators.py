"""
Tests unitaires pour core/validators.py
Coverage cible : 80%
"""
import pytest
from pydantic import ValidationError
from core.validators import (
    AIResponseSchema,
    ResponseValidator,
    validate_and_sanitize_response,
    AIResponseValidationError
)


class TestAIResponseSchema:
    """Tests pour le schema Pydantic"""
    
    def test_valid_response(self):
        """Schema valide une bonne réponse"""
        data = {
            'category': 'LIVRAISON',
            'response': 'Bonjour, votre commande arrive bientôt. Cordialement',
            'action': 'send',
            'confidence': 0.95,
            'summary': 'Info livraison'
        }
        
        validated = AIResponseSchema(**data)
        assert validated.category == 'LIVRAISON'
        assert validated.action == 'send'
        assert validated.confidence == 0.95
    
    def test_category_normalization(self):
        """Catégorie en minuscule normalisée en majuscule"""
        data = {
            'category': 'livraison',
            'response': 'Test réponse de 10+ caractères',
            'action': 'send',
            'confidence': 0.8
        }
        
        validated = AIResponseSchema(**data)
        assert validated.category == 'LIVRAISON'
    
    def test_invalid_category_defaults_to_autre(self):
        """Catégorie invalide devient AUTRE"""
        data = {
            'category': 'CATEGORIE_INVALIDE',
            'response': 'Test réponse',
            'action': 'send',
            'confidence': 0.5
        }
        
        validated = AIResponseSchema(**data)
        assert validated.category == 'AUTRE'
    
    def test_invalid_action_defaults(self):
        """Action invalide devient send_and_escalate"""
        data = {
            'category': 'AUTRE',
            'response': 'Test réponse',
            'action': 'action_invalide',
            'confidence': 0.5
        }
        
        validated = AIResponseSchema(**data)
        assert validated.action == 'send_and_escalate'
    
    def test_response_too_short_fails(self):
        """Réponse trop courte (<10 chars) échoue"""
        data = {
            'category': 'AUTRE',
            'response': 'Court',
            'action': 'send',
            'confidence': 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            AIResponseSchema(**data)
        assert 'at least 10 characters' in str(exc_info.value)
    
    def test_empty_response_fails(self):
        """Réponse vide échoue"""
        data = {
            'category': 'AUTRE',
            'response': '   ',
            'action': 'send',
            'confidence': 0.5
        }
        
        with pytest.raises(ValidationError):
            AIResponseSchema(**data)
    
    def test_placeholder_detection(self):
        """Détecte placeholders non remplacés"""
        placeholders = [
            'Bonjour {{nom}}, votre commande',
            'Colis [NUMERO] arrive',
            'TODO: ajouter info',
            'XXX temporaire'
        ]
        
        for placeholder_text in placeholders:
            data = {
                'category': 'AUTRE',
                'response': placeholder_text,
                'action': 'send',
                'confidence': 0.5
            }
            
            with pytest.raises(ValidationError):
                AIResponseSchema(**data)
    
    def test_confidence_bounds(self):
        """Confidence doit être entre 0 et 1"""
        # Confidence > 1
        with pytest.raises(ValidationError):
            AIResponseSchema(
                category='AUTRE',
                response='Test réponse',
                action='send',
                confidence=1.5
            )
        
        # Confidence < 0
        with pytest.raises(ValidationError):
            AIResponseSchema(
                category='AUTRE',
                response='Test réponse',
                action='send',
                confidence=-0.1
            )


class TestResponseValidatorSanity:
    """Tests pour check_response_sanity"""
    
    def test_order_number_consistency(self):
        """Vérifie cohérence numéro de commande"""
        response = "Votre commande #8650 arrive bientôt"
        ticket_data = {
            'order_details': {'order_number': '8650'}
        }
        
        is_valid, error = ResponseValidator.check_response_sanity(response, ticket_data)
        assert is_valid is True
        assert error is None
    
    def test_order_number_mismatch(self):
        """Détecte incohérence numéro commande"""
        response = "Votre commande #9999 arrive"
        ticket_data = {
            'order_details': {'order_number': '8650'}
        }
        
        is_valid, error = ResponseValidator.check_response_sanity(response, ticket_data)
        assert is_valid is False
        assert '9999' in error and '8650' in error
    
    def test_impossible_delay_detection(self):
        """Détecte délais impossibles"""
        response = "Livraison garantie en 2 jour"
        ticket_data = {}
        
        is_valid, error = ResponseValidator.check_response_sanity(response, ticket_data)
        assert is_valid is False
        assert 'impossible' in error.lower()
    
    def test_valid_delay_accepted(self):
        """Délai réaliste accepté"""
        response = "Livraison en 12 jours ouvrés"
        ticket_data = {}
        
        is_valid, error = ResponseValidator.check_response_sanity(response, ticket_data)
        assert is_valid is True


class TestResponseValidatorForbidden:
    """Tests pour detect_forbidden_content"""
    
    def test_no_forbidden_content(self):
        """Contenu propre passe"""
        response = "Votre commande arrive dans 12-15 jours. Cordialement"
        
        is_forbidden, reason = ResponseValidator.detect_forbidden_content(response)
        assert is_forbidden is False
        assert reason is None
    
    def test_forbidden_immediate_refund(self):
        """Détecte promesse remboursement immédiat"""
        response = "Nous procédons au remboursement immédiat"
        
        is_forbidden, reason = ResponseValidator.detect_forbidden_content(response)
        assert is_forbidden is True
        assert 'immédiat' in reason.lower()
    
    def test_forbidden_free_return(self):
        """Détecte promesse retour gratuit"""
        response = "Vous pouvez faire un retour gratuit"
        
        is_forbidden, reason = ResponseValidator.detect_forbidden_content(response)
        assert is_forbidden is True
        assert 'gratuit' in reason.lower()
    
    def test_forbidden_factory_mention(self):
        """Détecte mention usine/fabrication"""
        forbidden_words = ['usine', 'fabrication', 'chine', 'fournisseur']
        
        for word in forbidden_words:
            response = f"Le problème vient de l'{word}"
            is_forbidden, reason = ResponseValidator.detect_forbidden_content(response)
            assert is_forbidden is True
    
    def test_forbidden_unrealistic_delivery(self):
        """Détecte délai livraison irréaliste"""
        response = "Livraison en 24 heures"
        
        is_forbidden, reason = ResponseValidator.detect_forbidden_content(response)
        assert is_forbidden is True
        assert 'irréaliste' in reason.lower()


class TestValidateAndSanitize:
    """Tests pour la fonction principale"""
    
    def test_valid_response_passes(self):
        """Réponse valide passe tous les checks"""
        raw_response = {
            'category': 'LIVRAISON',
            'response': 'Bonjour, votre commande #8650 arrive dans 12 jours. Cordialement',
            'action': 'send',
            'confidence': 0.9
        }
        ticket_data = {
            'order_details': {'order_number': '8650'}
        }
        
        result = validate_and_sanitize_response(raw_response, ticket_data)
        
        assert result['action'] == 'send'
        assert result['category'] == 'LIVRAISON'
    
    def test_validation_error_escalates(self):
        """Erreur validation → escalation"""
        raw_response = {
            'category': 'TEST',
            'response': 'X',  # Trop court
            'action': 'send',
            'confidence': 2.0  # Invalide
        }
        ticket_data = {}
        
        result = validate_and_sanitize_response(raw_response, ticket_data)
        
        assert result['action'] == 'escalate'
        assert 'échouée' in result['summary'].lower()
    
    def test_sanity_fail_escalates(self):
        """Échec sanity check → escalation avec warning"""
        raw_response = {
            'category': 'COMMANDE',
            'response': 'Votre commande #9999 arrive bientôt. Cordialement',
            'action': 'send',
            'confidence': 0.8
        }
        ticket_data = {
            'order_details': {'order_number': '8650'}
        }
        
        result = validate_and_sanitize_response(raw_response, ticket_data)
        
        assert result['action'] == 'send_and_escalate'
        assert 'incohérence' in result['summary'].lower()
    
    def test_forbidden_content_blocks(self):
        """Contenu interdit → escalation pure (pas d'envoi)"""
        raw_response = {
            'category': 'RETOUR',
            'response': 'Nous vous offrons un retour gratuit immédiat. Cordialement',
            'action': 'send',
            'confidence': 0.9
        }
        ticket_data = {}
        
        result = validate_and_sanitize_response(raw_response, ticket_data)
        
        assert result['action'] == 'escalate'
        assert result['response'] == ''  # Bloqué
        assert 'interdit' in result['summary'].lower()
