from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import AddWordsCB, CategoryCB
from app.bot.filters import InState
from app.bot.keyboards.add_words import add_choose_category_kb, post_add_kb
from app.bot.keyboards.common import cancel_only_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_CHOOSE_CATEGORY,
    ADD_NO_WORDS,
    ADD_SUCCESS,
    ADD_WORDS_PROMPT,
    LIST_EXPIRED,
)
from app.config import get_settings
from app.domain.enums import LearningTrack, WordSource
from app.domain.models import User
from app.infrastructure.example_provider.local_json import LocalJsonExampleProvider
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.words import WordRepository
from app.services.analytics import EVENT_WORD_ADDED, Analytics
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.word_import_service import WordImportService
from app.services.word_parser import parse_input

router = Router(name="add_words")


@router.callback_query(AddWordsCB.filter(F.action == "start"))
async def on_add_start(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_MANUAL_WORDS)
    if query.message:
        await query.message.edit_text(
            ADD_WORDS_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML"
        )
    await query.answer()


CATEGORY_PICK_KIND = "cat_pick"


@router.message(InState(InteractionState.WAITING_MANUAL_WORDS), F.text)
async def on_manual_words_text(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    settings = get_settings()
    result = parse_input(
        message.text or "",
        max_lines=settings.txt_max_lines,
        max_words=settings.import_max_words,
    )
    if not result.words:
        await message.answer(ADD_NO_WORDS)
        return

    await state_service.set(
        user.id,
        InteractionState.WAITING_CATEGORY_FOR_WORDS,
        {
            "words": [
                {"e": w.english, "n": w.normalized, "t": w.translation, "x": w.example}
                for w in result.words
            ],
            "source": WordSource.MANUAL.value,
            "track": current_track.value,
        },
    )

    version = await screen_service.bump(user.id, CATEGORY_PICK_KIND)
    categories = await CategoryService(CategoryRepository(session)).list_user_categories(
        user.id, current_track
    )
    await message.answer(
        ADD_CHOOSE_CATEGORY,
        reply_markup=add_choose_category_kb(categories, flow="add", version=version),
    )


@router.callback_query(CategoryCB.filter((F.action == "pick") & (F.flow == "add")))
async def on_pick_category_for_add(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    analytics: Analytics,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, CATEGORY_PICK_KIND, callback_data.v):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return
    payload = await state_service.get(user.id)
    if payload.state != InteractionState.WAITING_CATEGORY_FOR_WORDS:
        await query.answer(LIST_EXPIRED, show_alert=False)
        return

    words_data = payload.data.get("words") or []
    if not words_data:
        await state_service.clear(user.id)
        await query.answer("Список слов пуст.")
        return

    try:
        track = LearningTrack(payload.data.get("track") or current_track.value)
    except ValueError:
        track = current_track

    from app.services.word_parser import ParsedWord
    words = [
        ParsedWord(english=w["e"], normalized=w["n"], translation=w["t"], example=w["x"])
        for w in words_data
    ]
    source = WordSource(payload.data.get("source") or WordSource.MANUAL.value)
    category_id = callback_data.category_id or None

    importer = WordImportService(
        WordRepository(session),
        UserWordRepository(session),
        LocalJsonExampleProvider(),
    )
    result = await importer.commit(
        user_id=user.id,
        track=track,
        words=words,
        category_id=category_id,
        source=source,
    )

    await analytics.emit(
        EVENT_WORD_ADDED,
        user_id=user.id,
        track=track.value,
        count=result.added,
        source=source.value,
        category_id=category_id,
    )
    await state_service.clear(user.id)

    if query.message:
        await query.message.edit_text(
            ADD_SUCCESS.format(count=result.added),
            reply_markup=post_add_kb(),
        )
    await query.answer()
