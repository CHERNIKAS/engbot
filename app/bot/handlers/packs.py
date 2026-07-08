from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PacksCB
from app.bot.keyboards.packs import (
    PACK_PAGE_SIZE,
    pack_browser_kb,
    pack_groups_kb,
    pack_remove_confirm_kb,
)
from app.bot.menu_nav import send_menu_card
from app.bot.states import InteractionState
from app.bot.texts import (
    PACK_COURSE_MANAGED,
    PACK_REMOVE_CONFIRM,
    PACK_REMOVED,
    PACK_TOGGLE_ADDED,
    PACK_TOGGLE_NONE_NEW,
    PACKS_GROUPS_TITLE,
    PACKS_TITLE,
    STALE_CALLBACK,
)
from app.domain.enums import LearningTrack
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.packs import PackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.analytics import EVENT_PACK_ADDED, Analytics
from app.services.category_service import CategoryService, CategoryServiceError
from app.services.course_service import CourseService
from app.services.interaction_state_service import InteractionStateService
from app.services.pack_service import PackService

router = Router(name="packs")

PACK_REMOVE_KIND = "pack_remove"  # screen-version guard for destructive removal
_GROUP_ORDER = {"Уровни": 0, "Грамматика": 1, "Темы": 2, "Фразы": 3, "Экзамены": 4}
_LEVELS_GROUP = "Уровни"


async def _groups(user_id: int, track: LearningTrack, session: AsyncSession) -> list[tuple[str, int]]:
    counts = await PackRepository(session).category_counts(track)
    return sorted(counts, key=lambda c: (_GROUP_ORDER.get(c[0], 99), c[0]))


async def _cache(category: str, track: LearningTrack, user_id: int, session: AsyncSession) -> list[list]:
    """Rows: [pack_id, title, words_count, learned_pct, owned]. `owned` drives the
    ✅/⬜ mark (added vs not)."""
    repo = PackRepository(session)
    packs = await repo.list_by_category(track, category)
    stats = await repo.stats_for_user(user_id, track)
    out: list[list] = []
    for p in packs:
        owned, mastered = stats.get(p.id, (0, 0))
        pct = round(100 * mastered / p.words_count) if p.words_count else 0
        out.append([p.id, p.title, p.words_count, pct, owned])
    return out


async def _render_list(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    track: LearningTrack,
    session: AsyncSession,
    category: str,
    page: int,
) -> None:
    cache = await _cache(category, track, user.id, session)
    course_managed = category == _LEVELS_GROUP and CourseService.is_enrolled(user_track)
    total_pages = max(1, (len(cache) + PACK_PAGE_SIZE - 1) // PACK_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    rows = [
        (int(r[0]), str(r[1]), int(r[2]), int(r[3]), int(r[4]))
        for r in cache[page * PACK_PAGE_SIZE : (page + 1) * PACK_PAGE_SIZE]
    ]
    if query.message:
        await query.message.edit_text(
            PACKS_TITLE, reply_markup=pack_browser_kb(rows, page, total_pages, course_managed)
        )


def _pack_row(cache: list[list], pid: int) -> list | None:
    return next((r for r in cache if int(r[0]) == pid), None)


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
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await query.answer()
    category = callback_data.category
    await state_service.set(user.id, InteractionState.PACK_SELECTION, {"category": category})
    await _render_list(query, user, user_track, current_track, session, category, 0)


# ---- checklist (within a group): tap = add / ask-remove, applied immediately ----


@router.callback_query(PacksCB.filter(F.action == "page"))
async def on_page(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    category = (await state_service.get(user.id)).data.get("category")
    if category:
        await query.answer()
        await _render_list(query, user, user_track, current_track, session, category, callback_data.page)
    else:
        # State expired — the «Отмена» / pagination button would otherwise be a
        # silent no-op. Tell the user and drop the stale card.
        await query.answer(STALE_CALLBACK, show_alert=False)
        try:
            await query.message.delete()
        except Exception:  # noqa: BLE001
            pass


@router.callback_query(PacksCB.filter(F.action == "course_info"))
async def on_course_info(query: CallbackQuery) -> None:
    await query.answer(PACK_COURSE_MANAGED, show_alert=False)


@router.callback_query(PacksCB.filter(F.action == "toggle"))
async def on_toggle(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    analytics: Analytics,
    screen_service,
) -> None:
    category = (await state_service.get(user.id)).data.get("category")
    if not category:
        await query.answer()
        return
    cache = await _cache(category, current_track, user.id, session)
    row = _pack_row(cache, callback_data.pack_id)
    if row is None:
        await query.answer()
        return
    _pid, title, wc, _pct, owned = int(row[0]), str(row[1]), int(row[2]), int(row[3]), int(row[4])

    # Already fully added → ask before removing (it drops progress).
    if wc > 0 and owned >= wc:
        await query.answer()
        version = await screen_service.bump(user.id, PACK_REMOVE_KIND)
        if query.message:
            await query.message.edit_text(
                PACK_REMOVE_CONFIRM.format(title=title, count=owned),
                reply_markup=pack_remove_confirm_kb(callback_data.pack_id, callback_data.page, version),
            )
        return

    # Otherwise add the pack (creates a folder named after it).
    pack_repo = PackRepository(session)
    cat_repo = CategoryRepository(session)
    pack = await pack_repo.get(callback_data.pack_id)
    if pack is None:
        await query.answer()
        return
    try:
        track = LearningTrack(pack.track)
    except ValueError:
        track = current_track
    folder = await cat_repo.get_by_name(user.id, track, pack.title)
    if folder is None:
        try:
            folder = await CategoryService(cat_repo).create(user.id, track, pack.title)
        except CategoryServiceError:
            folder = await cat_repo.get_by_name(user.id, track, pack.title)
    result = await PackService(pack_repo, UserWordRepository(session)).add_pack(
        user.id, track, callback_data.pack_id, folder.id if folder else None
    )
    await analytics.emit(
        EVENT_PACK_ADDED, user_id=user.id, track=track.value, pack_id=callback_data.pack_id, added=result.added
    )
    await query.answer(
        PACK_TOGGLE_ADDED.format(count=result.added) if result.added else PACK_TOGGLE_NONE_NEW
    )
    await _render_list(query, user, user_track, current_track, session, category, callback_data.page)


@router.callback_query(PacksCB.filter(F.action == "rem_ok"))
async def on_remove_confirm(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    # Guard the destructive removal against a stale confirm card (after the
    # screen version was bumped by any later action / the state TTL lapsed).
    if not await screen_service.check(user.id, PACK_REMOVE_KIND, callback_data.v):
        await query.answer(STALE_CALLBACK, show_alert=False)
        return
    category = (await state_service.get(user.id)).data.get("category")
    pack_repo = PackRepository(session)
    pack = await pack_repo.get(callback_data.pack_id)
    track = current_track
    if pack is not None:
        try:
            track = LearningTrack(pack.track)
        except ValueError:
            track = current_track
    removed = await PackService(pack_repo, UserWordRepository(session)).remove_pack(
        user.id, track, callback_data.pack_id
    )
    await query.answer(PACK_REMOVED.format(count=removed))
    if category:
        await _render_list(query, user, user_track, current_track, session, category, callback_data.page)
