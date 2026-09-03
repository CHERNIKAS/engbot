from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import CategoryCB, ImportCB
from app.bot.filters import InState
from app.bot.keyboards.add_words import (
    add_choose_category_kb,
    import_priority_kb,
    post_add_kb,
)
from app.bot.keyboards.common import cancel_only_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_CHOOSE_CATEGORY,
    LIST_EXPIRED,
    IMPORT_ASK_PRIORITY,
    IMPORT_PRIORITY_SET,
    TXT_IMPORT_DONE,
    TXT_NOT_TEXT,
    TXT_PARSE_ERROR,
    TXT_PREVIEW,
    TXT_PROMPT,
    TXT_TOO_BIG,
    TXT_TOO_MANY_LINES,
)
from app.config import get_settings
from app.domain.enums import LearningTrack, WordSource
from app.domain.models import User
from app.infrastructure.example_provider.local_json import LocalJsonExampleProvider
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.words import WordRepository
from app.logging_setup import get_logger
from app.services.analytics import EVENT_TXT_IMPORTED, Analytics
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.word_import_service import WordImportService
from app.services.word_parser import parse_input

router = Router(name="txt_import")
log = get_logger("txt_import")


@router.callback_query(ImportCB.filter(F.action == "start"))
async def on_import_start(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_TXT_FILE)
    if query.message:
        await query.message.edit_text(TXT_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML")
    await query.answer()


CATEGORY_PICK_KIND = "cat_pick"


@router.message(InState(InteractionState.WAITING_TXT_FILE), F.document)
async def on_document(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    bot: Bot,
    screen_service,
) -> None:
    settings = get_settings()
    doc = message.document
    if doc is None:
        return

    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()
    is_text = mime.startswith("text/") or name.endswith(".txt")
    if not is_text:
        await message.answer(TXT_NOT_TEXT)
        return

    if doc.file_size and doc.file_size > settings.txt_max_bytes:
        await message.answer(TXT_TOO_BIG.format(limit_kb=settings.txt_max_bytes // 1024))
        return

    try:
        file = await bot.get_file(doc.file_id)
        if file.file_path is None:
            await message.answer(TXT_PARSE_ERROR)
            return
        buf = await bot.download_file(file.file_path)
        if buf is None:
            await message.answer(TXT_PARSE_ERROR)
            return
        content_bytes = buf.read()
    except Exception:  # noqa: BLE001
        log.exception("txt_download_failed", user_id=user.id)
        await message.answer(TXT_PARSE_ERROR)
        return

    try:
        text = content_bytes.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        await message.answer(TXT_PARSE_ERROR)
        return

    if text.count("\n") > settings.txt_max_lines:
        await message.answer(TXT_TOO_MANY_LINES.format(limit=settings.txt_max_lines))
        return

    result = parse_input(text, max_lines=settings.txt_max_lines, max_words=settings.import_max_words)
    if not result.words:
        await message.answer(TXT_PARSE_ERROR)
        return

    await state_service.set(
        user.id,
        InteractionState.WAITING_TXT_CATEGORY,
        {
            "words": [
                {"e": w.english, "n": w.normalized, "t": w.translation, "x": w.example}
                for w in result.words
            ],
            "track": current_track.value,
        },
    )

    already = await UserWordRepository(session).existing_normalized(
        user.id, current_track, [w.normalized for w in result.words]
    )
    already_count = len(already)
    will_add = len(result.words) - already_count

    preview_lines = [
        f"🔎 Найдено: <b>{result.seen_count}</b>",
        f"Дубликатов: <b>{result.duplicates}</b>",
    ]
    if result.invalid:
        preview_lines.append(f"Не распознано: <b>{result.invalid}</b>")
    if already_count:
        preview_lines.append(f"Уже в словаре: <b>{already_count}</b>")
    if result.truncated:
        preview_lines.append(
            f"⚠️ Лимит {settings.import_max_words}: <b>{result.truncated}</b> не влезли"
        )
    preview_lines.append(f"🌱 Будет добавлено: <b>{will_add}</b>")
    preview = "\n".join(preview_lines)
    version = await screen_service.bump(user.id, CATEGORY_PICK_KIND)
    categories = await CategoryService(CategoryRepository(session)).list_user_categories(
        user.id, current_track
    )
    await message.answer(
        f"{preview}\n\n{ADD_CHOOSE_CATEGORY}",
        reply_markup=add_choose_category_kb(categories, flow="imp", version=version),
        parse_mode="HTML",
    )


@router.callback_query(CategoryCB.filter((F.action == "pick") & (F.flow == "imp")))
async def on_pick_category_for_import(
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
    if payload.state != InteractionState.WAITING_TXT_CATEGORY:
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
        source=WordSource.TXT_IMPORT,
    )
    await analytics.emit(
        EVENT_TXT_IMPORTED,
        user_id=user.id,
        track=track.value,
        count=result.added,
        category_id=category_id,
    )
    skipped = len(words) - result.added
    done_text = TXT_IMPORT_DONE.format(count=result.added)
    if skipped > 0:
        done_text += f"\n({skipped} уже были у тебя)"

    if result.added and result.word_ids:
        # Offer this batch a place at the front of the queue. Ordering by level
        # serves the majority who never import anything, but the two heaviest
        # users keep 60-68% of their vocabulary as their own lists — and a list
        # assembled for a deadline is about intent, not difficulty. The ids are
        # held briefly so the flag lands on exactly this import and nothing older.
        await state_service.set(
            user.id,
            InteractionState.IMPORT_PRIORITY,
            {"word_ids": result.word_ids},
        )
        done_text += f"\n\n{IMPORT_ASK_PRIORITY}"
        keyboard = import_priority_kb()
    else:
        await state_service.clear(user.id)
        keyboard = post_add_kb()

    if query.message:
        await query.message.edit_text(done_text, reply_markup=keyboard)
    await query.answer()


@router.callback_query(ImportCB.filter(F.action == "prioritise"))
async def on_import_prioritise(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    word_ids = payload.data.get("word_ids") or []
    if payload.state == InteractionState.IMPORT_PRIORITY and word_ids:
        await UserWordRepository(session).set_priority(user.id, word_ids)
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(IMPORT_PRIORITY_SET, reply_markup=post_add_kb())
    await query.answer()
