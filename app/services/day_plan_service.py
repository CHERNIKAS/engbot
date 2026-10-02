"""Opening, serving and closing the day's plan.

The plan stores *what kind* of card each slot holds and nothing more — the
specific word or exercise is chosen when the card is actually sent.

That is deliberate, and it is the opposite of what "freeze the plan" sounds
like. Freezing concrete ids would break on everything that legitimately moves
underneath: a word deleted from the vocabulary, a theme whose remaining words
were all marked as known, a grammar topic that passed overnight. Each would
leave a slot pointing at something gone, and a slot that cannot be filled means
a plan that cannot be closed — which blocks every following day.

What the learner was promised is the shape of the day: four grammar, two
phrases, three new words, the rest review. That shape is what is frozen. Which
particular word arrives is not something they were told, so nothing is broken
by choosing it late — and choosing it late is what keeps review cards honest,
since a card picked three days ago is no longer the one most in need of
repeating.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import day_plan as plan_rules
from app.domain.enums import LearningTrack, WordSource
from app.domain.levels import level_from_coverage
from app.domain.models import DayPlan, User
from app.infrastructure.repositories.constructor import ConstructorRepository
from app.infrastructure.repositories.day_plans import DayPlanRepository
from app.infrastructure.repositories.user_words import UserWordRepository


@dataclass(frozen=True)
class PlanProgress:
    done: int
    total: int

    @property
    def closed(self) -> bool:
        return plan_rules.is_closed(self.done, self.total)

    @property
    def remaining_percent(self) -> int:
        return plan_rules.remaining_percent(self.done, self.total)


class DayPlanService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._plans = DayPlanRepository(session)
        self._words = UserWordRepository(session)
        self._constructor = ConstructorRepository(session)

    # ---- keeping the pool stocked ----
    #
    # The pickers only look at words the learner already owns. Something has to
    # put them there, and nothing did after the course was switched off — a
    # plan composed against an empty vocabulary is four grammar cards and a
    # silent day.

    # How many unstarted entries of each kind to keep waiting. Sized in days of
    # intake rather than as a round number: roughly a fortnight of new words at
    # the plan's cap, so a top-up is rare, and small enough that the learner's
    # vocabulary is not a dumping ground they never asked for. The pool ceiling
    # that used to matter is gone — nothing is *in flight* until a card is
    # actually served, so a deep buffer costs nothing.
    BUFFER_FREQUENCY = 40
    BUFFER_THEME = 25
    BUFFER_PHRASES = 12

    async def _top_up(self, user: User, track: LearningTrack) -> None:
        """Pull the next catalogue entries into the learner's vocabulary."""
        have_words = await self._words.count_new_startable(user.id, track, phrases=False)
        if have_words < self.BUFFER_FREQUENCY:
            ids = await self._words.catalogue_top_up(
                user.id, track, user.level, self.BUFFER_FREQUENCY - have_words
            )
            if ids:
                await self._words.bulk_add(
                    user.id, track, ids, None, WordSource.PACK
                )
        # Themes and the phrasebook arrive in their own declared order, which
        # frequency would scramble — numbers would run «eight, eighteen».
        for category, buffer_size in (
            ("Темы", self.BUFFER_THEME),
            ("Фразы", self.BUFFER_PHRASES),
        ):
            ids = await self._words.pack_top_up(user.id, track, category, buffer_size)
            if ids:
                await self._words.bulk_add(user.id, track, ids, None, WordSource.PACK)

    # ---- opening ----

    async def ensure_plan(
        self, user: User, track: LearningTrack, push_day: date
    ) -> tuple[DayPlan | None, bool]:
        """The plan to work on now, and whether it was just opened.

        An unfinished plan is returned as it is, whatever day it was made for.
        That is the rule: yesterday's plan is today's plan until it is closed.
        It neither expires (which would make a missed day pointless) nor stacks
        (which would meet a returning learner with a week of debt).

        Returns `(None, False)` when there is nothing to study at all — an
        empty plan would freeze and block every day after it, so none is
        opened.
        """
        existing = await self._plans.open_plan(user.id, track)
        if existing is not None:
            return existing, False
        # A finished day stays finished until the next one. Without this the
        # tick after a plan closed composed a second plan for the same day, and
        # «план пройден — жди завтра» was never true.
        if await self._plans.closed_on(user.id, track, push_day):
            return None, False

        # Stock the vocabulary before measuring it: composing first would size
        # the day against what was left over from yesterday.
        await self._top_up(user, track)
        size = await self._next_size(user, track)
        composition = await self._compose(user, track, size)
        if composition.total <= 0:
            return None, False

        items = self._items_for(composition)
        plan = await self._plans.create(
            user_id=user.id,
            track=track,
            size=size,
            items=items,
            opened_on=push_day,
        )
        return plan, True

    async def refresh_level(self, user: User, track: LearningTrack) -> str:
        """Derive the learner's level from what they have mastered, and store it.

        This is what replaced the placement test: twelve questions answered once
        used to decide the level forever, and for most users it decided it
        wrongly — one had B2 on record with 36 words of the first thousand
        actually mastered.

        The write is unconditional and moves in both directions, including down
        when a stored level is higher than the evidence supports — that B2 drops
        to A1 on the next plan. The level is the bot's own reading, not a
        setting: nothing in the interface writes it, so there is no hand-set
        value here to preserve.

        Called once a day, when the plan is built. Anywhere more often would
        reorder the queue under the learner mid-day, since `level_rank` sorts
        above `ngsl_rank` in both pickers.
        """
        band1, band2, _t1, _t2 = await self._words.band_coverage(user.id, track)
        derived = level_from_coverage(band1, band2)
        if user.level != derived:
            user.level = derived
            await self._session.flush()
        return derived

    async def open_plan_or_none(self, user_id: int, track: LearningTrack) -> DayPlan | None:
        """The plan in flight, if there is one. Read-only: the «Сегодня» screen
        must not open a plan, or looking at the day would start it."""
        return await self._plans.open_plan(user_id, track)

    async def _compose(
        self, user: User, track: LearningTrack, size: int
    ) -> plan_rules.Composition:
        due = await self._words.count_overdue(user.id, track)
        new_words = await self._words.count_new_startable(user.id, track, phrases=False)
        phrases = await self._words.count_new_startable(user.id, track, phrases=True)
        # Ask the repository that will actually serve the card. Booking slots
        # off one notion of "active topic" while the card comes from another
        # lets the plan promise grammar the constructor cannot deliver, and the
        # slots then tick off empty all day.
        topic = await self._constructor.active_topic(user.id)
        # Without a topic the slot is left empty rather than filled from
        # somewhere else, because grammar is a sequence and borrowing from the
        # next topic would teach it out of order.
        grammar = plan_rules.GRAMMAR_PER_DAY if topic is not None else 0
        # How many words the triage screen could actually offer. It works a
        # theme at a time, so the count is that theme's unstarted words — not
        # the whole backlog, which would book a slot the screen cannot fill.
        theme = await self._words.current_theme(user.id, track)
        triage_available = (
            len(
                await self._words.theme_batch(
                    user.id, track, theme.id, plan_rules.TRIAGE_THRESHOLD
                )
            )
            if theme is not None
            else 0
        )
        test_due = await self._constructor.due_test_topic(user.id) is not None
        return plan_rules.compose(
            size=size,
            due_repeats=due,
            grammar_available=grammar,
            phrases_available=phrases,
            new_available=new_words,
            triage_available=triage_available,
            test_due=test_due,
        )

    @staticmethod
    def _items_for(composition: plan_rules.Composition) -> list[dict]:
        """The plan as a flat list of slots.

        Ordered so a session that gets interrupted still did the most valuable
        part: review first (forgetting is the thing with a deadline), then
        grammar, then what is new. The learner can answer them in any order the
        push happens to deliver — this only decides what is served first.
        """
        items: list[dict] = []
        for kind, count in (
            # Triage leads: it is the one slot that makes the rest of the day
            # smaller. Clearing fifteen already-known words before the new ones
            # are served is the difference between studying and tapping through
            # «one, two, fourteen» one card at a time.
            (plan_rules.TRIAGE, composition.triage),
            (plan_rules.REPEAT, composition.repeats),
            (plan_rules.GRAMMAR, composition.grammar),
            (plan_rules.TEST, composition.test),
            (plan_rules.NEW_THEME_WORD, composition.new_theme),
            (plan_rules.NEW_WORD, composition.new_frequency),
            (plan_rules.PHRASE, composition.phrases),
        ):
            items.extend({"kind": kind, "done": False} for _ in range(count))
        return items

    async def _next_size(self, user: User, track: LearningTrack) -> int:
        previous = await self._plans.last_size(user.id, track)
        if previous is None:
            return plan_rules.DEFAULT_SIZE
        closes, misses = await self._streaks(user, track)
        return plan_rules.next_size(previous, closes, misses)

    async def _streaks(self, user: User, track: LearningTrack) -> tuple[int, int]:
        """(consecutive closes, consecutive misses) over recent plans.

        A miss is a plan that took more than one push day to close — that is
        what "did not finish it that day" means once plans are allowed to carry
        over. Counting unclosed plans instead would never see a miss, since a
        carried plan eventually closes too.
        """
        recent = await self._plans.recent_closed(user.id, track, limit=14)
        closes = misses = 0
        for plan in recent:
            if plan.closed_at is None:
                break
            same_day = plan.closed_at.date() == plan.opened_on
            if same_day:
                if misses:
                    break
                closes += 1
            else:
                if closes:
                    break
                misses += 1
        return closes, misses

    # ---- serving ----

    @staticmethod
    def next_kind(plan: DayPlan) -> str | None:
        """What kind of card to send next, or None when the plan is finished."""
        for item in plan.items or []:
            if not item.get("done"):
                return item.get("kind")
        return None

    async def mark_done(self, plan: DayPlan, kind: str) -> PlanProgress:
        """Tick off one slot of this kind.

        Called after a card is answered — right or wrong, because the plan
        measures attendance. Also called when a slot turns out to be
        unfillable, which is the escape valve: a theme with nothing left to
        teach must not hold the day open forever.
        """
        items = [dict(item) for item in (plan.items or [])]
        for item in items:
            if item.get("kind") == kind and not item.get("done"):
                item["done"] = True
                break
        plan.items = items
        await self._plans.save_items(plan.id, items)
        return self.progress(plan)

    @staticmethod
    def progress(plan: DayPlan) -> PlanProgress:
        items = plan.items or []
        return PlanProgress(done=sum(1 for i in items if i.get("done")), total=len(items))

    async def close_if_complete(self, plan: DayPlan) -> bool:
        """Close the plan when every slot is ticked. Returns whether it closed
        now, so the caller knows to send the day's summary exactly once."""
        if plan.closed_at is not None:
            return False
        if not self.progress(plan).closed:
            return False
        await self._plans.close(plan.id)
        return True

    @staticmethod
    def counts_by_kind(plan: DayPlan) -> dict[str, int]:
        """How many slots of each kind the plan holds — for the plan card."""
        out: dict[str, int] = {}
        for item in plan.items or []:
            kind = item.get("kind", "")
            out[kind] = out.get(kind, 0) + 1
        return out
