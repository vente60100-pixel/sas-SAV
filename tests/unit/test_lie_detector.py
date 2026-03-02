"""
Tests unitaires pour core/lie_detector.py  
Coverage cible : 100%
"""
import pytest
from core.lie_detector import detect_lies, format_violation_report


class TestDetectLies:
    """Tests pour la détection de mensonges"""
    
    def test_clean_response_no_lies(self):
        """Réponse propre sans mensonges"""
        response = "Bonjour, votre commande a été expédiée le 25/02. Délai estimé : 12-15 jours."
        is_clean, violations = detect_lies(response)
        
        assert is_clean is True
        assert len(violations) == 0
    
    def test_detect_temporal_lies(self):
        """Détecte promesses temporelles impossibles"""
        response = "Nous allons traiter cela aujourd'hui même."
        is_clean, violations = detect_lies(response)
        
        assert is_clean is False
        assert len(violations) == 1
        assert violations[0]['type'] == 'TEMPS_IMPOSSIBLE'
    
    def test_detect_multiple_lies(self):
        """Détecte plusieurs mensonges dans une réponse"""
        response = """
        Je viens de relancer votre dossier en urgence absolue.
        Nous allons vous rembourser immédiatement. 
        Le colis sera renvoyé par Colissimo dans les prochaines heures.
        """
        is_clean, violations = detect_lies(response)
        
        assert is_clean is False
        assert len(violations) >= 6
    
    def test_detect_carrier_mention(self):
        """Détecte mention de transporteur (interdit)"""
        carriers = ['colissimo', 'chronopost', 'dhl', 'fedex']
        
        for carrier in carriers:
            response = f"Votre colis est envoyé par {carrier}."
            is_clean, violations = detect_lies(response)
            
            assert is_clean is False
            assert violations[0]['type'] == 'TRANSPORTEUR'
    
    def test_detect_human_action_lies(self):
        """Détecte actions humaines inventées"""
        lies = [
            "Je viens de contacter le transporteur",
            "Mon responsable va répondre",
            "J'ai transmis à la direction"
        ]
        
        for lie in lies:
            is_clean, violations = detect_lies(lie)
            assert is_clean is False, f"Failed to detect: {lie}"
            assert violations[0]['type'] == 'ACTION_HUMAINE'
    
    def test_detect_refund_promises(self):
        """Détecte promesses de remboursement"""
        promises = [
            "Vous serez remboursé",
            "Remboursement confirmé",
            "Nous avons procédé au remboursement"
        ]
        
        for promise in promises:
            is_clean, violations = detect_lies(promise)
            assert is_clean is False
            assert violations[0]['type'] == 'PROMESSE_REMBOURSEMENT'
    
    def test_case_insensitive(self):
        """Détection insensible à la casse"""
        response_lower = "nous traiterons cela aujourd'hui même"
        response_upper = "NOUS TRAITERONS CELA AUJOURD'HUI MÊME"
        
        _, violations_lower = detect_lies(response_lower)
        _, violations_upper = detect_lies(response_upper)
        
        assert len(violations_lower) > 0
        assert len(violations_upper) > 0


class TestFormatViolationReport:
    """Tests pour le formatage des rapports"""
    
    def test_format_empty_violations(self):
        """Rapport pour liste vide"""
        report = format_violation_report([])
        assert report == "Aucune violation"
    
    def test_format_single_violation(self):
        """Rapport pour une violation"""
        violations = [{
            'type': 'TEMPS_IMPOSSIBLE',
            'phrase': 'aujourd hui',
            'explanation': 'Ne pas promettre',
            'position': 10
        }]
        
        report = format_violation_report(violations)
        assert '1 mensonge(s)' in report
        assert 'TEMPS_IMPOSSIBLE' in report
    
    def test_format_multiple_violations(self):
        """Rapport pour plusieurs violations"""
        violations = [
            {'type': 'TYPE1', 'phrase': 'p1', 'explanation': 'e1', 'position': 0},
            {'type': 'TYPE2', 'phrase': 'p2', 'explanation': 'e2', 'position': 10}
        ]
        
        report = format_violation_report(violations)
        assert '2 mensonge(s)' in report


class TestLieDetectorIntegration:
    """Tests d'intégration avec exemples réels"""
    
    def test_real_good_response(self):
        """Vraie bonne réponse OKTAGON"""
        response = """
        Bonjour,
        
        Votre commande #8650 a été expédiée le 15/02/2026.
        Le délai de livraison est de 12 à 15 jours ouvrés.
        Vous recevrez votre colis d'ici le 05/03/2026.
        
        Vous pouvez suivre votre colis via le lien de suivi.
        
        Cordialement,
        L'équipe OKTAGON
        """
        
        is_clean, violations = detect_lies(response)
        assert is_clean is True
    
    def test_real_bad_response(self):
        """Vraie mauvaise réponse (mensonges multiples)"""
        response = """
        Je viens de contacter Colissimo.
        Votre colis sera livré aujourd'hui même en urgence absolue.
        Si problème, nous vous rembourserons immédiatement.
        Mon responsable va traiter votre dossier dans les prochaines heures.
        """
        
        is_clean, violations = detect_lies(response)
        assert is_clean is False
        assert len(violations) >= 5
