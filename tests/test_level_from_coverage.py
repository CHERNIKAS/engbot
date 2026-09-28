"""The level derived from what the learner has actually mastered.

This replaces the placement test, and it carries more weight than its size
suggests: `level_rank` sorts *above* `ngsl_rank` in both pickers
(`user_words.py:592` and `:1169`), so the level is an axis over frequency, not
a tiebreak under it. One step too high and the learner meets B1 words before
the first thousand — the exact complaint v2 was built to fix.

So the properties worth pinning are: never start high, never move backwards,
and never move because the catalogue grew.
"""
from __future__ import annotations

import pytest

from app.domain.levels import (
    LEVEL_FROM_BAND1,
    LEVEL_FROM_BAND2,
    index,
    level_from_coverage,
)


def test_a_learner_with_nothing_mastered_starts_at_the_bottom():
    """The old default was A2 for anyone without a level, which quietly served
    a complete beginner A2 words ahead of A1 ones."""
    assert level_from_coverage(0, 0) == "A1"


def test_the_first_thousand_gates_everything_above_a1():
    """Until the band that carries ~85% of ordinary text is half known, there
    is nothing to be gained from harder words."""
    assert level_from_coverage(LEVEL_FROM_BAND1 - 1, 0) == "A1"
    assert level_from_coverage(LEVEL_FROM_BAND1 - 1, 10_000) == "A1"
    assert level_from_coverage(LEVEL_FROM_BAND1, 0) == "A2"


def test_b1_needs_both_bands():
    assert level_from_coverage(850, LEVEL_FROM_BAND2 - 1) == "A2"
    assert level_from_coverage(849, LEVEL_FROM_BAND2) == "A2"
    assert level_from_coverage(850, LEVEL_FROM_BAND2) == "B1"


@pytest.mark.parametrize("band1", [0, 1, 99, 499, 500, 849, 850, 5000])
@pytest.mark.parametrize("band2", [0, 1, 199, 200, 5000])
def test_the_level_never_goes_down_as_words_are_learned(band1, band2):
    """Monotonic in both arguments. `mastered` only ever grows, so a level that
    could fall would mean it fell for someone who only kept studying."""
    here = index(level_from_coverage(band1, band2))
    assert index(level_from_coverage(band1 + 1, band2)) >= here
    assert index(level_from_coverage(band1, band2 + 1)) >= here


def test_the_answer_does_not_depend_on_catalogue_size():
    """Thresholds are counts, not ratios, and this is why: a ratio moves when
    the catalogue grows, so adding four hundred words to the first band would
    drop everyone's level overnight through no fault of their own. Nothing here
    takes a denominator at all — this test exists to keep it that way."""
    import inspect

    from app.domain import levels

    source = inspect.getsource(levels.level_from_coverage)
    assert "/" not in source, "деление — значит появился знаменатель от каталога"


def test_the_real_users_all_come_out_at_a1():
    """Measured on production on 2026-09-26. The most-advanced learner had 36
    words of the first band mastered; nobody is near the A2 bar, which is the
    expected state after a month and the reason the bar is set where it is."""
    production = {1: (10, 7), 3: (36, 1), 5: (5, 0), 6: (0, 0), 8: (0, 0)}
    for uid, (band1, band2) in production.items():
        assert level_from_coverage(band1, band2) == "A1", uid


class _FakeWords:
    def __init__(self, band1, band2):
        self.band1, self.band2 = band1, band2

    async def band_coverage(self, user_id, track):
        return self.band1, self.band2, 1044, 495


class _FakeUser:
    id = 1

    def __init__(self, level):
        self.level = level


def _service(band1, band2):
    from app.services.day_plan_service import DayPlanService

    service = DayPlanService.__new__(DayPlanService)
    service._words = _FakeWords(band1, band2)

    class _Session:
        async def flush(self):
            pass

    service._session = _Session()
    return service


@pytest.mark.asyncio
async def test_the_level_is_rewritten_on_every_build_not_just_the_first():
    """The bug this pins: a level screen once offered a manual pick, and it
    looked fine because a single call left it alone. The second build — the
    next day — overwrote it, so the button was decorative. Anything that lives
    between days has to be checked on the second run, not the first."""
    from app.domain.enums import LearningTrack

    service = _service(0, 0)
    user = _FakeUser("B2")
    assert await service.refresh_level(user, LearningTrack.ENGLISH) == "A1"
    assert user.level == "A1"
    # And again, as tomorrow would: still derived, not whatever was stored.
    user.level = "C1"
    assert await service.refresh_level(user, LearningTrack.ENGLISH) == "A1"
    assert user.level == "A1"


@pytest.mark.asyncio
async def test_a_stored_level_above_the_evidence_comes_down():
    """User 3 carried B2 from the placement test with 36 words of the first
    thousand mastered. The write moves in both directions on purpose."""
    from app.domain.enums import LearningTrack

    service = _service(36, 1)
    user = _FakeUser("B2")
    await service.refresh_level(user, LearningTrack.ENGLISH)
    assert user.level == "A1"
