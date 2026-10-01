from __future__ import annotations

from aiogram import Dispatcher

from app.bot.handlers import (
    add_words,
    categories,
    course,
    fallback,
    main_menu,
    my_words,
    onboarding,
    pack_admin,
    packs,
    progress,
    push,
    search,
    settings,
    study,
    txt_import,
)


def register_handlers(dp: Dispatcher) -> None:
    """Register routers in the order that matters for fallback handling."""
    dp.include_router(onboarding.router)
    dp.include_router(main_menu.router)
    dp.include_router(course.router)
    dp.include_router(my_words.router)
    dp.include_router(add_words.router)
    dp.include_router(txt_import.router)
    dp.include_router(categories.router)
    dp.include_router(packs.router)
    dp.include_router(pack_admin.router)
    dp.include_router(study.router)
    dp.include_router(progress.router)
    dp.include_router(search.router)
    dp.include_router(settings.router)
    dp.include_router(push.router)
    dp.include_router(fallback.router)
