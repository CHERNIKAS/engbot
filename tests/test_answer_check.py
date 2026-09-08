from __future__ import annotations

import json
from types import SimpleNamespace

from app.domain import mastery
from app.services.answer_check import AnswerCheckService, AnswerVerdict
from app.services.regrade import ParkedAnswer, RegradeQueue, RegradeService


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
        gemini_api_key=key,
        ai_model="m",
        answer_check_timeout_seconds=8.0,
        answer_check_retries=1,
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
    class Broken(FakeRedis):
        async def lpush(self, key, value):
            raise RuntimeError("redis down")

    await RegradeQueue(Broken()).park(ParkedAnswer(1, 9, 4, "w", "п", "a", 1.0))


# ---- the re-grade itself: it writes scores and messages real people ----


class FakeQueueRedis(FakeRedis):
    def __init__(self, items=None):
        super().__init__()
        self.items = list(items or [])

    async def lpush(self, key, value):
        self.items.insert(0, value)

    async def ltrim(self, key, start, end):
        self.items = self.items[start : end + 1]

    async def rpop(self, key):
        return self.items.pop() if self.items else None

    async def llen(self, key):
        return len(self.items)


class FakeUserWord:
    def __init__(self, uw_id=42, user_id=1):
        self.id = uw_id
        self.user_id = user_id
        self.learning_score = 2.0
        self.production_count = 0


def _service(redis, verdict, uw=None, key="k"):
    """A RegradeService with the checker and repository stubbed out."""
    svc = RegradeService.__new__(RegradeService)
    svc._session = SimpleNamespace(flush=_noop)
    svc._queue = RegradeQueue(redis)

    class Checker:
        enabled = bool(key)

        async def classify(self, word, translation, answer):
            return verdict

    class Repo:
        async def get(self, uw_id, owner_id=None):
            return uw

    svc._checker = Checker()
    svc._uw = Repo()
    return svc


async def _noop(*_a, **_kw):
    return None


def _parked(at=1000.0):
    return ParkedAnswer(1, 999, 42, "reliable", "надёжный", "relaible", at)


async def _queued(item):
    redis = FakeQueueRedis()
    await RegradeQueue(redis).park(item)
    return redis


async def test_a_credited_answer_gets_its_score_after_the_fact():
    uw = FakeUserWord()
    redis = await _queued(_parked())
    svc = _service(redis, AnswerVerdict(mastery.TYPED_TYPO, "опечатка"), uw)
    result = await svc.run(now=1001.0)
    assert result.upgraded == 1
    assert uw.learning_score > 2.0
    assert uw.production_count == 1
    assert 999 in result.per_user  # the user is told what changed


async def test_a_genuine_miss_changes_nothing():
    uw = FakeUserWord()
    redis = await _queued(_parked())
    svc = _service(redis, AnswerVerdict(mastery.WRONG, ""), uw)
    result = await svc.run(now=1001.0)
    assert result.checked == 1
    assert result.upgraded == 0
    assert uw.learning_score == 2.0
    assert not result.per_user


async def test_a_stale_answer_is_dropped_rather_than_resurrected():
    """A surprise "your answer from Tuesday was fine" is noise, not a gift."""
    uw = FakeUserWord()
    redis = await _queued(_parked(at=0.0))
    svc = _service(redis, AnswerVerdict(mastery.TYPED_TYPO, "x"), uw)
    result = await svc.run(now=10_000_000.0)
    assert result.checked == 0 and result.upgraded == 0


async def test_a_still_dead_api_puts_the_answer_back():
    """Otherwise an outage would drain the queue into nothing."""
    redis = await _queued(_parked())
    svc = _service(redis, None, FakeUserWord())
    result = await svc.run(now=1001.0)
    assert result.upgraded == 0
    assert await svc._queue.pending() == 1


async def test_nothing_runs_without_a_checker():
    redis = await _queued(_parked())
    svc = _service(redis, AnswerVerdict(mastery.TYPED_TYPO, "x"), FakeUserWord(), key="")
    result = await svc.run(now=1001.0)
    assert result.checked == 0
    assert await svc._queue.pending() == 1  # untouched, retried when it returns


async def test_a_word_that_vanished_is_skipped_without_crashing():
    redis = await _queued(_parked())
    svc = _service(redis, AnswerVerdict(mastery.TYPED_TYPO, "x"), uw=None)
    result = await svc.run(now=1001.0)
    assert result.upgraded == 0


# ---- a slow round trip should not cost the user credit ----


async def test_a_single_timeout_is_retried_before_giving_up():
    """Prod misses came from one unlucky round trip, not from a dead API. The
    fallback is not free — the user is told they missed and has to wait for the
    regrade — so it is worth asking twice."""
    svc = _svc()
    calls = []

    async def flaky(word, translation, answer):
        calls.append(answer)
        if len(calls) == 1:
            raise TimeoutError
        return AnswerVerdict(mastery.TYPED_TYPO, "опечатка")

    svc._ask = flaky
    verdict = await svc.classify("explain", "объяснять", "explane")
    assert len(calls) == 2
    assert verdict is not None
    assert verdict.credited


async def test_it_gives_up_once_the_retries_are_spent():
    """Still None on a real outage — the degraded notice and the parked answer
    depend on this staying distinct from a 'wrong' verdict."""
    svc = _svc()
    calls = []

    async def always_slow(word, translation, answer):
        calls.append(answer)
        raise TimeoutError

    svc._ask = always_slow
    assert await svc.classify("explain", "объяснять", "explane") is None
    assert len(calls) == 2  # the original try plus one retry


async def test_a_retried_success_is_still_cached():
    svc = _svc()
    state = {"n": 0}

    async def flaky(word, translation, answer):
        state["n"] += 1
        if state["n"] == 1:
            raise TimeoutError
        return AnswerVerdict(mastery.TYPED_TYPO, "опечатка")

    svc._ask = flaky
    await svc.classify("explain", "объяснять", "explane")
    state["n"] = 5  # any further call would return the wrong thing
    again = await svc.classify("explain", "объяснять", "explane")
    assert again is not None and again.credited


# ---- the promised recount is always reported back ----


async def test_a_genuine_miss_still_reports_that_the_checker_returned():
    """The card promised «вернётся сама, ответ пересчитаю». Going quiet because
    the miss really was a miss leaves that promise looking dropped."""
    redis = await _queued(_parked())
    svc = _service(redis, AnswerVerdict(mastery.WRONG, ""), FakeUserWord())
    result = await svc.run(now=1001.0)
    assert result.rechecked == {999}
    assert not result.per_user  # nothing to list, but the user is still told


async def test_an_upgrade_reports_the_same_user_once():
    redis = await _queued(_parked())
    svc = _service(redis, AnswerVerdict(mastery.TYPED_TYPO, "опечатка"), FakeUserWord())
    result = await svc.run(now=1001.0)
    assert result.rechecked == {999}
    assert 999 in result.per_user


async def test_a_still_dead_api_tells_nobody_anything():
    """Nothing was rechecked, so there is no news to deliver."""
    redis = await _queued(_parked())
    svc = _service(redis, None, FakeUserWord())
    result = await svc.run(now=1001.0)
    assert result.rechecked == set()


async def test_a_stale_answer_produces_no_notice():
    redis = await _queued(_parked(at=0.0))
    svc = _service(redis, AnswerVerdict(mastery.TYPED_TYPO, "x"), FakeUserWord())
    result = await svc.run(now=10_000_000.0)
    assert result.rechecked == set()
