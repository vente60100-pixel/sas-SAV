"""
OKTAGON SAV v11.0 — Tenant Registry
Charge les tenants depuis la DB, cache en mémoire.
"""
import json
from typing import Optional

from tenants.models import TenantConfig


class TenantRegistry:
    """Registre des tenants avec cache mémoire."""

    def __init__(self, db):
        self.db = db
        self._cache: dict[str, TenantConfig] = {}

    async def get(self, tenant_id: str) -> Optional[TenantConfig]:
        """Récupère un tenant (cache ou DB)."""
        if tenant_id in self._cache:
            return self._cache[tenant_id]
        return await self._load_from_db(tenant_id)

    async def get_all_active(self) -> list[TenantConfig]:
        """Récupère tous les tenants actifs."""
        rows = await self.db.fetch_all(
            "SELECT * FROM tenants WHERE active = true"
        )
        tenants = []
        for row in rows:
            tenant = self._row_to_tenant(row)
            self._cache[tenant.id] = tenant
            tenants.append(tenant)
        return tenants

    async def _load_from_db(self, tenant_id: str) -> Optional[TenantConfig]:
        """Charge un tenant depuis la DB."""
        row = await self.db.fetch_one(
            "SELECT * FROM tenants WHERE id = $1 AND active = true", tenant_id
        )
        if not row:
            return None
        tenant = self._row_to_tenant(row)
        self._cache[tenant_id] = tenant
        return tenant

    def _row_to_tenant(self, row) -> TenantConfig:
        """Convertit une ligne DB en TenantConfig."""
        def _parse_json(val, default=None):
            if default is None:
                default = {}
            if val is None:
                return default
            if isinstance(val, (dict, list)):
                return val
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return default

        return TenantConfig(
            id=row['id'],
            name=row.get('name', ''),
            active=row.get('active', True),
            ecommerce_type=row.get('ecommerce_type', 'shopify'),
            ecommerce_config=_parse_json(row.get('ecommerce_config')),
            channel_type=row.get('channel_type', 'email'),
            channel_config=_parse_json(row.get('channel_config')),
            ai_type=row.get('ai_type', 'claude'),
            ai_config=_parse_json(row.get('ai_config')),
            telegram_config=_parse_json(row.get('telegram_config')),
            auto_categories=_parse_json(row.get('auto_categories'), ['QUESTION_PRODUIT', 'LIVRAISON']),
            confidence_threshold=float(row.get('confidence_threshold', 0.90)),
            autonomy_level=int(row.get('autonomy_level', 2)),
            max_emails_per_hour=int(row.get('max_emails_per_hour', 3)),
            max_emails_per_day=int(row.get('max_emails_per_day', 8)),
            brand_name=row.get('brand_name', ''),
            brand_color=row.get('brand_color', '#F0FF27'),
            brand_tagline=row.get('brand_tagline', ''),
            product_type=row.get('product_type', ''),
            return_address=row.get('return_address', ''),
            custom_rules=_parse_json(row.get('custom_rules')),
            prompts=_parse_json(row.get('prompts')),
            email_template=row.get('email_template', ''),
            blocked_emails=_parse_json(row.get('blocked_emails'), [])
        )

    def invalidate(self, tenant_id: str = None):
        """Invalide le cache (tout ou un tenant)."""
        if tenant_id:
            self._cache.pop(tenant_id, None)
        else:
            self._cache.clear()
