"""What a recorded answer duration is allowed to mean.

The whole day-plan arithmetic — how many cards fit a day, what a plan costs in
attention — is built on the per-card duration, and until now that number was
guessed. These pin the cases where a duration would lie if recorded naively.
"""
from __future__ import annotations

from app.services.push_service import _MAX_RESPONSE_SECONDS, _timing

SENT = 1_000_000.0


def test_answer_on_the_first_push_is_the_clean_sample():
    ms, attempts = _timing({"sent_ts": SENT, "attempts": 0}, SENT + 12.5)
    assert ms == 12_500
    assert attempts == 1


def test_attempts_counts_the_push_that_was_answered_not_the_nudges_before():
    """attempts is 1-based so the clean sample is a plain `attempts == 1`."""
    _, first = _timing({"sent_ts": SENT, "attempts": 0}, SENT + 1)
    _, third = _timing({"sent_ts": SENT, "attempts": 2}, SENT + 1)
    assert (first, third) == (1, 3)


def test_a_card_with_no_send_stamp_reports_no_duration():
    """Cards already in flight when this shipped have no stamp — they must come
    back as unknown rather than as an invented zero, which would drag the
    average down and look like instant answers."""
    ms, attempts = _timing({"attempts": 0}, SENT)
    assert ms is None
    assert attempts == 1


def test_a_clock_jump_is_not_a_measurement():
    """Backwards, or longer than any nudge cycle could produce: both mean the
    clock moved, not that the learner was slow."""
    assert _timing({"sent_ts": SENT, "attempts": 0}, SENT - 5)[0] is None
    assert _timing({"sent_ts": SENT, "attempts": 0}, SENT + _MAX_RESPONSE_SECONDS + 1)[0] is None


def test_attempts_still_recorded_when_the_duration_is_unusable():
    """A dropped duration must not drop the attempt count with it — otherwise
    the rows that prove a card was nudged disappear from the sample."""
    _, attempts = _timing({"sent_ts": SENT, "attempts": 1}, SENT - 5)
    assert attempts == 2
