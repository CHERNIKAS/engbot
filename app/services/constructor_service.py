"""Driving one construction exercise from first tap to settled result.

Everything happens inside a single Telegram message. A card is sent once —
that is the notification — and every tap after it edits that same message in
place. Sending a new one per tap would leave a learner scrolling through
fifteen dead cards to find the live one, and the chat is the interface here.

The service holds no state of its own. What the learner has built lives in the
push inflight blob in Redis, which is where the rest of the card state already
lives, and the durable part — the topic score, the mode, what was asked
recently — lives in `user_grammar_topics`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import constructor as c
from app.domain.models import GrammarPhrase, GrammarTopic
from app.infrastructure.repositories.constructor import ConstructorRepository


@dataclass(frozen=True)
class CardView:
    """A rendered card, ready to send or to edit into place."""

    text: str
    phrase_id: int
    options: list[str]
    typing: bool
    can_undo: bool


@dataclass(frozen=True)
class Settlement:
    """The outcome of a finished exercise."""

    correct: bool
    answer_credit: float
    score_before: float
    score_after: float
    switched_to_typing: bool
    passed: bool
    expected: str


class ConstructorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ConstructorRepository(session)

    # ---- opening a card ----

    async def open_card(
        self, user_id: int, plan_done: int = 0, plan_total: int = 0
    ) -> tuple[CardView, GrammarPhrase, GrammarTopic] | None:
        """The next sentence to build, or None when there is nothing to serve.

        None is a normal outcome, not an error: a learner who has passed every
        topic has no active one. The caller ticks the plan slot off rather than
        holding the day open for a card that will never come.
        """
        topic = await self._repo.active_topic(user_id)
        if topic is None:
            return None
        phrase = await self._repo.pick_phrase(user_id, topic.id)
        if phrase is None:
            return None

        state_row = await self._repo.state(user_id, topic.id)
        typing = bool(state_row.typing) if state_row else False
        score = float(state_row.score) if state_row else 0.0

        view = self._render(
            topic=topic,
            phrase=phrase,
            score=score,
            state=c.CardState(typing=typing),
            plan_done=plan_done,
            plan_total=plan_total,
        )
        return view, phrase, topic

    def _render(
        self,
        *,
        topic: GrammarTopic,
        phrase: GrammarPhrase,
        score: float,
        state: c.CardState,
        plan_done: int = 0,
        plan_total: int = 0,
    ) -> CardView:
        slots = list(phrase.slots or [])
        hinted_prefix = ""
        if state.typing and state.hinted:
            hinted_prefix = c.hint_prefix(phrase.en)

        text = c.render_card(
            topic_title=topic.title,
            # The figure is withheld until the topic has been answered enough
            # for it to mean anything — 0.8 after three cards reads as a
            # verdict on the learner rather than as a start.
            score=score if self._score_is_meaningful(score, state) else None,
            ru=phrase.ru,
            built=c.assembled(slots, list(state.chosen)),
            typing=state.typing,
            attempt=state.attempt,
            hinted_prefix=hinted_prefix,
            plan_done=plan_done,
            plan_total=plan_total,
        )
        return CardView(
            text=text,
            phrase_id=phrase.id,
            options=[] if state.typing else c.slot_options(slots, state.slot_index),
            typing=state.typing,
            can_undo=bool(state.chosen),
        )

    @staticmethod
    def _score_is_meaningful(score: float, state: c.CardState) -> bool:
        return score > 0 or state.typing

    # ---- taps ----

    async def tap_slot(
        self,
        user_id: int,
        phrase: GrammarPhrase,
        topic: GrammarTopic,
        state: c.CardState,
        option_index: int,
        plan_done: int = 0,
        plan_total: int = 0,
    ) -> tuple[c.CardState, CardView | None]:
        """One tap in the assisted mode.

        Returns the new state and a card to edit into place, or `None` for the
        card when the exercise is over — either the sentence is complete or the
        attempts are gone. The caller settles it; this only decides that it is
        finished.
        """
        new_state, _ok = c.choose(state, list(phrase.slots or []), option_index)
        if c.is_complete(list(phrase.slots or []), list(new_state.chosen)):
            return new_state, None
        if new_state.exhausted:
            return new_state, None
        return new_state, await self._rerender(user_id, topic, phrase, new_state, plan_done, plan_total)

    async def undo(
        self,
        user_id: int,
        phrase: GrammarPhrase,
        topic: GrammarTopic,
        state: c.CardState,
        plan_done: int = 0,
        plan_total: int = 0,
    ) -> tuple[c.CardState, CardView]:
        new_state = c.undo(state)
        return new_state, await self._rerender(user_id, topic, phrase, new_state, plan_done, plan_total)

    async def hint(
        self,
        user_id: int,
        phrase: GrammarPhrase,
        topic: GrammarTopic,
        state: c.CardState,
        plan_done: int = 0,
        plan_total: int = 0,
    ) -> tuple[c.CardState, CardView]:
        """Ask for help.

        In the assisted mode the help is the correct piece, placed for them —
        there is nothing else to reveal when the options are already visible.
        In the typing mode it is the opening of the sentence.
        """
        new_state = c.use_hint(state)
        if not new_state.typing:
            slots = list(phrase.slots or [])
            new_state = c.place(new_state, c.slot_correct(slots, new_state.slot_index))
        return new_state, await self._rerender(
            user_id, topic, phrase, new_state, plan_done, plan_total
        )

    async def _rerender(
        self,
        user_id: int,
        topic: GrammarTopic,
        phrase: GrammarPhrase,
        state: c.CardState,
        plan_done: int,
        plan_total: int,
    ) -> CardView:
        row = await self._repo.state(user_id, topic.id)
        score = float(row.score) if row else 0.0
        return self._render(
            topic=topic,
            phrase=phrase,
            score=score,
            state=state,
            plan_done=plan_done,
            plan_total=plan_total,
        )

    # ---- settling ----

    async def settle(
        self,
        user_id: int,
        phrase: GrammarPhrase,
        topic: GrammarTopic,
        state: c.CardState,
        answer: str | None = None,
    ) -> Settlement:
        """Score the finished exercise and write the topic's new standing.

        `answer` is what was typed; in the assisted mode it is the assembled
        sentence. Both are checked against the same expectation, so the two
        modes cannot drift into grading different things.
        """
        slots = list(phrase.slots or [])
        given = answer if answer is not None else c.assembled(slots, list(state.chosen))
        correct = c.matches(given, phrase.en, list(phrase.alternatives or []))
        answer_credit = c.credit(state.attempt, hinted=state.hinted) if correct else 0.0

        row = await self._repo.ensure_state(user_id, topic.id)
        before = float(row.score or 0.0)
        after = c.update_score(before, answer_credit)
        answered = int(row.answered or 0) + 1

        switch = c.should_switch_to_typing(after, bool(row.typing))
        passed = c.should_pass(after, answered, bool(row.typing) or switch)

        await self._repo.record_answer(
            user_id=user_id,
            topic_id=topic.id,
            phrase_id=phrase.id,
            score=after,
            typing=True if switch else None,
            passed=passed,
        )
        return Settlement(
            correct=correct,
            answer_credit=answer_credit,
            score_before=before,
            score_after=after,
            switched_to_typing=switch,
            passed=passed,
            expected=phrase.en,
        )
