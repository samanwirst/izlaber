from aiogram import Router

from bot.handlers.admin import router as admin_router
from bot.handlers.common import router as common_router
from bot.handlers.start import router as start_router

routers: tuple[Router, ...] = (
    admin_router,
    start_router,
    common_router,
)
