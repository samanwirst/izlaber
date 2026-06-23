from aiogram import Dispatcher

from bot.middlewares.consent import ConsentMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware


def register_middlewares(dispatcher: Dispatcher) -> None:
    """Register project middlewares in one place."""
    rate_limit = RateLimitMiddleware()
    consent = ConsentMiddleware()
    dispatcher.message.outer_middleware(rate_limit)
    dispatcher.callback_query.outer_middleware(rate_limit)
    dispatcher.guest_message.outer_middleware(rate_limit)
    dispatcher.message.outer_middleware(consent)
    dispatcher.callback_query.outer_middleware(consent)
    dispatcher.guest_message.outer_middleware(consent)
