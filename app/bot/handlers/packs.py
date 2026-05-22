from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PacksCB
from app.bot.keyboards.packs import PACK_PAGE_SIZE, pack_browser_kb, pack_groups_kb
from app.bot.menu_nav import send_menu_card
from app.bot.states import InteractionState
from app.bot.texts import (
    PACKS_ADDED_SUMMARY,
    PACKS_GROUPS_TITLE,
    PACKS_NONE_SELECTED,
    PACKS_TITLE,
)
from app.domain.enums import LearningTrack
from app.domain.models import User
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.packs import PackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.analytics import EVENT_PACK_ADDED, Analytics
from app.services.category_service import CategoryService, CategoryServiceError
from app.services.interaction_state_service import InteractionStateService
from app.services.pack_service import PackService

router = Router(name="packs")

_GROUP_ORDER = {"Уровни": 0, "Грамматика": 1, "Темы": 2, "Фразы": 3, "Экзамены": 4}


def _selected(payload) -> set[int]:
    return {int(x) for x in (payload.data or {}).get("selected") or []}


async def _groups(user_id: int, track: LearningTrack, session: AsyncSession) -> list[tuple[str, int]]:
    counts = await PackRepository(session).category_counts(track)
    return sorted(counts, key=lambda c: (_GROUP_ORDER.get(c[0], 99), c[0]))


async def _build_cache(category: str, track: LearningTrack, user_id: int, session: AsyncSession) -> list[list]:
    repo = PackRepository(session)
    packs = await repo.list_by_category(track, category)
    stats = await repo.stats_for_user(user_id, track)
    cache: list[list] = []
    for p in packs:
        _owned, mastered = stats.get(p.id, (0, 0))
        pct = round(100 * mastered / p.words_count) if p.words_count else 0
        cache.append([p.id, p.title, p.words_count, pct])
    return cache


def _kb(cache: list[list], selected: set[int], page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(cache) + PACK_PAGE_SIZE - 1) // PACK_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_rows = [
        (int(r[0]), str(r[1]), int(r[2]), int(r[3]))
        for r in cache[page * PACK_PAGE_SIZE : (page + 1) * PACK_PAGE_SIZE]
    ]
    return pack_browser_kb(page_rows, selected, page, total_pages)


# ---- groups (top level) ----


async def open_packs(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    redis: Redis,
) -> None:
    await state_service.clear(user.id)
    await send_menu_card(
        message,
        redis,
        user.id,
        PACKS_GROUPS_TITLE,
        reply_markup=pack_groups_kb(await _groups(user.id, current_track, session)),
    )


@router.callback_query(PacksCB.filter(F.action == "menu"))
async def on_packs_menu(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await query.answer()
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(
            PACKS_GROUPS_TITLE,
            reply_markup=pack_groups_kb(await _groups(user.id, current_track, session)),
        )


@router.callback_query(PacksCB.filter(F.action == "group"))
async def on_group(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await query.answer()
    category = callback_data.category
    cache = await _build_cache(category, current_track, user.id, session)
    await state_service.set(
        user.id,
        InteractionState.PACK_SELECTION,
        {"selected": [], "cache": cache, "category": category},
    )
    if query.message:
        await query.message.edit_text(PACKS_TITLE, reply_markup=_kb(cache, set(), 0))


# ---- checklist (within a group) ----


async def _cached(query, user, current_track, session, state_service) -> tuple[list, set[int]]:
    payload = await state_service.get(user.id)
    data = payload.data or {}
    cache = data.get("cache")
    if not cache and data.get("category"):
        cache = await _build_cache(data["category"], current_track, user.id, session)
        await state_service.update_data(user.id, cache=cache)
    return cache or [], _selected(payload)


@router.callback_query(PacksCB.filter(F.action == "toggle"))
async def on_toggle(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await query.answer()
    cache, selected = await _cached(query, user, current_track, session, state_service)
    pid = callback_data.pack_id
    selected.discard(pid) if pid in selected else selected.add(pid)
    await state_service.update_data(user.id, selected=list(selected))
    if query.message:
        await query.message.edit_reply_markup(reply_markup=_kb(cache, selected, callback_data.page))


@router.callback_query(PacksCB.filter(F.action == "page"))
async def on_page(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await query.answer()
    cache, selected = await _cached(query, user, current_track, session, state_service)
    if query.message:
        await query.message.edit_reply_markup(reply_markup=_kb(cache, selected, callback_data.page))


@router.callback_query(PacksCB.filter(F.action == "reset"))
async def on_reset(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await query.answer()
    cache, _ = await _cached(query, user, current_track, session, state_service)
    await state_service.update_data(user.id, selected=[])
    if query.message:
        await query.message.edit_reply_markup(reply_markup=_kb(cache, set(), 0))


@router.callback_query(PacksCB.filter(F.action == "add"))
async def on_add(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    analytics: Analytics,
) -> None:
    payload = await state_service.get(user.id)
    selected = _selected(payload)
    if not selected:
        await query.answer(PACKS_NONE_SELECTED, show_alert=True)
        return
    await query.answer()

    pack_repo = PackRepository(session)
    cat_repo = CategoryRepository(session)
    cat_service = CategoryService(cat_repo)
    pack_service = PackService(pack_repo, UserWordRepository(session))

    total_added = 0
    packs_done = 0
    for pid in selected:
        pack = await pack_repo.get(pid)
        if pack is None:
            continue
        try:
            track = LearningTrack(pack.track)
        except ValueError:
            track = current_track
        category = await cat_repo.get_by_name(user.id, track, pack.title)
        if category is None:
            try:
                category = await cat_service.create(user.id, track, pack.title)
            except CategoryServiceError:
                category = await cat_repo.get_by_name(user.id, track, pack.title)
        category_id = category.id if category else None
        result = await pack_service.add_pack(user.id, track, pid, category_id)
        total_added += result.added
        packs_done += 1
        await analytics.emit(
            EVENT_PACK_ADDED, user_id=user.id, track=track.value, pack_id=pid, added=result.added
        )

    await state_service.clear(user.id)
    # Back to the groups list (with the summary on top) so the user can keep
    # browsing other sections instead of being dropped out of the flow.
    if query.message:
        summary = PACKS_ADDED_SUMMARY.format(added=total_added, packs=packs_done)
        await query.message.edit_text(
            f"{summary}\n\n{PACKS_GROUPS_TITLE}",
            reply_markup=pack_groups_kb(await _groups(user.id, current_track, session)),
        )
