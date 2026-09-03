from __future__ import annotations

import json
from types import SimpleNamespace

from app.domain import mastery
from app.services.answer_check import AnswerCheckService, AnswerVerdict


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.gets = 0

    async def get(self, key):
        self.gets += 1
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


def _svc(key: str = "k", redis: FakeRedis | None = None) -> AnswerCheckService:
    svc = AnswerCheckService.__new__(AnswerCheckService)
    svc._redis = redis or FakeRedis()
    svc._settings = SimpleNamespace(
        gemini_api_key=key, ai_model="m", answer_check_timeout_seconds=5.0
    )
    return svc


def _response(verdict: str, hint: str = "подсказка") -> dict:
    payload = json.dumps({"verdict": verdict, "hint": hint})
    return {"candidates": [{"content": {"parts": [{"text": payload}]}}]}


# ---- reading the model's answer ----


def test_each_verdict_maps_to_its_score_kind():
    for verdict, kind in (
        ("typo", mastery.TYPED_TYPO),
        ("synonym", mastery.TYPED_SYNONYM),
        ("grammar", mastery.TYPED_GRAMMAR),
        ("wrong", mastery.WRONG),
    ):
        assert AnswerCheckService._parse(_response(verdict)).kind == kind


def test_an_unknown_verdict_reads_as_wrong():
    """A slip must not invent credit — the strict check already said no."""
    assert AnswerCheckService._parse(_response("brilliant")).kind == mastery.WRONG


def test_unparseable_response_raises_rather_than_guessing():
    for bad in ({}, {"candidates": []}, {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}):
        try:
            AnswerCheckService._parse(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


# ---- what counts as knowing the word ----


def test_typo_and_synonym_are_credited():
    assert AnswerVerdict(mastery.TYPED_TYPO, "").credited
    assert AnswerVerdict(mastery.TYPED_SYNONYM, "").credited


def test_grammar_and_wrong_are_not_credited():
    """A grammar slip still scores, but it doesn't clear the card: the point of
    the typed stage is producing the word correctly."""
    assert not AnswerVerdict(mastery.TYPED_GRAMMAR, "").credited
    assert not AnswerVerdict(mastery.WRONG, "").credited


# ---- the Cyrillic hole found during recon ----


async def test_a_russian_answer_is_always_wrong_without_asking_the_model():
    """The model was observed marking the Russian translation correct while its
    own hint said the answer had to be in English. Settled in code instead."""
    svc = _svc()
    verdict = await svc.classify("obtain", "получать", "получать")
    assert verdict is not None
    assert verdict.kind == mastery.WRONG
    assert verdict.hint


async def test_mixed_script_answer_is_also_refused():
    svc = _svc()
    verdict = await svc.classify("obtain", "получать", "obtaйn")
    assert verdict.kind == mastery.WRONG


# ---- graceful degradation ----


async def test_disabled_without_a_key_returns_none_not_a_verdict():
    """None means 'couldn't check' and must stay distinct from 'wrong' — the
    card shows a different message for each."""
    assert await _svc(key="").classify("obtain", "получать", "recieve") is None


async def test_empty_answer_is_wrong_without_a_call():
    assert (await _svc().classify("obtain", "получать", "   ")).kind == mastery.WRONG


# ---- caching ----


async def test_a_cached_verdict_is_reused():
    redis = FakeRedis()
    svc = _svc(redis=redis)
    key = svc._key("obtain", "recieve")
    redis.store[key] = json.dumps({"kind": mastery.TYPED_TYPO, "hint": "опечатка"})
    verdict = await svc.classify("obtain", "получать", "recieve")
    assert verdict.kind == mastery.TYPED_TYPO
    assert verdict.hint == "опечатка"


async def test_the_cache_key_ignores_case():
    svc = _svc()
    assert svc._key("Obtain", "Recieve") == svc._key("obtain", "recieve")


async def test_a_broken_cache_does_not_break_the_answer():
    class Broken(FakeRedis):
        async def get(self, key):
            raise RuntimeError("redis down")

    svc = _svc(key="", redis=Broken())
    # No key, so it stops before the network — the point is that the cache read
    # above didn't propagate its error.
    assert await svc.classify("obtain", "получать", "recieve") is None


# ---- deferred re-grading ----


async def test_a_parked_answer_survives_the_round_trip():
    from app.services.regrade import ParkedAnswer, RegradeQueue

    class ListRedis(FakeRedis):
        def __init__(self):
            super().__init__()
            self.items: list[str] = []

        async def lpush(self, key, value):
            self.items.insert(0, value)

        async def ltrim(self, key, start, end):
            self.items = self.items[start : end + 1]

        async def rpop(self, key):
            return self.items.pop() if self.items else None

        async def llen(self, key):
            return len(self.items)

    redis = ListRedis()
    q = RegradeQueue(redis)
    item = ParkedAnswer(1, 999, 42, "reliable", "надёжный", "relaible", 123.0)
    await q.park(item)
    assert await q.pending() == 1
    assert await q.drain(10) == [item]
    assert await q.pending() == 0


async def test_a_malformed_queue_entry_does_not_block_the_rest():
    from app.services.regrade import ParkedAnswer, RegradeQueue

    class ListRedis(FakeRedis):
        def __init__(self, items):
            super().__init__()
            self.items = list(items)

        async def rpop(self, key):
            return self.items.pop() if self.items else None

    good = ParkedAnswer(1, 999, 42, "w", "п", "a", 1.0)
    redis = ListRedis([json.dumps(good.__dict__), "not json"])
    drained = await RegradeQueue(redis).drain(10)
    assert drained == [good]


async def test_parking_never_raises_when_redis_is_down():
    """A failed park must not cost the user their answer."""
    from app.services.regrade import ParkedAnswer, RegradeQueue

    class Broken(FakeRedis):
        async def lpush(self, key, value):
            raise RuntimeError("redis down")

    await RegradeQueue(Broken()).park(ParkedAnswer(1, 9, 4, "w", "п", "a", 1.0))
