from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import SearchCB
from app.bot.filters import InState
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.search import search_results_kb
from app.bot.states import InteractionState
from app.bot.texts import SEARCH_ADDED, SEARCH_EMPTY, SEARCH_PROMPT, SEARCH_RESULTS
from app.domain.enums import LearningTrack, WordSource
from app.domain.models import User
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.words import WordRepository
from app.services.interaction_state_service import InteractionStateService

router = Router(name="search")

_LIMIT = 5
_QUERY_MAX = 64


async def _render_results(
    message: Message,
    user: User,
    track: LearningTrack,
    session: AsyncSession,
    query_text: str,
) -> None:
    own_rows = await UserWordRepository(session).search_own(
        user.id, track, query_text, limit=_LIMIT
    )
    catalog = await WordRepository(session).search_catalog(
        track, query_text, exclude_user_id=user.id, limit=_LIMIT
    )
    safe_query = html.escape(query_text)
    if not own_rows and not catalog:
        await message.answer(
            SEARCH_EMPTY.format(query=safe_query), parse_mode="HTML"
        )
        return
    own = [
        (uw.id, w.writing, uw.custom_translation or w.translation)
        for uw, w in own_rows
    ]
    found = [(w.id, w.writing, w.translation) for w in catalog]
    await message.answer(
        SEARCH_RESULTS.format(query=safe_query, own=len(own), catalog=len(found)),
        reply_markup=search_results_kb(own, found),
        parse_mode="HTML",
    )


@router.callback_query(SearchCB.filter(F.action == "open"))
async def on_search_open(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_SEARCH_QUERY)
    if query.message:
        await query.message.edit_text(
            SEARCH_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML"
        )
    await query.answer()


@router.message(InState(InteractionState.WAITING_SEARCH_QUERY), F.text)
async def on_search_query(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    query_text = (message.text or "").strip()[:_QUERY_MAX]
    if not query_text:
        return
    # Remember the query so a catalog-add can re-render the same results.
    await state_service.set(
        user.id, InteractionState.WAITING_SEARCH_QUERY, {"q": query_text}
    )
    await _render_results(message, user, current_track, session, query_text)


@router.callback_query(SearchCB.filter(F.action == "add"))
async def on_search_add(
    query: CallbackQuery,
    callback_data: SearchCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    interaction_state,
) -> None:
    added = await UserWordRepository(session).bulk_add(
        user.id, current_track, [callback_data.word_id], None, WordSource.MANUAL
    )
    await query.answer(SEARCH_ADDED if added else "Уже в словаре 👌")
    # Refresh the results so the word moves to the «в твоём словаре» section.
    last_query = ((interaction_state.data if interaction_state else None) or {}).get("q")
    if last_query and query.message:
        await _render_results(query.message, user, current_track, session, str(last_query))
        try:
            await query.message.delete()
        except Exception:  # noqa: BLE001 — old message may already be gone
            pass
