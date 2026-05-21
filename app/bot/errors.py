from __future__ import annotations

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

from app.bot.texts import GENERIC_ERROR
from app.logging_setup import get_logger

log = get_logger("errors")


async def on_unhandled_error(event: ErrorEvent) -> bool:
    """Last-resort handler: log the exception and show the user a soft message.

    Never leaks tracebacks to the user. Returning True marks the error handled
    so aiogram doesn't re-raise and kill the polling loop.
    """
    update = event.update
    log.error(
        "unhandled_exception",
        exc_info=event.exception,
        update_id=getattr(update, "update_id", None),
    )

    try:
        if update.callback_query is not None:
            await update.callback_query.answer(GENERIC_ERROR, show_alert=False)
            if update.callback_query.message is not None:
                # best-effort: don't crash if the message can't be edited
                pass
        elif update.message is not None:
            await update.message.answer(GENERIC_ERROR)
    except Exception:  # noqa: BLE001 — notifying the user must never raise
        log.warning("error_notify_failed", update_id=getattr(update, "update_id", None))

    return True


def register_error_handler(dp: Dispatcher) -> None:
    dp.errors.register(on_unhandled_error)
