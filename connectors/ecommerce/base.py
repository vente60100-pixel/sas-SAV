"""
OKTAGON SAV v4.0 — Interface abstraite E-commerce
Shopify aujourd'hui, WooCommerce/PrestaShop demain.
"""
from abc import ABC, abstractmethod
from typing import Optional


class EcommerceConnector(ABC):
    """Interface pour tout connecteur e-commerce."""

    @abstractmethod
    async def get_order(self, order_number: str) -> Optional[dict]:
        """Récupère les détails d'une commande.
        Retourne dict avec: order_number, customer_name, customer_email,
        fulfillment_status, financial_status, total_price, currency,
        shipping_address, tracking_numbers, tracking_urls, line_items
        Ou None si non trouvée."""
        pass

    @abstractmethod
    async def get_customer(self, email: str) -> Optional[dict]:
        """Récupère les infos client par email.
        Retourne dict avec: name, email, orders_count, total_spent"""
        pass
