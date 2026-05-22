from __future__ import annotations

from dataclasses import dataclass, field

# Pure, I/O-free drill engine. The study session stores this in Redis and wraps
# it with cards/quiz options + spaced-repetition persistence.
#
# Model: every word must be cleared through two stages —
#   1. QUIZ  — recognise the translation among options
#   2. TYPE  — reproduce the English word from the translation
# A correct QUIZ promotes the word to TYPE; a correct TYPE marks it learned.
# Any wrong answer keeps the word at the same stage and pushes it a few cards
# back, so unknown words keep coming back until they're answered correctly.

STAGE_QUIZ = "quiz"
STAGE_TYPE = "type"

# How many other cards to put between a re-queued word and "now".
REQUEUE_GAP = 3


def normalize_answer(text: str) -> str:
    """Forgiving normalization for typed answers (case / spacing / leading 'to ')."""
    s = " ".join(text.strip().lower().split())
    if s.startswith("to "):
        s = s[3:].strip()
    return s


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def is_typing_correct(user_input: str, writing: str) -> bool:
    if not user_input or not writing:
        return False
    typed = normalize_answer(user_input)
    target = normalize_answer(writing)
    if typed == target:
        return True
    # Forgive a single typo on longer words (a slip shouldn't fail the card and
    # tank the spacing interval). Short words must match exactly — there one
    # edit is a different word ("cat"/"car").
    return len(target) >= 4 and _levenshtein(typed, target) <= 1


@dataclass
class DrillState:
    queue: list[list]  # [[user_word_id, stage], ...] — index 0 is the current card
    learned: list[int] = field(default_factory=list)
    mistakes: dict[str, int] = field(default_factory=dict)  # str(uw_id) -> count
    total: int = 0
    quiz_only: list[int] = field(default_factory=list)  # phrases: cleared after QUIZ, no TYPE

    @classmethod
    def new(cls, user_word_ids: list[int], quiz_only: list[int] | None = None) -> DrillState:
        ids = list(dict.fromkeys(int(i) for i in user_word_ids))  # dedupe, keep order
        qo = [int(i) for i in (quiz_only or [])]
        return cls(queue=[[i, STAGE_QUIZ] for i in ids], learned=[], mistakes={}, total=len(ids), quiz_only=qo)

    # ---- inspection ----

    def current(self) -> tuple[int, str] | None:
        if not self.queue:
            return None
        uw_id, stage = self.queue[0]
        return int(uw_id), str(stage)

    def is_complete(self) -> bool:
        return not self.queue

    def learned_count(self) -> int:
        return len(self.learned)

    def remaining_count(self) -> int:
        return max(0, self.total - len(self.learned))

    def mistakes_for(self, uw_id: int) -> int:
        return int(self.mistakes.get(str(int(uw_id)), 0))

    # ---- transitions ----

    def answer(self, correct: bool) -> None:
        if not self.queue:
            return
        uw_id, stage = self.queue.pop(0)
        uw_id = int(uw_id)
        if correct:
            if stage == STAGE_QUIZ and uw_id not in self.quiz_only:
                self._requeue([uw_id, STAGE_TYPE])
            elif uw_id not in self.learned:
                self.learned.append(uw_id)
        else:
            key = str(uw_id)
            self.mistakes[key] = int(self.mistakes.get(key, 0)) + 1
            self._requeue([uw_id, stage])

    def skip(self) -> None:
        """Move the current card to the back without penalty."""
        if self.queue:
            self.queue.append(self.queue.pop(0))

    def remove_current(self) -> None:
        """Drop the current word from the session entirely (e.g. deleted)."""
        if not self.queue:
            return
        uw_id = int(self.queue[0][0])
        self.queue = [item for item in self.queue if int(item[0]) != uw_id]
        if uw_id in self.learned:
            self.learned.remove(uw_id)
        self.mistakes.pop(str(uw_id), None)
        self.total = max(0, self.total - 1)

    def _requeue(self, item: list) -> None:
        pos = min(len(self.queue), REQUEUE_GAP)
        self.queue.insert(pos, item)

    # ---- serialization ----

    def to_dict(self) -> dict:
        return {
            "queue": [[int(i), str(s)] for i, s in self.queue],
            "learned": [int(i) for i in self.learned],
            "mistakes": {str(k): int(v) for k, v in self.mistakes.items()},
            "total": int(self.total),
            "quiz_only": [int(i) for i in self.quiz_only],
        }

    @classmethod
    def from_dict(cls, data: dict) -> DrillState:
        return cls(
            queue=[[int(i), str(s)] for i, s in data.get("queue", [])],
            learned=[int(i) for i in data.get("learned", [])],
            mistakes={str(k): int(v) for k, v in (data.get("mistakes") or {}).items()},
            total=int(data.get("total", 0)),
            quiz_only=[int(i) for i in (data.get("quiz_only") or [])],
        )
