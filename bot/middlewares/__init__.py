from aiogram import Dispatcher

from bot.middlewares.consent import ConsentMiddleware


def register_middlewares(dispatcher: Dispatcher) -> None:
    """Register project middlewares in one place."""
    consent = ConsentMiddleware()
    dispatcher.message.outer_middleware(consent)
    dispatcher.callback_query.outer_middleware(consent)
    dispatcher.guest_message.outer_middleware(consent)
