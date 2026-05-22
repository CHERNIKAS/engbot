"""grammar pack 3: plurals, comparatives, quantifiers, modals, tenses, conditionals, questions

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-23

Phase-1 grammar expansion — pure seeded content (delivery already exists). Nine
more choose-the-form topics, appended after articles/prepositions, incl. a
"word order" exercise style. Idempotent by slug; downgrade removes them.
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


GRAMMAR: list[dict] = [
    {
        "slug": "plurals_basic",
        "title": "Множественное число",
        "level": "A1",
        "position": 6,
        "rule": (
            "🔢 <b>Множественное число</b>: обычно <b>+s</b> (cat→cats); после s/x/ch/sh "
            "<b>+es</b> (box→boxes); y→ies (city→cities). Особые: man→men, child→children, "
            "foot→feet, tooth→teeth."
        ),
        "items": [
            ("one cat → two ___", "cats", ["cat", "cates", "caties"]),
            ("one box → two ___", "boxes", ["boxs", "box", "boxies"]),
            ("one child → two ___", "children", ["childs", "childrens", "childes"]),
            ("one man → two ___", "men", ["mans", "mens", "man"]),
            ("one foot → two ___", "feet", ["foots", "feets", "foot"]),
            ("one city → two ___", "cities", ["citys", "cityes", "citis"]),
        ],
    },
    {
        "slug": "comparatives",
        "title": "Степени сравнения",
        "level": "A2",
        "position": 7,
        "rule": (
            "📊 <b>Сравнение</b>: короткие слова <b>+er / the …est</b> (big→bigger→the biggest); "
            "длинные — <b>more / the most</b> (more interesting). Особые: good→better→best, "
            "bad→worse→worst."
        ),
        "items": [
            ("An elephant is ___ than a cat.", "bigger", ["big", "biggest", "more big"]),
            ("This book is ___ than that one.", "more interesting", ["interestinger", "most interesting", "interesting"]),
            ("Today is ___ than yesterday.", "better", ["gooder", "best", "more good"]),
            ("He runs ___ than me.", "faster", ["more fast", "fastest", "fast"]),
            ("This is the ___ film I've seen.", "best", ["better", "goodest", "most good"]),
            ("January is the ___ month here.", "coldest", ["colder", "most cold", "more cold"]),
        ],
    },
    {
        "slug": "quantifiers_basic",
        "title": "much / many / some / any",
        "level": "A2",
        "position": 8,
        "rule": (
            "🥤 <b>many</b> — со счётными (many books), <b>much</b> — с несчётными (much water). "
            "<b>some</b> — в утверждениях, <b>any</b> — в вопросах и отрицаниях."
        ),
        "items": [
            ("How ___ water do you drink?", "much", ["many", "some", "a"]),
            ("There aren't ___ apples left.", "any", ["some", "much", "a"]),
            ("I have ___ friends in London.", "many", ["much", "any", "a"]),
            ("Would you like ___ tea?", "some", ["any", "many", "much"]),
            ("She doesn't have ___ money.", "much", ["many", "some", "a"]),
            ("There are ___ books on the shelf.", "some", ["much", "any", "a"]),
        ],
    },
    {
        "slug": "modals_basic",
        "title": "Модальные: can / must / should / have to",
        "level": "A2",
        "position": 9,
        "rule": (
            "🛠 <b>can</b> — умение/возможность, <b>must</b> — обязанность, <b>should</b> — совет, "
            "<b>have to</b> — необходимость. После модального — базовая форма (can swim)."
        ),
        "items": [
            ("I ___ swim very well.", "can", ["must", "should", "have"]),
            ("You ___ see a doctor.", "should", ["can", "must to", "have"]),
            ("Drivers ___ stop at red lights.", "must", ["can", "should", "would"]),
            ("She ___ wear a uniform at work.", "has to", ["must to", "can to", "should to"]),
            ("___ you help me, please?", "Can", ["Must", "Should", "Have"]),
            ("We ___ hurry — we have plenty of time.", "don't have to", ["mustn't", "shouldn't", "can't"]),
        ],
    },
    {
        "slug": "future_going_to",
        "title": "Future: to be going to",
        "level": "A2",
        "position": 10,
        "rule": (
            "🗓 <b>to be going to</b> — планы и очевидное будущее. <b>am/is/are going to</b> + "
            "глагол. I'm going to travel."
        ),
        "items": [
            ("Look at the clouds! It ___ rain.", "is going to", ["going to", "will going", "is go to"]),
            ("I ___ visit my granny tomorrow.", "am going to", ["going to", "is going to", "will to"]),
            ("They ___ buy a new car.", "are going to", ["is going to", "going", "will going to"]),
            ("She ___ start a new job.", "is going to", ["are going to", "am going to", "going"]),
            ("We ___ watch a film tonight.", "are going to", ["is going to", "going", "will to"]),
            ("He ___ study medicine.", "is going to", ["are going to", "going to be", "will going"]),
        ],
    },
    {
        "slug": "present_perfect",
        "title": "Present Perfect",
        "level": "B1",
        "position": 11,
        "rule": (
            "✅ <b>Present Perfect</b> (have/has + V3) — действие связано с настоящим: опыт, "
            "результат, «уже/ещё». I <b>have seen</b> it."
        ),
        "items": [
            ("I ___ never been to Japan.", "have", ["has", "am", "did"]),
            ("She ___ already finished her work.", "has", ["have", "is", "did"]),
            ("___ you ever eaten sushi?", "Have", ["Has", "Did", "Are"]),
            ("We ___ lived here for ten years.", "have", ["has", "are", "did"]),
            ("He ___ just left the office.", "has", ["have", "is", "did"]),
            ("They ___ not arrived yet.", "have", ["has", "are", "did"]),
        ],
    },
    {
        "slug": "past_continuous",
        "title": "Past Continuous",
        "level": "B1",
        "position": 12,
        "rule": (
            "⏳ <b>Past Continuous</b> (was/were + V-ing) — действие шло в момент в прошлом. "
            "I <b>was reading</b> when he called."
        ),
        "items": [
            ("I ___ TV when you called.", "was watching", ["watched", "am watching", "were watching"]),
            ("They ___ football at 5 pm.", "were playing", ["was playing", "played", "are playing"]),
            ("She ___ when the phone rang.", "was sleeping", ["slept", "were sleeping", "is sleeping"]),
            ("We ___ dinner at eight.", "were having", ["was having", "had", "are having"]),
            ("What ___ you doing yesterday?", "were", ["was", "did", "are"]),
            ("It ___ raining all morning.", "was", ["were", "is", "did"]),
        ],
    },
    {
        "slug": "conditionals_01",
        "title": "Условные: 0 и 1 тип",
        "level": "B1",
        "position": 13,
        "rule": (
            "🔀 <b>0-й тип</b> (факты): If + Present, Present (If you heat ice, it melts).\n"
            "<b>1-й тип</b> (реальное будущее): If + Present, <b>will</b> (If it rains, we will stay)."
        ),
        "items": [
            ("If you heat water, it ___.", "boils", ["will boil", "boiled", "boil"]),
            ("If it rains tomorrow, we ___ at home.", "will stay", ["stay", "stayed", "would stay"]),
            ("If you ___ hard, you'll pass.", "study", ["will study", "studied", "would study"]),
            ("Ice ___ if you heat it.", "melts", ["will melt", "melted", "would melt"]),
            ("If she calls, I ___ you.", "will tell", ["tell", "told", "would tell"]),
            ("Plants die if they ___ water.", "don't get", ["won't get", "didn't get", "wouldn't get"]),
        ],
    },
    {
        "slug": "questions_word_order",
        "title": "Вопросы и порядок слов",
        "level": "A2",
        "position": 14,
        "rule": (
            "❓ <b>Вопрос</b>: вспомогательный глагол перед подлежащим (Do you…? Does she…? "
            "Did they…? Are you…?). Обычный порядок: <b>подлежащее → глагол → дополнение</b>."
        ),
        "items": [
            ("___ you like coffee?", "Do", ["Are", "Does", "Is"]),
            ("___ she live in Paris?", "Does", ["Do", "Is", "Are"]),
            ("___ they coming to the party?", "Are", ["Do", "Is", "Does"]),
            ("Where ___ you go yesterday?", "did", ["do", "are", "was"]),
            ("Выбери правильный порядок:", "She goes to school every day", [
                "She to school goes every day",
                "Goes she to school every day",
                "Every day she to school goes",
            ]),
            ("Выбери правильный порядок:", "I usually drink tea in the morning", [
                "I drink usually tea in the morning",
                "Usually I tea drink in the morning",
                "I tea drink usually in the morning",
            ]),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for topic in GRAMMAR:
        if conn.execute(
            sa.text("SELECT id FROM grammar_topics WHERE slug = :s"), {"s": topic["slug"]}
        ).first():
            continue
        tid = conn.execute(
            sa.text(
                "INSERT INTO grammar_topics (slug, track, title, rule, level, position) "
                "VALUES (:slug, 'en', :title, :rule, :level, :position) RETURNING id"
            ),
            {"slug": topic["slug"], "title": topic["title"], "rule": topic["rule"],
             "level": topic["level"], "position": topic["position"]},
        ).scalar()
        for pos, (prompt, correct, distractors) in enumerate(topic["items"]):
            conn.execute(
                sa.text(
                    "INSERT INTO grammar_items (topic_id, prompt, correct, distractors, position) "
                    "VALUES (:t, :p, :c, CAST(:d AS JSONB), :pos)"
                ),
                {"t": tid, "p": prompt, "c": correct, "d": json.dumps(distractors, ensure_ascii=False), "pos": pos},
            )


def downgrade() -> None:
    conn = op.get_bind()
    slugs = [t["slug"] for t in GRAMMAR]
    conn.execute(
        sa.text("DELETE FROM grammar_topics WHERE slug IN :s").bindparams(
            sa.bindparam("s", expanding=True)
        ),
        {"s": slugs},
    )
