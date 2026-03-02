"""
OKTAGON SAV v4.0 — Schema DB avec tenant_id
Migration : ajoute la table tenants + tenant_id sur les tables existantes.
"""

TENANT_TABLE = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    ecommerce_type TEXT DEFAULT 'shopify',
    ecommerce_config JSONB DEFAULT '{}',
    channel_type TEXT DEFAULT 'email',
    channel_config JSONB DEFAULT '{}',
    ai_type TEXT DEFAULT 'claude',
    ai_config JSONB DEFAULT '{}',
    telegram_config JSONB DEFAULT '{}',
    auto_categories JSONB DEFAULT '["QUESTION_PRODUIT","LIVRAISON"]',
    confidence_threshold NUMERIC DEFAULT 0.90,
    autonomy_level INTEGER DEFAULT 2,
    max_emails_per_hour INTEGER DEFAULT 3,
    max_emails_per_day INTEGER DEFAULT 8,
    brand_name TEXT,
    brand_color TEXT DEFAULT '#F0FF27',
    brand_tagline TEXT,
    product_type TEXT,
    return_address TEXT,
    custom_rules JSONB DEFAULT '{}',
    prompts JSONB DEFAULT '{}',
    email_template TEXT,
    blocked_emails JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

ADD_TENANT_ID = [
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE cancellations ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE address_changes ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE returns_tracking ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE outgoing_emails ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE usine_requests ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE auto_replies ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE attestations ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE conversation_history ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
    "ALTER TABLE admin_actions ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)",
]

# Mettre à jour les données existantes avec tenant_id = 'oktagon'
MIGRATE_EXISTING = [
    "UPDATE processed_emails SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE escalations SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE cancellations SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE address_changes SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE returns_tracking SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE outgoing_emails SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE usine_requests SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE auto_replies SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE attestations SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE conversation_history SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
    "UPDATE admin_actions SET tenant_id = 'oktagon' WHERE tenant_id IS NULL",
]


# INSERT tenant OKTAGON (idempotent)
INSERT_OKTAGON = """
INSERT INTO tenants (id, name, brand_name, brand_color, brand_tagline, product_type, return_address, custom_rules, prompts)
VALUES (
    'oktagon',
    'OKTAGON Shop',
    'OKTAGON',
    '#F0FF27',
    'Equipement sport de combat',
    'sport combat/MMA',
    'OKTAGON, 5 rue des Pierres, 60100 Creil, France',
    '{"website": "oktagon-shop.com", "instagram": "@oktagon_officiel", "flocage_gratuit": true, "delai_jours": "12-15", "short_price": 29.99, "affiliation_link": "https://goaffpro.com/oktagon"}'::jsonb,
    '{}'::jsonb
)
ON CONFLICT (id) DO NOTHING;
"""

async def run_migration(db):
    """Execute la migration v4.0 (idempotente)."""
    from logger import logger

    # 1. Creer la table tenants
    await db.execute(TENANT_TABLE)
    logger.info("Table tenants creee/verifiee", extra={"action": "migration"})

    # 2. Inserer le tenant OKTAGON (AVANT les FK)
    await db.execute(INSERT_OKTAGON)
    logger.info("Tenant OKTAGON insere/verifie", extra={"action": "migration"})

    # 3. Ajouter tenant_id a toutes les tables
    for sql in ADD_TENANT_ID:
        try:
            await db.execute(sql)
        except Exception:
            pass  # Colonne existe deja

    # 4. Migrer les donnees existantes
    for sql in MIGRATE_EXISTING:
        try:
            await db.execute(sql)
        except Exception:
            pass

    logger.info("Migration v4.0 terminee", extra={"action": "migration_complete"})


# === MIGRATION v4.1 — Intelligence & Quality ===
V41_MIGRATIONS = [
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS response_quality TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS urgency_level TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS detection_method TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS brain_category TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS brain_confidence NUMERIC",
]

async def run_migration_v41(db):
    """Migration v4.1 — colonnes intelligence (idempotente)."""
    from logger import logger
    for sql in V41_MIGRATIONS:
        try:
            await db.execute(sql)
        except Exception:
            pass
    logger.info("Migration v4.1 terminee", extra={"action": "migration_v41_complete"})


# === MIGRATION v5.0 — Client Profiles ===
V50_CLIENT_PROFILES = """
CREATE TABLE IF NOT EXISTS client_profiles (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id),
    email TEXT NOT NULL,
    prenom TEXT,
    dernier_ton TEXT,
    derniere_commande TEXT,
    nb_contacts INTEGER DEFAULT 1,
    vip BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);
"""

async def run_migration_v50(db):
    """Migration v5.0 — table client_profiles (idempotente)."""
    from logger import logger
    try:
        await db.execute(V50_CLIENT_PROFILES)
        logger.info("Migration v5.0 terminee — client_profiles", extra={"action": "migration_v50_complete"})
    except Exception as e:
        logger.warning(f"Migration v5.0 warning: {e}", extra={"action": "migration_v50_warning"})
