"""
OKTAGON SAV v11.0 — Point d'entrée principal
Monte le pipeline, connecte tout, lance le polling.
"""
import asyncio
import signal
import sys
import os

from dotenv import load_dotenv
load_dotenv()

# Sentry APRÈS load_dotenv pour avoir les env vars
from sentry_init import init_sentry
init_sentry()

from config import config
from logger import logger
from storage.database import Database
from storage.repos import Repos
from storage.schema import run_migration, run_migration_v41, run_migration_v50, run_migration_v105
from connectors.ecommerce.shopify import ShopifyConnector
from connectors.channels.email import EmailConnector
from connectors.ai.claude import ClaudeConnector
from tenants.registry import TenantRegistry
from core.pipeline import Pipeline
from workers.polling import polling_loop
from workers.followup import followup_loop
from workers.recovery import recover_pending
from workers.notifier import TelegramNotifier
from security import security_check
from dashboard import app as dashboard_app, init_dashboard


async def main():
    """Initialise tout et lance le service."""
    logger.info('═══ OKTAGON SAV v11.0 — DÉMARRAGE ═══', extra={'action': 'startup'})

    # ── 1. Base de données ──
    db = Database()
    await db.connect(
        host=config.database.host,
        port=config.database.port,
        database=config.database.database,
        user=config.database.user,
        password=config.database.password,
        pool_min=config.database.pool_min,
        pool_max=config.database.pool_max
    )

    # Migration (crée table tenants + ajoute tenant_id si besoin)
    await run_migration(db)
    await run_migration_v41(db)
    await run_migration_v50(db)
    await run_migration_v105(db)

    # ── 2. Repos ──
    repos = Repos(db)

    # ── 3. Tenant registry ──
    registry = TenantRegistry(db)
    tenants = await registry.get_all_active()

    if not tenants:
        logger.warning('Aucun tenant actif trouvé — vérifier la table tenants',
                       extra={'action': 'no_tenants'})
        # Fallback : créer pipeline OKTAGON depuis config.py
        from tenants.models import TenantConfig
        oktagon = TenantConfig(
            id='oktagon',
            name='OKTAGON',
            ecommerce_type='shopify',
            ecommerce_config={
                'store': config.shopify.store,
                'client_id': config.shopify.client_id,
                'client_secret': config.shopify.client_secret,
                'api_version': config.shopify.api_version
            },
            channel_type='email',
            channel_config={
                'address': config.gmail.address,
                'password': config.gmail.password,
                'imap_host': 'imap.gmail.com',
                'smtp_host': 'smtp.gmail.com'
            },
            ai_type='claude',
            ai_config={
                'api_key': config.claude.api_key,
                'model': config.claude.model,
                'max_tokens': config.claude.max_tokens,
                'temperature': config.claude.temperature
            },
            telegram_config={
                'bot_token': config.telegram.bot_token,
                'admin_chat_id': config.telegram.admin_chat_id,
                'usine_bot_token': config.telegram.usine_bot_token,
                'usine_chat_id': config.telegram.usine_chat_id
            },
            auto_categories=['QUESTION_PRODUIT', 'LIVRAISON'],
            confidence_threshold=config.agent.confidence_threshold,
            autonomy_level=config.agent.autonomy_level,
            max_emails_per_hour=config.security.anti_spam_max_per_client_hour,
            max_emails_per_day=100,
            brand_name='OKTAGON',
            brand_color='#F0FF27',
            brand_tagline='Équipement sport de combat',
            custom_rules={
                'website': 'oktagon-shop.com',
                'instagram': '@oktagon_officiel'
            },
            blocked_emails=[]
        )
        tenants = [oktagon]

    # ── 4. Créer un pipeline par tenant ──
    pipelines = []
    for tenant in tenants:
        # Connecteurs — secrets depuis .env si pas dans le tenant DB
        ecommerce = ShopifyConnector(
            store=tenant.ecommerce_config.get('store') or config.shopify.store,
            client_id=tenant.ecommerce_config.get('client_id') or config.shopify.client_id,
            client_secret=tenant.ecommerce_config.get('client_secret') or config.shopify.client_secret,
            api_version=tenant.ecommerce_config.get('api_version') or config.shopify.api_version
        )

        channel = EmailConnector(
            address=tenant.channel_config.get('address') or config.gmail.address,
            password=tenant.channel_config.get('password') or config.gmail.password,
            imap_host=tenant.channel_config.get('imap_host', 'imap.gmail.com'),
            smtp_host=tenant.channel_config.get('smtp_host', 'smtp.gmail.com')
        )

        ai = ClaudeConnector(
            api_key=tenant.ai_config.get('api_key') or config.claude.api_key,
            model=tenant.ai_config.get('model') or config.claude.model,
            max_tokens=tenant.ai_config.get('max_tokens') or config.claude.max_tokens,
            temperature=tenant.ai_config.get('temperature') or config.claude.temperature
        )

        # Notifier Telegram
        notifier = None
        if tenant.telegram_config.get('bot_token') and tenant.telegram_config.get('admin_chat_id'):
            tg = TelegramNotifier(
                bot_token=tenant.telegram_config['bot_token'],
                chat_id=tenant.telegram_config['admin_chat_id']
            )
            notifier = tg.send

        # Pipeline
        pipeline = Pipeline(
            tenant=tenant,
            repos=repos,
            ecommerce=ecommerce,
            channel=channel,
            ai=ai,
            notifier=notifier,
            security_check_fn=security_check,
        )
        pipelines.append(pipeline)
        logger.info(f'Pipeline créé pour tenant: {tenant.name}',
                    extra={'action': 'pipeline_created', 'tenant': tenant.id})

    # ── 5. Dashboard (initialisé pour chaque tenant) ──
    for pipeline in pipelines:
        init_dashboard(
            db=db,
            repos=repos,
            shopify_connector=pipeline.ecommerce,
            email_connector=pipeline.channel,
            claude_connector=pipeline.ai,
            config=config,
            tenant_id=pipeline.tenant.id
        )
    app = dashboard_app

    # ── 6. Lancer le polling pour chaque pipeline ──
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f'Signal {sig} reçu — arrêt propre', extra={'action': 'shutdown'})
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Recovery au démarrage
    for pipeline in pipelines:
        await recover_pending(pipeline)

    # Polling tasks
    tasks = []
    for pipeline in pipelines:
        task = asyncio.create_task(
            polling_loop(pipeline, interval=30, shutdown_event=shutdown_event)
        )
        tasks.append(task)

        # v7.0 — Worker de suivi (tickets ouverts, fermeture auto, rapport quotidien)
        followup_task = asyncio.create_task(
            followup_loop(
                db, pipeline.tenant.id,
                pipeline.notifier, shutdown_event,
                repos=repos
            )
        )
        tasks.append(followup_task)

    # Dashboard task (uvicorn)
    import uvicorn
    uvi_config = uvicorn.Config(app, host='0.0.0.0', port=config.server.port, log_level='warning')
    server = uvicorn.Server(uvi_config)
    tasks.append(asyncio.create_task(server.serve()))

    logger.info(
        f'═══ SERVICE PRÊT ═══ | {len(pipelines)} tenant(s) | Dashboard :{config.server.port}',
        extra={'action': 'ready'}
    )

    # Attendre shutdown
    await shutdown_event.wait()

    # Cleanup
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await db.close()
    logger.info('═══ SERVICE ARRÊTÉ ═══', extra={'action': 'shutdown_complete'})


if __name__ == '__main__':
    asyncio.run(main())
