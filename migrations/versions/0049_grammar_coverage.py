"""Make the grammar topics actually cover what the stoplist handed them.

The function-word stoplist removes ~196 entries from the vocabulary rotation
because a card like "translate: of" has no single right answer. The stated
justification was that grammar teaches these instead. It did not: the
prepositions topic contained `at`, `in`, `on`, `to`; quantifiers had `any`,
`many`, `much`, `some`; modals stopped at `can` / `must` / `should` /
`have to`. Roughly twenty of the 196 were covered.

So about 175 words — among them `would`, the 36th most frequent word in
English, plus `may`, `without`, `within`, `among` and `above` — were taught by
neither side. They had simply left the product.

This adds 82 exercises covering 41 of those words, two sentences each so a word
is not learned off a single context. The format is the existing gap-fill; the
planned rework into sentence construction is a separate, much larger job, and
the hole should not stay open until it lands.

Distractors come from the same closed set as the answer, so the card cannot be
solved by elimination — a preposition of place is quizzed against other
prepositions of place. Each was verified to have exactly one blank, an answer
that appears nowhere else in the sentence, and three distinct distractors.

Revision ID: 0049
Revises: 0048
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

# (topic_slug, prompt, correct, distractors)
ITEMS: tuple[tuple, ...] = (
    ("modals_basic", "I ___ swim very well when I was a child.", "could",
     ["must", "shall", "will"]),
    ("modals_basic", "___ you please open the window for me, thanks?", "could",
     ["must", "shall", "should"]),
    ("modals_basic", "It ___ rain later, so take your umbrella with you.", "may",
     ["must", "should", "shall"]),
    ("modals_basic", "You ___ go home now if you are feeling tired.", "may",
     ["must", "will", "would"]),
    ("modals_basic", "He ___ be late because there is a lot of traffic.", "might",
     ["can", "must", "shall"]),
    ("modals_basic", "We ___ visit our friends if we have enough time.", "might",
     ["must", "shall", "will"]),
    ("modals_basic", "___ we go to the cinema this evening together?", "shall",
     ["can", "will", "would"]),
    ("modals_basic", "___ I open the door for you, dear guest?", "shall",
     ["will", "would", "could"]),
    ("modals_basic", "I ___ call you as soon as I get home.", "will",
     ["must", "would", "might"]),
    ("modals_basic", "The weather ___ be sunny tomorrow according to news.", "will",
     ["could", "should", "might"]),
    ("modals_basic", "___ you like to go to the cinema with me tonight?", "would",
     ["could", "should", "must"]),
    ("modals_basic", "I ___ like to have a cup of tea, please.", "would",
     ["can", "must", "should"]),
    ("prepositions_basic", "We saw a beautiful painting hanging ___ the fireplace.", "above",
     ["between", "among", "across"]),
    ("prepositions_basic", "The clouds are high ___ the green hills today.", "above",
     ["under", "between", "through"]),
    ("prepositions_basic", "They decided to swim ___ the wide blue river.", "across",
     ["between", "during", "among"]),
    ("prepositions_basic", "We walked ___ the street to get to the shop.", "across",
     ["behind", "under", "near"]),
    ("prepositions_basic", "I always feel tired ___ a long day at the office.", "after",
     ["before", "during", "until"]),
    ("prepositions_basic", "The small dog ran ___ the big cat across the yard.", "after",
     ["before", "near", "above"]),
    ("prepositions_basic", "The ladder is leaning ___ the wall of the house.", "against",
     ["inside", "near", "across"]),
    ("prepositions_basic", "Don't push your chair ___ the door like that, please.", "against",
     ["under", "outside", "around"]),
    ("prepositions_basic", "She was happy to be ___ her best friends.", "among",
     ["between", "across", "through"]),
    ("prepositions_basic", "The teacher stood ___ the students in the class.", "among",
     ["between", "above", "below"]),
    ("prepositions_basic", "We sat ___ the table to eat our tasty dinner.", "around",
     ["against", "inside", "across"]),
    ("prepositions_basic", "There are many beautiful trees ___ the small village square.", "around",
     ["under", "behind", "against"]),
    ("prepositions_basic", "Please wash your hands ___ you sit down for dinner.", "before",
     ["after", "during", "while"]),
    ("prepositions_basic", "The park is right ___ the old library on this street.", "before",
     ["behind", "between", "under"]),
    ("prepositions_basic", "The cat is hiding ___ the big green sofa now.", "behind",
     ["across", "outside", "around"]),
    ("prepositions_basic", "I left my keys ___ the door on the table.", "behind",
     ["under", "against", "inside"]),
    ("prepositions_basic", "The temperature is ten degrees ___ zero this morning.", "below",
     ["above", "across", "between"]),
    ("prepositions_basic", "Look at the small village ___ the high mountain.", "below",
     ["above", "between", "across"]),
    ("prepositions_basic", "The small cat is hiding ___ the two big chairs.", "between",
     ["through", "during", "among"]),
    ("prepositions_basic", "Please sit ___ me and my brother at the table.", "between",
     ["across", "above", "below"]),
    ("prepositions_basic", "I usually go to work ___ bus every single morning.", "by",
     ["in", "on", "at"]),
    ("prepositions_basic", "The new cafe is located ___ the river in the center.", "by",
     ["near", "under", "through"]),
    ("prepositions_basic", "It rained a lot ___ the long summer holiday.", "during",
     ["between", "across", "through"]),
    ("prepositions_basic", "I felt very tired ___ the long movie yesterday.", "during",
     ["under", "above", "between"]),
    ("prepositions_basic", "I received a lovely gift ___ my aunt for my birthday.", "from",
     ["to", "at", "by"]),
    ("prepositions_basic", "The train leaves ___ the main station at eight o'clock.", "from",
     ["to", "in", "at"]),
    ("prepositions_basic", "It is cold, so please wait ___ the warm house.", "inside",
     ["outside", "across", "behind"]),
    ("prepositions_basic", "Put the milk ___ the fridge to keep it cool.", "inside",
     ["around", "near", "under"]),
    ("prepositions_basic", "She walked ___ the kitchen to make some fresh coffee.", "into",
     ["onto", "out", "along"]),
    ("prepositions_basic", "The boy threw his dirty socks ___ the laundry basket.", "into",
     ["onto", "across", "under"]),
    ("prepositions_basic", "They live ___ the park so they walk there daily.", "near",
     ["across", "inside", "outside"]),
    ("prepositions_basic", "Is there a bus stop ___ your new house here?", "near",
     ["around", "against", "under"]),
    ("prepositions_basic", "The children are playing ___ in the sunny garden today.", "outside",
     ["inside", "against", "across"]),
    ("prepositions_basic", "Leave your wet shoes ___ the door before coming in.", "outside",
     ["under", "around", "behind"]),
    ("prepositions_basic", "The cat jumped ___ the garden fence to escape the dog.", "over",
     ["under", "in", "at"]),
    ("prepositions_basic", "We talked about our plans ___ a nice cup of tea.", "over",
     ["behind", "through", "near"]),
    ("prepositions_basic", "The train goes ___ a long tunnel every day.", "through",
     ["above", "below", "between"]),
    ("prepositions_basic", "We walked ___ the forest to reach the lake.", "through",
     ["among", "across", "during"]),
    ("prepositions_basic", "I found my lost pen ___ the small wooden desk.", "under",
     ["around", "outside", "across"]),
    ("prepositions_basic", "The dog is sleeping ___ the table in the kitchen.", "under",
     ["inside", "against", "near"]),
    ("prepositions_basic", "I like to eat my pasta ___ a lot of cheese.", "with",
     ["by", "for", "at"]),
    ("prepositions_basic", "She lives in a small house ___ her two best friends.", "with",
     ["by", "near", "among"]),
    ("prepositions_basic", "I cannot drink my morning coffee ___ any sugar in it.", "without",
     ["under", "behind", "near"]),
    ("prepositions_basic", "He went to the park ___ his dog this afternoon.", "without",
     ["above", "below", "across"]),
    ("quantifiers_basic", "___ the students are ready for the final exam.", "all",
     ["each", "both", "every"]),
    ("quantifiers_basic", "She ate ___ the cookies in the blue jar.", "all",
     ["each", "both", "every"]),
    ("quantifiers_basic", "___ of my parents are teachers at the school.", "both",
     ["all", "each", "every"]),
    ("quantifiers_basic", "I like ___ books because they have great stories.", "both",
     ["all", "each", "every"]),
    ("quantifiers_basic", "The teacher gave ___ student a small red apple.", "each",
     ["some", "all", "many"]),
    ("quantifiers_basic", "___ person in the room has a unique name tag.", "each",
     ["all", "some", "many"]),
    ("quantifiers_basic", "You can take ___ road to reach the station.", "either",
     ["neither", "each", "every"]),
    ("quantifiers_basic", "You can take ___ of these two books to read tonight.", "either",
     ["both", "all", "every"]),
    ("quantifiers_basic", "I visit my parents ___ weekend to help them.", "every",
     ["each", "all", "some"]),
    ("quantifiers_basic", "I visit my grandmother ___ Sunday for a nice lunch.", "every",
     ["some", "much", "few"]),
    ("quantifiers_basic", "I have very ___ friends living in this big city.", "few",
     ["many", "some", "all"]),
    ("quantifiers_basic", "There are ___ cookies left in the blue jar.", "few",
     ["many", "all", "some"]),
    ("quantifiers_basic", "___ people enjoy drinking coffee in the morning time.", "most",
     ["few", "none", "neither"]),
    ("quantifiers_basic", "___ of my friends live near the city center.", "most",
     ["few", "neither", "each"]),
    ("quantifiers_basic", "___ of the two brothers wanted to go home.", "neither",
     ["either", "none", "each"]),
    ("quantifiers_basic", "___ car is fast enough for the long race.", "neither",
     ["either", "each", "some"]),
    ("quantifiers_basic", "I wanted some milk but there was ___ left.", "none",
     ["few", "most", "several"]),
    ("quantifiers_basic", "___ of the students knew the correct answer today.", "none",
     ["most", "several", "few"]),
    ("quantifiers_basic", "I bought ___ shirts at the shop this morning.", "several",
     ["each", "every", "none"]),
    ("quantifiers_basic", "There are ___ problems with the new computer system.", "several",
     ["every", "each", "none"]),
    ("relative_clauses", "I do not know ___ he wants for his birthday party.", "what",
     ["that", "which", "who"]),
    ("relative_clauses", "Please tell me ___ you are doing this weekend at home.", "what",
     ["that", "who", "which"]),
    ("relative_clauses", "She is the woman ___ I saw at the park yesterday.", "whom",
     ["who", "which", "whose"]),
    ("relative_clauses", "The doctor ___ I visited last week gave me medicine.", "whom",
     ["who", "which", "whose"]),
    ("relative_clauses", "That is the girl ___ brother plays in our school band.", "whose",
     ["who", "which", "that"]),
    ("relative_clauses", "I met a man ___ car was parked in my spot.", "whose",
     ["who", "that", "which"]),)


def upgrade() -> None:
    bind = op.get_bind()
    topics = dict(
        bind.execute(sa.text("SELECT slug, id FROM grammar_topics")).fetchall()
    )
    # Append after whatever each topic already has, so the existing exercises
    # keep their order and the new ones follow rather than interleave.
    next_pos = dict(
        bind.execute(
            sa.text("SELECT topic_id, COALESCE(MAX(position), -1) + 1 FROM grammar_items GROUP BY topic_id")
        ).fetchall()
    )
    rows = []
    for slug, prompt, correct, distractors in ITEMS:
        topic_id = topics.get(slug)
        if topic_id is None:
            continue
        pos = next_pos.get(topic_id, 0)
        next_pos[topic_id] = pos + 1
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
    op.get_bind().execute(
        sa.text("DELETE FROM grammar_items WHERE prompt = ANY(:prompts)"),
        {"prompts": [p for _, p, _, _ in ITEMS]},
    )
