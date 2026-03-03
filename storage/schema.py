"""
OKTAGON SAV v11.0 — Schema DB avec tenant_id
Migration : ajoute la table tenants + tenant_id sur les tables existantes.
"""
import asyncpg

# ══════════════════════════════════════════════════════════
# TABLES DE BASE (créées avant les migrations)
# ══════════════════════════════════════════════════════════

BASE_TABLES = [
    """CREATE TABLE IF NOT EXISTS processed_emails (
        id SERIAL PRIMARY KEY,
        email_hash TEXT UNIQUE,
        email_from TEXT NOT NULL,
        email_subject TEXT,
        email_body_preview TEXT,
        language TEXT DEFAULT 'fr',
        has_attachments BOOLEAN DEFAULT false,
        attachment_count INTEGER DEFAULT 0,
        conversation_step TEXT DEFAULT 'step1_category',
        collected_data JSONB DEFAULT '{}',
        category TEXT,
        message_id TEXT,
        parent_email_id INTEGER,
        response_sent BOOLEAN DEFAULT false,
        rerouted_from TEXT,
        response_text TEXT,
        email_to TEXT,
        brain_category TEXT,
        brain_confidence NUMERIC,
        detection_method TEXT,
        processing_time_ms INTEGER,
        urgency_level TEXT,
        response_quality TEXT,
        satisfaction_score NUMERIC,
        satisfaction_source TEXT,
        client_reply_sentiment TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS escalations (
        id SERIAL PRIMARY KEY,
        email_id INTEGER,
        email_from TEXT NOT NULL,
        category TEXT,
        reason TEXT,
        subject TEXT,
        resolved BOOLEAN DEFAULT false,
        admin_action TEXT,
        admin_response TEXT,
        resolved_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS cancellations (
        id SERIAL PRIMARY KEY,
        email_from TEXT NOT NULL,
        order_number TEXT,
        email_id INTEGER,
        escalation_id INTEGER,
        fulfillment_status TEXT,
        items_json JSONB DEFAULT '[]',
        refundable_amount NUMERIC DEFAULT 0,
        non_refundable_amount NUMERIC DEFAULT 0,
        case_type TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS address_changes (
        id SERIAL PRIMARY KEY,
        email_id INTEGER,
        escalation_id INTEGER,
        email_from TEXT NOT NULL,
        order_number TEXT,
        old_address TEXT,
        new_address TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS returns_tracking (
        id SERIAL PRIMARY KEY,
        email_from TEXT NOT NULL,
        order_number TEXT,
        tracking_number TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS outgoing_emails (
        id SERIAL PRIMARY KEY,
        email_to TEXT NOT NULL,
        email_type TEXT DEFAULT 'auto',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS usine_requests (
        id SERIAL PRIMARY KEY,
        email_from TEXT,
        request_type TEXT,
        details JSONB DEFAULT '{}',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS auto_replies (
        id SERIAL PRIMARY KEY,
        email_from TEXT,
        email_to TEXT,
        subject TEXT,
        body TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS attestations (
        id SERIAL PRIMARY KEY,
        email_from TEXT,
        order_number TEXT,
        attestation_type TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS conversation_history (
        id SERIAL PRIMARY KEY,
        email_from TEXT,
        role TEXT,
        content TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS admin_actions (
        id SERIAL PRIMARY KEY,
        action_type TEXT,
        target_email TEXT,
        details JSONB DEFAULT '{}',
        admin_user TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
]


async def create_base_tables(db):
    """Crée toutes les tables de base (idempotent)."""
    from logger import logger
    for sql in BASE_TABLES:
        await db.execute(sql)
    logger.info("Tables de base créées/vérifiées", extra={"action": "base_tables"})


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
        except asyncpg.PostgresError:  # Column/table may already exist
            pass

    # 4. Migrer les donnees existantes
    for sql in MIGRATE_EXISTING:
        try:
            await db.execute(sql)
        except asyncpg.PostgresError:  # Table may not exist yet
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
        except asyncpg.PostgresError:  # Column/table may already exist
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
    except asyncpg.PostgresError as e:
        logger.warning(f"Migration v5.0 warning: {e}", extra={"action": "migration_v50_warning"})


# === MIGRATION v10.5 — Tables manquantes ===

V105_TICKETS = """
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id),
    email_from TEXT NOT NULL,
    first_email_id INTEGER,
    last_email_id INTEGER,
    subject TEXT,
    category TEXT,
    status TEXT DEFAULT 'open',
    message_count INTEGER DEFAULT 1,
    response_count INTEGER DEFAULT 0,
    last_client_message_at TIMESTAMPTZ,
    last_response_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolution_type TEXT,
    resolution_trigger TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

V105_FEEDBACK_EXAMPLES = """
CREATE TABLE IF NOT EXISTS feedback_examples (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id),
    category TEXT NOT NULL,
    client_message TEXT NOT NULL,
    correct_response TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    quality_score NUMERIC DEFAULT 0.5,
    used_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

V105_TENANT_LEARNING = """
CREATE TABLE IF NOT EXISTS tenant_learning (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id) UNIQUE,
    confidence_threshold NUMERIC DEFAULT 0.85,
    total_responses INTEGER DEFAULT 0,
    positive_responses INTEGER DEFAULT 0,
    negative_responses INTEGER DEFAULT 0,
    last_adjusted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

V105_COLUMNS = [
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS response_text TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS email_to TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS satisfaction_score NUMERIC",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS satisfaction_source TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS client_reply_sentiment TEXT",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS subject TEXT",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS admin_action TEXT",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS admin_response TEXT",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS emotion_detected TEXT",
    "ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS emotion_score NUMERIC",
]


async def run_migration_v105(db):
    """Migration v10.5 — tables tickets, feedback_examples, tenant_learning + colonnes manquantes."""
    from logger import logger
    try:
        await db.execute(V105_TICKETS)
        await db.execute(V105_FEEDBACK_EXAMPLES)
        await db.execute(V105_TENANT_LEARNING)
        for sql in V105_COLUMNS:
            try:
                await db.execute(sql)
            except asyncpg.PostgresError:  # Column/table may already exist
                pass
        # Initialiser tenant_learning pour OKTAGON si pas encore fait
        await db.execute(
            """INSERT INTO tenant_learning (tenant_id) VALUES ('oktagon')
               ON CONFLICT (tenant_id) DO NOTHING"""
        )
        logger.info("Migration v10.5 terminee — tickets, feedback_examples, tenant_learning, colonnes",
                     extra={"action": "migration_v105_complete"})
    except asyncpg.PostgresError as e:
        logger.warning(f"Migration v10.5 warning: {e}", extra={"action": "migration_v105_warning"})
