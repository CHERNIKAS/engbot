"""Pack admin screens.

Gated by `ADMIN_IDS` and entered by typing /packs_admin. Deliberately absent from
every menu: a button nobody but one person may press is clutter for everybody
else, and a 404-style toast is a worse answer than no button.

Every write moves the pack to `origin = 'admin'`, which takes it out of the
migrations' reach. See migration 0062 for why, and `migrations/pack_ownership.py`
for the loud-skip helper that keeps that trade honest.

Creating packs and editing `pack_words` are not here on purpose: adding a word
means resolving it against the catalogue, and that makes this a catalogue editor
instead.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PackAdminCB
from app.bot.filters import InState
from app.bot.keyboards.pack_admin import (
    categories_kb,
    category_pick_kb,
    pack_kb,
    packs_kb,
)
from app.bot.states import InteractionState
from app.config import get_settings
from app.domain.models import User
from app.services.interaction_state_service import InteractionStateService
from app.services.pack_admin_service import (
    AUTOFILL_CATEGORIES,
    PackAdminService,
    category_at,
)

router = Router(name="pack_admin")

_HEAD = "🛠 <b>Паки</b>"


def _is_admin(user: User) -> bool:
    return user.telegram_id in get_settings().admin_id_set


def _pack_text(pack, words: list[tuple[str, str | None]], total: int) -> str:
    owner = "миграции" if pack.origin == "migration" else "админка"
    lines = [
        f"🛠 <b>{pack.title}</b>",
        f"<code>{pack.slug}</code>",
        "",
        f"Категория: <b>{pack.category}</b>"
        + ("" if pack.category in AUTOFILL_CATEGORIES else " — вне автопополнения"),
        f"Позиция: {pack.position} · слов: {total}",
        f"Выдача: {'включена' if pack.is_active else 'выключена'}",
        f"Владелец: {owner}",
    ]
    if words:
        shown = ", ".join(w for w, _t in words)
        lines += ["", f"<i>{shown}{'…' if total > len(words) else ''}</i>"]
    return "\n".join(lines)


@router.message(Command("packs_admin"))
async def cmd_packs_admin(
    message: Message, user: User, session: AsyncSession, state_service: InteractionStateService
) -> None:
    if not _is_admin(user):
        return  # silence, not a refusal: a stranger learns nothing about this
    await state_service.clear(user.id)
    rows = await PackAdminService(session).categories()
    await message.answer(_HEAD, reply_markup=categories_kb(rows), parse_mode="HTML")


@router.callback_query(PackAdminCB.filter(F.action == "cats"))
async def on_cats(query: CallbackQuery, user: User, session: AsyncSession) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    rows = await PackAdminService(session).categories()
    if query.message:
        await query.message.edit_text(_HEAD, reply_markup=categories_kb(rows), parse_mode="HTML")
    await query.answer()


@router.callback_query(PackAdminCB.filter(F.action == "list"))
async def on_list(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    category = category_at(callback_data.cat)
    if category is None:
        await query.answer("Неизвестная категория")
        return
    packs = await PackAdminService(session).packs_in(category)
    note = "" if category in AUTOFILL_CATEGORIES else "\n<i>Вне автопополнения.</i>"
    if query.message:
        await query.message.edit_text(
            f"🛠 <b>{category}</b> · {len(packs)}{note}",
            reply_markup=packs_kb(category, packs),
            parse_mode="HTML",
        )
    await query.answer()


async def _show_pack(query: CallbackQuery, session: AsyncSession, pack_id: int) -> None:
    service = PackAdminService(session)
    pack = await service.get(pack_id)
    if pack is None:
        await query.answer("Пак не найден")
        return
    words = await service.words(pack.id)
    if query.message:
        await query.message.edit_text(
            _pack_text(pack, words, pack.words_count),
            reply_markup=pack_kb(pack),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(PackAdminCB.filter(F.action == "open"))
async def on_open(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    await _show_pack(query, session, callback_data.pack_id)


@router.callback_query(PackAdminCB.filter(F.action == "toggle"))
async def on_toggle(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    service = PackAdminService(session)
    pack = await service.get(callback_data.pack_id)
    if pack is None:
        await query.answer("Пак не найден")
        return
    now_on = await service.toggle_active(pack)
    await session.commit()
    # Says what does NOT happen, because that is the part people fear: nobody
    # loses words they already have — `user_words` has no pack reference.
    await query.answer(
        "Выдача включена" if now_on else "Выдача выключена. Уже выданные слова остаются у юзеров"
    )
    await _show_pack(query, session, pack.id)


@router.callback_query(PackAdminCB.filter(F.action.in_({"up", "down"})))
async def on_move(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    service = PackAdminService(session)
    pack = await service.get(callback_data.pack_id)
    if pack is None:
        await query.answer("Пак не найден")
        return
    moved = await service.move(pack, -1 if callback_data.action == "up" else 1)
    await session.commit()
    # The pack card does not show its position, so a silent success looked
    # exactly like a dead button.
    if not moved:
        await query.answer("Уже крайний")
    else:
        await query.answer("⬆️ Выше" if callback_data.action == "up" else "⬇️ Ниже")
    await _show_pack(query, session, pack.id)


@router.callback_query(PackAdminCB.filter(F.action == "cat"))
async def on_category_pick(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    pack = await PackAdminService(session).get(callback_data.pack_id)
    if pack is None:
        await query.answer("Пак не найден")
        return
    if query.message:
        await query.message.edit_text(
            f"🛠 <b>{pack.title}</b>\n\nКуда перенести?\n"
            "<i>⚠️ — категория вне автопополнения: пак останется, но новые слова "
            "из него выдаваться перестанут.</i>",
            reply_markup=category_pick_kb(pack),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(PackAdminCB.filter(F.action == "cat_set"))
async def on_category_set(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    service = PackAdminService(session)
    pack = await service.get(callback_data.pack_id)
    target = category_at(callback_data.cat)
    if pack is None or target is None:
        await query.answer("Не найдено")
        return
    warn = service.leaves_autofill(pack.category, target)
    await service.set_category(pack, target)
    await session.commit()
    # The 0058 trap, said out loud at the moment it is sprung rather than found
    # in a migration months later.
    await query.answer(
        f"Перенесён в «{target}». Выпал из автопополнения!" if warn else f"Перенесён в «{target}»",
        show_alert=warn,
    )
    await _show_pack(query, session, pack.id)


@router.callback_query(PackAdminCB.filter(F.action == "reset"))
async def on_reset(
    query: CallbackQuery, callback_data: PackAdminCB, user: User, session: AsyncSession
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    service = PackAdminService(session)
    pack = await service.get(callback_data.pack_id)
    if pack is None:
        await query.answer("Пак не найден")
        return
    await service.reset_to_migration(pack)
    await session.commit()
    await query.answer("Миграции снова могут его менять")
    await _show_pack(query, session, pack.id)


@router.callback_query(PackAdminCB.filter(F.action == "rename"))
async def on_rename_start(
    query: CallbackQuery,
    callback_data: PackAdminCB,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    if not _is_admin(user):
        await query.answer()
        return
    pack = await PackAdminService(session).get(callback_data.pack_id)
    if pack is None:
        await query.answer("Пак не найден")
        return
    await state_service.set(
        user.id, InteractionState.WAITING_PACK_RENAME, {"pack_id": pack.id}
    )
    if query.message:
        await query.message.edit_text(
            f"🛠 <b>{pack.title}</b>\n\nПришли новое название сообщением.",
            parse_mode="HTML",
        )
    await query.answer()


@router.message(InState(InteractionState.WAITING_PACK_RENAME), F.text)
async def on_rename_text(
    message: Message,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    interaction_state,
) -> None:
    if not _is_admin(user):
        await state_service.clear(user.id)
        return
    pack_id = (interaction_state.data or {}).get("pack_id")
    service = PackAdminService(session)
    pack = await service.get(int(pack_id)) if pack_id else None
    if pack is None:
        await state_service.clear(user.id)
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым. Пришли ещё раз.")
        return
    await service.rename(pack, title)
    await session.commit()
    await state_service.clear(user.id)
    words = await service.words(pack.id)
    await message.answer(
        _pack_text(pack, words, pack.words_count),
        reply_markup=pack_kb(pack),
        parse_mode="HTML",
    )
