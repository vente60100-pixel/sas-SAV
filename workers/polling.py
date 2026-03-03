"""
OKTAGON SAV v11.0 — Worker Polling IMAP
Boucle de polling qui fetch les emails et les passe au pipeline.
"""
import asyncio
import traceback
from logger import logger


async def polling_loop(pipeline, interval: int = 30, shutdown_event=None):
    """Boucle principale : fetch emails toutes les N secondes.
    Si shutdown_event est fourni, s'arrête quand il est set.
    """
    logger.info(f'Polling démarré — intervalle {interval}s | tenant={pipeline.tenant.id}',
                extra={'action': 'polling_start'})
    while True:
        if shutdown_event and shutdown_event.is_set():
            logger.info('Polling arrêté — shutdown', extra={'action': 'polling_shutdown'})
            break
        try:
            messages = await pipeline.channel.fetch_messages()
            if messages:
                logger.info(f'{len(messages)} emails récupérés',
                            extra={'action': 'emails_fetched', 'count': len(messages)})
            for msg in messages:
                try:
                    await pipeline.process(msg)
                except Exception as e:
                    logger.error(f'Erreur traitement {msg.sender}: {e}\n{traceback.format_exc()}',
                                 extra={'action': 'process_error'})
        except Exception as e:
            logger.error(f'Erreur polling: {e}', extra={'action': 'polling_error'})
        # Sleep interruptible
        if shutdown_event:
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
                break  # shutdown_event set
            except asyncio.TimeoutError:
                pass  # Timeout = continue polling
        else:
            await asyncio.sleep(interval)
