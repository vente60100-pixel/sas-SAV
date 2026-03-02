"""
OKTAGON SAV v7.1 — Worker Recovery
Reprend les emails bloqués après un restart.
Utilise pipeline.reprocess() pour sauter le filtre de dédup.
"""
import asyncio
from logger import logger


async def recover_pending(pipeline):
    """Reprend les emails ready_for_ai avec response_sent=false."""
    pending = await pipeline.repos.find_pending_recovery(pipeline.tenant.id)
    if not pending:
        logger.info("Aucun email en attente", extra={"action": "recovery_none"})
        return

    logger.info(f"REPRISE | {len(pending)} emails a retraiter",
                extra={"action": "recovery_start", "count": len(pending)})

    success = 0
    errors = 0
    for row in pending:
        try:
            email_id = row['id']
            logger.info(
                f"REPRISE | {row['email_from']} | {(row['email_subject'] or '')[:40]}",
                extra={"action": "recovery_processing"}
            )
            ok = await pipeline.reprocess(email_id)
            if ok:
                success += 1
            else:
                errors += 1
            # Petit délai pour ne pas surcharger l'API Claude
            await asyncio.sleep(2)
        except Exception as e:
            errors += 1
            logger.error(f"REPRISE ERREUR | {row['id']} | {e}",
                         extra={"action": "recovery_error"})

    logger.info(
        f"REPRISE TERMINEE | {success} OK, {errors} erreurs sur {len(pending)}",
        extra={"action": "recovery_complete", "success": success, "errors": errors}
    )