from __future__ import annotations

import secrets

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import QuickAddCB
from app.bot.filters import InState
from app.bot.keyboards.add_words import add_choose_category_kb, post_add_kb
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_CHOOSE_CATEGORY,
    ADD_SUCCESS,
    MAIN_MENU,
    QUICK_ADD_NONE,
    QUICK_ADD_PROMPT_MANY,
    QUICK_ADD_PROMPT_ONE,
    STALE_CALLBACK,
)
from app.domain.enums import LearningTrack, WordSource
from app.domain.models import User
from app.infrastructure.example_provider.local_json import LocalJsonExampleProvider
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.words import WordRepository
from app.services.analytics import EVENT_WORD_ADDED, Analytics
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.user_track_service import UserTrackService
from app.services.word_import_service import WordImportService
from app.services.word_parser import parse_input

router = Router(name="fallback")

QUICK_ADD_KEY = "quickadd:{token}"
QUICK_ADD_TTL = 300  # 5 min


def _quick_add_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить", callback_data=QuickAddCB(action="add", token=token).pack())],
            [InlineKeyboardButton(text="📁 Выбрать категорию", callback_data=QuickAddCB(action="choose_cat", token=token).pack())],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=QuickAddCB(action="cancel", token=token).pack())],
        ]
    )


@router.message(InState(InteractionState.IDLE), F.text)
async def on_idle_text(
    message: Message,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    redis: Redis,
) -> None:
    result = parse_input(message.text or "", max_lines=200, max_words=200)
    if not result.words:
        active = await user_track_service.list_active(user.id)
        await message.answer(QUICK_ADD_NONE, reply_markup=main_menu_kb(active, current_track))
        return

    token = secrets.token_urlsafe(8)
    import json as _json
    payload = _json.dumps(
        {
            "track": current_track.value,
            "words": [
                {"e": w.english, "n": w.normalized, "t": w.translation, "x": w.example}
                for w in result.words
            ],
        }
    )
    await redis.set(QUICK_ADD_KEY.format(token=token), payload, ex=QUICK_ADD_TTL)

    if len(result.words) == 1:
        text = QUICK_ADD_PROMPT_ONE.format(word=result.words[0].english)
    else:
        text = QUICK_ADD_PROMPT_MANY.format(count=len(result.words))
    await message.answer(text, reply_markup=_quick_add_kb(token))


async def _load_quick_add(redis: Redis, token: str):
    import json as _json
    raw = await redis.get(QUICK_ADD_KEY.format(token=token))
    if not raw:
        return None
    try:
        data = _json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    # Backwards-compat with older payloads (list of words without a track wrapper).
    if isinstance(data, list):
        return {"track": LearningTrack.ENGLISH.value, "words": data}
    return data


@router.callback_query(QuickAddCB.filter(F.action == "add"))
async def on_quick_add(
    query: CallbackQuery,
    callback_data: QuickAddCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    redis: Redis,
    analytics: Analytics,
) -> None:
    payload = await _load_quick_add(redis, callback_data.token)
    if not payload:
        await query.answer(STALE_CALLBACK, show_alert=False)
        return

    try:
        track = LearningTrack(payload.get("track") or current_track.value)
    except ValueError:
        track = current_track

    from app.services.word_parser import ParsedWord
    items = payload.get("words") or []
    words = [
        ParsedWord(english=i["e"], normalized=i["n"], translation=i["t"], example=i["x"])
        for i in items
    ]
    importer = WordImportService(
        WordRepository(session),
        UserWordRepository(session),
        LocalJsonExampleProvider(),
    )
    result = await importer.commit(
        user_id=user.id,
        track=track,
        words=words,
        category_id=None,
        source=WordSource.MANUAL,
    )
    await analytics.emit(
        EVENT_WORD_ADDED,
        user_id=user.id,
        track=track.value,
        count=result.added,
        source=WordSource.MANUAL.value,
        category_id=None,
    )
    await redis.delete(QUICK_ADD_KEY.format(token=callback_data.token))
    if query.message:
        await query.message.edit_text(
            ADD_SUCCESS.format(count=result.added),
            reply_markup=post_add_kb(),
        )
    await query.answer()


@router.callback_query(QuickAddCB.filter(F.action == "choose_cat"))
async def on_quick_choose_cat(
    query: CallbackQuery,
    callback_data: QuickAddCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    redis: Redis,
    state_service: InteractionStateService,
) -> None:
    payload = await _load_quick_add(redis, callback_data.token)
    if not payload:
        await query.answer(STALE_CALLBACK, show_alert=False)
        return

    track_str = payload.get("track") or current_track.value
    items = payload.get("words") or []
    await state_service.set(
        user.id,
        InteractionState.WAITING_CATEGORY_FOR_WORDS,
        {"words": items, "source": WordSource.MANUAL.value, "track": track_str},
    )
    await redis.delete(QUICK_ADD_KEY.format(token=callback_data.token))

    try:
        track = LearningTrack(track_str)
    except ValueError:
        track = current_track
    categories = await CategoryService(CategoryRepository(session)).list_user_categories(
        user.id, track
    )
    if query.message:
        await query.message.edit_text(
            ADD_CHOOSE_CATEGORY,
            reply_markup=add_choose_category_kb(categories, flow="add"),
        )
    await query.answer()


@router.callback_query(QuickAddCB.filter(F.action == "cancel"))
async def on_quick_cancel(
    query: CallbackQuery,
    callback_data: QuickAddCB,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    redis: Redis,
) -> None:
    await redis.delete(QUICK_ADD_KEY.format(token=callback_data.token))
    active = await user_track_service.list_active(user.id)
    if query.message:
        await query.message.edit_text(MAIN_MENU, reply_markup=main_menu_kb(active, current_track))
    await query.answer()


@router.callback_query()
async def on_unhandled_callback(query: CallbackQuery) -> None:
    await query.answer(STALE_CALLBACK, show_alert=False)
