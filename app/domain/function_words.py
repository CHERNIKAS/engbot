"""Words the vocabulary rotation must never teach as cards.

A "pick the translation" card only works when the word has one answer a learner
could actually retrieve. These fail that test in one of two ways:

  * no single answer exists — `of` is «из / о / от / с» depending on the noun
    behind it, so any card either marks correct answers wrong or teaches one
    context as if it were the word's meaning;
  * the answer is grammar wearing a vocabulary card — `must`, `some`, `which`
    are each the subject of a grammar topic in this bot, where they get a rule
    and exercises in context instead of four buttons.

Nothing here is dropped from the curriculum; it moves to where it is taught
properly. Migration 0040 flagged the first twenty of these (articles and
negated auxiliaries) after prod showed them being served as cards whose
distractors differed only by tense.

Deliberately NOT here:

  * numbers — `seven` → «семь» is an exact pair that has to be memorised, and
    the flag is a hard filter in the pickers, so listing them would leave the
    numbers topic with nothing to serve;
  * content prepositions with one stable sense (`without`, `between`) are still
    listed, because the prepositions grammar topic owns them as a set and
    splitting the set across two delivery systems teaches neither.
"""

from __future__ import annotations

# No translation to pick at all.
ARTICLES = ("a", "an", "the")

# Carry tense and person, not meaning. Every honest distractor for «не делает»
# is «не делал» / «не делаю» — a grammar question with vocabulary's clothes on.
AUXILIARIES = (
    "be", "am", "is", "are", "was", "were", "been", "being",
    "do", "does", "did", "done",
    "have", "has", "had", "having",
)

CONTRACTIONS = (
    "it's", "i'm", "i've", "i'll", "let's", "that's",
    "he's", "she's", "we're", "they're", "you're",
    "aren't", "isn't", "wasn't", "weren't",
    "can't", "couldn't", "mustn't", "shouldn't", "won't", "wouldn't",
    "didn't", "doesn't", "don't", "hadn't", "hasn't", "haven't",
)

PRONOUNS = (
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their",
    "mine", "yours", "hers", "ours", "theirs",
    "myself", "yourself", "himself", "herself", "itself",
    "ourselves", "yourselves", "themselves",
    "this", "that", "these", "those", "there",
)

# Taught by the modal-verbs topic, which is where their meaning lives: `must`
# alone is not «должен», it is a slot in a table of obligation and certainty.
#
# `may` is deliberately absent: the month May is ordinary vocabulary, and this
# check lowercases before matching, so listing the modal would take the month
# down with it. The modal is covered by the grammar topic, which reads from
# grammar_items and never consults this list.
MODALS = ("can", "could", "might", "must", "shall", "should", "will", "would", "ought")

PREPOSITIONS = (
    "of", "to", "in", "for", "on", "with", "at", "from", "by", "as",
    "about", "into", "onto", "over", "under", "above", "below", "after", "before",
    "between", "among", "amongst", "through", "throughout", "during", "despite",
    "against", "across", "along", "around", "behind", "beside", "besides",
    "beyond", "within", "without", "inside", "outside", "unlike",
    "toward", "towards", "up", "down", "out", "off", "near", "per", "via", "upon",
    "alongside", "underneath", "opposite",
)

CONJUNCTIONS = (
    "and", "but", "or", "so", "if", "than", "nor",
    "because", "although", "though", "while", "since", "until", "unless", "whether",
)

# Question words: the subject of their own topic, and answered by sentence
# order rather than by recall.
WH_WORDS = ("where", "when", "how", "why", "which", "who", "whom", "whose", "what")

# The much / many / some / any topic owns these as a contrast set.
QUANTIFIERS = (
    "all", "any", "both", "each", "either", "every", "few", "many", "more",
    "most", "much", "neither", "several", "some", "such",
)

NEGATION = ("not", "no", "none", "never", "nothing", "nobody", "nowhere")

# Degree and frequency: `always` / `often` / `sometimes` are introduced with
# Present Simple as a position-in-the-sentence rule, not as standalone words.
ADVERBS = (
    "very", "too", "also", "just", "only", "even", "still", "yet", "already",
    "ever", "always", "often", "sometimes", "usually", "then", "now", "here",
)

FUNCTION_WORDS: frozenset[str] = frozenset(
    ARTICLES
    + AUXILIARIES
    + CONTRACTIONS
    + PRONOUNS
    + MODALS
    + PREPOSITIONS
    + CONJUNCTIONS
    + WH_WORDS
    + QUANTIFIERS
    + NEGATION
    + ADVERBS
)


def is_function_word(writing: str | None) -> bool:
    """Whether this entry belongs to grammar rather than the word rotation.

    Multi-word entries are never function words: a phrase like "a lot of" is a
    phrasebook item that happens to be built from them.
    """
    if not writing:
        return False
    cleaned = writing.strip().lower()
    if not cleaned or " " in cleaned:
        return False
    return cleaned in FUNCTION_WORDS
