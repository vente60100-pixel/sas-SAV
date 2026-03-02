"""
OKTAGON SAV v5.0 — Handler Registry (simplifié)
Plus que 2 handlers pour les steps intermédiaires.
Tout le reste est géré par le cerveau unifié.
"""
from handlers.address import handle_address_confirmation
from handlers.cancellation import handle_return_tracking


# Steps intermédiaires (suite de conversation multi-tour)
STEP_HANDLERS = {
    'step4_confirm_address': handle_address_confirmation,
    'step5_return_tracking': handle_return_tracking,
}


def get_step_handler(step: str):
    """Retourne le handler pour un step intermédiaire."""
    return STEP_HANDLERS.get(step)
