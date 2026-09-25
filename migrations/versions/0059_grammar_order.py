"""Put the grammar topics in an order where nothing arrives before what it stands on.

The sequence had a hole the learner could not work around: `did` was taught at
position 14 while Past Simple sat at position 2. For twelve topics in a row the
learner knew `went` and had no way to ask «Did you go?». The verb `to be` had no
topic of its own at all, and `wasn't` first appeared at position 21 — inside a
lesson about something else.

Three topics fill the gaps, and they go near the front because that is where
they are needed: `to be` right after Present Simple, `do / does` before the
tense that uses them to ask anything, `was / were` beside Past Simple.

`questions_word_order` is renamed rather than replaced. It was already a
mixed bag — two `do/does` questions, one `are`, one `did`, and two word-order
items — so what it really contained was the four new topics in one. It narrows
to «Вопросы в прошлом: did», keeping its slug and the exercise that belongs to
it; the other five move to the topics that now own them. Nothing is discarded.

Positions are assigned by an explicit slug → position list rather than by
shifting what is already there. The shifting is what caused the drift this
migration is fixing: 0054 moved everything below its insertion point by two,
and every position written down before that quietly became wrong.

No progress rows are reset. On the day this was written `user_grammar_topics`
held no row for `questions_word_order` at all, so there is nothing that would
be mistaken for a passed topic about `did` — see the guard below, which fails
loudly if that ever stops being true.

Revision ID: 0059
Revises: 0058
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


# The curriculum, in teaching order. Position is the index in this list.
ORDER = [
    "tense_present_simple",
    "verb_to_be",
    "do_does_questions",
    "tense_present_continuous",
    "tense_past_simple",
    "irregular_past",
    "was_were",
    "questions_word_order",
    "plurals_basic",
    "quantifiers_basic",
    "articles_basic",
    "prepositions_basic",
    "comparatives",
    "tense_future_will",
    "future_going_to",
    "modals_basic",
    "past_continuous",
    "irregular_participle",
    "present_perfect",
    "past_perfect",
    "present_perfect_continuous",
    "used_to",
    "gerund_infinitive",
    "conditionals_01",
    "conditional_second",
    "conditional_third",
    "passive_simple",
    "reported_speech",
    "relative_clauses",
    "tag_questions",
]

NEW_TOPICS = [
    (
        "verb_to_be",
        "Глагол to be (am/is/are)",
        "🔹 <b>am</b> — только с I. <b>is</b> — он, она, оно. <b>are</b> — you, we, they.\n"
        "Отрицание: <b>I'm not</b>, <b>he isn't</b>, <b>they aren't</b>.\n"
        "Вопрос — глагол вперёд: <b>Are you ready?</b> <b>Is she at home?</b>\n"
        "У to be нет do/does: «Do you are» — не бывает.",
        "A1",
    ),
    (
        "do_does_questions",
        "Отрицания и вопросы: do / does",
        "❓ Обычный глагол спрашивает и отрицает через <b>do</b> / <b>does</b>.\n"
        "<b>do</b> — I, you, we, they. <b>does</b> — he, she, it.\n"
        "Do you work? · Does he work? · I don't work · She doesn't work.\n"
        "Главное: после do/does глагол <b>без -s</b> — «Does she works» неверно.",
        "A1",
    ),
    (
        "was_were",
        "was / were и отрицания в прошлом",
        "⏪ Прошедшее от to be: <b>was</b> — I, he, she, it. <b>were</b> — you, we, they.\n"
        "Отрицание: <b>wasn't</b> / <b>weren't</b>. Вопрос — глагол вперёд: <b>Were you there?</b>\n"
        "Это не то же, что <b>didn't</b>: didn't — для обычных глаголов "
        "(I didn't go), wasn't — для состояния (I wasn't ready).",
        "A1",
    ),
]


# Twelve exercises per new topic, generated offline and checked mechanically.
# The check that mattered here is polarity: an option differing from the answer
# only by the contraction (`was` / `wasn't`) is a second correct answer unless
# the sentence says which one it means, so every such prompt carries the clause
# that decides it.
NEW_ITEMS = {
    "verb_to_be": [
        ("I ___ very hungry because I did not eat my breakfast today.", "am", ["is", "are", "isn't"]),
        ("I ___ ready to go out since I have finished all my work.", "am", ["is", "are", "aren't"]),
        ("The weather ___ nice today so we can go for a walk.", "is", ["am", "are", "aren't"]),
        ("My brother ___ at home because he has no lessons today.", "is", ["am", "are", "aren't"]),
        ("This book ___ very interesting so I read it every single night.", "is", ["am", "are", "isn't"]),
        ("You and I ___ friends because we have known each other for years.", "are", ["am", "is", "isn't"]),
        ("They ___ late for school because the bus did not come on time.", "are", ["am", "is", "isn't"]),
        ("We ___ going to the cinema tonight because we have free tickets.", "are", ["am", "is", "aren't"]),
        ("This coffee ___ hot anymore because I left it on the table.", "isn't", ["am", "is", "are"]),
        ("The door ___ locked because I forgot to turn the key today.", "isn't", ["am", "is", "are"]),
        ("These shoes ___ comfortable because they are too small for my feet.", "aren't", ["am", "is", "are"]),
        ("We ___ happy because we lost the game and played very badly.", "aren't", ["am", "is", "are"]),
    ],
    "do_does_questions": [
        ("How often ___ you play tennis at the local park?", "do", ["does", "don't", "doesn't"]),
        ("What ___ your friends usually eat for their lunch today?", "do", ["does", "don't", "doesn't"]),
        ("I always ___ my homework after school because I want good grades.", "do", ["does", "don't", "doesn't"]),
        ("When ___ your mother usually come home from her work?", "does", ["do", "don't", "doesn't"]),
        ("He ___ his best every day so he can pass the exam.", "does", ["do", "don't", "doesn't"]),
        ("How ___ this machine work to clean the dirty floor?", "does", ["do", "don't", "doesn't"]),
        ("I ___ like cold weather, so I prefer staying home.", "don't", ["do", "does", "doesn't"]),
        ("They ___ want to leave yet because the party is fun.", "don't", ["do", "does", "doesn't"]),
        ("We ___ need any help because we finished the job.", "don't", ["do", "does", "doesn't"]),
        ("She ___ eat meat because she is a strict vegetarian.", "doesn't", ["do", "does", "don't"]),
        ("She ___ like coffee at all because it tastes too bitter.", "doesn't", ["do", "does", "don't"]),
        ("The shop ___ open on Sundays, so we go there on Monday.", "doesn't", ["do", "does", "don't"]),
    ],
    "was_were": [
        ("The weather ___ sunny yesterday, so we went to the beach.", "was", ["were", "wasn't", "weren't"]),
        ("The test ___ easy because I studied all night for it.", "was", ["were", "wasn't", "weren't"]),
        ("The movie ___ very long, so we finished it after midnight.", "was", ["were", "wasn't", "weren't"]),
        ("The kids ___ happy because they got many gifts today.", "were", ["was", "wasn't", "weren't"]),
        ("The children ___ hungry after school, so they ate some snacks.", "were", ["was", "wasn't", "weren't"]),
        ("They ___ excited since they won the game yesterday afternoon.", "were", ["was", "wasn't", "weren't"]),
        ("He ___ tired, so he decided to go for a run.", "wasn't", ["was", "were", "weren't"]),
        ("The cake ___ good because it had too much salt in it.", "wasn't", ["was", "were", "weren't"]),
        ("The office ___ open today, so I stayed home to sleep.", "wasn't", ["was", "were", "weren't"]),
        ("They ___ ready for the exam, so they failed the test.", "weren't", ["was", "were", "wasn't"]),
        ("We ___ at the cinema because we stayed home to study.", "weren't", ["was", "were", "wasn't"]),
        ("The shops ___ busy, so we bought everything very quickly.", "weren't", ["was", "were", "wasn't"]),
    ],
}

RENAMED = {
    "slug": "questions_word_order",
    "title": "Вопросы в прошлом: did",
    "rule": (
        "⏪ Вопрос о прошлом — <b>did</b> перед подлежащим: <b>Did you go?</b> "
        "<b>Where did she work?</b>\n"
        "Отрицание: <b>didn't</b>. Глагол после did/didn't — <b>в первой форме</b>: "
        "«Did you went» неверно, правильно <b>Did you go</b>.\n"
        "did не используется с to be: не «Did you were», а <b>Were you</b>."
    ),
    "level": "A2",
}

# The old values, copied from 0027, so a downgrade restores the topic rather
# than leaving it under a title describing something it no longer teaches.
RENAMED_OLD = {
    "title": "Вопросы и порядок слов",
    "rule": (
        "❓ <b>Вопрос</b>: вспомогательный глагол перед подлежащим (Do you…? Does she…? "
        "Did they…? Are you…?). Обычный порядок: <b>подлежащее → глагол → дополнение</b>."
    ),
    "level": "A2",
}

# Which topic each of the six exercises belongs to once the mixed bag is split.
# Matched on the prompt: ids differ between databases, prompts do not.
ITEM_MOVES = [
    ("___ you like coffee?", "do_does_questions"),
    ("___ she live in Paris?", "do_does_questions"),
    ("___ they coming to the party?", "verb_to_be"),
    ("Выбери правильный порядок:", "tense_present_simple"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # A topic whose progress rows point at a different lesson than the one the
    # title now promises would count as passed without having been taught.
    # There were none when this was written; refuse rather than guess if there
    # are now.
    leftover = bind.execute(
        sa.text(
            "SELECT count(*) FROM user_grammar_topics u"
            " JOIN grammar_topics t ON t.id = u.topic_id"
            " WHERE t.slug = 'questions_word_order'"
        )
    ).scalar_one()
    if leftover:
        raise RuntimeError(
            f"{leftover} progress rows on questions_word_order: decide whether to reset "
            "them before renaming the topic to «Вопросы в прошлом: did»"
        )

    for slug, title, rule, level in NEW_TOPICS:
        bind.execute(
            sa.text(
                "INSERT INTO grammar_topics (slug, track, title, rule, level, position)"
                " VALUES (:slug, 'en', :title, :rule, :level, 0)"
                " ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "title": title, "rule": rule, "level": level},
        )

    bind.execute(
        sa.text(
            "UPDATE grammar_topics SET title = :title, rule = :rule, level = :level"
            " WHERE slug = :slug"
        ),
        RENAMED,
    )

    for slug, items in NEW_ITEMS.items():
        for position, (prompt, correct, distractors) in enumerate(items):
            bind.execute(
                sa.text(
                    "INSERT INTO grammar_items (topic_id, prompt, correct, distractors, position)"
                    " SELECT id, :prompt, :correct, CAST(:distractors AS jsonb), :position"
                    " FROM grammar_topics WHERE slug = :slug"
                ),
                {
                    "slug": slug,
                    "prompt": prompt,
                    "correct": correct,
                    "distractors": json.dumps(distractors),
                    "position": position,
                },
            )

    for prompt, slug in ITEM_MOVES:
        bind.execute(
            sa.text(
                "UPDATE grammar_items SET topic_id ="
                " (SELECT id FROM grammar_topics WHERE slug = :slug)"
                " WHERE prompt = :prompt AND topic_id ="
                " (SELECT id FROM grammar_topics WHERE slug = 'questions_word_order')"
            ),
            {"slug": slug, "prompt": prompt},
        )

    for position, slug in enumerate(ORDER):
        bind.execute(
            sa.text("UPDATE grammar_topics SET position = :pos WHERE slug = :slug"),
            {"pos": position, "slug": slug},
        )


def downgrade() -> None:
    bind = op.get_bind()

    for prompt, _slug in ITEM_MOVES:
        bind.execute(
            sa.text(
                "UPDATE grammar_items SET topic_id ="
                " (SELECT id FROM grammar_topics WHERE slug = 'questions_word_order')"
                " WHERE prompt = :prompt AND topic_id IN"
                " (SELECT id FROM grammar_topics WHERE slug = ANY(:slugs))"
            ),
            {"prompt": prompt, "slugs": [s for _p, s in ITEM_MOVES]},
        )

    bind.execute(
        sa.text(
            "UPDATE grammar_topics SET title = :title, rule = :rule, level = :level"
            " WHERE slug = 'questions_word_order'"
        ),
        RENAMED_OLD,
    )

    bind.execute(
        sa.text("DELETE FROM grammar_items WHERE topic_id IN"
                " (SELECT id FROM grammar_topics WHERE slug = ANY(:slugs))"),
        {"slugs": [t[0] for t in NEW_TOPICS]},
    )
    bind.execute(
        sa.text("DELETE FROM grammar_topics WHERE slug = ANY(:slugs)"),
        {"slugs": [t[0] for t in NEW_TOPICS]},
    )

    # The order before this migration, as 0054 left it.
    previous = [
        "tense_present_simple",
        "tense_present_continuous",
        "tense_past_simple",
        "irregular_past",
        "tense_future_will",
        "articles_basic",
        "prepositions_basic",
        "plurals_basic",
        "comparatives",
        "quantifiers_basic",
        "modals_basic",
        "future_going_to",
        "irregular_participle",
        "present_perfect",
        "past_continuous",
        "conditionals_01",
        "questions_word_order",
        "used_to",
        "gerund_infinitive",
        "past_perfect",
        "present_perfect_continuous",
        "passive_simple",
        "reported_speech",
        "conditional_second",
        "conditional_third",
        "tag_questions",
        "relative_clauses",
    ]
    for position, slug in enumerate(previous):
        bind.execute(
            sa.text("UPDATE grammar_topics SET position = :pos WHERE slug = :slug"),
            {"pos": position, "slug": slug},
        )
