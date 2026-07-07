"""grammar wave 2: past perfect, perfect continuous, passive, reported speech, conditionals 2/3, tags, relative clauses

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-08

Eight more choose-the-form topics (B1/B2), appended after gerund/infinitive
(positions 17-24). Pure seeded content — delivery already exists. Rules follow
the 0029 style: explicit form mappings with inline mini-examples. Idempotent by
slug; downgrade removes the topics (items and per-user progress cascade).
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


GRAMMAR: list[dict] = [
    {
        "slug": "past_perfect",
        "title": "Past Perfect",
        "level": "B1",
        "position": 17,
        "rule": (
            "⏮ <b>Past Perfect</b> — действие случилось <b>раньше</b> другого момента "
            "в прошлом. Для всех лиц одинаково: <b>had + 3-я форма</b>.\n"
            "• When I arrived, the film <b>had started</b> (началось до моего прихода).\n"
            "• She was tired because she <b>had worked</b> all night.\n"
            "Часто с before, after, by the time, already."
        ),
        "items": [
            ("When we arrived, the film ___ already started.", "had", ["has", "have", "did"]),
            ("She ___ her keys, so she couldn't open the door.", "had lost", ["has lost", "loses", "was losing"]),
            ("By the time he was 20, he ___ three countries.", "had visited", ["has visited", "visits", "was visiting"]),
            ("I didn't laugh because I ___ the joke before.", "had heard", ["have heard", "hear", "was hearing"]),
            ("After they ___ dinner, they went for a walk.", "had eaten", ["have eaten", "eat", "were eating"]),
            ("He was tired because he ___ all night.", "had worked", ["has worked", "works", "is working"]),
            ("The house was quiet — everyone ___ to bed.", "had gone", ["has gone", "goes", "is going"]),
            ("We got home and saw that somebody ___ the window.", "had broken", ["has broken", "breaks", "is breaking"]),
        ],
    },
    {
        "slug": "present_perfect_continuous",
        "title": "Present Perfect Continuous",
        "level": "B1",
        "position": 18,
        "rule": (
            "🔄 <b>Present Perfect Continuous</b> — началось в прошлом и <b>до сих пор "
            "длится</b> (или только что закончилось). <b>have/has been + V-ing</b>:\n"
            "• I / you / we / they → <b>have been</b>: I <b>have been waiting</b> for an hour.\n"
            "• he / she / it → <b>has been</b>: She <b>has been working</b> since morning.\n"
            "Часто с for (как долго) и since (с какого момента)."
        ),
        "items": [
            ("I ___ for the bus for 20 minutes — it still hasn't come.", "have been waiting", ["am waiting", "was waiting", "wait"]),
            ("She ___ English since 2020.", "has been learning", ["is learning", "learns", "was learning"]),
            ("How long ___ you been working here?", "have", ["has", "are", "did"]),
            ("He ___ TV all day — tell him to stop!", "has been watching", ["have been watching", "was watching", "watch"]),
            ("It ___ since morning — the streets are wet.", "has been raining", ["is raining", "rained", "rains"]),
            ("They ___ in this flat for ten years.", "have been living", ["are living", "has been living", "living"]),
            ("My eyes hurt because I ___ at the screen for hours.", "have been staring", ["am staring", "was stared", "stares"]),
            ("Sorry I'm sweaty — I ___.", "have been running", ["am run", "has been running", "was ran"]),
        ],
    },
    {
        "slug": "passive_simple",
        "title": "Пассив: Present и Past Simple",
        "level": "B1",
        "position": 19,
        "rule": (
            "🏭 <b>Passive</b> — важно само действие, а не кто его совершил. "
            "<b>be + 3-я форма</b>:\n"
            "• Present: ед. ч. → <b>is</b>, мн. ч. → <b>are</b>: English <b>is spoken</b> "
            "here. Cars <b>are made</b> in Japan.\n"
            "• Past: ед. ч. → <b>was</b>, мн. ч. → <b>were</b>: The house <b>was built</b> in 1990."
        ),
        "items": [
            ("English ___ in many countries.", "is spoken", ["speaks", "is speaking", "spoke"]),
            ("This house ___ in 1985.", "was built", ["built", "is build", "was building"]),
            ("These cars ___ in Germany.", "are made", ["is made", "are making", "make"]),
            ("The letter ___ yesterday.", "was sent", ["sent", "was send", "is sent"]),
            ("Breakfast ___ from 7 to 10 every day.", "is served", ["serves", "served", "is serving"]),
            ("The windows ___ broken during the storm.", "were", ["was", "is", "did"]),
            ("Rice ___ in China.", "is grown", ["is grow", "grown", "are grown"]),
            ("The thieves ___ by the police last night.", "were arrested", ["was arrested", "arrested", "are arrested"]),
        ],
    },
    {
        "slug": "reported_speech",
        "title": "Косвенная речь",
        "level": "B1",
        "position": 20,
        "rule": (
            "🗣 <b>Косвенная речь</b> — пересказываем чужие слова: He said (that)… "
            "Время сдвигается на шаг назад:\n"
            "• Present → Past: «I work» → He said he <b>worked</b>.\n"
            "• will → <b>would</b>: «I'll call» → She said she <b>would call</b>.\n"
            "• can → <b>could</b>, have done → <b>had done</b>.\n"
            "Важно: say без лица, tell + кому (He told <b>me</b>…)."
        ),
        "items": [
            ("She said she ___ tired.", "was", ["am", "be", "are"]),
            ("He said he ___ call me the next day.", "would", ["will", "is", "can to"]),
            ("They told me they ___ in Rome then.", "lived", ["live", "living", "are living"]),
            ("She said she ___ swim when she was five.", "could", ["can", "cans", "could to"]),
            ("He told us he ___ finished the project the week before.", "had", ["have", "is", "did"]),
            ("Anna said that she ___ a new job.", "had found", ["has find", "finding", "find"]),
            ("He ___ me that the shop was closed.", "told", ["said", "sayed", "telled"]),
            ("She said they ___ at the hotel at that moment.", "were staying", ["are staying", "stays", "be staying"]),
        ],
    },
    {
        "slug": "conditional_second",
        "title": "Условные: 2 тип",
        "level": "B1",
        "position": 21,
        "rule": (
            "🌈 <b>Условные 2-го типа</b> — нереальная или маловероятная ситуация "
            "<b>сейчас/в будущем</b>.\n"
            "Формула: If + <b>Past Simple</b>, <b>would</b> + глагол.\n"
            "• If I <b>had</b> a million, I <b>would buy</b> a house.\n"
            "• С to be — <b>were</b> для всех лиц: If I <b>were</b> you, I would wait."
        ),
        "items": [
            ("If I ___ rich, I would travel the world.", "were", ["am", "will be", "would be"]),
            ("If she had more time, she ___ learn Spanish.", "would", ["will", "would to", "is"]),
            ("What ___ you do if you won the lottery?", "would", ["will", "did", "do"]),
            ("If we ___ in the city, we would walk to work.", "lived", ["live", "will live", "would live"]),
            ("He would be happier if he ___ less.", "worked", ["works", "will work", "would work"]),
            ("They ___ more if the tickets were cheaper.", "would travel", ["will travel", "travelled", "travel"]),
            ("If it ___ so cold, we would go for a walk.", "weren't", ["isn't", "won't be", "not be"]),
            ("If dogs ___ talk, what would they say?", "could", ["can", "will", "would to"]),
        ],
    },
    {
        "slug": "conditional_third",
        "title": "Условные: 3 тип",
        "level": "B2",
        "position": 22,
        "rule": (
            "⏪ <b>Условные 3-го типа</b> — нереальное <b>прошлое</b>: уже случилось, "
            "не изменить (сожаления, упущенные шансы).\n"
            "Формула: If + <b>had + V3</b>, <b>would have + V3</b>.\n"
            "• If you <b>had told</b> me, I <b>would have helped</b>.\n"
            "• She <b>wouldn't have been</b> late if she <b>had taken</b> a taxi."
        ),
        "items": [
            ("If you had told me, I ___ helped you.", "would have", ["would", "will have", "had"]),
            ("If she ___ harder, she would have passed the exam.", "had studied", ["studies", "has studied", "would study"]),
            ("We would have caught the train if we ___ earlier.", "had left", ["leave", "have left", "would leave"]),
            ("He ___ the job if he had prepared for the interview.", "would have got", ["had got", "will have got", "got"]),
            ("If I ___ about the party, I would have come.", "had known", ["know", "have known", "would know"]),
            ("She wouldn't have been late if she ___ a taxi.", "had taken", ["takes", "has taken", "would take"]),
            ("___ you have come if I had invited you?", "Would", ["Will", "Did", "Had"]),
            ("I ___ that mistake if I had been more careful.", "wouldn't have made", ["didn't make", "won't have made", "hadn't made"]),
        ],
    },
    {
        "slug": "tag_questions",
        "title": "Разделительные вопросы (tags)",
        "level": "B1",
        "position": 23,
        "rule": (
            "🏷 <b>Разделительный вопрос</b> — «хвостик» для переспроса. "
            "Полярность меняется на противоположную:\n"
            "• Утверждение → отрицательный хвост: You like tea, <b>don't you?</b>\n"
            "• Отрицание → положительный: She isn't here, <b>is she?</b>\n"
            "Хвост повторяет вспомогательный глагол: He can swim, <b>can't he?</b> "
            "They went, <b>didn't they?</b>"
        ),
        "items": [
            ("You like coffee, ___?", "don't you", ["don't we", "aren't you", "didn't you"]),
            ("She isn't from Spain, ___?", "is she", ["isn't she", "she is", "does she"]),
            ("They went home, ___?", "didn't they", ["don't they", "weren't they", "hadn't they"]),
            ("He can drive, ___?", "can't he", ["doesn't he", "isn't he", "won't he"]),
            ("You haven't seen my keys, ___?", "have you", ["haven't you", "did you", "you have"]),
            ("It's cold today, ___?", "isn't it", ["doesn't it", "wasn't it", "aren't it"]),
            ("Your parents don't smoke, ___?", "do they", ["don't they", "are they", "do you"]),
            ("We're late, ___?", "aren't we", ["don't we", "weren't we", "isn't we"]),
        ],
    },
    {
        "slug": "relative_clauses",
        "title": "Относительные: who / which / that / where",
        "level": "B1",
        "position": 24,
        "rule": (
            "🔗 <b>Относительные местоимения</b> соединяют части предложения:\n"
            "• <b>who</b> — люди: the man <b>who</b> called\n"
            "• <b>which</b> — вещи и животные: the book <b>which</b> I read\n"
            "• <b>that</b> — универсальное; обычно после everything и превосходной "
            "степени: the best film <b>that</b> I've seen\n"
            "• <b>where</b> — места: the café <b>where</b> we met"
        ),
        "items": [
            ("The woman ___ lives next door is a doctor.", "who", ["which", "where", "whose"]),
            ("This is the book ___ I told you about.", "which", ["who", "where", "whom"]),
            ("That's the café ___ we first met.", "where", ["which", "who", "that"]),
            ("It's the best film ___ I've ever seen.", "that", ["who", "where", "what"]),
            ("They live in a house ___ was built 100 years ago.", "which", ["who", "where", "whose"]),
            ("Do you know anyone ___ can fix computers?", "who", ["which", "whose", "where"]),
            ("Everything ___ he said was true.", "that", ["who", "what", "where"]),
            ("Is that the office ___ you used to work?", "where", ["which", "who", "what"]),
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
