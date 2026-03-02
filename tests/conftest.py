"""
Pytest configuration et fixtures globales
"""
import pytest
import asyncio
from typing import AsyncGenerator


@pytest.fixture(scope='session')
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_email():
    """Sample customer email for testing"""
    return {
        'from': 'client@example.com',
        'subject': 'Où est ma commande #8650 ?',
        'body': 'Bonjour, je n ai toujours pas reçu ma commande passée il y a 15 jours.'
    }


@pytest.fixture
def sample_order():
    """Sample Shopify order for testing"""
    return {
        'order_number': '8650',
        'total_price': '49.99',
        'fulfillment_status': 'fulfilled',
        'tracking_numbers': ['ABC123456789'],
        'customer_email': 'client@example.com',
        'line_items': [
            {'title': 'Rashguard Noir', 'quantity': 1, 'price': '49.99'}
        ]
    }
