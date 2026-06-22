from aiogram import Router

from bot.handlers.admin import router as admin_router
from bot.handlers.common import router as common_router
from bot.handlers.consent import router as consent_router
from bot.handlers.language import router as language_router
from bot.handlers.start import router as start_router

routers: tuple[Router, ...] = (
    admin_router,
    consent_router,
    language_router,
    start_router,
    common_router,
)
