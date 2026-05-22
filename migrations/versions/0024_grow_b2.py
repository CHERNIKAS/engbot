"""grow level B2 with common upper-intermediate words (vocab growth batch 4)

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-23

Curated growth (no NGSL file). ~90 common B2 words that were missing, each with
translation + example, level=B2 + inferred POS, appended to level_b2. Candidate
list pre-checked against the DB to avoid duplicates; translations chosen distinct
to avoid synonym collisions. Idempotent.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.domain.pos import infer_part_of_speech

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

LEVEL_SLUG = "level_b2"
LEVEL = "B2"

NEW_WORDS: list[tuple[str, str, str]] = [
    # verbs
    ("abandon", "покидать / бросать", "They abandoned the old house."),
    ("alter", "изменять / переделывать", "She altered the dress to fit."),
    ("bother", "докучать", "Don't bother him while he works."),
    ("collapse", "рухнуть / обрушиться", "The old bridge collapsed."),
    ("convert", "конвертировать", "Convert the file to PDF."),
    ("cope", "справляться (с трудностями)", "She copes well under pressure."),
    ("declare", "заявлять", "They declared independence."),
    ("detect", "засекать / обнаруживать", "The alarm detects smoke."),
    ("distribute", "распределять / раздавать", "They distribute food to the poor."),
    ("enable", "давать возможность", "This app enables fast payments."),
    ("evolve", "эволюционировать", "Languages evolve over time."),
    ("exaggerate", "преувеличивать", "Don't exaggerate the problem."),
    ("exclude", "исключать", "The price excludes tax."),
    ("expose", "разоблачать", "The report exposed the fraud."),
    ("generate", "генерировать", "The plant generates power."),
    ("guarantee", "гарантировать", "We guarantee fast delivery."),
    ("highlight", "выделять", "Let me highlight the key point."),
    ("illustrate", "иллюстрировать", "The chart illustrates the trend."),
    ("impose", "навязывать", "They imposed strict rules."),
    ("incorporate", "встраивать", "We incorporated your feedback."),
    ("inspire", "вдохновлять", "Her speech inspired us."),
    ("integrate", "интегрировать", "The tool integrates with email."),
    ("investigate", "расследовать", "Police investigate the crime."),
    ("modify", "модифицировать", "We modified the design."),
    ("monitor", "отслеживать", "Doctors monitor his heart."),
    ("negotiate", "вести переговоры", "They negotiated a new deal."),
    ("overcome", "преодолевать", "She overcame many obstacles."),
    ("preserve", "сохранять / оберегать", "We must preserve nature."),
    ("pursue", "преследовать (цель)", "He pursued his dream."),
    ("restore", "восстанавливать", "They restored the old painting."),
    ("retain", "удерживать", "The soil retains water."),
    ("seize", "захватывать", "The army seized the city."),
    ("specify", "уточнять", "Please specify the size."),
    ("strengthen", "усиливать", "Exercise strengthens muscles."),
    ("summarize", "резюмировать", "Summarize the article in one sentence."),
    ("tackle", "браться за (проблему)", "We must tackle this issue."),
    ("withdraw", "отзывать / снимать деньги", "She withdrew some cash."),
    # nouns
    ("assumption", "предположение", "That's a false assumption."),
    ("circumstance", "обстоятельство", "Under the circumstances, we agreed."),
    ("constraint", "ограничение", "We work under tight constraints."),
    ("contribution", "вклад", "Thanks for your contribution."),
    ("controversy", "полемика", "The decision caused controversy."),
    ("crisis", "кризис", "The country faced an economic crisis."),
    ("depth", "глубина", "The depth of the lake is 30 metres."),
    ("dimension", "измерение / аспект", "Add a new dimension to the project."),
    ("discipline", "дисциплина", "Learning needs discipline."),
    ("dispute", "спор", "They settled the dispute calmly."),
    ("domain", "область / сфера", "This is outside my domain."),
    ("framework", "рамки / каркас", "We built a clear framework."),
    ("incentive", "стимул", "Bonuses are a strong incentive."),
    ("initiative", "инициатива", "She showed great initiative."),
    ("insight", "проницательность", "The book offers deep insight."),
    ("legislation", "законодательство", "New legislation was passed."),
    ("mechanism", "механизм", "The clock has a simple mechanism."),
    ("norm", "норма", "Remote work is now the norm."),
    ("obstacle", "препятствие", "She overcame every obstacle."),
    ("outcome", "исход / итог", "The outcome was positive."),
    ("perspective", "точка зрения", "Try a different perspective."),
    ("phase", "фаза / этап", "We are in the final phase."),
    ("portion", "порция / часть", "A small portion of food."),
    ("priority", "приоритет", "Safety is our top priority."),
    ("prospect", "перспектива", "The job has good prospects."),
    ("scenario", "сценарий", "Imagine the worst-case scenario."),
    ("stability", "стабильность", "The region enjoys political stability."),
    ("transition", "переход", "The transition was smooth."),
    ("trait", "черта характера", "Patience is a useful trait."),
    ("variable", "переменная", "Price is the key variable."),
    # adjectives
    ("abstract", "абстрактный", "This is too abstract for me."),
    ("absolute", "абсолютный", "I have absolute trust in her."),
    ("acute", "острый (резкий)", "He felt an acute pain."),
    ("consistent", "последовательный", "Be consistent in your effort."),
    ("conventional", "традиционный", "We used a conventional method."),
    ("dense", "плотный", "The forest is very dense."),
    ("dynamic", "динамичный", "She has a dynamic personality."),
    ("evident", "явный / заметный", "His talent is evident."),
    ("exclusive", "исключительный", "This is an exclusive offer."),
    ("extensive", "масштабный", "They did extensive research."),
    ("finite", "конечный", "We have finite resources."),
    ("intense", "интенсивный", "The training was intense."),
    ("intrinsic", "неотъемлемый", "Curiosity is intrinsic to learning."),
    ("minimal", "минимальный", "The damage was minimal."),
    ("mutual", "взаимный", "We have mutual respect."),
    ("neutral", "нейтральный", "Switzerland stayed neutral."),
    ("optimal", "оптимальный", "Find the optimal solution."),
    ("parallel", "параллельный", "The two roads run parallel."),
    ("precise", "чёткий", "Give me a precise answer."),
    ("preliminary", "предварительный", "These are preliminary results."),
    ("rigid", "жёсткий", "The rules are too rigid."),
    ("robust", "крепкий / устойчивый", "We need a robust system."),
    ("vast", "необъятный", "The desert is vast."),
    ("vivid", "красочный", "She has a vivid imagination."),
]


def upgrade() -> None:
    conn = op.get_bind()
    pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": LEVEL_SLUG}).first()
    if pack is None:
        return
    pack_id = pack[0]
    pos = conn.execute(
        sa.text("SELECT COALESCE(max(position), -1) + 1 FROM pack_words WHERE pack_id = :p"),
        {"p": pack_id},
    ).scalar()
    for english, translation, example in NEW_WORDS:
        n = english.strip().lower()
        row = conn.execute(
            sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"), {"n": n}
        ).first()
        if row:
            wid = row[0]
            conn.execute(
                sa.text(
                    "UPDATE words SET level = COALESCE(level, :l), "
                    "example_sentence = COALESCE(example_sentence, :e), "
                    "part_of_speech = COALESCE(part_of_speech, :pos) WHERE id = :id"
                ),
                {"l": LEVEL, "e": example, "pos": infer_part_of_speech(translation), "id": wid},
            )
        else:
            wid = conn.execute(
                sa.text(
                    "INSERT INTO words (track, writing, normalized_word, translation, "
                    "example_sentence, level, part_of_speech) VALUES "
                    "('en', :w, :n, :t, :e, :l, :pos) RETURNING id"
                ),
                {"w": english, "n": n, "t": translation, "e": example, "l": LEVEL,
                 "pos": infer_part_of_speech(translation)},
            ).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :pos) "
                "ON CONFLICT DO NOTHING"
            ),
            {"p": pack_id, "w": wid, "pos": pos},
        )
        pos += 1
    conn.execute(
        sa.text("UPDATE packs SET words_count = (SELECT count(*) FROM pack_words WHERE pack_id = :p) WHERE id = :p"),
        {"p": pack_id},
    )


def downgrade() -> None:
    conn = op.get_bind()
    names = [w[0].strip().lower() for w in NEW_WORDS]
    pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": LEVEL_SLUG}).first()
    conn.execute(
        sa.text("DELETE FROM words WHERE track = 'en' AND normalized_word IN :n").bindparams(
            sa.bindparam("n", expanding=True)
        ),
        {"n": names},
    )
    if pack is not None:
        conn.execute(
            sa.text("UPDATE packs SET words_count = (SELECT count(*) FROM pack_words WHERE pack_id = :p) WHERE id = :p"),
            {"p": pack[0]},
        )
