"""
OKTAGON SAV v11.0 — Connecteur Shopify
Implémente EcommerceConnector pour l'API Shopify.
Authentification OAuth2 (client_credentials → access_token).
"""
import time
import httpx
from typing import Optional

# v6.0 — Circuit breaker integration
from core.circuit_breaker import shopify_circuit, CircuitBreakerOpenError
from core.retry import retry_async, SHOPIFY_RETRY_CONFIG
from core.metrics import metrics

from connectors.ecommerce.base import EcommerceConnector
from logger import logger


class ShopifyConnector(EcommerceConnector):
    """Connecteur Shopify REST API avec OAuth2."""

    def __init__(self, store: str, client_id: str, client_secret: str, api_version: str = '2025-01'):
        self.store = store
        self.base_url = f"https://{store}/admin/api/{api_version}"
        self.client_id = client_id
        self.client_secret = client_secret
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _get_token(self) -> str:
        """Obtenir token OAuth2 avec cache (expire toutes les 30 min)."""
        now = time.time()
        if self._cached_token and now < self._token_expires_at:
            return self._cached_token

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://{self.store}/admin/oauth/access_token",
                    json={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials"
                    }
                )
                token = resp.json().get("access_token", "")
                if token:
                    self._cached_token = token
                    self._token_expires_at = now + 1800  # 30 minutes
                    logger.info("Shopify token rafraîchi",
                                extra={"action": "shopify_token_refresh"})
                else:
                    logger.error(f"Shopify token vide — réponse: {resp.text[:200]}",
                                 extra={"action": "shopify_token_error"})
                return token
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify token erreur: {e}",
                         extra={"action": "shopify_token_error"})
            return ""

    async def _headers(self) -> dict:
        """Headers avec token OAuth2."""
        token = await self._get_token()
        return {"X-Shopify-Access-Token": token}

    async def get_order(self, order_number: str) -> Optional[dict]:
        """Cherche une commande par son numéro (ex: '8418')."""
        # v6.0 — Circuit breaker + retry protection
        try:
            return await shopify_circuit.call(
                retry_async,
                self._get_order_internal,
                order_number,
                config=SHOPIFY_RETRY_CONFIG
            )
        except CircuitBreakerOpenError as e:
            logger.error(f"Shopify circuit breaker OPEN: {e}")
            metrics.record_shopify_call(success=False)
            return None

    async def _get_order_internal(self, order_number: str) -> Optional[dict]:
        try:
            headers = await self._headers()
            if not headers.get("X-Shopify-Access-Token"):
                logger.error("Shopify: pas de token, impossible de chercher commande",
                             extra={"action": "shopify_error"})
                return None

            async with httpx.AsyncClient(timeout=15) as client:
                # Essai avec #
                resp = await client.get(
                    f"{self.base_url}/orders.json",
                    params={"name": f"#{order_number}", "status": "any"},
                    headers=headers
                )
                if resp.status_code != 200:
                    logger.error(f"Shopify API {resp.status_code}: {resp.text[:200]}",
                                 extra={"action": "shopify_error"})
                    return None

                orders = resp.json().get("orders", [])

                # Fallback sans #
                if not orders:
                    resp2 = await client.get(
                        f"{self.base_url}/orders.json",
                        params={"name": order_number, "status": "any"},
                        headers=headers
                    )
                    if resp2.status_code == 200:
                        orders = resp2.json().get("orders", [])

                if not orders:
                    logger.warning(f"Commande #{order_number} non trouvée dans Shopify",
                                   extra={"action": "shopify_order_not_found"})
                    return None

                return self._format_order(orders[0])
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify get_order erreur: {e}",
                         extra={"action": "shopify_error"})
            return None

    def _format_order(self, order: dict) -> dict:
        """Formate un order Shopify brut en dict standardisé.
        FILTRE les données internes Shopify pour ne garder que l'utile."""
        tracking_numbers = []
        tracking_urls = []
        for f in order.get("fulfillments", []):
            tn = f.get("tracking_number")
            if tn:
                tracking_numbers.append(tn)
            tu = f.get("tracking_url")
            if tu:
                tracking_urls.append(tu)

        shipping = order.get("shipping_address") or {}
        address_str = ""
        if shipping:
            parts = [
                shipping.get("address1", ""),
                shipping.get("address2", ""),
                shipping.get("zip", ""),
                shipping.get("city", ""),
                shipping.get("country", "")
            ]
            address_str = ", ".join(p for p in parts if p)

        line_items = []
        for li in order.get("line_items", []):
            price = float(li.get("price", "0") or "0")

            # FILTRER les articles gratuits (e-books, cadeaux) — ne pas les montrer au cerveau
            if price == 0:
                continue

            # FILTRER les propriétés internes Shopify (commencent par _)
            clean_properties = []
            for prop in li.get("properties", []):
                prop_name = str(prop.get("name", ""))
                prop_value = str(prop.get("value", "")).strip()
                # Ignorer les props internes (_esid, _moonBundleCart, __upcart*)
                if prop_name.startswith("_") or prop_name.startswith("__"):
                    continue
                # Ignorer les props sans valeur
                if not prop_value:
                    continue
                clean_properties.append(prop)

            # Nettoyer variant_title (enlever None)
            variant = li.get("variant_title") or ""

            line_items.append({
                "title": li.get("title", ""),
                "quantity": li.get("quantity", 1),
                "price": li.get("price", "0"),
                "variant_title": variant,
                "properties": clean_properties
            })

        customer = order.get("customer") or {}

        # Nettoyer le nom client (Shopify met parfois 'None' comme prénom)
        first = customer.get('first_name') or ''
        last = customer.get('last_name') or ''
        if first.lower() == 'none':
            first = ''
        if last.lower() == 'none':
            last = ''
        customer_name = f"{first} {last}".strip()

        # Utiliser le total réel de la commande (inclut les promos)
        # C'est le prix que le client a PAYÉ, pas la somme des articles
        return {
            "order_number": order.get("name", ""),
            "customer_name": customer_name,
            "customer_email": (order.get("email") or customer.get("email") or "").lower(),
            "fulfillment_status": order.get("fulfillment_status"),
            "financial_status": order.get("financial_status"),
            "total_price": order.get("total_price", "0"),
            "currency": order.get("currency", "EUR"),
            "shipping_address": address_str,
            "tracking_numbers": tracking_numbers,
            "tracking_urls": tracking_urls,
            "line_items": line_items,
            "created_at": order.get("created_at", ""),
            "discount_codes": [d.get("code", "") for d in order.get("discount_codes", []) if d.get("code")],
        }

    async def get_orders_by_email(self, email: str, limit: int = 5) -> list:
        """Récupère les dernières commandes d'un client par email."""
        try:
            headers = await self._headers()
            if not headers.get("X-Shopify-Access-Token"):
                return []

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/orders.json",
                    params={"email": email, "status": "any", "limit": limit},
                    headers=headers
                )
                if resp.status_code != 200:
                    logger.error(f"Shopify orders_by_email {resp.status_code}",
                                 extra={"action": "shopify_error"})
                    return []
                orders = resp.json().get("orders", [])
                return [self._format_order(o) for o in orders]
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify get_orders_by_email erreur: {e}",
                         extra={"action": "shopify_error"})
            return []

    async def get_customer(self, email: str) -> Optional[dict]:
        """Récupère les infos client par email."""
        try:
            headers = await self._headers()
            if not headers.get("X-Shopify-Access-Token"):
                return None

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/customers/search.json",
                    params={"query": f"email:{email}"},
                    headers=headers
                )
                if resp.status_code != 200:
                    return None
                customers = resp.json().get("customers", [])
                if not customers:
                    return None
                c = customers[0]
                return {
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                    "email": c.get("email", ""),
                    "orders_count": c.get("orders_count", 0),
                    "total_spent": c.get("total_spent", "0")
                }
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify get_customer erreur: {e}",
                         extra={"action": "shopify_error"})
            return None

    async def search_orders_by_name(self, first_name: str, last_name: str) -> list:
        """v7.3 — Recherche commandes par nom+prénom quand email introuvable."""
        try:
            headers = await self._headers()
            if not headers.get("X-Shopify-Access-Token"):
                return []

            async with httpx.AsyncClient(timeout=15) as client:
                # Chercher le client par nom
                query = f"{first_name} {last_name}".strip()
                resp = await client.get(
                    f"{self.base_url}/customers/search.json",
                    params={"query": query, "limit": 5},
                    headers=headers
                )
                if resp.status_code != 200:
                    return []
                customers = resp.json().get("customers", [])
                if not customers:
                    return []

                # Pour chaque client trouvé, récupérer ses commandes
                results = []
                for c in customers:
                    cn = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip().lower()
                    qn = query.lower()
                    # Vérifier que le nom correspond vraiment
                    if cn and qn and (qn in cn or cn in qn):
                        cust_id = c.get("id")
                        if cust_id:
                            resp2 = await client.get(
                                f"{self.base_url}/orders.json",
                                params={"customer_id": cust_id, "status": "any", "limit": 5},
                                headers=headers
                            )
                            if resp2.status_code == 200:
                                for order in resp2.json().get("orders", []):
                                    results.append(self._format_order(order))
                return results
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify search_orders_by_name erreur: {e}",
                         extra={"action": "shopify_error"})
            return []

    async def search_by_confirmation(self, confirmation_number: str) -> dict:
        """v8.2 — Recherche commande par numéro de confirmation avec PAGINATION."""
        try:
            headers = await self._headers()
            if not headers.get("X-Shopify-Access-Token"):
                return None

            from datetime import datetime, timedelta
            since = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")

            async with httpx.AsyncClient(timeout=30) as client:
                since_id = 0
                pages = 0
                max_pages = 5  # Max 5 pages x 250 = 1250 commandes

                while pages < max_pages:
                    params = {
                        "status": "any", "limit": 250,
                        "created_at_min": since, "since_id": since_id
                    }
                    resp = await client.get(
                        f"{self.base_url}/orders.json",
                        params=params, headers=headers
                    )
                    if resp.status_code != 200:
                        return None

                    orders = resp.json().get("orders", [])
                    if not orders:
                        break

                    for order in orders:
                        if order.get("confirmation_number") == confirmation_number:
                            formatted = self._format_order(order)
                            formatted["confirmation_number"] = order.get("confirmation_number")
                            return formatted

                    # Page suivante
                    since_id = orders[-1].get("id", 0)
                    pages += 1

                    if len(orders) < 250:
                        break  # Dernière page

                return None
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify search_by_confirmation erreur: {e}",
                         extra={"action": "shopify_error"})
            return None

    async def search_by_amount(self, amount: str, email: str = None) -> list:
        """v8.2 — Recherche commandes par montant payé avec PAGINATION."""
        try:
            headers = await self._headers()
            if not headers.get("X-Shopify-Access-Token"):
                return []

            target = float(amount.replace(",", ".").replace("€", "").strip())

            async with httpx.AsyncClient(timeout=30) as client:
                from datetime import datetime, timedelta
                since = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")

                # Si email fourni, pas besoin de pagination (peu de résultats)
                if email:
                    resp = await client.get(
                        f"{self.base_url}/orders.json",
                        params={"status": "any", "limit": 20, "email": email},
                        headers=headers
                    )
                    if resp.status_code != 200:
                        return []
                    results = []
                    for order in resp.json().get("orders", []):
                        order_total = float(order.get("total_price", "0"))
                        if abs(order_total - target) <= 1.0:
                            results.append(self._format_order(order))
                    return results

                # Sans email : pagination
                results = []
                since_id = 0
                pages = 0
                max_pages = 5

                while pages < max_pages:
                    params = {
                        "status": "any", "limit": 250,
                        "created_at_min": since, "since_id": since_id
                    }
                    resp = await client.get(
                        f"{self.base_url}/orders.json",
                        params=params, headers=headers
                    )
                    if resp.status_code != 200:
                        break

                    orders = resp.json().get("orders", [])
                    if not orders:
                        break

                    for order in orders:
                        order_total = float(order.get("total_price", "0"))
                        if abs(order_total - target) <= 1.0:
                            results.append(self._format_order(order))

                    since_id = orders[-1].get("id", 0)
                    pages += 1

                    if len(orders) < 250:
                        break

                return results
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Shopify search_by_amount erreur: {e}",
                         extra={"action": "shopify_error"})
            return []
