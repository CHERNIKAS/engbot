from __future__ import annotations

# Deterministic part-of-speech inference from a Russian translation. No external
# data, no API — used to backfill words.part_of_speech (migration 0016) so quiz
# distractors can be matched by POS. Tuned for *precision*: when in doubt return
# None (the distractor picker then falls back to level/random), because a wrong
# tag produces a confidently-wrong distractor, while None just degrades softly.

# Dictionary-form verb endings: a vowel + ть (infinitives), -ти/-чь, and the
# reflexive -ться/-тись/-чься. We deliberately don't accept a bare "ть": that
# would swallow abstract nouns on -ость/-сть («возможность», «честность»).
_VERB_ENDINGS = (
    "ться", "тись", "чься",
    "ать", "ять", "еть", "ить", "ыть", "уть", "оть",
    "ти", "чь",
)

# Dictionary-form adjective endings (masc/fem singular). Note these all end in
# 'й'/'я' and so do NOT collide with neuter nouns on -ие/-ие or -ия (день 'е'/'я'
# nouns like «знание», «ситуация»), which we deliberately do NOT treat as adj.
_ADJ_ENDINGS = ("ый", "ий", "ой", "ая", "яя")

# Common adverbs whose translations would otherwise default to "noun".
_ADVERBS = {
    "сейчас", "здесь", "там", "тут", "сегодня", "завтра", "вчера",
    "скоро", "рано", "поздно", "всегда", "никогда", "часто", "редко",
}


def _first_sense(translation: str) -> str:
    """First alternative of a multi-sense translation, lowercased.
    «идти / ехать» -> «идти», «решать (проблему)» -> «решать»."""
    s = translation.strip().lower()
    for sep in ("/", ",", ";"):
        if sep in s:
            s = s.split(sep, 1)[0]
    # drop a trailing parenthetical clarifier: «решать (проблему)» -> «решать»
    if "(" in s:
        s = s.split("(", 1)[0]
    return s.strip()


def infer_part_of_speech(translation: str | None) -> str | None:
    """Best-effort POS ('verb' | 'adj' | 'noun') from a RU translation, or None
    when it can't be inferred confidently (phrases, adverbs, unknown shapes)."""
    if not translation:
        return None
    sense = _first_sense(translation)
    if not sense:
        return None
    # Only single-word senses are safe to tag; phrases ("ждать с нетерпением",
    # "окружающая среда") are left to pack-level overrides / None.
    if len(sense.split()) != 1:
        return None
    word = sense
    if word in _ADVERBS:
        return None
    if word.endswith(_VERB_ENDINGS):
        return "verb"
    if word.endswith(_ADJ_ENDINGS):
        return "adj"
    return "noun"
