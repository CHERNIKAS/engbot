"""Teach the irregular verb forms the word rotation stopped serving.

Migration 0051 flagged `drove`, `knew`, `said` and twenty others as inflections
and took them out of the vocabulary queue, because «drove — вел машину» asks a
learner to memorise a translation of a tense. That was right, and it left a
hole: the forms were no longer taught by anything at all, so `drive / drove /
driven` — the single most-drilled table in any beginner course — was not in the
product.

Two topics rather than one, placed where each is needed:

  * the second form lands straight after Past Simple, which is the lesson that
    creates the need for it;
  * the third form lands just before Present Perfect, for the same reason, and
    only for the twenty verbs whose participle actually differs from the past.
    Drilling `bought / bought` teaches nothing the previous topic did not.

Splitting them also keeps either topic from becoming the monster that the
prepositions topic turned into: 50 and 19 exercises instead of one block of 69.

Distractors are the learner's own likely errors — the bare stem, the -s form,
and the regular `-ed` that does not exist (`selled`, `payed`) — so the card
tests the form rather than rewarding elimination.

Revision ID: 0054
Revises: 0053
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

PAST_RULE = (
    "🔁 <b>Неправильные глаголы: вторая форма</b>\n"
    "Большинство глаголов образуют прошедшее через <b>-ed</b>: work → worked.\n"
    "Но самые частые глаголы — исключения, и их формы нужно просто помнить:\n"
    "go → <b>went</b>, see → <b>saw</b>, buy → <b>bought</b>, take → <b>took</b>.\n"
    "Их около двухсот, но в обычной речи работают примерно пятьдесят."
)

PARTICIPLE_RULE = (
    "🔁 <b>Неправильные глаголы: третья форма</b>\n"
    "Третья форма нужна для Present Perfect и пассива: I have <b>seen</b> it.\n"
    "У многих глаголов она совпадает со второй: buy → bought → <b>bought</b>.\n"
    "Но у самых частых — отличается:\n"
    "go → went → <b>gone</b>, see → saw → <b>seen</b>, give → gave → <b>given</b>."
)

# (slug, title, rule, level, position it must occupy once everything shifts)
TOPICS = (
    ("irregular_past", "Неправильные глаголы: 2-я форма", PAST_RULE, "A2", 3),
    ("irregular_participle", "Неправильные глаголы: 3-я форма", PARTICIPLE_RULE, "B1", 12),
)

# (topic_slug, prompt, correct, distractors)
ITEMS: tuple[tuple, ...] = (
    ("irregular_participle", "I have ___ to the cinema three times this month.", "been",
     ["be", "was", "were"]),
    ("irregular_participle", "He has already ___ his homework for the next lesson.", "done",
     ["do", "did", "does"]),
    ("irregular_participle", "My sister has ___ to the park with her friends.", "gone",
     ["go", "went", "goes"]),
    ("irregular_participle", "I have ___ this famous actor for many years now.", "known",
     ["know", "knew", "knows"]),
    ("irregular_participle", "They have ___ many photos of the beautiful mountain view.", "taken",
     ["take", "took", "takes"]),
    ("irregular_participle", "We have ___ that interesting movie at the cinema twice.", "seen",
     ["see", "saw", "sees"]),
    ("irregular_participle", "I hope you will ___ to my birthday party tomorrow.", "come",
     ["came", "comes", "coming"]),
    ("irregular_participle", "She has ___ me a nice gift for my birthday.", "given",
     ["give", "gave", "gives"]),
    ("irregular_participle", "She wants to ___ a doctor when she grows up.", "become",
     ["became", "becomes", "becoming"]),
    ("irregular_participle", "He has ___ us his new house after the renovation.", "shown",
     ["show", "showed", "shows"]),
    ("irregular_participle", "The heavy rain has ___ to fall on the roof.", "begun",
     ["begin", "began", "begins"]),
    ("irregular_participle", "This letter was ___ by my friend last week.", "written",
     ["write", "wrote", "writes"]),
    ("irregular_participle", "He has ___ five kilometers in the park today.", "run",
     ["ran", "runs", "running"]),
    ("irregular_participle", "English is ___ by millions of people every day.", "spoken",
     ["speak", "spoke", "speaks"]),
    ("irregular_participle", "The map was ___ by a very famous artist.", "drawn",
     ["draw", "drew", "draws"]),
    ("irregular_participle", "The glass was ___ when it fell to floor.", "broken",
     ["break", "broke", "breaks"]),
    ("irregular_participle", "All the cake has been ___ by the children.", "eaten",
     ["eat", "ate", "eats"]),
    ("irregular_participle", "The cold water has already been ___ by him.", "drunk",
     ["drink", "drank", "drinks"]),
    ("irregular_participle", "The car has been ___ for many long hours.", "driven",
     ["drive", "drove", "drives"]),
    ("irregular_past", "My father ___ at home all day yesterday.", "was",
     ["be", "been", "beed"]),
    ("irregular_past", "She ___ a nice dream last night.", "had",
     ["have", "haveed", "has"]),
    ("irregular_past", "I ___ my homework before dinner time.", "did",
     ["do", "done", "doed"]),
    ("irregular_past", "He ___ hello to me this morning.", "said",
     ["say", "sayed", "says"]),
    ("irregular_past", "We ___ to the park last Sunday.", "went",
     ["go", "gone", "goed"]),
    ("irregular_past", "I ___ a letter from my friend today.", "got",
     ["get", "geted", "gets"]),
    ("irregular_past", "She ___ a cake for my birthday.", "made",
     ["make", "makeed", "makes"]),
    ("irregular_past", "I ___ the answer to the question.", "knew",
     ["know", "known", "knowed"]),
    ("irregular_past", "He ___ it was a good idea.", "thought",
     ["think", "thinked", "thinks"]),
    ("irregular_past", "She ___ her umbrella to the office.", "took",
     ["take", "taken", "takeed"]),
    ("irregular_past", "I ___ a big dog in the street.", "saw",
     ["see", "seen", "seeed"]),
    ("irregular_past", "My brother ___ home very late yesterday.", "came",
     ["come", "comeed", "comes"]),
    ("irregular_past", "I ___ a coin on the ground.", "found",
     ["find", "finded", "finds"]),
    ("irregular_past", "She ___ me a beautiful red apple.", "gave",
     ["give", "given", "giveed"]),
    ("irregular_past", "He ___ me a very funny story.", "told",
     ["tell", "telled", "tells"]),
    ("irregular_past", "The weather ___ very cold late last night.", "became",
     ["become", "becomeed", "becomes"]),
    ("irregular_past", "The guide ___ us the old castle yesterday afternoon.", "showed",
     ["show", "shown", "showing"]),
    ("irregular_past", "She ___ the house early this morning.", "left",
     ["leave", "leaveed", "leaves"]),
    ("irregular_past", "I ___ very tired after the long trip.", "felt",
     ["feel", "feeled", "feels"]),
    ("irregular_past", "My friend ___ a gift to the party.", "brought",
     ["bring", "bringed", "brings"]),
    ("irregular_past", "The movie ___ ten minutes ago at home.", "began",
     ["begin", "begined", "begun"]),
    ("irregular_past", "He ___ his keys in his pocket yesterday.", "kept",
     ["keep", "keeped", "keeps"]),
    ("irregular_past", "She ___ my hand during the scary movie.", "held",
     ["hold", "holded", "holds"]),
    ("irregular_past", "He ___ a letter to his grandma yesterday.", "wrote",
     ["write", "writeed", "written"]),
    ("irregular_past", "We ___ in line for an hour today.", "stood",
     ["stand", "standed", "stands"]),
    ("irregular_past", "I ___ a strange noise outside last night.", "heard",
     ["hear", "heared", "hears"]),
    ("irregular_past", "My mother ___ me stay up late last Saturday.", "let",
     ["leted", "lets", "letting"]),
    ("irregular_past", "He ___ to say something nice to her.", "meant",
     ["mean", "meaned", "means"]),
    ("irregular_past", "They ___ the table for dinner ten minutes ago.", "set",
     ["seted", "sets", "setting"]),
    ("irregular_past", "I ___ my best friend at the park.", "met",
     ["meet", "meeted", "meets"]),
    ("irregular_past", "The young boy ___ to the park yesterday morning.", "ran",
     ["run", "runed", "running"]),
    ("irregular_past", "I ___ for the dinner with my credit card.", "paid",
     ["pay", "payed", "paying"]),
    ("irregular_past", "She ___ on the comfortable sofa all evening long.", "sat",
     ["sit", "sited", "sitting"]),
    ("irregular_past", "He ___ to his teacher after the math class.", "spoke",
     ["speak", "speaked", "spoken"]),
    ("irregular_past", "I ___ a very interesting book last weekend.", "read",
     ["readed", "reads", "reading"]),
    ("irregular_past", "We ___ some fresh fruit at the local market.", "bought",
     ["buy", "buyed", "buying"]),
    ("irregular_past", "My friend ___ me a nice postcard from Italy.", "sent",
     ["send", "sended", "sending"]),
    ("irregular_past", "They ___ a small house near the blue lake.", "built",
     ["build", "builded", "building"]),
    ("irregular_past", "I ___ everything the teacher explained in class.", "understood",
     ["understand", "understanded", "understanding"]),
    ("irregular_past", "She ___ a beautiful picture for her mother yesterday.", "drew",
     ["draw", "drawed", "drawn"]),
    ("irregular_past", "He accidentally ___ his favorite coffee cup today.", "broke",
     ["break", "breaked", "broken"]),
    ("irregular_past", "I ___ all my money on the new shoes.", "spent",
     ["spend", "spended", "spending"]),
    ("irregular_past", "We ___ a delicious pizza for lunch yesterday.", "ate",
     ["eat", "eated", "eaten"]),
    ("irregular_past", "She ___ a glass of cold water this morning.", "drank",
     ["drink", "drinked", "drunk"]),
    ("irregular_past", "My father ___ his new car to work today.", "drove",
     ["drive", "driveed", "driven"]),
    ("irregular_past", "The man ___ his old car to his neighbor yesterday.", "sold",
     ["sell", "selled", "sells"]),
    ("irregular_past", "Our team ___ the big football game last Sunday afternoon.", "won",
     ["win", "wined", "wins"]),
    ("irregular_past", "My mother ___ me how to cook delicious pasta dishes.", "taught",
     ["teach", "teached", "teaches"]),
    ("irregular_past", "The boy ___ the ball during the game at school.", "caught",
     ["catch", "catched", "catches"]),
    ("irregular_past", "I ___ very well in my bed all night long.", "slept",
     ["sleep", "sleeped", "sleeps"]),)


def upgrade() -> None:
    bind = op.get_bind()
    for slug, title, rule, level, position in TOPICS:
        # Open the slot: everything at or after it moves down one.
        bind.execute(
            sa.text("UPDATE grammar_topics SET position = position + 1 WHERE position >= :pos"),
            {"pos": position},
        )
        bind.execute(
            sa.text(
                "INSERT INTO grammar_topics (slug, track, title, rule, level, position)"
                " VALUES (:slug, 'en', :title, :rule, :level, :pos)"
                " ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "title": title, "rule": rule, "level": level, "pos": position},
        )

    topics = dict(bind.execute(sa.text("SELECT slug, id FROM grammar_topics")).fetchall())
    rows = []
    seen: dict[int, int] = {}
    for slug, prompt, correct, distractors in ITEMS:
        topic_id = topics.get(slug)
        if topic_id is None:
            continue
        pos = seen.get(topic_id, 0)
        seen[topic_id] = pos + 1
        rows.append(
            {
                "topic_id": topic_id,
                "prompt": prompt,
                "correct": correct,
                "distractors": json.dumps(distractors, ensure_ascii=False),
                "position": pos,
            }
        )
    if rows:
        bind.execute(
            sa.text(
                "INSERT INTO grammar_items (topic_id, prompt, correct, distractors, position)"
                " VALUES (:topic_id, :prompt, :correct, CAST(:distractors AS jsonb), :position)"
            ),
            rows,
        )


def downgrade() -> None:
    bind = op.get_bind()
    slugs = [t[0] for t in TOPICS]
    bind.execute(
        sa.text(
            "DELETE FROM grammar_items WHERE topic_id IN"
            " (SELECT id FROM grammar_topics WHERE slug = ANY(:slugs))"
        ),
        {"slugs": slugs},
    )
    for slug, _title, _rule, _level, position in reversed(TOPICS):
        bind.execute(sa.text("DELETE FROM grammar_topics WHERE slug = :slug"), {"slug": slug})
        bind.execute(
            sa.text("UPDATE grammar_topics SET position = position - 1 WHERE position > :pos"),
            {"pos": position},
        )
