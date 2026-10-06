"""Pack editing for the admin screens.

Every write here moves the pack to `origin = 'admin'`, which takes it out of
the migrations' reach (see migration 0062 and `migrations/pack_ownership.py`).
That is deliberate and it is the whole mechanism: a pack cannot be half-owned.

What is not here, on purpose: creating packs and editing `pack_words`. Adding a
word to a pack means resolving it against the catalogue, and a word that is not
there yet turns the screen into a catalogue editor — a different, larger thing.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Pack, PackWord, Word

ORIGIN_ADMIN = "admin"

# Categories the top-up walks (`pack_top_up`). Moving a pack out of these takes
# it out of automatic delivery — the trap migration 0058 had to clean up after.
AUTOFILL_CATEGORIES = ("Темы", "Фразы")

# The categories a pack can be moved between, in a fixed order — callbacks carry
# the index, so this list is an interface: append only, never reorder, or a
# stale button in somebody's chat moves a pack into the wrong category.
KNOWN_CATEGORIES: tuple[str, ...] = (
    "Темы",
    "Фразы",
    "Уровни",
    "Грамматика",
    "Экзамены",
    "Узкие темы",
    "Живой английский",
)


def category_at(index: int) -> str | None:
    if 0 <= index < len(KNOWN_CATEGORIES):
        return KNOWN_CATEGORIES[index]
    return None


def index_of(category: str) -> int:
    try:
        return KNOWN_CATEGORIES.index(category)
    except ValueError:
        return -1


class PackAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def categories(self) -> list[tuple[str, int, int]]:
        """(category, packs, active packs) in a stable order."""
        q = (
            select(
                Pack.category,
                func.count(Pack.id),
                func.count(Pack.id).filter(Pack.is_active.is_(True)),
            )
            .group_by(Pack.category)
            .order_by(Pack.category)
        )
        return [(r[0], int(r[1]), int(r[2])) for r in (await self._session.execute(q)).all()]

    async def packs_in(self, category: str) -> list[Pack]:
        q = (
            select(Pack)
            .where(Pack.category == category)
            .order_by(Pack.position.asc(), Pack.id.asc())
        )
        return list((await self._session.execute(q)).scalars().all())

    async def get(self, pack_id: int) -> Pack | None:
        return await self._session.get(Pack, pack_id)

    async def words(self, pack_id: int, limit: int = 30) -> list[tuple[str, str | None]]:
        q = (
            select(Word.writing, Word.translation)
            .join(PackWord, PackWord.word_id == Word.id)
            .where(PackWord.pack_id == pack_id)
            .order_by(PackWord.position.asc())
            .limit(limit)
        )
        return [(r[0], r[1]) for r in (await self._session.execute(q)).all()]

    async def _claim(self, pack: Pack) -> None:
        """Move the pack under admin ownership. Called by every write."""
        pack.origin = ORIGIN_ADMIN

    async def toggle_active(self, pack: Pack) -> bool:
        """Flip delivery on or off.

        Words already handed to learners are untouched: `user_words` does not
        reference a pack at all, so switching one off only stops new words
        arriving from it. Nobody loses progress.
        """
        pack.is_active = not pack.is_active
        await self._claim(pack)
        await self._session.flush()
        return pack.is_active

    async def rename(self, pack: Pack, title: str) -> None:
        pack.title = title.strip()[:128]
        await self._claim(pack)
        await self._session.flush()

    async def move(self, pack: Pack, delta: int) -> bool:
        """Swap the pack with its neighbour inside the category.

        Swapping rather than renumbering: positions decide the order the top-up
        walks, and rewriting a whole category's numbers to move one pack is how
        a position drifts away from what anybody intended.
        """
        siblings = await self.packs_in(pack.category)
        ids = [p.id for p in siblings]
        if pack.id not in ids:
            return False
        i = ids.index(pack.id)
        j = i + delta
        if not (0 <= j < len(siblings)):
            return False
        other = siblings[j]
        pack.position, other.position = other.position, pack.position
        await self._claim(pack)
        await self._claim(other)
        await self._session.flush()
        return True

    async def set_category(self, pack: Pack, category: str) -> None:
        pack.category = category
        await self._claim(pack)
        await self._session.flush()

    @staticmethod
    def leaves_autofill(old_category: str, new_category: str) -> bool:
        """True when this move takes the pack out of automatic delivery.

        `pack_top_up` reads only «Темы» and «Фразы». A pack moved elsewhere
        keeps existing and stops being handed out, with nothing on screen
        saying so — which is exactly what migration 0058 had to repair.
        """
        return old_category in AUTOFILL_CATEGORIES and new_category not in AUTOFILL_CATEGORIES

    async def reset_to_migration(self, pack: Pack) -> None:
        """Hand the pack back to the migrations.

        The escape hatch for the one failure this design allows: a shipped fix
        that skipped this pack because the admin had touched it.
        """
        pack.origin = "migration"
        await self._session.flush()
